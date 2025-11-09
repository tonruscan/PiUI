# /build/system/cc_registry.py
import os, sys
import json, threading, hashlib, importlib, showlog
import config as cfg
cfg.sys_folders()

# ensure /build is on sys.path for state_manager import
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from system import state_manager

_lock = threading.RLock()
_REGISTRY = {}
_FILE = os.path.join(os.path.dirname(__file__), "cc_registry.json")

def init():
    """Load existing CC registry (safe empty start)."""
    global _REGISTRY
    try:
        if os.path.isfile(_FILE):
            with open(_FILE, "r", encoding="utf-8") as f:
                _REGISTRY = json.load(f)
            showlog.debug(f"[CC_REG] Loaded {_FILE}")
        else:
            _REGISTRY = {}
            showlog.debug("[CC_REG] Fresh start")
    except Exception as e:
        showlog.error(f"[CC_REG] Init failed: {e}")
        _REGISTRY = {}


def allocate(family: str, label: str) -> int:
    """Allocate a new CC number for a family/label pair."""
    with _lock:
        # existing?
        for cc, info in _REGISTRY.items():
            if info.get("family") == family and info.get("label") == label:
                return int(cc)

        # find next free CC (0-127)
        for cc in range(128):
            if str(cc) not in _REGISTRY:
                _REGISTRY[str(cc)] = {"family": family, "label": label}
                _save()
                showlog.debug(f"[CC_REG] Allocated CC {cc} for {family}:{label}")
                return cc
        showlog.error("[CC_REG] No free CC numbers")
        return -1


def lookup(family: str, label: str) -> int:
    """Return CC for given family/label, or -1 if missing."""
    with _lock:
        for cc, info in _REGISTRY.items():
            if info.get("family") == family and info.get("label") == label:
                return int(cc)
    return -1


def _save():
    try:
        tmp = _FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_REGISTRY, f, indent=2)
        os.replace(tmp, _FILE)
    except Exception as e:
        showlog.error(f"[CC_REG] Save failed: {e}")


def _make_param_id(device: str, label: str) -> str:
    """Generate a short 4-digit hex hash from device + label."""
    base = f"{device.lower()}:{label.lower()}"
    return hashlib.md5(base.encode()).hexdigest()[:4].upper()


def load_from_device(device_name: str):
    """Import /device/{device_name}.py and register its dials into the StateManager (no UI access here)."""
    showlog.debug(f"[CC_REG] Importing device.{device_name.lower()} from {cfg.DEVICE_DIR}")

    # NEW: skip if there is no /device/<name>.py module (e.g., a standalone plugin)
    import importlib.util
    modname = f"device.{device_name.lower()}"
    if importlib.util.find_spec(modname) is None:
        # 🔄 fallback: try modules/<name>_mod.py
        alt_modname = f"modules.{device_name.lower()}_mod"
        if importlib.util.find_spec(alt_modname) is not None:
            showlog.debug(f"[CC_REG] Fallback to module import: {alt_modname}")
            modname = alt_modname
        else:
            showlog.debug(f"[CC_REG] skip load_from_device: '{device_name}' has no device or module")
            return

    try:
        import importlib
        module = importlib.import_module(modname)
        
        reg = getattr(module, "REGISTRY", None) or {}
        # Case-insensitive family key resolution
        if device_name in reg:
            family_key = device_name
        else:
            family_key = next((k for k in reg.keys() if k.lower() == device_name.lower()), None)

        if not family_key:
            showlog.warn(f"[CC_REG] No REGISTRY for {device_name}")
            return

        family = reg[family_key]

        # NEW: respect family "type" flag
        if isinstance(family, dict) and family.get("type") == "module":
            showlog.debug(f"[CC_REG] '{device_name}' marked type=module — skipping device loader")
            return
        
        if not family_key:
            showlog.warn(f"[CC_REG] No REGISTRY for {device_name}")
            return
        

        family = reg[family_key]


        from system import state_manager
        sm = getattr(state_manager, "manager", None)
        if not sm:
            showlog.warn("[CC_REG] StateManager not ready")
            return

        imported = 0
        for i in range(1, 9):  # always 8 dials; fill EMPTY if missing
            key = f"{i:02d}"
            data = family.get(key) or {
                "label": "EMPTY",
                "cc": None,
                "range": [0, 100],
                "type": "raw",
                "options": None,
                "default_slot": i,
                "family": device_name,
            }

            label    = data.get("label", f"Dial {key}")
            param_id = _make_param_id(device_name, label)
            cc       = data.get("cc")

            sm.create_knob(
                source_type="device",
                source_name=device_name,            # e.g. "BMLPF"
                param_id=param_id,                  # hashed id (e.g., "16E6")
                label=label,
                value=0,
                range_=data.get("range", [0, 127]),
            )

            showlog.debug(f"[CC_REG] Registered {device_name}:{label} (id={param_id}, cc={cc})")
            imported += 1

        showlog.debug(f"[CC_REG] Loaded {imported} dials from {device_name}")

    except Exception as e:
        showlog.error(f"[CC_REG] load_from_device failed for {device_name}: {e}")


def load_from_module(module_name: str, registry: dict = None, device_name: str = None) -> None:
    """
    Register a module's REGISTRY into StateManager.
    If device_name is provided, state is namespaced as '{DEVICE}:{MODULE}'.
    """
    try:
        import importlib
        src_name = f"{device_name}:{module_name}" if device_name else module_name

        # Pull REGISTRY from the module if not supplied
        if registry is None:
            mod = importlib.import_module(f"pages.{module_name}")
            reg = getattr(mod, "REGISTRY", None) or {}
        else:
            reg = registry

        if not isinstance(reg, dict) or module_name not in reg:
            showlog.warn(f"[CC_REG] No REGISTRY for module {module_name}")
            return

        imported = 0
        family = reg.get(module_name) or {}

        for key, data in family.items():
            # Skip metadata entries like "type" (non-dict values)
            if not isinstance(data, dict):
                continue

            label    = data.get("label", f"Dial {key}")
            param_id = _make_param_id(src_name, label)

            # Create once; harmless to upsert if already present
            if param_id not in state_manager.manager.knobs:
                state_manager.manager.create_knob(
                    source_type="module",
                    source_name=src_name,
                    param_id=param_id,
                    label=label,
                    value=0,
                    range_=data.get("range", [0, 127]),
                )
                imported += 1


        showlog.debug(f"[CC_REG] Loaded {imported} module dials from {module_name} (src={src_name})")

    except Exception as e:
        showlog.error(f"[CC_REG] load_from_module failed for {module_name}: {e}")




def attach_mapping_to_dials(device_name: str, dials: list) -> None:
    """
    Attach sm_source_name/sm_param_id to built Dial objects, based on their *labels*.
    Call this AFTER rebuild_dials() + set_dials(...).
    """
    try:
        if not dials:
            showlog.debug(f"[CC_REG] attach: no dials to map for {device_name}")
            return

        mapped = 0
        for d in dials:
            label = getattr(d, "label", None)
            if not label:
                showlog.debug(f"[CC_REG] attach: dial {getattr(d,'id','?')} has no label; skip")
                continue
            pid = _make_param_id(device_name, label)
            d.sm_source_name = device_name
            d.sm_param_id    = pid
            mapped += 1
            showlog.debug(f"[CC_REG] attach: dial {getattr(d,'id','?')} '{label}' -> src={device_name} pid={pid}")

        showlog.debug(f"[CC_REG] attach: mapped {mapped} dials for {device_name}")

    except Exception as e:
        showlog.warn(f"[CC_REG] attach_mapping_to_dials failed for {device_name}: {e}")


