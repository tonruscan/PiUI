# /build/system/state_manager.py
# -------------------------------------------------------------------
# Centralized, reference-based State Manager
# -------------------------------------------------------------------
# - Stores ONLY live runtime state (value/semantic/uid/active/family/cc)
# - Canonical dial metadata (label/range/options/type/default_slot/...)
#   lives in registry (devices.json / cc_registry)
#
# API:
#   init(base_dir=None)
#   register_instance(family:str, cc:int, uid:str, value=0, semantic=None, active=True) -> dict
#   set_value(family:str, cc:int, uid:str, value, semantic=None) -> None
#   get_state(family:str|None=None) -> dict
#   save_now() -> None
#   load() -> None
#
# Notes:
# - On disk: /states/device_state.json (atomic writes)
# - In memory: nested by family, keys "CC::UID"
# -------------------------------------------------------------------

from __future__ import annotations
import os, json, time, tempfile, threading
from typing import Dict, Any, Optional
import config as cfg
import showlog

# ------------------------------
# Paths
# ------------------------------
_BASE_DIR = None
_STATES_DIR = None
_STATE_FILE = None

# ------------------------------
# In-memory global store (legacy-compatible)
# ------------------------------
_lock = threading.RLock()
_states: Dict[str, Dict[str, Dict[str, Any]]] = {}  # family -> { "cc::uid": {...} }
_dirty = False


