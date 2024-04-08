from opentelemetry.instrumentation.system_metrics import SystemMetricsInstrumentor

from opentelemetry_wrapper.dependencies.opentelemetry.instrument_decorator import instrument_decorate


@instrument_decorate
def instrument_system_metrics():
    # to configure custom metrics
    SystemMetricsInstrumentor(config={
        "system.cpu.time":                ["idle", "user", "system", "irq"],
        "system.cpu.utilization":         ["idle", "user", "system", "irq"],
        "system.memory.usage":            ["used", "free", "cached"],
        "system.memory.utilization":      ["used", "free", "cached"],
        "system.swap.usage":              ["used", "free"],
        "system.swap.utilization":        ["used", "free"],
        "system.disk.io":                 ["read", "write"],
        "system.disk.operations":         ["read", "write"],
        "system.disk.time":               ["read", "write"],
        "system.network.dropped.packets": ["transmit", "receive"],
        "system.network.packets":         ["transmit", "receive"],
        "system.network.errors":          ["transmit", "receive"],
        "system.network.io":              ["transmit", "receive"],
        "system.network.connections":     ["family", "type"],
        "system.thread_count":            None,  # why is this None? does it even exist? it's in the docs though
        "process.runtime.memory":         ["rss", "vms"],
        "process.runtime.cpu.time":       ["user", "system"],
    }).instrument()
