"""
Compatibility wrapper for cv_client.py
Delegates to CVClient service in ServiceRegistry.
"""

from core.service_registry import ServiceRegistry

_registry = ServiceRegistry()
_cv = None


def _get_cv():
    global _cv
    if _cv is None:
        _cv = _registry.get('cv_client')
        if _cv is None:
            import showlog
            showlog.error("[CV_CLIENT COMPAT] CVClient service not registered!")
    return _cv


def send_cv(channel, voltage):
    cv = _get_cv()
    if cv:
        cv.send_cv(channel, voltage)


def send(channel, voltage):
    """Alias for send_cv for backward compatibility."""
    cv = _get_cv()
    if cv:
        cv.send_cv(channel, voltage)


def send_cv_glide(channel, voltage, glide_ms=0):
    cv = _get_cv()
    if cv:
        cv.send_cv_glide(channel, voltage, glide_ms)


def send_cal(channel, cal_lo, cal_hi):
    cv = _get_cv()
    if cv:
        cv.send_cal(channel, cal_lo, cal_hi)


def send_raw(command):
    cv = _get_cv()
    if cv:
        cv.send_raw(command)


def is_connected():
    cv = _get_cv()
    return cv.is_connected() if cv else False


def __getattr__(name):
    cv = _get_cv()
    if cv and hasattr(cv, name):
        return getattr(cv, name)
    raise AttributeError(f"module 'cv_client' has no attribute '{name}'")
