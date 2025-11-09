# dialhandlers.py
from unicodedata import name
import midiserver
import devices
import showlog
import device_states
import cv_client
import unit_router
import config as cfg


class DialLatchManager:
    """Tracks latch state for external controller moves."""

    def __init__(self, enabled: bool, threshold: int, release: int):
        self.enabled = bool(enabled)
        self.threshold = max(0, int(threshold))
        # Release window cannot exceed the trigger threshold
        release = max(0, int(release))
        self.release = min(self.threshold, release) if self.threshold else 0
        self._states = {}

    def configure(self, enabled: bool = None, threshold: int = None, release: int = None):
        if enabled is not None:
            self.enabled = bool(enabled)
        if threshold is not None:
            self.threshold = max(0, int(threshold))
        if release is not None:
            release = max(0, int(release))
            self.release = min(self.threshold, release) if self.threshold else 0
        elif threshold is not None:
            # Clamp existing release when threshold changes
            self.release = min(self.threshold, self.release) if self.threshold else 0
        if not self.enabled or self.threshold == 0:
            self._states.clear()

    def reset_for_dial(self, dial_id: int):
        self._states.pop(int(dial_id), None)

    def reset_all(self):
        self._states.clear()

    def evaluate(self, dial_id: int, controller_value: int, ui_value: int):
        """Return (allow, reason) for an incoming controller event."""
        if not self.enabled or self.threshold == 0:
            return True, "disabled"
        if ui_value is None:
            # Nothing rendered yet, just accept the update
            return True, "no_ui_state"

        try:
            dial_id = int(dial_id)
            ctrl_val = int(controller_value)
            ui_val = int(ui_value)
        except (TypeError, ValueError):
            return True, "non_numeric"
        state = self._states.get(dial_id)

        diff = abs(ctrl_val - ui_val)
        if state:
            state["last_value"] = ctrl_val
            if diff <= self.release:
                self._states.pop(dial_id, None)
                return True, "released"
            return False, "holding"

        if diff > self.threshold:
            self._states[dial_id] = {
                "target": ui_val,
                "last_value": ctrl_val,
            }
            return False, "latched"

        return True, "in_band"


_latch_manager = DialLatchManager(
    enabled=getattr(cfg, "DIAL_LATCH_ENABLED", False),
    threshold=getattr(cfg, "DIAL_LATCH_THRESHOLD", 0),
    release=getattr(cfg, "DIAL_LATCH_RELEASE", 0),
)

#from datetime import datetime
from device.quadraverb import set_default_mute_state, toggle_page_mute

dials = None  # will be set by ui.py at startup

# -------------------------------------------------------
# Global runtime state
# -------------------------------------------------------

current_device_id = "01"     # default: Quadraverb
current_page_id = "01"       # default: Reverb
msg_queue = None             # assigned by ui.py at init
live_states = {}             # in-memory snapshot for all devices/pages: {device: {page: [dial_values]}}
visited_pages = set()        # track which device:page combinations have been visited (for first-load init)
live_button_states = {}      # button states for module pages: {page_id: {button_var: value}}
device_states.load()
current_device_name = None  # updated when a device is selected


def get_page_mute_states(device_name: str):
    """Return the current page mute state map for the given device."""
    if not device_name:
        return {}

    name_key = str(device_name).strip().upper()
    if name_key == "QUADRAVERB":
        try:
            import importlib
            mod = importlib.import_module("device.quadraverb")
            return getattr(mod, "page_mute_states", {})
        except Exception as exc:
            showlog.debug(f"[DIALHANDLERS] get_page_mute_states error: {exc}")
            return {}

    # Default: device has no mute states tracked
    return {}


# -------------------------------------------------------
# Initialization
# -------------------------------------------------------

def init(msg_q):
    """Called once from ui.py to share the message queue."""
    global msg_queue
    msg_queue = msg_q

def set_dials(dials_ref):
    """Called from ui.py to register the active dials list."""
    global dials
    dials = dials_ref
    _latch_manager.reset_all()
    showlog.info(f"*[DIALHANDLERS] set_dials() called - {len(dials_ref)} dials registered")
    for i, d in enumerate(dials_ref[:8], 1):
        if d:
            showlog.info(f"*[DIALHANDLERS] 🔍 Dial {i}: label='{getattr(d, 'label', 'NO_LABEL')}', id={getattr(d, 'id', 'NO_ID')}, value={getattr(d, 'value', 'NO_VAL')}")

