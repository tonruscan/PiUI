# /build/custom_controls.py
import os, json
import showlog
from typing import Optional, Dict, Any

_CFG_PATH = os.path.join(os.path.dirname(__file__), "config", "custom_dials.json")
_CACHE = None

def _load() -> dict:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    try:
        with open(_CFG_PATH, "r", encoding="utf-8") as f:
            _CACHE = json.load(f)
            if not isinstance(_CACHE, dict):
                showlog.warn("[custom_controls] JSON root must be an object")
                _CACHE = {}
    except FileNotFoundError:
        showlog.warn(f"[custom_controls] Missing {_CFG_PATH}")
        _CACHE = {}
    except Exception as e:
        showlog.warn(f"[custom_controls] Failed to read {_CFG_PATH}: {e}")
        _CACHE = {}
    return _CACHE

def reload():
    global _CACHE
    _CACHE = None
    return _load()

def get(control_id: str) -> Optional[Dict[str, Any]]:
    """Return the control dict, e.g. {"label","cc","range","type","page","options"}"""
    data = _load()
    return data.get(control_id)

def all_controls() -> Dict[str, Dict[str, Any]]:
    return _load()
