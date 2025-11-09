# /build/devices.py
import json
import os
import showlog
import config as cfg
import importlib
import dialhandlers
msg_queue = None  # injected from ui.py
DEVICE_DB = {}          # existing JSON devices
DEVICE_MODULES = {}     # per-device Python modules (populated at startup)
DEVICE_INDEX = {}       # map device names → module data

# ---------------------------------------------------------------------
# Path to per-device modules  (renamed folder: /device/)
# ---------------------------------------------------------------------
DEVICES_DIR = os.path.join(os.path.dirname(__file__), "device")

# ---------------------------------------------------------------------
# Try to load a Python module for per-device definitions
# ---------------------------------------------------------------------
def _try_load_module(device_name):
    """Return cached DEVICE_INFO for a given device."""
    dev_key = device_name.strip().upper()
    if dev_key in DEVICE_MODULES:
        return DEVICE_MODULES[dev_key]
    showlog.warn(f"fallback lookup for {device_name}")
    return None


# ---------------------------------------------------------------------
# Unified dial map loader (from module or JSON)
# ---------------------------------------------------------------------
def get_dial_map(device_name, page_id="01"):
    """Return the dial layout for the given device/page."""
    showlog.debug(f"get_dial_map() called → {device_name}:{page_id}")

    try:
        info = _try_load_module(device_name)
        if info:
            pages = info.get("pages", {})
            page = pages.get(page_id)
            if page and "dials" in page:
                showlog.debug(f"Using dials from module {device_name}:{page_id}")
                return page["dials"]
            else:
                showlog.debug(f"Module has no page {page_id} or 'dials' key for {device_name}")
    except Exception as e:
        showlog.error(f"get_dial_map() failed for {device_name}: {e}")

    # fallback to JSON
    try:
        dev_entry = DEVICE_DB.get(device_name.upper())
        if dev_entry:
            page = dev_entry.get("pages", {}).get(page_id)
            if page and "dials" in page:
                showlog.debug(f"Using dials from JSON for {device_name}:{page_id}")
                return page["dials"]
    except Exception as e:
        showlog.error(f"JSON fallback failed for {device_name}: {e}")

    showlog.warn(f"No dials found for {device_name}:{page_id}")
    return {}