def load_device(device_name):
    """
    Switch the active device mapping by name.
    Sets both current_device_name and current_device_id correctly.
    """
    global current_device_name, current_device_id

    showlog.info(f"*[DIALHANDLERS] 🔄 load_device() called with device_name='{device_name}'")
    
    # Clear any active module when switching to a device page
    try:
        from pages import module_base
        if module_base._ACTIVE_MODULE is not None:
            showlog.info(f"*[DIALHANDLERS] ♻️ Clearing active module when loading device '{device_name}'")
            showlog.info(f"*[DIALHANDLERS] 🔍 Previous module: {module_base._ACTIVE_MODULE}")
            module_base._ACTIVE_MODULE = None
            module_base._MOD_INSTANCE = None
            module_base._CUSTOM_WIDGET_INSTANCE = None
    except Exception as e:
        showlog.debug(f"Failed to clear active module: {e}")

    _latch_manager.reset_all()

    # --- Normalize to uppercase once so all modules match ---
    if isinstance(device_name, str):
        device_name = device_name.strip().upper()

    showlog.verbose(f"Normalized device_name to: '{device_name}'")

    current_device_name = device_name
    showlog.verbose(f"Set current_device_name to: '{current_device_name}'")

    dev_id = devices.get_id_by_name(device_name)
    showlog.debug(f"devices.get_id_by_name('{device_name}') returned: '{dev_id}'")
    
    if not dev_id:
        showlog.warn(f"Device not found in devices.json: {device_name}")
        showlog.warn(f"[MAP] Device not found in devices.json: {device_name}")
        return

    current_device_id = dev_id
    showlog.verbose(f"Set current_device_id to: '{current_device_id}'")
    
    dev = devices.get(current_device_id)
    showlog.verbose(f"devices.get('{current_device_id}') returned: {dev is not None}")
    
    if dev:
        page01_name = dev["pages"].get("01", {}).get("name", "Page 01")
        showlog.verbose(f"Device pages: {list(dev.get('pages', {}).keys())}")
        showlog.debug(f"[MAP] Selected device → ID={current_device_id}, Name={dev['name']} - {page01_name}")
    else:
        showlog.warn(f"Failed to get device info for ID '{current_device_id}'")

    # Apply Quadraverb default mute state on load (Reverb unmuted, others muted)
    try:
        if device_name == "QUADRAVERB":
            set_default_mute_state()
    except Exception as e:
        showlog.error(f"[MAP] Default mute setup failed: {e}")

    # --- Determine and return the device’s starting page ---
    # Prefer explicit setting from devices.json if available
    start_page = dev.get("default_page")

    # Fallback: use presets for everything except Quadraverb
    if not start_page:
        start_page = "dials" if device_name == "QUADRAVERB" else "presets"

    showlog.debug(f"[MAP] {device_name} → default page '{start_page}'")

    try:
        unit_router.load_device(name, on_midi_cc)
    except Exception as e:
        showlog.error(f"unit_router.load_device failed: {e}")
    
    return start_page


