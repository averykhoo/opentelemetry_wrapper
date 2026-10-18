"""
configuration (DEC-27, DEC-28, DEC-9): providers for all three signals, built once, under one lock

* decorating never configures; the first span configures from env vars only if nothing has configured yet;
  `otel.instrument(...)` configures eagerly; `otel.configure(...)` is explicit > env > default
* final once built: the same settings again are a no-op, different ones warn once and are ignored, except the log level
* someone else configured first: warn once; attach our processors to an SDK provider, otherwise leave it alone
* every exporter we build goes through `_wrap_exporter` (the scrubbing hook, workstream 5b) and a switchable sink, so
  the pytest plugin can turn real exports off and capture what would be exported (DEC-10)
* a bounded flush at exit, also in forked `multiprocessing` children
"""
import atexit
import importlib.util
import logging
import multiprocessing.util
import threading
from dataclasses import dataclass
from dataclasses import field
from types import MappingProxyType
from typing import Any
from typing import List
from typing import Mapping
from typing import Optional

from opentelemetry import trace

from opentelemetry_wrapper.v1 import _env
from opentelemetry_wrapper.v1._warnings import report
from opentelemetry_wrapper.v1._warnings import warn

SHUTDOWN_TIMEOUT_SECONDS = 5.0  # an unreachable collector must never hold up a process's exit (workstream 9)
SCRUBBING_MODULE = 'opentelemetry_wrapper.v1.scrubbing'

_lock = threading.RLock()


@dataclass
class _State:
    settings: _env.Settings
    tracer_provider: Any = None  # ours, or the foreign SDK provider we attached to (None: left alone)
    logger_provider: Any = None
    meter_provider: Any = None  # ours only: a foreign meter provider can't take readers
    owned: List[Any] = field(default_factory=list)  # providers we created, to flush at exit
    sinks: List[Any] = field(default_factory=list)  # our real exporters' processors, switchable by the pytest plugin
    logging_instrumented: bool = False
    failed: bool = False


_state: Optional[_State] = None
_span_test_sinks: List[Any] = []  # in-memory exporters registered by the pytest plugin, attached once built
_log_test_sinks: List[Any] = []


# ----------------------------------------------------------------------------------------------------------------------
# exporters: the scrubbing hook and the switchable sink
# ----------------------------------------------------------------------------------------------------------------------

def _wrap_exporter(exporter: Any, signal: str) -> Any:
    """
    the one place every span / log exporter we build passes through: wraps it in the scrubbing exporter of workstream
    5b (`opentelemetry_wrapper.v1.scrubbing`) when that module exists, and is a pass-through when it doesn't. if the
    module exists but fails, the exporter is dropped (fail closed: never export unscrubbed) and the error is raised to
    the caller, which warns at startup
    """
    if signal not in ('traces', 'logs') or importlib.util.find_spec(SCRUBBING_MODULE) is None:
        return exporter
    scrubbing = importlib.import_module(SCRUBBING_MODULE)
    if signal == 'traces':
        return scrubbing.ScrubbingSpanExporter(exporter)
    return scrubbing.ScrubbingLogExporter(exporter)


_exporters_enabled = True  # False while a test has opted in (the pytest plugin)


def _switchable(processor_class: Any) -> Any:
    """a processor that drops what ends while our real exporters are switched off (the pytest plugin's opt-in,
    DEC-10); decided when the span ends or the record is emitted, so a batch exported later can't leak a test's
    spans"""

    class Switchable(processor_class):
        enabled = True

        def on_end(self, span: Any) -> None:
            if self.enabled:
                super().on_end(span)

        def on_emit(self, *args: Any, **kwargs: Any) -> None:
            if self.enabled:
                super().on_emit(*args, **kwargs)

    Switchable.__name__ = Switchable.__qualname__ = f'Switchable{processor_class.__name__}'
    return Switchable