# ===================================================================
# StateManager Class
# ===================================================================
class StateManager:
    """Runtime knob-level state management + autosave."""

    def __init__(self):
        self.knobs: Dict[str, Dict[str, Any]] = {}
        self.states: Dict[str, Any] = {}
        self.active_state_id: Optional[str] = None

        self.states_dir = os.path.join(cfg.BASE_DIR, "states")
        self.state_file = os.path.join(self.states_dir, "device_state.json")

        self._dirty = False
        self._lock = threading.RLock()
        os.makedirs(self.states_dir, exist_ok=True)

        # Start background autosave thread
        threading.Thread(target=self._autosave_loop, daemon=True).start()


    def _debug_inventory(self):
        """Log what knobs we currently have, grouped by source_name."""
        try:
            by_src = {}
            for k in self.knobs.values():
                src = k.get("source_name", "?")
                by_src.setdefault(src, []).append(k.get("param_id"))
            for src, ids in by_src.items():
                try:
                    ids_sorted = sorted([str(i) for i in ids])
                except Exception:
                    ids_sorted = [str(i) for i in ids]
                showlog.debug(f"[STATE_MGR] INVENTORY[{src}] param_ids={ids_sorted}")
        except Exception as e:
            showlog.warn(f"[STATE_MGR] INVENTORY dump failed: {e}")


    # --------------------------------------------------------------
    # Knob registration
    # --------------------------------------------------------------
    def create_knob(
        self,
        source_type: str,
        source_name: str,
        param_id: str,
        label: str,
        value: int = 0,
        range_: list = None
    ):
        """Register a new knob entry for a device or module."""
        with self._lock:
            if not range_:
                range_ = [0, 127]
            knob = {
                "source_type": source_type,   # e.g. 'device' or 'module'
                "source_name": source_name,   # e.g. 'bmlpf' or 'vibrato'
                "param_id": str(param_id),    # hashed unique id or slot-like id
                "label": label,               # human-readable
                "value": int(value),
                "range": range_,
            }
            self.knobs[str(param_id)] = knob
            self._dirty = True
            showlog.debug(f"[STATE_MGR] Created knob src={source_name} "
                          f"label='{label}' id={param_id} range={range_} value={value}")


    # --------------------------------------------------------------
    # Internal helpers
    # --------------------------------------------------------------
    def mark_dirty(self):
        with self._lock:
            self._dirty = True

    def _autosave_loop(self, interval=5.0):
        while True:
            time.sleep(interval)
            with self._lock:
                if not self._dirty:
                    continue
                self._dirty = False
            try:
                self.save_now()
                showlog.debug("[STATE_MGR] Autosaved state")
            except Exception as e:
                showlog.error(f"[STATE_MGR] Autosave failed: {e}")

    # --------------------------------------------------------------
    # Persistence
    # --------------------------------------------------------------
    def _load_from_disk(self):
        """Load knob states from disk if present."""
        if not os.path.isfile(self.state_file):
            return
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "knobs" in data:
                    self.knobs = data["knobs"]
                    showlog.debug(f"[STATE_MGR] Loaded {len(self.knobs)} knobs from disk")
        except Exception as e:
            showlog.error(f"[STATE_MGR] Failed to load state: {e}")

    def save_now(self):
        """Immediately write all knob states to disk (atomic)."""
        with self._lock:
            try:
                os.makedirs(self.states_dir, exist_ok=True)
                tmp_file = self.state_file + ".tmp"
                with open(tmp_file, "w", encoding="utf-8") as f:
                    json.dump({"knobs": self.knobs}, f, indent=2, ensure_ascii=False)
                os.replace(tmp_file, self.state_file)
                self._dirty = False
                showlog.debug("[STATE_MGR] State saved successfully")
            except Exception as e:
                showlog.error(f"[STATE_MGR] Save failed: {e}")

    # --------------------------------------------------------------
    # Core value access
    # --------------------------------------------------------------
    def set_value(self, source_name: str, param_id: str, value: int):
        """Update stored value for a knob, mark dirty. Returns True if updated."""
        updated = False
        src = str(source_name)
        pid = str(param_id)

        showlog.verbose(f"[STATE_MGR] set_value() lookup src={src} pid={pid} "
                      f"(knobs={len(self.knobs)})")

        with self._lock:
            for knob_id, k in self.knobs.items():
                k_src = str(k.get("source_name"))
                k_pid = str(k.get("param_id"))
                if k_src == src and k_pid == pid:
                    k["value"] = int(value)
                    self._dirty = True
                    updated = True
                    showlog.verbose(f"[STATE_MGR] set_value() HIT knob_id={knob_id} "
                                  f"src={k_src} pid={k_pid} → {value}")
                    break
                else:
                    # Log near-misses to see what's wrong
                    if k_src == src and k_pid != pid:
                        showlog.verbose(f"  · candidate mismatch: same src={src} "
                                      f"but have pid={k_pid} want pid={pid}")
                    elif k_pid == pid and k_src != src:
                        showlog.debug(f"  · candidate mismatch: same pid={pid} "
                                      f"but have src={k_src} want src={src}")

        if not updated:
            showlog.warn(f"[STATE_MGR] set_value() → Knob {src}:{pid} not found in registry")
            self._debug_inventory()
        return updated


    def get_value(self, source_name: str, param_id: str):
        """Return value for a knob or None if not found; logs lookup path."""
        src = str(source_name)
        pid = str(param_id)
        showlog.verbose(f"[STATE_MGR] get_value() lookup src={src} pid={pid} "
                      f"(knobs={len(self.knobs)})")

        with self._lock:
            for knob_id, k in self.knobs.items():
                k_src = str(k.get("source_name"))
                k_pid = str(k.get("param_id"))
                if k_src == src and k_pid == pid:
                    val = k.get("value")
                    showlog.verbose(f"[STATE_MGR] get_value() HIT knob_id={knob_id} "
                                  f"src={k_src} pid={k_pid} → {val}")
                    return val

        showlog.warn(f"[STATE_MGR] get_value() → Knob {src}:{pid} not found in registry")
        self._debug_inventory()
        return None




    def get_all_for_source(self, source_name: str) -> dict:
        """Return {param_id: value} for all knobs from a source."""
        with self._lock:
            return {
                k["param_id"]: k["value"]
                for k in self.knobs.values()
                if k.get("source_name") == source_name
            }

    # --------------------------------------------------------------
    # Dial-page compatibility wrappers
    # --------------------------------------------------------------
    def get_page(self, page: str):
        """Return all knobs for a UI page as {slot: (value, semantic)}."""
        out = {}
        with self._lock:
            for k in self.knobs.values():
                if k.get("source_name") == page:
                    slot = k.get("param_id")
                    out[slot] = (int(k.get("value", 0)), k.get("semantic", None))
        return out

    def apply_to_dials(self, page: str, dials):
        """In-place update: if stored value exists, write it back (no redraw)."""
        with self._lock:
            for d in dials:
                try:
                    for k in self.knobs.values():
                        if (
                            k.get("source_name") == page
                            and k.get("param_id") == str(int(d.id))
                        ):
                            d.value = int(k.get("value", 0))
                            break
                except Exception:
                    continue


# ===================================================================
# Legacy-level static functions
# ===================================================================
def _key(cc: int, uid: str) -> str:
    return f"{int(cc)}::{str(uid)}"