def get_theme(device_name):
    """
    Return THEME dict for a device or module.
    - Devices: load their own THEME from /device/<name>.py
    - Modules: inherit the currently active device's theme
    - Plugins: check active module class for THEME
    """
    import os, importlib, showlog
    from dialhandlers import current_device_name
    from devices import DEVICES_DIR

    showlog.info(f"[THEME] get_theme() called with device_name='{device_name}'")

    # ──────────────────────────────────────────────────────────────
    # 0️⃣  Check if there's an active module with a THEME (plugin support)
    # ──────────────────────────────────────────────────────────────
    try:
        from pages import module_base
        active_module = getattr(module_base, "_ACTIVE_MODULE", None)
        showlog.info(f"[THEME] Checking active module: {active_module}")
        
        if active_module and hasattr(active_module, "THEME"):
            theme = getattr(active_module, "THEME")
            showlog.info(f"[THEME] Found THEME attribute: {type(theme)}, is_dict={isinstance(theme, dict)}, empty={not theme if isinstance(theme, dict) else 'N/A'}")
            if isinstance(theme, dict) and theme:
                showlog.info(f"[THEME] ✅ Using THEME from active module class: {list(theme.keys())[:5]}")
                return theme
            else:
                showlog.info(f"[THEME] THEME found but invalid or empty")
        else:
            showlog.info(f"[THEME] Active module has no THEME attribute")
    except Exception as e:
        showlog.info(f"[THEME] Active module check failed: {e}")
        import traceback
        showlog.info(f"[THEME] Traceback: {traceback.format_exc()}")

    # ──────────────────────────────────────────────────────────────
    # 1️⃣  Detect and resolve module → parent device theme
    # ──────────────────────────────────────────────────────────────
    try:
        devname_lower = str(device_name).strip().lower()

        # Gather all known device filenames
        dev_files = [f[:-3] for f in os.listdir(DEVICES_DIR)
                     if f.endswith(".py") and f != "__init__.py"]

        # If this entity isn't an actual device file, assume it's a module
        if devname_lower not in dev_files:
            parent_dev = getattr(dialhandlers, "current_device_name", None)
            # Only inherit if parent device is different AND not None/empty
            if isinstance(parent_dev, str) and parent_dev.strip() and parent_dev.lower() != devname_lower:
                showlog.debug(f"[THEME] '{device_name}' appears to be a module → using parent device '{parent_dev}' theme")
                device_name = parent_dev
            else:
                # Module with no parent device → return empty theme (use config defaults)
                showlog.debug(f"[THEME] Module '{device_name}' has no parent device → using config defaults")
                return {}

    except Exception as e:
        showlog.warn(f"[THEME] Module inheritance check failed for '{device_name}': {e}")


    # ──────────────────────────────────────────────────────────────
    # 2️⃣  Normal device theme lookup
    # ──────────────────────────────────────────────────────────────
    try:
        module_name = f"device.{device_name.lower()}"
        module = importlib.import_module(module_name)

        if hasattr(module, "THEME"):
            theme = getattr(module, "THEME")
            showlog.verbose(f"[DEBUG DEVICES] Loaded THEME from {module_name}: {theme}")
            return theme
        else:
            showlog.warn(f"No THEME in {module_name}")

    except Exception as e:
        showlog.warn(f"get_theme() import by filename failed for '{device_name}': {e}")

    # ──────────────────────────────────────────────────────────────
    # 3️⃣  Fallback: scan /device modules by DEVICE_INFO name
    # ──────────────────────────────────────────────────────────────
    try:
        dev_uc = str(device_name).strip().upper()
        if os.path.isdir(DEVICES_DIR):
            for fname in os.listdir(DEVICES_DIR):
                if not fname.endswith(".py") or fname == "__init__.py":
                    continue
                mod_name = fname[:-3]
                try:
                    mod = importlib.import_module(f"device.{mod_name}")
                    info = getattr(mod, "DEVICE_INFO", None)
                    if info and str(info.get("name", "")).strip().upper() == dev_uc:
                        theme = getattr(mod, "THEME", None)
                        if theme:
                            showlog.debug(f"THEME matched by DEVICE_INFO.name in device.{mod_name}")
                            return theme
                except Exception:
                    continue
    except Exception as e:
        showlog.error(f"THEME fallback scan failed for '{device_name}': {e}")

    # ──────────────────────────────────────────────────────────────
    # 4️⃣  Plugin theme lookup (for standalone plugins)
    # ──────────────────────────────────────────────────────────────
    try:
        # Try to load from plugins folder
        plugin_module_name = f"plugins.{device_name.lower()}_plugin"
        showlog.info(f"[THEME] Attempting to load plugin: {plugin_module_name}")
        plugin_module = importlib.import_module(plugin_module_name)
        showlog.info(f"[THEME] Successfully imported plugin: {plugin_module_name}")
        
        # Check if the plugin module has a THEME attribute
        if hasattr(plugin_module, "THEME"):
            theme = getattr(plugin_module, "THEME")
            showlog.info(f"[THEME] ✅ Loaded THEME from plugin module: {plugin_module_name}")
            return theme
        else:
            showlog.info(f"[THEME] No module-level THEME in {plugin_module_name}")
        
        # Also check if the module class has THEME (e.g., VK8M.THEME)
        showlog.info(f"[THEME] Checking classes in {plugin_module_name} for THEME attribute")
        for attr_name in dir(plugin_module):
            attr = getattr(plugin_module, attr_name)
            if hasattr(attr, "THEME") and isinstance(getattr(attr, "THEME"), dict):
                theme = getattr(attr, "THEME")
                showlog.info(f"[THEME] ✅ Loaded THEME from plugin class: {plugin_module_name}.{attr_name}")
                return theme
        
        showlog.info(f"[THEME] No THEME found in any class of {plugin_module_name}")
                
    except Exception as e:
        showlog.warn(f"[THEME] Plugin theme lookup failed for '{device_name}': {e}")
        import traceback
        showlog.warn(f"[THEME] Traceback: {traceback.format_exc()}")

    # ──────────────────────────────────────────────────────────────
    # 5️⃣  Final fallback → empty dict (use cfg defaults)
    # ──────────────────────────────────────────────────────────────
    return {}


# ---------------------------------------------------------------------
# NEW: Init state loader (from module or JSON)
# ---------------------------------------------------------------------
def get_init_state(device_name):
    """Return init_state from module or JSON fallback."""
    showlog.log(None, f"[DEBUG DEVICES] get_init_state() called for {device_name}")
    try:
        info = _try_load_module(device_name)
        if info and "init_state" in info:
            showlog.debug(f" Using init_state from module {device_name}")
            return info["init_state"]
    except Exception as e:
        showlog.error(f"get_init_state() module load failed: {e}")

    # fallback
    try:
        dev_entry = get_by_name(device_name)
        if dev_entry and "init_state" in dev_entry:
            showlog.debug(f"Using init_state from JSON for {device_name}")
            return dev_entry["init_state"]
    except Exception as e:
        showlog.error(f"JSON init_state fallback failed: {e}")

    showlog.warn(f"No init_state found for {device_name}")
    return {}