# -------------------------------------------------------
# OUTGOING – when user moves a dial
# -------------------------------------------------------
def on_dial_change(dial_id, value, source="ui"):
    try:
        if source != "controller":
            _latch_manager.reset_for_dial(dial_id)

        device = devices.get(current_device_id)
        page = device["pages"][current_page_id]
        dial_meta = page["dials"][f"{dial_id:02d}"]

        label = dial_meta["label"]
        param_range = dial_meta.get("range", 127)
        page_offset = dial_meta.get("page", 0)

        # ✅ Try to load CC_OVERRIDE from the device module dynamically
        try:
            dev_module = __import__(f"device.{device['name'].lower()}", fromlist=["CC_OVERRIDE"])
            override_cc = getattr(dev_module, "CC_OVERRIDE", {}).get(f"{dial_id:02d}")
            showlog.debug(f"[DIAL_CHANGE] Found override for dial {dial_id}: CC {override_cc}")
        except Exception:
            showlog.debug(f"[DIAL_CHANGE] No override found for dial {dial_id}")
            override_cc = None

        # Resolve the Dial object (for UI value/mapping)
        d = None
        try:
            if dials and 1 <= dial_id <= len(dials):
                d = dials[dial_id - 1]
        except Exception:
            d = None

        # Helper: persist to StateManager (used below in both CV and MIDI paths)
        def _persist_state():
            try:
                # Skip EMPTY labels to avoid bogus "unknown" entries
                if not label or str(label).upper() == "EMPTY":
                    showlog.debug(f"[STATE PERSIST] Skip slot={dial_id} because label is EMPTY")
                    return

                from system import state_manager
                sm = getattr(state_manager, "manager", None)
                if not sm:
                    showlog.warn(f"[STATE PERSIST] No StateManager instance; skip persist")
                    return

                # Prefer existing mapping attached to dial; otherwise derive param_id exactly like registry
                src = getattr(d, "sm_source_name", device["name"]) if d else device["name"]
                pid = getattr(d, "sm_param_id", None)
                if not pid:
                    try:
                        from system import cc_registry
                        pid = cc_registry._make_param_id(device["name"], label)
                        if d:
                            d.sm_source_name = src
                            d.sm_param_id = pid
                        showlog.debug(f"[STATE PERSIST] Derived mapping slot={dial_id} src={src} pid={pid} (label='{label}')")
                    except Exception as e:
                        showlog.warn(f"[STATE PERSIST] Failed to derive pid for slot={dial_id} label='{label}': {e}")
                        return

                # Value to persist: use the dial's current display value if we have the dial, else the incoming 'value'
                persist_val = int(getattr(d, "value", value)) if d else int(value)
                sm.set_value(src, pid, persist_val)
                showlog.debug(f"[STATE PERSIST] slot={dial_id} src={src} pid={pid} val={persist_val}")

            except Exception as e:
                showlog.warn(f"[STATE PERSIST] exception slot={dial_id}: {e}")

        # --- Check for CV-based transport (e.g., BMLPF) -------------------
        try:
            dev_module = __import__(f"device.{device['name'].lower()}", fromlist=["TRANSPORT"])
            if getattr(dev_module, "TRANSPORT", None) == "cv":
                showlog.debug(f"[CV_ROUTE] CV transport detected for {device['name']}")
                
                # Check if device has custom CV handler
                custom_handled = False
                if hasattr(dev_module, "handle_cv_send"):
                    try:
                        showlog.verbose(f"[CV_ROUTE] Calling custom CV handler for {device['name']}")
                        custom_handled = dev_module.handle_cv_send(dial_id, value, current_page_id)
                        showlog.verbose(f"[CV_ROUTE] Custom CV handler returned: {custom_handled}")
                    except Exception as e:
                        showlog.error(f"[CV_ROUTE] Custom CV handler error: {e}")
                        custom_handled = False
                
                # If custom handler didn't handle it, use default CV logic
                if not custom_handled:
                    showlog.verbose(f"[CV_ROUTE] Using default CV logic for {device['name']}")
                    cv_map = getattr(dev_module, "CV_MAP", {})
                    ch = cv_map.get(f"{dial_id:02d}")
                    if ch is not None:
                        # Clamp + scale from MIDI-style 0–127 → full DAC range
                        max_val = getattr(dev_module, "CV_RESOLUTION", 4095)
                        scaled_val = int(round((value / 127.0) * max_val))
                        scaled_val = max(0, min(max_val, scaled_val))
                        cv_client.send(ch, scaled_val)
                        showlog.debug(f"[CV_ROUTE] Default CV send: {device['name']} dial {dial_id:02d} → CH{ch} = {scaled_val}")
                    else:
                        showlog.warn(f"[CV_ROUTE] No CV mapping for dial {dial_id:02d}")

                # ✅ Persist to StateManager (if available)
                _persist_state()

                # ✅ ALSO update LIVE state (this was missing for CV)
                page_map = live_states.setdefault(device["name"], {})
                if current_page_id not in page_map:
                    try:
                        baseline = [int(getattr(dd, "value", 0)) for dd in (dials or [])]
                        if len(baseline) < 8:
                            baseline += [0] * (8 - len(baseline))
                        page_map[current_page_id] = baseline[:8]
                    except Exception:
                        page_map[current_page_id] = [0] * 8
                page_map[current_page_id][dial_id - 1] = int(value)

                # (optional UI sync, harmless)
                # if msg_queue: msg_queue.put(("update_dial_value", dial_id, value))
                return

                return
        except Exception as e:
            showlog.error(f"[CV_ROUTE] {e}")

        # --- Send to midiserver (unchanged) ---
        midiserver.enqueue_device_message(
            device_name=device["name"],
            dial_index=dial_id,
            value=value,
            param_range=param_range,
            section_id=int(current_page_id),
            page_offset=page_offset,
            dial_obj=dials[dial_id - 1] if dials and 1 <= dial_id <= len(dials) else None,
            cc_override=override_cc,
        )

        if override_cc is not None:
            showlog.debug(f"[CC_OVERRIDE] Using CC {override_cc} for dial {dial_id}")

        # --- Update LIVE state (unchanged) ---
        page_map = live_states.setdefault(device["name"], {})
        if current_page_id not in page_map:
            try:
                baseline = [int(getattr(dd, "value", 0)) for dd in (dials or [])]
                if len(baseline) < 8:
                    baseline += [0] * (8 - len(baseline))
                page_map[current_page_id] = baseline[:8]
            except Exception:
                page_map[current_page_id] = [0] * 8

        page_map[current_page_id][dial_id - 1] = int(value)

        # ✅ Persist for non-CV / normal path as well
        _persist_state()

        if msg_queue:
            msg_queue.put(f"(OUT) {device['name']}:{page['name']} {label} = {value}")

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        showlog.error(f"[Out] {e}\nTraceback:\n{tb}")




