"""
static checks on the packaging (OTW-13, AC-20, DEC-35, DEC-36, DEC-44, DEC-57): pyproject.toml declares the pins, the
extras, the pytest entry point and `py.typed`, no gRPC exporter, and requirements.txt (what CI installs) agrees with it

nothing is installed or built here: the real install trial is CI's `extras: none` job (ci/test.sh core)
"""
import importlib.metadata
import re
import tomllib
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']

# the SDK family releases as 1.x, the contrib packages (and semantic conventions) as 0.XbY, in lockstep (DEC-57)
SDK_FAMILY = ('opentelemetry-api', 'opentelemetry-sdk', 'opentelemetry-exporter-otlp-proto-http')
CONTRIB_FAMILY = ('opentelemetry-semantic-conventions', 'opentelemetry-instrumentation-logging',
                  'opentelemetry-exporter-prometheus')
INSTRUMENTORS = {
    'fastapi': 'opentelemetry-instrumentation-fastapi',
    'sqlalchemy': 'opentelemetry-instrumentation-sqlalchemy',
    'requests': 'opentelemetry-instrumentation-requests',
    'system-metrics': 'opentelemetry-instrumentation-system-metrics',
}
GRPC_NAMES = {'grpcio', 'grpcio-tools', 'opentelemetry-exporter-otlp', 'opentelemetry-exporter-otlp-proto-grpc'}


def _requirements(deps):
    return [Requirement(d) for d in deps]


def _core():
    return _requirements(PYPROJECT['dependencies'])


def _extras():
    return {name: _requirements(deps) for name, deps in PYPROJECT['optional-dependencies'].items()}


def _everything():
    return _core() + [r for reqs in _extras().values() for r in reqs]


def _named(reqs, name):
    found = [r for r in reqs if r.name == name]
    assert found, f'{name} is not declared'
    return found


def _bounds(req):
    """(lower, upper) of a `>=a,<b` specifier, failing for any other shape"""
    ops = {s.operator: s.version for s in req.specifier}
    assert set(ops) == {'>=', '<'} and len(req.specifier) == 2, f'{req}: expected exactly `>=lower,<upper`'
    return Version(ops['>=']), Version(ops['<'])


def _requirements_txt():
    lines = (ROOT / 'requirements.txt').read_text(encoding='utf-8').splitlines()
    return _requirements(line.strip() for line in lines if line.strip() and not line.lstrip().startswith('#'))


def test_python_floor_is_3_12():  # DEC-44
    assert PYPROJECT['requires-python'] == '>=3.12'


@pytest.mark.parametrize('name', SDK_FAMILY + ('opentelemetry-exporter-otlp-proto-grpc',))  # grpc: see below
def test_sdk_family_is_capped_at_the_next_minor(name):  # DEC-57
    for req in _named(_everything(), name):
        lower, upper = _bounds(req)
        assert lower.major == 1 and upper == Version(f'1.{lower.minor + 1}'), f'{req}: not capped at the next minor'


@pytest.mark.parametrize('name', CONTRIB_FAMILY + tuple(INSTRUMENTORS.values()))
def test_contrib_family_is_in_the_zero_minor_window(name):  # DEC-57
    for req in _named(_everything(), name):
        lower, upper = _bounds(req)
        assert lower.major == 0 and lower.pre is not None and lower.minor > 0, f'{req}: lower bound is not 0.XbY'
        assert upper == Version(f'0.{lower.minor + 1}'), f'{req}: not capped at the next minor'


def test_the_contrib_window_matches_the_sdk_window():  # DEC-57: they release in lockstep
    (sdk,) = _named(_core(), 'opentelemetry-sdk')
    sdk_lower, _ = _bounds(sdk)
    try:
        installed_sdk = Version(importlib.metadata.version('opentelemetry-sdk'))
        semconv_pin = next(r for r in _requirements(importlib.metadata.requires('opentelemetry-sdk') or [])
                           if r.name == 'opentelemetry-semantic-conventions')
    except (importlib.metadata.PackageNotFoundError, StopIteration):
        pytest.skip('opentelemetry-sdk is not installed')
    # the SDK release inside our window requires one exact semantic-conventions release: our contrib window admits it
    assert installed_sdk in sdk.specifier, f'installed sdk {installed_sdk} is outside the declared window {sdk}'
    (semconv,) = _named(_core(), 'opentelemetry-semantic-conventions')
    lockstep = Version(next(iter(semconv_pin.specifier)).version)
    assert lockstep in semconv.specifier, f'sdk {installed_sdk} needs semantic-conventions {lockstep}, not {semconv}'
    assert sdk_lower <= installed_sdk


