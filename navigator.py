# navigator.py
import showlog

_history = []
_current = None
_transitioning = False

def set_page(page_name, record=True):
    """Set current page; optionally record in history."""
    global _current, _history, _transitioning

    # ignore redundant sets
    if _current == page_name:
        return

    _transitioning = True  # signal: in transition

    showlog.log(f"Page set → {page_name} (record={record})")

    # only record if we're moving forward, not coming back
    if record and (_current and (_current not in _history or _history[-1] != _current)):
        _history.append(_current)
    else:
        showlog.debug(f"Not recording {page_name} to history")

    _current = page_name
   
    _transitioning = False  # finished transition

    
def go_back():
    """Return previous recorded page, or None if no more history."""
    global _current, _history

    if _history:
        _current = _history.pop()
        showlog.log(None, f"Page set → {_current} (record=False)")
        return _current

    return None


def current():
    return _current

def is_transitioning():
    return _transitioning