def route_param(target_device, dial_id, value, page_id=None):
    """
    Send a value for a specific device+dial (used by Frankenstein/router pages).
    target_device: name or id (case-insensitive)
    dial_id: int or '01'..'08'
    """
    try:
        # Resolve device dict
        dev = devices.get_by_name(target_device) if isinstance(target_device, str) else devices.get(target_device)
        if not dev:
            showlog.warn(f"[Router] Device not found: {target_device}")
            return

        device_name = dev["name"]
        dev_id = dev.get("id")
        dial_id = int(dial_id) if isinstance(dial_id, str) else dial_id

        # Load device module for CV/overrides
        import importlib
        dev_module = importlib.import_module(f"device.{device_name.lower()}")

        # --- CV transport? ---
        try:
            if getattr(dev_module, "TRANSPORT", None) == "cv":
                cv_map = getattr(dev_module, "CV_MAP", {})
                ch = cv_map.get(f"{dial_id:02d}")
                if ch is not None:
                    max_val = getattr(dev_module, "CV_RESOLUTION", 4095)
                    scaled_val = int(round((value / 127.0) * max_val))
                    scaled_val = max(0, min(max_val, scaled_val))
                    cv_client.send(ch, scaled_val)
                    showlog.debug(f"[CV_SEND][router] {device_name} dial {dial_id:02d} → CH{ch} = {scaled_val}")
                    return
        except Exception as e:
            showlog.warn(f"[CV_ROUTE router] {e}")

        # --- CC override if defined ---
        try:
            override_cc = getattr(dev_module, "CC_OVERRIDE", {}).get(f"{dial_id:02d}")
        except Exception:
            override_cc = None

        # Page offset/range if we can infer them (safe defaults otherwise)
        pages = dev.get("pages", {})
        pid = page_id or next(iter(pages.keys()), "01")
        meta = pages.get(pid, {}).get("dials", {}).get(f"{dial_id:02d}", {})
        param_range = meta.get("range", 127)
        page_offset = meta.get("page", 0)

        midiserver.enqueue_device_message(
            device_name=device_name,
            dial_index=dial_id,
            value=value,
            param_range=param_range,
            section_id=int(pid) if str(pid).isdigit() else 1,
            page_offset=page_offset,
            dial_obj=None,
            cc_override=override_cc,
        )

        # new: seed from current rendered dials, not zeros
        page_map = live_states.setdefault(device_name, {})
        if pid not in page_map:
            try:
                baseline = [int(getattr(d, "value", 0)) for d in (dials or [])]
                if len(baseline) < 8:
                    baseline += [0] * (8 - len(baseline))
                page_map[pid] = baseline[:8]
            except Exception:
                page_map[pid] = [0] * 8

        page_map[pid][dial_id - 1] = int(value)

        if msg_queue:
            label = meta.get("label", f"Dial {dial_id:02d}")
            page_name = pages.get(pid, {}).get("name", pid)
            msg_queue.put(f"(OUT)[router] {device_name}:{page_name} {label} = {value}")

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        showlog.error(f"[DialRouter OUT error] {e}\n{tb}")


# -------------------------------------------------------
# OUTGOING – when user press a button
# -------------------------------------------------------

ui_mode = "dials"   # <-- add near the top of file, with other globals