def test_core_dependencies_include_the_otlp_http_family():  # DEC-36
    names = {r.name for r in _core()}
    assert set(SDK_FAMILY + CONTRIB_FAMILY) <= names


def test_no_grpc_exporter_is_declared():  # DEC-36
    declared = {r.name for r in _everything()} | {r.name for r in _requirements_txt()}
    # the one transitional exception: v0's otel_providers.py imports the gRPC exporters at module level, and the
    # package root imports v0, so the exporter package stays a core dependency until ASK-23 lands; then empty this set
    allowed = {'opentelemetry-exporter-otlp-proto-grpc'}
    assert not (declared & GRPC_NAMES) - allowed, sorted((declared & GRPC_NAMES) - allowed)
    # grpcio comes only through that package, and never as an extra
    assert not {r.name for reqs in _extras().values() for r in reqs} & GRPC_NAMES
    assert 'opentelemetry-exporter-otlp' not in declared  # the meta package: gRPC and HTTP together


def test_the_integrations_are_extras_with_their_instrumentor():  # DEC-35, AC-20
    extras = _extras()
    for extra, instrumentor in INSTRUMENTORS.items():
        assert extra in extras, f'missing extra [{extra}]'
        assert instrumentor in {r.name for r in extras[extra]}, f'[{extra}] does not pull {instrumentor}'
    assert 'fastapi' in {r.name for r in extras['fastapi']}
    assert 'sqlalchemy' in {r.name for r in extras['sqlalchemy']}
    assert 'requests' in {r.name for r in extras['requests']}


def test_hyperscan_and_dev_extras():  # DEC-16
    extras = _extras()
    assert {r.name for r in extras['hyperscan']} == {'hyperscan'}
    assert {'pytest', 'interegular'} <= {r.name for r in extras['dev']}


def test_sqlalchemy_stays_below_2_1_until_the_instrumentor_supports_it():  # OTW-15
    for req in _named(_everything() + _requirements_txt(), 'sqlalchemy'):
        assert req.specifier.contains('2.0.54') and not req.specifier.contains('2.1.0'), f'{req}: lost the <2.1 cap'


def test_pytest_plugin_entry_point():  # DEC-27: `-p no:opentelemetry_wrapper` needs this exact name
    assert PYPROJECT['entry-points']['pytest11'] == {'opentelemetry_wrapper': 'opentelemetry_wrapper.v1.pytest_plugin'}
    assert (ROOT / 'opentelemetry_wrapper' / 'v1' / 'pytest_plugin.py').is_file()


def test_resource_detector_entry_points_resolve_to_detectors():  # OTW-9: usable from plain OpenTelemetry too
    import importlib

    from opentelemetry.sdk.resources import ResourceDetector
    detectors = PYPROJECT['entry-points']['opentelemetry_resource_detector']
    assert set(detectors) == {'otel_wrapper_k8s', 'otel_wrapper_process'}
    for target in detectors.values():
        module, _, name = target.partition(':')
        detector = getattr(importlib.import_module(module), name)()  # no-argument constructors, as the SDK calls them
        assert isinstance(detector, ResourceDetector)


def test_py_typed_ships_with_the_package():
    assert (ROOT / 'opentelemetry_wrapper' / 'py.typed').is_file()
    assert 'Typing :: Typed' in PYPROJECT['classifiers']


def test_requirements_txt_agrees_with_pyproject():  # CI installs requirements.txt, so it must not drift
    wanted = {}
    for req in _everything():
        wanted.setdefault(req.name, set()).add(str(req.specifier))
    have = {}
    for req in _requirements_txt():
        have.setdefault(req.name, set()).add(str(req.specifier))
    for name, specs in wanted.items():
        assert name in have, f'requirements.txt lacks {name}'
        assert specs <= have[name], f'requirements.txt has {name}{sorted(have[name])}, pyproject has {sorted(specs)}'


def test_ci_keeps_both_extras_axes_and_fails_when_no_tests_are_collected():  # DEC-56
    workflow = (ROOT / '.github' / 'workflows' / 'tests.yml').read_text(encoding='utf-8')
    assert re.search(r"extras:\s*\[\s*'all'\s*,\s*'none'\s*\]", workflow)
    assert 'ci/test.sh core' in workflow and 'ci/test.sh all' in workflow
    script = (ROOT / 'ci' / 'test.sh').read_text(encoding='utf-8')
    pytest_lines = [line for line in script.splitlines() if '-m pytest' in line]
    assert len(pytest_lines) == 1 and '||' not in pytest_lines[0], pytest_lines  # exit 5 (no tests) must fail the job
    assert '--co' not in pytest_lines[0] and '--suppress-no-test-exit-code' not in script