def set_exporters_enabled(enabled: bool) -> None:
    """switch our real exporters on or off (the in-memory test sinks are unaffected)"""
    global _exporters_enabled
    with _lock:
        _exporters_enabled = enabled
        for sink in (_state.sinks if _state is not None else ()):
            sink.enabled = enabled


def _otlp_kwargs(settings: _env.Settings, signal: str) -> dict:
    kwargs: dict = {}
    if settings.otlp_endpoint:
        kwargs['endpoint'] = f'{settings.otlp_endpoint.rstrip("/")}/v1/{signal}'
    if settings.otlp_headers:
        kwargs['headers'] = dict(settings.otlp_headers)
    return kwargs


def _guarded_wrap(exporter: Any, signal: str, notes: List[str]) -> Any:
    try:
        return _wrap_exporter(exporter, signal)
    except Exception as e:  # fail closed: this exporter is dropped, never used unscrubbed
        notes.append(f'the scrubbing wrapper failed, so {type(exporter).__name__} is not used: '
                     f'{type(e).__name__}: {e}')
        return None


def _span_processors(state: _State, notes: List[str]) -> list:
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.trace.export import ConsoleSpanExporter
    processors = []
    for name in state.settings.traces_exporter:
        if name == 'otlp':
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(**_otlp_kwargs(state.settings, 'traces'))
        else:
            exporter = ConsoleSpanExporter()
        wrapped = _guarded_wrap(exporter, 'traces', notes)
        if wrapped is None:
            continue
        processor = _switchable(BatchSpanProcessor)(wrapped)
        processor.enabled = _exporters_enabled
        state.sinks.append(processor)
        processors.append(processor)
    return processors


def _log_processors(state: _State, notes: List[str]) -> list:
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.sdk._logs.export import ConsoleLogRecordExporter
    processors = []
    for name in state.settings.logs_exporter:
        if name == 'otlp':
            from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
            exporter = OTLPLogExporter(**_otlp_kwargs(state.settings, 'logs'))
        else:
            exporter = ConsoleLogRecordExporter()
        wrapped = _guarded_wrap(exporter, 'logs', notes)
        if wrapped is None:
            continue
        processor = _switchable(BatchLogRecordProcessor)(wrapped)
        processor.enabled = _exporters_enabled
        state.sinks.append(processor)
        processors.append(processor)
    return processors


def _metric_readers(settings: _env.Settings) -> list:
    from opentelemetry.sdk.metrics.export import ConsoleMetricExporter
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    readers = []
    for name in settings.metrics_exporter:
        if name == 'otlp':
            from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
            readers.append(PeriodicExportingMetricReader(OTLPMetricExporter(**_otlp_kwargs(settings, 'metrics'))))
        else:
            readers.append(PeriodicExportingMetricReader(ConsoleMetricExporter()))
    return readers


def _resource(settings: _env.Settings) -> Any:
    """our detectors (guesses) < OTEL_SERVICE_NAME / OTEL_RESOURCE_ATTRIBUTES < explicit (PLAN, "Resource precedence")
    """
    from opentelemetry.sdk.resources import OTELResourceDetector
    from opentelemetry.sdk.resources import Resource
    explicit = dict(settings.resource_attributes)
    if settings.service_name:
        explicit['service.name'] = settings.service_name
    detected = Resource.get_empty()  # workstream 6 (resource detectors) plugs in here
    return (Resource.create().merge(detected).merge(OTELResourceDetector().detect())
            .merge(Resource.create(explicit) if explicit else Resource.get_empty()))


def _is_proxy(provider: Any) -> bool:
    # the API hands out a proxy until a provider is set; the log and meter proxies' classes are private
    return isinstance(provider, trace.ProxyTracerProvider) or type(provider).__name__ in (
        'ProxyLoggerProvider', '_ProxyMeterProvider')


# ----------------------------------------------------------------------------------------------------------------------
# building
# ----------------------------------------------------------------------------------------------------------------------