def on_button_press(button_index, suppress_render=False):
    """
    Called when a left/right button is pressed on the touchscreen.  
    Handles page switching, device navigation, and page-level functions.
    
    Args:
        button_index: Button number (1-10)
        suppress_render: If True, don't queue force_redraw message (for pre-loading)
    """

    global current_page_id, ui_mode, live_states
    
    # Only trigger render if not suppressed (allows pre-loading state without flashing)
    if not suppress_render:
        msg_queue.put(("force_redraw", 50))  # 50 frames of full redraw
    
    showlog.debug(f"[DIALHANDLERS] on_button_press called with button_index={button_index}, suppress_render={suppress_render}")
    showlog.debug(f"[DIALHANDLERS] current_device_name='{current_device_name}', current_device_id='{current_device_id}'")
    
    # --- Device-specific hook (if defined in /device/<name>.py) ---
    try:
        import importlib
        if current_device_name:
            module_name = f"device.{current_device_name.lower()}"
            showlog.verbose(f"Attempting to import module: '{module_name}'")
            dev_module = importlib.import_module(module_name)
            showlog.verbose(f"Successfully imported {module_name}")
            
            if hasattr(dev_module, "on_button_press"):
                showlog.verbose(f"Found on_button_press in {module_name}, calling with button {button_index}")
                handled = dev_module.on_button_press(button_index)
                showlog.verbose(f"{module_name}.on_button_press returned: {handled}")
                if handled:
                    showlog.verbose(f"Button {button_index} fully handled by {current_device_name}")
                    return  # device handled this button fully
                else:
                    showlog.verbose(f"Button {button_index} not handled by {current_device_name}, continuing to default logic")
            else:
                showlog.warn(f"No on_button_press defined for {current_device_name}")
        else:
            showlog.warn(f"current_device_name is None/empty, skipping device-specific handler")
    except Exception as e:
        showlog.error(f"Device hook error: {e}")
        import traceback
        showlog.error(f"Device hook traceback: {traceback.format_exc()}")

    showlog.verbose(f"Proceeding to default button logic for button {button_index}")

    try:
        # --- UI-LEVEL NAVIGATION BUTTONS -------------------------------------
        if button_index == 7:
            # Open Presets pageD
            msg_queue.put(("ui_mode", "presets"))
            msg_queue.put("[NAV] UI mode changed to PRESETS")
            return

        elif button_index == 9:
            # Open Text Input page
            msg_queue.put(("ui_mode", "text_input"))
            msg_queue.put("[NAV] UI mode changed to TEXT_INPUT")
            return
        # ---------------------------------------------------------------------

        # --- DEVICE SELECT NAVIGATION (button 10) ----------------------------
        if button_index == 10:
            msg_queue.put(("ui_mode", "device_select"))
            msg_queue.put("[NAV] UI mode changed to DEVICE_SELECT")
            return

        # --- SAVE CURRENT PAGE INIT STATE (button 6) -------------------------
        elif button_index == 6:
            global dials

            dev = devices.get(current_device_id)
            dev_name = dev["name"] if dev else "UnknownDevice"

            dial_values = [d.value for d in dials]
            device_states.store_init(dev_name, current_page_id, dial_values)
            msg_queue.put(f"[STATE] Stored INIT for {dev_name}:{current_page_id}")
            return

        # --- MUTE / UNMUTE CURRENT PAGE (button 8) ---------------------------
        elif button_index == 8:
            # Delegate Quadraverb page mute/unmute to device module
            if not current_page_id:
                msg_queue.put("[MUTE] No active page to mute/unmute")
                return
            
            dev = devices.get(current_device_id)
            dev_name = dev["name"] if dev else "Unknown"
            page_key = f"{int(current_page_id):02d}"

            if dev_name.strip().upper() == "QUADRAVERB":
                toggle_page_mute(page_key, dev_name, msg_queue)
            else:
                msg_queue.put(f"[MUTE] Not supported for {dev_name}")
            return
        # ---------------------------------------------------------------------

        # --- STANDARD PAGE SWITCHING (buttons 1–4 etc.) ----------------------
        showlog.debug(f"[DIALHANDLERS] Starting standard page switching logic for button {button_index}")
        
        dev = devices.get(current_device_id)
        showlog.debug(f"[DIALHANDLERS] devices.get('{current_device_id}') returned: {dev is not None}")
        if not dev:
            showlog.error(f"[DIALHANDLERS] No active device loaded (current_device_id='{current_device_id}')")
            msg_queue.put("[BUTTON] No active device loaded")
            return

        showlog.debug(f"[DIALHANDLERS] Device: {dev.get('name')}, available pages: {list(dev.get('pages', {}).keys())}")

        page_key = f"{int(button_index):02d}"
        showlog.debug(f"[DIALHANDLERS] Generated page_key: '{page_key}' from button_index: {button_index}")
        
        if page_key not in dev["pages"]:
            showlog.error(f"[DIALHANDLERS] Page {page_key} not found for {dev['name']}")
            msg_queue.put(f"[BUTTON] Page {page_key} not found for {dev['name']}")
            return
        
        showlog.debug(f"[DIALHANDLERS] Found page {page_key} in device")
        
        page_info = dev["pages"][page_key]
        page_type = page_info.get("type", "dials")
        showlog.debug(f"[DIALHANDLERS] Page info: {page_info}, page_type: '{page_type}'")

        # --- Mixer pages use a dedicated UI mode (handled by ui.py) ---
        if page_type == "mixer":
            showlog.debug(f"[DIALHANDLERS] Page type is mixer, switching to mixer UI mode")
            msg_queue.put(("ui_mode", "mixer"))
            msg_queue.put(f"[PAGE] Switched to {dev['name']} - {page_info.get('name', 'Mixer')}")
            showlog.log(None, f"Queued UI mode change to MIXER for {dev['name']}")
            return
        
        showlog.debug(f"[DIALHANDLERS] Page type is '{page_type}', proceeding with standard dial page switch")

        prev_page_id = current_page_id
        current_page_id = page_key
        showlog.debug(f"[DIALHANDLERS] Updated current_page_id from '{prev_page_id}' to '{current_page_id}'")
        _latch_manager.reset_all()

        # Update dial layout for new page
        showlog.debug(f"[DIALHANDLERS] Calling devices.update_from_device('{current_device_id}', '{current_page_id}', dials, 'Header')")
        header_text, button_info = devices.update_from_device(
            current_device_id, current_page_id, dials, "Header"
        )
        showlog.debug(f"[DIALHANDLERS] devices.update_from_device returned header_text: '{header_text}', button_info: {button_info}")

        page_name = dev["pages"][page_key]["name"]
        showlog.debug(f"[DIALHANDLERS] Page name: '{page_name}'")
        
        msg1 = f"[PAGE] Switched to {dev['name']} - {page_name}"
        msg2 = ("sysex_update", header_text, str(button_index))
        msg3 = ("select_button", str(button_index))
        
        showlog.debug(f"[DIALHANDLERS] Sending messages: '{msg1}', {msg2}, {msg3}")
        msg_queue.put(msg1)
        msg_queue.put(msg2)
        msg_queue.put(msg3)

        # Recall LIVE or INIT states
        page_vals = None
        if dev["name"] in live_states and current_page_id in live_states[dev["name"]]:
            page_vals = live_states[dev["name"]][current_page_id]
            msg_queue.put(f"[STATE] Recalling LIVE state for {dev['name']}:{current_page_id}")
        else:
            init_data = device_states.get_init(dev["name"], current_page_id)
            showlog.verbose(f"[DEBUG STATE] init_data={init_data}")

            # Extract proper values
            if isinstance(init_data, dict) and "init" in init_data:
                page_vals = init_data["init"]
            elif isinstance(init_data, list):
                page_vals = init_data
            else:
                page_vals = None

            if page_vals:
                msg_queue.put(f"[STATE] Recalling INIT for {dev['name']}:{current_page_id}")
            else:
                msg_queue.put(f"[STATE] No INIT values found for {dev['name']}:{current_page_id}")

            # 🔎 DIAGNOSTIC: show the source and full values we’re about to apply
            try:
                src = "LIVE" if (dev["name"] in live_states and current_page_id in live_states[dev["name"]]) else "INIT"
                showlog.debug(f"[RECALL {src}] {dev['name']}:{current_page_id} → {page_vals}")
            except Exception:
                pass
                # 🔎 Existing path set page_vals from LIVE or INIT above

        # ✅ NEW: merge in any persisted values from state_manager (replaces old dial_state)
        try:
            import system.state_manager as sm
            dev_name = dev["name"]
            ds_key = f"{dev_name}:{current_page_id}"
            # state_manager stores dicts {uid→entry} or nested {family→{cc→entry}}
            sm_state = sm.get_state(dev_name)


            # --- DEBUG PROBE: show what state_manager currently holds for this device/page
            try:
                showlog.debug(
                    None,
                    f"[STATE DEBUG] sm.get_state({dev_name}) → "
                    f"{list(sm_state.keys()) if isinstance(sm_state, dict) else type(sm_state).__name__}"
                )
                if isinstance(sm_state, dict) and current_page_id in sm_state:
                    showlog.debug(None, f"[STATE DEBUG] page {current_page_id} = {sm_state[current_page_id]}")
                else:
                    showlog.debug(None, f"[STATE DEBUG] no page entry for {current_page_id}")
            except Exception as _e:
                showlog.warn(f"[STATE DEBUG] probe failed: {_e}")


            ds_vals = []
            have_any = False

            for i in range(1, 9):
                val = None
                if isinstance(sm_state, dict):
                    # search by family/page + dial index (stringified)
                    page_state = sm_state.get(current_page_id)
                    if isinstance(page_state, dict):
                        # entry might be under 'value' or raw int
                        entry = page_state.get(str(i))
                        if isinstance(entry, dict):
                            val = entry.get("value")
                        elif isinstance(entry, (int, float)):
                            val = entry
                if val is not None:
                    ds_vals.append(int(val))
                    have_any = True
                else:
                    ds_vals.append(page_vals[i - 1] if i - 1 < len(page_vals) else 0)

            if have_any:
                page_vals = ds_vals
                showlog.debug(f"[RECALL OVERRIDE] Using state_manager for {ds_key}: {page_vals}")

        except Exception as _e:
            showlog.warn(f"[RECALL OVERRIDE] state_manager merge failed: {_e}")

        # Debug: log the final page_vals before using it
        showlog.debug(f"[BUTTON RECALL] Final page_vals for {dev['name']}:{current_page_id} = {page_vals} (type: {type(page_vals).__name__})")

        if page_vals:
            # Handle both dict format {'dials': [...], 'buttons': {}} and list format [...]
            if isinstance(page_vals, dict):
                dial_values = page_vals.get('dials', [])
                showlog.debug(f"[BUTTON RECALL] Extracted dial_values from dict: {dial_values}")
            else:
                dial_values = page_vals
            
            for dial_id, val in enumerate(dial_values, start=1):
                try:
                    # Debug log to trace data source
                    if not isinstance(val, (int, float)):
                        showlog.error(
                            f"[BUTTON] Invalid state value type for dial {dial_id}: "
                            f"type={type(val).__name__}, value={repr(val)}, "
                            f"page_vals={page_vals}, device={dev['name']}, page={current_page_id}"
                        )
                    
                    dials[dial_id - 1].set_value(val)
                    dials[dial_id - 1].display_text = f"{dials[dial_id - 1].label}: {val}"
                except (ValueError, IndexError) as e:
                    showlog.error(
                        f"[BUTTON] Failed to restore dial {dial_id}: {e}, "
                        f"val={repr(val)}, page_vals={page_vals}"
                    )
            
            # ✅ NEW (Phase 1): Set is_empty flag on each dial after state is loaded
            for dial in dials:
                dial.is_empty = (dial.label.upper() == "EMPTY")
            
        else:
            msg_queue.put(f"[STATE] No state found for {dev['name']}:{current_page_id}")

    except Exception as e:
        showlog.error(f"[DialHandler BUTTON error] {e}")