# ---------------------------------------------------------------------
# NEW: Announce message loader (from module or JSON)
# ---------------------------------------------------------------------
def get_announce_msg(device_name):
    """Return announce_msg (list of bytes) from module or JSON fallback."""
    showlog.debug(f"get_announce_msg() called for {device_name}")
    try:
        info = _try_load_module(device_name)
        if info and "announce_msg" in info:
            showlog.debug(f"Using announce_msg from module {device_name}")
            return info["announce_msg"]
    except Exception as e:
        showlog.error(f"get_announce_msg() module load failed: {e}")

    # fallback
    try:
        dev_entry = get_by_name(device_name)
        if dev_entry and "announce_msg" in dev_entry:
            showlog.debug(f"Using announce_msg from JSON for {device_name}")
            return dev_entry["announce_msg"]
    except Exception as e:
        showlog.error(f"JSON announce_msg fallback failed: {e}")

    showlog.warn(f"No announce_msg found for {device_name}")
    return []


# ---------------------------------------------------------------------
# Load device definitions from JSON + preload Python modules
# ---------------------------------------------------------------------
def load(path=None):
    """Load device definitions from JSON into DEVICE_DB and preload all /device modules."""
    global DEVICE_DB, DEVICE_MODULES, DEVICE_INDEX

    DEVICE_MODULES = {}
    DEVICE_INDEX = {}

    if path is None:
        path = cfg.config_path("devices.json")

    # -------------------------------------------------------------
    # 1️⃣ Load JSON-based devices
    # -------------------------------------------------------------
    try:
        with open(path, "r", encoding="utf-8") as f:
            DEVICE_DB = json.load(f)["devices"]

        for dev_id, dev in DEVICE_DB.items():
            if "name" in dev and isinstance(dev["name"], str):
                dev["name"] = dev["name"].strip().upper()
            for page_id, page in dev.get("pages", {}).items():
                for dial_id, dial_def in page.get("dials", {}).items():
                    page_val = dial_def.get("page")
                    if page_val in ("", None):
                        dial_def["page"] = None
                    else:
                        try:
                            dial_def["page"] = int(page_val)
                        except Exception:
                            dial_def["page"] = None

        showlog.debug(f"Loaded {len(DEVICE_DB)} devices from {path} (upper-case normalized)")

    except Exception as e:
        DEVICE_DB = {}
        showlog.error(f"[DEVICES] Load error: {e}")

    # -------------------------------------------------------------
    # 2️⃣ Preload Python device modules in /device/
    # -------------------------------------------------------------
    showlog.debug("Preloading Python device modules...")
    try:
        if not os.path.isdir(DEVICES_DIR):
            showlog.debug(f"No /device directory found at {DEVICES_DIR}")
            return

        for fname in os.listdir(DEVICES_DIR):
            if fname.endswith(".py") and fname != "__init__.py":
                mod_name = fname[:-3]
                try:
                    module = importlib.import_module(f"device.{mod_name}")
                    if hasattr(module, "DEVICE_INFO"):
                        info = module.DEVICE_INFO
                        dev_name = info.get("name", mod_name).upper()
                        dev_id = info.get("id", mod_name)
                        DEVICE_MODULES[dev_name] = info
                        DEVICE_INDEX[dev_id] = dev_name
                        showlog.debug(f"Loaded module: {dev_name} (ID {dev_id})")
                    else:
                        showlog.warn(f"Skipped {mod_name} – no DEVICE_INFO found")
                except Exception as e:
                    showlog.error(f"Failed to load module {mod_name}: {e}")

        showlog.debug(f"Preloaded {len(DEVICE_MODULES)} Python device modules successfully")

    except Exception as e:
        showlog.error(f"Module preloading error: {e}")


# ---------------------------------------------------------------------
# Access Helpers
# ---------------------------------------------------------------------
def get(device_id):
    """Return a device definition dict from DEVICE_DB using its ID."""
    try:
        dev_key = f"{int(device_id):02d}" if not isinstance(device_id, str) or len(device_id) < 2 else device_id
        return DEVICE_DB.get(dev_key)
    except Exception as e:
        showlog.error(f"get() error for id {device_id}: {e}")
        return None


