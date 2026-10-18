"""
canary: the SDK updates a provider's resource in a forked child (`TracerProvider._handle_fork`, registered with
`os.register_at_fork`), re-running the process-dependent detectors (by default `service.instance.id`), and existing
tracers pick the new resource up (OTW-9; the "Fork" notes in `docs/archive/PLAN.md`). what v1 relies on is that
workers forked after configuration (gunicorn `--preload`) do not all report the master's instance id, and that a
detector opts in through `ResourceDetector.is_process_dependent`

there is no fork on Windows, so this only runs on Linux CI
"""
import os

import pytest

from tests.v0._harness import scenario

FORK = scenario(__name__, 'upstream_fork_resource', r'''
import os
from opentelemetry.sdk.resources import Resource, ResourceDetector
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

emit('detector_hook', callable(getattr(ResourceDetector, 'is_process_dependent', None)))
exporter = InMemorySpanExporter()
provider = TracerProvider(resource=Resource.create({'service.name': 'canary'}))
provider.add_span_processor(SimpleSpanProcessor(exporter))
tracer = provider.get_tracer('canary')  # created before the fork
emit('parent', provider.resource.attributes.get('service.instance.id'))

read_end, write_end = os.pipe()
pid = os.fork()
if pid == 0:  # child: report through the pipe, then leave without running the parent's atexit hooks
    import json
    with tracer.start_as_current_span('in child'):
        pass
    [span] = exporter.get_finished_spans()
    os.write(write_end, json.dumps({
        'provider': provider.resource.attributes.get('service.instance.id'),
        'span': span.resource.attributes.get('service.instance.id'),
        'service_name': span.resource.attributes.get('service.name'),
    }).encode())
    os._exit(0)
os.close(write_end)
data = b''
while chunk := os.read(read_end, 4096):
    data += chunk
os.waitpid(pid, 0)
import json
emit('child', json.loads(data))
''') if hasattr(os, 'fork') else None


@pytest.mark.skipif(not hasattr(os, 'fork'), reason='no fork on this platform (Linux CI runs it)')
def test_a_forked_child_gets_a_new_instance_id_on_existing_tracers():
    result = FORK.result()
    assert result['detector_hook'] is True
    parent, child = result['parent'], result['child']
    assert parent
    assert child['provider'] and child['provider'] != parent
    assert child['span'] == child['provider']
    assert child['service_name'] == 'canary'  # the rest of the resource is kept