# -------------------------------------------------------
# INCOMING – from midiserver (CC updates)
# -------------------------------------------------------

def on_midi_cc(dial_id, value):
    """Called by midiserver when incoming CC arrives (1–8)."""
    if not msg_queue:
        return

    try:
        msg_queue.put(f"(MIDI IN) Dial {dial_id} → {value}")
        ui_val = None
        try:
            if dials and 1 <= dial_id <= len(dials):
                ui_val = getattr(dials[dial_id - 1], "value", None)
        except Exception as exc:
            showlog.debug(f"[LATCH] UI lookup failed for dial {dial_id}: {exc}")

        allow, reason = _latch_manager.evaluate(dial_id, value, ui_val)

        if not allow:
            if reason == "latched":
                showlog.debug(f"[LATCH] Dial {dial_id} latched: ui={ui_val} ctrl={value}")
                try:
                    msg_queue.put(f"[LATCH] Dial {dial_id} waiting for controller to reach {ui_val}")
                except Exception:
                    pass
            return

        if reason == "released":
            showlog.debug(f"[LATCH] Dial {dial_id} released at ctrl={value}")
            try:
                msg_queue.put(f"[LATCH] Dial {dial_id} released")
            except Exception:
                pass

        # --- Update logic identical to on_dial_change ---
        on_dial_change(dial_id, value, source="controller")

        # --- Ensure UI reflects it visually ---
        msg_queue.put(("update_dial_value", dial_id, value))

    except Exception as e:
        showlog.log(None, f"[DialHandler IN CC error] {e}")