def get_by_name(name):
    """Return device dict by name or ID (case-insensitive, supports partial matches)."""
    showlog.debug(f"get_by_name() called with name={name!r}")
    try:
        if not name:
            return None

        # Handle numeric or string IDs like '01', 1, etc.
        if isinstance(name, (int, float)) or (isinstance(name, str) and name.isdigit()):
            dev_key = f"{int(name):02d}"
            dev = DEVICE_DB.get(dev_key)
            if dev:
                showlog.debug(f"get_by_name() ID lookup success → {dev.get('name')}")
                return dev

        # Normalize for name-based lookup
        name_uc = str(name).strip().upper()

        # Try Python module cache first
        mod_info = _try_load_module(name_uc)
        if mod_info:
            showlog.debug(f"Loaded from module: {name_uc}")
            return mod_info
        else:
            showlog.warn(f"No module found for: {name_uc}")

        # Exact match in JSON
        for dev in DEVICE_DB.values():
            if dev.get("name", "").strip().upper() == name_uc:
                return dev

        # Partial match fallback
        for dev in DEVICE_DB.values():
            devname = dev.get("name", "").strip().upper()
            if name_uc in devname or devname in name_uc:
                return dev

    except Exception as e:
        showlog.error(f"get_by_name() error: {e}")

    return None


def get_id_by_name(name):
    """Return device ID (key) by name (case-insensitive)."""
    try:
        name_uc = str(name).strip().upper()
        # First: JSON DB
        for dev_id, dev in DEVICE_DB.items():
            if dev.get("name", "").strip().upper() == name_uc:
                return dev_id

        # Fallback: module-loaded devices (DEVICE_MODULES has name→info)
        if name_uc in DEVICE_MODULES:
            info = DEVICE_MODULES.get(name_uc) or {}
            # Prefer explicit id from module, else return None
            return info.get("id")
    except Exception as e:
        showlog.error(f"get_id_by_name() error: {e}")
    return None


# ---------------------------------------------------------------------
# Update dials + header text
# ---------------------------------------------------------------------
def update_from_device(device_id, layer_id, dials, header_text_ref):
    """Update dials and header text from device module or JSON fallback."""
    global DEVICE_DB, msg_queue

    showlog.debug(f"Update_from_device() called → device_id={device_id!r}, layer_id={layer_id!r}")
    dev_key = f"{int(device_id):02d}"
    layer_key = "NA" if layer_id in ("NA", 0x7F) else f"{int(layer_id):02d}"
    showlog.debug(f"Normalized keys → dev_key={dev_key}, layer_key={layer_key}")

    # --- Load dial map ---
    dial_map = get_dial_map(device_id, layer_key)
    if not dial_map:
        showlog.warn(f"get_dial_map() returned empty for {device_id}:{layer_key}")
        msg_queue.put(f"(MAP) Missing dev {dev_key} / layer {layer_key}")
        return header_text_ref, None

    showlog.debug(f"Dial count in map: {len(dial_map)}")

    # --- Load name + page title ---
    dev_entry = get_by_name(device_id)
    dev_name = dev_entry.get("name", device_id)
    page_name = dev_entry.get("pages", {}).get(layer_key, {}).get("name", "")
    header_text = dev_name if layer_key == "NA" else f"{dev_name} - {page_name}"

    # --- Map each dial ---
    for d in dials:
        dial_key = f"{d.id:02d}"
        dial_def = dial_map.get(dial_key)
        if dial_def:
            label = dial_def.get("label", "?")
            showlog.verbose(f"Mapping dial {dial_key} → {label}")
            d.label = label
            d.range = dial_def.get("range", 127)
            d.cc_num = dial_def.get("cc", None)
            d.options = dial_def.get("options")
            d.page = dial_def.get("page")
            if "type" in dial_def:
                d.type = dial_def["type"]
        else:
            showlog.warn(f"No mapping for dial {dial_key} in page {layer_key}")

    msg_queue.put(f"(MAP) {header_text}")

    # --- Determine left button ---
    page_button = None
    if layer_key != "NA":
        try:
            idx = int(layer_key)
            if 1 <= idx <= 5:
                page_button = str(idx)
                showlog.debug(f"Page button = {page_button}")
        except Exception as e:
            showlog.error(f"Page button calc error: {e}")

    showlog.debug(f"update_from_device() finished OK → header='{header_text}', button={page_button}")
    return header_text, page_button


# ---------------------------------------------------------------------
# Left-button index by page name
# ---------------------------------------------------------------------
def get_button_index_by_page_name(device_name, page_name):
    """Return the left-button index (1-5) for a given device and page name."""
    try:
        dev = get_by_name(device_name)
        if not dev:
            return None
        pages = dev.get("pages", {})
        for pid, pdata in pages.items():
            if pdata.get("name", "").strip().lower() == page_name.strip().lower():
                try:
                    idx = int(pid)
                    if 1 <= idx <= 5:
                        return idx
                except Exception:
                    continue
        return None
    except Exception as e:
        showlog.error(f"get_button_index_by_page_name() error: {e}")
        return None