def register_instance(
    family: str,
    cc: int,
    uid: str,
    value: Any = 0,
    semantic: Optional[str] = None,
    active: bool = True,
) -> Dict[str, Any]:
    """Create (or upsert) a live instance entry."""
    global _dirty
    entry_key = _key(cc, uid)
    with _lock:
        fam = _states.setdefault(family, {})
        entry = fam.get(
            entry_key,
            {
                "family": family,
                "cc": int(cc),
                "uid": str(uid),
                "value": value,
                "semantic": semantic,
                "active": bool(active),
            },
        )
        entry["value"] = value
        entry["semantic"] = semantic
        entry["active"] = bool(active)
        fam[entry_key] = entry
        _dirty = True
        return entry


def set_value(family: str, cc: int, uid: str, value: Any, semantic: Optional[str] = None) -> None:
    """Update the current value for a live instance."""
    global _dirty
    entry_key = _key(cc, uid)
    with _lock:
        fam = _states.setdefault(family, {})
        if entry_key not in fam:
            fam[entry_key] = {
                "family": family,
                "cc": int(cc),
                "uid": str(uid),
                "value": value,
                "semantic": semantic,
                "active": True,
            }
        else:
            fam[entry_key]["value"] = value
            if semantic is not None:
                fam[entry_key]["semantic"] = semantic
        _dirty = True


def get_state(family: Optional[str] = None) -> Dict[str, Any]:
    """Return a snapshot of all live states."""
    with _lock:
        if family:
            return json.loads(json.dumps(_states.get(family, {})))
        return json.loads(json.dumps(_states))


def load() -> None:
    """Load /states/device_state.json into memory."""
    if not _STATE_FILE:
        init()
    if not os.path.isfile(_STATE_FILE):
        return

    with _lock:
        try:
            with open(_STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            families = (
                data.get("families", {})
                if "families" in data
                else {k: v for k, v in data.items() if k != "meta"}
            )

            cleaned = {}
            for fam_name, inst_map in families.items():
                if not isinstance(inst_map, dict):
                    continue
                cleaned[fam_name] = {}
                for inst_key, entry in inst_map.items():
                    if not isinstance(entry, dict):
                        continue
                    cleaned[fam_name][inst_key] = {
                        "family": entry.get("family", fam_name),
                        "cc": int(entry.get("cc", 0)),
                        "uid": str(entry.get("uid", "")),
                        "value": entry.get("value", 0),
                        "semantic": entry.get("semantic"),
                        "active": bool(entry.get("active", True)),
                    }

            _states.clear()
            _states.update(cleaned)
        except Exception as e:
            showlog.warn(f"[STATE_MGR] load failed: {e}")


def save_now() -> None:
    """Write device_state.json atomically if anything changed."""
    global _dirty
    if not _STATE_FILE:
        init()

    with _lock:
        if not _dirty:
            return

        payload = {
            "meta": {
                "version": 1,
                "last_saved": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
            **_states,
        }

        tmp_fd, tmp_path = tempfile.mkstemp(prefix="device_state.", suffix=".json", dir=_STATES_DIR)
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, _STATE_FILE)
            _dirty = False
        except Exception as e:
            showlog.warn(f"[STATE_MGR] save_now failed: {e}")
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


# ===================================================================
# Initialization
# ===================================================================
manager: Optional["StateManager"] = None


def init(base_dir: Optional[str] = None) -> None:
    """Initialize paths and global StateManager."""
    global _BASE_DIR, _STATES_DIR, _STATE_FILE, manager

    _BASE_DIR = base_dir or os.path.dirname(os.path.dirname(__file__))  # /build
    _STATES_DIR = os.path.join(_BASE_DIR, "states")
    _STATE_FILE = os.path.join(_STATES_DIR, "device_state.json")

    os.makedirs(_STATES_DIR, exist_ok=True)

    manager = StateManager()

    # Attempt to load existing global state
    if os.path.isfile(_STATE_FILE):
        try:
            load()
            showlog.log(None, f"[STATE_MGR] Loaded existing {_STATE_FILE}")
        except Exception as e:
            showlog.warn(f"[STATE_MGR] Failed to load {_STATE_FILE}: {e}")
    else:
        showlog.log(None, "[STATE_MGR] No device_state.json found (fresh start)")

    showlog.log(None, "[STATE_MGR] Initialized")