def _build(settings: _env.Settings, notes: List[str]) -> _State:
    from opentelemetry import _logs
    from opentelemetry import metrics
    from opentelemetry.sdk._logs import LoggerProvider
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.trace import TracerProvider

    state = _State(settings)
    resource = _resource(settings)

    existing = trace.get_tracer_provider()
    if _is_proxy(existing):
        state.tracer_provider = TracerProvider(resource=resource, shutdown_on_exit=False)
        state.owned.append(state.tracer_provider)
        trace.set_tracer_provider(state.tracer_provider)
    elif isinstance(existing, TracerProvider):
        notes.append(f'another tracer provider was configured first ({type(existing).__name__}); '
                     f'opentelemetry_wrapper '
                     f'attached its span processors to it, and its own resource settings are not applied')
        state.tracer_provider = existing
    else:
        notes.append(f'another tracer provider was configured first ({type(existing).__name__}), and it is not the '
                     f'SDK\'s: opentelemetry_wrapper leaves it alone and exports no spans of its own')
    if state.tracer_provider is not None:
        for processor in _span_processors(state, notes):
            state.tracer_provider.add_span_processor(processor)

    existing = _logs.get_logger_provider()
    if _is_proxy(existing):
        state.logger_provider = LoggerProvider(resource=resource, shutdown_on_exit=False)
        state.owned.append(state.logger_provider)
        _logs.set_logger_provider(state.logger_provider)
    elif isinstance(existing, LoggerProvider):
        notes.append(f'another logger provider was configured first ({type(existing).__name__}); '
                     f'opentelemetry_wrapper '
                     f'attached its log processors to it')
        state.logger_provider = existing
    else:
        notes.append(f'another logger provider was configured first ({type(existing).__name__}), and it is not the '
                     f'SDK\'s: opentelemetry_wrapper leaves it alone and exports no logs of its own')
    if state.logger_provider is not None:
        for processor in _log_processors(state, notes):
            state.logger_provider.add_log_record_processor(processor)

    existing = metrics.get_meter_provider()
    if _is_proxy(existing):
        state.meter_provider = MeterProvider(resource=resource, metric_readers=_metric_readers(settings),
                                             shutdown_on_exit=False)
        state.owned.append(state.meter_provider)
        metrics.set_meter_provider(state.meter_provider)
    else:
        notes.append(f'another meter provider was configured first ({type(existing).__name__}): opentelemetry_wrapper '
                     f'leaves it alone and exports no metrics of its own')

    for exporter in _span_test_sinks:
        _attach_sink(state, exporter, 'traces', notes)
    for exporter in _log_test_sinks:
        _attach_sink(state, exporter, 'logs', notes)
    _register_exit_flush(state)
    return state


def _attach_sink(state: _State, exporter: Any, signal: str, notes: List[str]) -> None:
    """an in-memory test sink, behind the same scrubbing wrapper as the real exporters, exported synchronously"""
    wrapped = _guarded_wrap(exporter, signal, notes)
    if wrapped is None:
        return
    if signal == 'traces' and state.tracer_provider is not None:
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        state.tracer_provider.add_span_processor(SimpleSpanProcessor(wrapped))
    elif signal == 'logs' and state.logger_provider is not None:
        from opentelemetry.sdk._logs.export import SimpleLogRecordProcessor
        state.logger_provider.add_log_record_processor(SimpleLogRecordProcessor(wrapped))


def _add_sink(exporter: Any, signal: str) -> None:
    notes: List[str] = []
    with _lock:
        (_span_test_sinks if signal == 'traces' else _log_test_sinks).append(exporter)
        if _state is not None and not _state.failed:
            _attach_sink(_state, exporter, signal, notes)
    for note in notes:
        warn(note)


def add_span_sink(exporter: Any) -> None:
    """register an in-memory span exporter (the pytest plugin's); it sees what would be exported, scrubbed"""
    _add_sink(exporter, 'traces')


def add_log_sink(exporter: Any) -> None:
    """register an in-memory log record exporter (the pytest plugin's)"""
    _add_sink(exporter, 'logs')


