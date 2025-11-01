"""
Compatibility wrapper for network.py
Delegates to NetworkServer service in ServiceRegistry.
"""

from core.service_registry import ServiceRegistry

_registry = ServiceRegistry()
_net = None


def _get_net():
    global _net
    if _net is None:
        _net = _registry.get('network_server')
        if _net is None:
            import showlog
            showlog.error("[NETWORK COMPAT] NetworkServer service not registered!")
    return _net


def send_led_line(text, row=0):
    net = _get_net()
    if net:
        net.send_led_line(text, row)


def forward_to_pico(message):
    net = _get_net()
    if net:
        net._forward_to_pico(message)


def is_running():
    net = _get_net()
    return net.is_running() if net else False


def __getattr__(name):
    net = _get_net()
    if net and hasattr(net, name):
        return getattr(net, name)
    raise AttributeError(f"module 'network' has no attribute '{name}'")
