"""
the wrapper's two output channels about itself

* `OtelWrapperWarning` through `warnings.warn`, on startup paths only (decoration, `instrument`, `configure`, reading
  environment variables), never per call and never through `logging` (DEC-49). call `warn` outside our own
  `try`/`except`, once state is consistent, so an error filter can't leave anything half-built
* a failure swallowed at runtime writes one JSON line to stderr, once per failure site, directly and inside its own
  `try`/`except`, never through `warnings` or `logging`; `OTEL_WRAPPER_DEBUG=true` reports every occurrence, with the
  traceback (DEC-75)
"""
import json
import os
import sys
import threading
import traceback
import warnings
from typing import Hashable
from typing import Optional
from typing import Set
from typing import Tuple

_PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # opentelemetry_wrapper/

DEBUG_ENV_VAR = 'OTEL_WRAPPER_DEBUG'


class OtelWrapperWarning(UserWarning):
    """something could not be instrumented or is misconfigured; emitted once, at startup"""


_warned: Set[Hashable] = set()
_warned_lock = threading.Lock()


def _caller_site() -> Tuple[str, int]:
    frame = sys._getframe(1)
    while frame is not None and frame.f_code.co_filename.startswith(_PACKAGE_DIR):
        frame = frame.f_back
    if frame is None:
        return '<unknown>', 0
    return frame.f_code.co_filename, frame.f_lineno


def warn(message: str, key: Optional[Hashable] = None, anywhere: bool = False) -> None:
    """
    one `OtelWrapperWarning`, attributed to the first frame outside this package, at most once per (key or message,
    call site), or once per process with `anywhere`; deliberately not wrapped in `try`/`except`: an error filter must
    be able to raise it (DEC-8)
    """
    site = None if anywhere else _caller_site()
    dedupe = (key if key is not None else message, site)
    with _warned_lock:
        if dedupe in _warned:
            return
    warnings.warn(message, OtelWrapperWarning, skip_file_prefixes=(_PACKAGE_DIR,))
    # recorded only once the warning was issued: under an error filter `warn` raises, and the same misuse at the same
    # site must keep raising at decoration time rather than go quiet after the first time
    with _warned_lock:
        _warned.add(dedupe)


_reported: Set[Tuple[str, str]] = set()
_reported_lock = threading.Lock()


def _debug() -> bool:
    return os.environ.get(DEBUG_ENV_VAR, '').strip().casefold() in ('true', '1')


def report(site: str, exc: BaseException) -> None:
    """report a failure the wrapper swallowed at runtime: one stderr JSON line per (site, exception type); never
    raises"""
    try:
        debug = _debug()
        key = (site, f'{type(exc).__module__}.{type(exc).__qualname__}')
        if not debug:
            with _reported_lock:
                if key in _reported:
                    return
                _reported.add(key)
        record = {'opentelemetry_wrapper': 'internal error, swallowed', 'site': site, 'error.type': key[1],
                  'message': str(exc)}
        if debug:
            record['traceback'] = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        else:
            record['hint'] = f'set {DEBUG_ENV_VAR}=true for every occurrence, with tracebacks'
        stream = sys.__stderr__ if sys.stderr is None else sys.stderr
        if stream is not None:
            stream.write(json.dumps(record, default=repr) + '\n')
            stream.flush()
    except Exception:  # the reporter itself must never raise into the app
        pass