# -------------------------------------------------------
# INCOMING – from midiserver (SysEx updates)
# -------------------------------------------------------

def on_midi_sysex(device, layer, dial_id, value, cc_num):
    """
    Called by midiserver when SysEx arrives.
    Handles:
      • New lightweight patch SysEx (F0 7D qq 00 00 pp 00 F7)
      • Normal Quadraverb parameter/page SysEx
      • Button-6 “Save INIT” trigger
    """
    try:
        # --- 1️⃣ Detect new lightweight patch SysEx ------------------------
        if layer == 0 and dial_id == 0 and cc_num == 0:
            showlog.debug(f"[DH] lightweight patch sysex dev={device} value={value}")
            from devices import DEVICE_DB
            from device_patches import _patch_cache as PATCH_DB

            dev_entry = DEVICE_DB.get(f"{device:02d}")
            dev_name = dev_entry["name"].strip().upper() if dev_entry else f"DEV{device:02d}"

            # --- normalize so it matches uppercase DB everywhere else ---
            dev_name = dev_name.strip().upper()



            showlog.debug(f"[ON_MIDI_SYSEX] device_selected {dev_name}")
            # --- NEW: notify UI of device switch before patch select ---
            try:
                import dialhandlers
                current = getattr(dialhandlers, "current_device_name", None)
                if str(current).upper() != str(dev_name).upper():
                    msg_queue.put(("device_selected", dev_name))
                    showlog.debug(f"[SYSEX] Queued device_selected for {dev_name}")
                else:
                    showlog.debug(f"[SYSEX] Ignored redundant device_selected for {dev_name}")
            except Exception as e:
                showlog.error(f"[SYSEX DEVICE_SELECT] {e}")



            # Patch numbers in patches.json are zero-padded strings
            patch_key = f"{value:02d}"
            patch_name = None

            if dev_name in PATCH_DB:
                patch_name = PATCH_DB[dev_name].get(patch_key)

            # Build display text (e.g. "09.Piano")
            display_text = (
                f"{patch_key}.{patch_name}"
                if patch_name else f"{patch_key}"
            )

            # Log and forward to UI (matches the old TCP format)
            showlog.debug(f"Patch select → {dev_name} {display_text}")
            msg_queue.put(f"[PATCH_SELECT] {dev_name}|{display_text}")

            # Also update LED + LCD locally
            from network import send_led_line
            send_led_line(f"DEV1 TXT:{dev_name}")
            send_led_line(f"DEV2 TXT:{display_text}")
            return

        # --- 2️⃣ Special control: Button 6 triggers SAVE -------------------
        if dial_id == 6 and value >= 100:
            showlog.debug("[SysEx] Save INIT triggered from external controller")
            on_button_press(6)
            return

        # --- 3️⃣ Normal Quadraverb page/parameter SysEx --------------------
        header_text, page_button = devices.update_from_device(
            device, layer, dials, "Header"
        )

        msg_queue.put(("sysex_update", header_text, page_button))
        msg_queue.put(f"(SysEx) Dev{device} Layer{layer} Dial{dial_id} = {value}")

    except Exception as e:
        showlog.error(f"- on_midi_sysex {e}")