# ----------------------------------------------------------------------------------------------------------------------
# exit: a bounded flush, in the main process and in forked multiprocessing children
# ----------------------------------------------------------------------------------------------------------------------

def _flush_and_shutdown(providers: List[Any]) -> None:
    for provider in providers:
        try:
            provider.shutdown()
        except Exception as e:
            report('shutdown', e)


def _bounded_shutdown(state: _State) -> None:
    if not state.owned:
        return
    providers, state.owned = list(state.owned), []  # once
    worker = threading.Thread(target=_flush_and_shutdown, args=(providers,), name='otel-wrapper-shutdown', daemon=True)
    worker.start()
    worker.join(SHUTDOWN_TIMEOUT_SECONDS)


class _ForkHook:
    """`multiprocessing.util.register_after_fork` keeps a weak reference, so it needs an object to hold on to"""

    def __init__(self, state: _State):
        self.state = state


_fork_hooks: List[_ForkHook] = []


def _after_fork(hook: _ForkHook) -> None:
    # a forked child skips atexit (multiprocessing ends it with os._exit), but runs its multiprocessing finalizers
    multiprocessing.util.Finalize(None, _bounded_shutdown, args=(hook.state,), exitpriority=10)


def _register_exit_flush(state: _State) -> None:
    atexit.register(_bounded_shutdown, state)
    hook = _ForkHook(state)
    _fork_hooks.append(hook)
    multiprocessing.util.register_after_fork(hook, _after_fork)
    if multiprocessing.parent_process() is not None:  # already a child (spawned, or forked before configuring)
        _after_fork(hook)


# ----------------------------------------------------------------------------------------------------------------------
# the public entry points
# ----------------------------------------------------------------------------------------------------------------------

def configure(explicit: Optional[Mapping[str, Any]] = None) -> None:
    """explicit configuration, or (with nothing explicit) configuration from env vars; warnings are emitted last"""
    global _state
    if _env.disabled():
        return
    explicit = dict(explicit or {})
    settings, notes = _env.resolve(explicit)
    conflict = None
    with _lock:
        if _state is None:
            try:
                _state = _build(settings, notes)
            except Exception as e:
                _state = _State(settings, failed=True)
                notes.append(f'configuring OpenTelemetry failed, so no telemetry is exported: {type(e).__name__}: {e}')
        else:
            notes = []  # env var notes were emitted when configuration was built
            if explicit and settings.without_log_level() != _state.settings.without_log_level():
                conflict = ('otel.configure() was called with different settings after configuration was built (by '
                            'otel.configure, otel.instrument or the first span); they are ignored, except the log '
                            'level. Call otel.configure() once, at startup, before otel.instrument()')
            if 'log_level' in explicit and settings.log_level != _state.settings.log_level:
                _state.settings = _env.Settings(**{**_env.asdict_shallow(_state.settings),
                                                   'log_level': settings.log_level})
                _apply_log_level(_state)
    for note in notes:
        warn(note)
    if conflict is not None:
        warn(conflict, key='configure-conflict', anywhere=True)


def ensure_configured() -> None:
    """configure from env vars if nothing has configured yet (the first span, `otel.instrument`)"""
    if _state is None:
        configure()


def is_configured() -> bool:
    return _state is not None


def config_view() -> Mapping[str, Any]:
    """`otel.config`: the effective configuration, read-only, secrets redacted"""
    with _lock:
        settings = _state.settings if _state is not None else _env.resolve({})[0]
    return MappingProxyType(settings.redacted())


def logger_provider() -> Any:
    return _state.logger_provider if _state is not None else None


def mark_logging_instrumented() -> None:
    with _lock:
        if _state is not None:
            _state.logging_instrumented = True
            _apply_log_level(_state)


def _apply_log_level(state: _State) -> None:
    if not state.logging_instrumented:
        return
    level = logging.getLevelName(state.settings.log_level.upper())
    if isinstance(level, int):
        logging.getLogger().setLevel(level)