# -------------------------------------------------------
# INCOMING – MIDI note events
# -------------------------------------------------------

def on_midi_note(note: int, velocity: int, channel: int = None):
    """Handle incoming MIDI Note On/Off messages."""
    try:
        if msg_queue:
            msg_queue.put(f"(MIDI NOTE) {channel}: {note} → {velocity}")
    except Exception:
        pass

    try:
        from pages import module_base
        return module_base.handle_midi_note(note, velocity, channel)
    except Exception as exc:
        showlog.error(f"[DIALHANDLERS] on_midi_note error: {exc}")
        return False


# -------------------------------------------------------
# Preset / Init helpers
# -------------------------------------------------------

def store_init_state():
    """Store the current dial states and button states for the active device/page."""
    try:
        dev = devices.get(current_device_id)
        dev_name = dev["name"]
        values = live_states.get(dev_name, {}).get(current_page_id, [0]*8)
        buttons = live_button_states.get(current_page_id, {})
        device_states.store_init(dev_name, current_page_id, values, button_states=buttons)
        msg_queue.put(f"[STATE] Stored INIT for {dev_name}:{current_page_id} (dials + buttons)")
    except Exception as e:
        showlog.error(f"[DialHandler store_init error] {e}")


def recall_init_state():
    """Recall the init state and resend values to hardware."""
    try:
        dev = devices.get(current_device_id)
        dev_name = dev["name"]
        init_vals = device_states.get_init(dev_name, current_page_id)
        if not init_vals:
            msg_queue.put(f"[STATE] No INIT state found for {dev_name}:{current_page_id}")
            return

        for dial_id, val in enumerate(init_vals, start=1):
            on_dial_change(dial_id, val)

        msg_queue.put(f"[STATE] Recalled INIT for {dev_name}:{current_page_id}")

    except Exception as e:
        showlog.error(f"[DialHandler recall_init error] {e}")


def update_button_state(page_id, var_name, value):
    """
    Track a button state variable for a module page.
    Called by module pages when button state changes (e.g., is_on toggle).
    
    Args:
        page_id: Page identifier (e.g., 'vibrato')
        var_name: Variable name (e.g., 'is_on')
        value: Current value (typically bool or int)
    """
    global live_button_states
    if page_id not in live_button_states:
        live_button_states[page_id] = {}
    live_button_states[page_id][var_name] = value
    showlog.debug(f"[BUTTON_STATE] {page_id}.{var_name} = {value}")


def get_button_states(page_id):
    """
    Get the stored button states for a page.
    Returns dict of {var_name: value} or empty dict if none stored.
    """
    return live_button_states.get(page_id, {})



