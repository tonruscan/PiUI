# /plugins/YOUR_MODULE_plugin.py
# TEMPLATE: Replace YOUR_MODULE with your actual module name
# Replace YOUR_DEVICE with your device name

import showlog
from system.module_core import ModuleBase
# Uncomment if you have a hardware driver:
# from drivers import your_driver as driver
from core.plugin import Plugin as PluginBase

class YourModule(ModuleBase):
    """Your device controller module."""
    
    # REQUIRED: Unique identifier for this module
    MODULE_ID = "your_module"
    page_id = "your_module_main"
    page_label = "Your Device Name"
    
    # OPTIONAL: Registry for CC mappings (can be empty)
    REGISTRY = {}
    
    # REQUIRED: Button definitions (standard 10-button layout)
    BUTTONS = [
        # Left column (1-5)
        {"id": "1", "label": "BTN1", "behavior": "state"},        # Toggle button
        {"id": "2", "label": "BTN2", "behavior": "transient"},    # Momentary button
        {"id": "3", "label": "BTN3", "behavior": "transient"},    # Custom
        {"id": "4", "label": "BTN4", "behavior": "transient"},    # Custom
        {"id": "5", "label": "BYP", "behavior": "transient", "action": "bypass_toggle"},
        
        # Right column (6-10) - Standard navigation
        {"id": "6", "label": "ST", "behavior": "nav", "action": "store_preset"},
        {"id": "7", "label": "P", "behavior": "nav", "action": "presets"},
        {"id": "8", "label": "M", "behavior": "transient", "action": "mute_toggle"},
        {"id": "9", "label": "S", "behavior": "nav", "action": "save_preset"},
        {"id": "10", "label": "X", "behavior": "nav", "action": "device_select"},
    ]
    
    # REQUIRED: Dial slot mapping (which dials to show in 2x4 grid)
    # Keys are dial IDs (1-8), values are control names that must match custom_dials.json
    SLOT_TO_CTRL = {
        1: "control_1",     # Top-left
        2: "control_2",     # Top-second
        # Add more dials as needed (up to 8 total)
    }

    def __init__(self):
        """Initialize module. IMPORTANT: No parameters allowed!"""
        super().__init__()
        
        # ---- Initialize your state ----
        self.button_states = {}
        self.dial_values = [64, 64]  # Default centered values for each dial
        
        # ---- Get MIDI service ----
        try:
            from system import service_registry
            midi_service = service_registry.get("midi")
            if midi_service and hasattr(midi_service, "send_message"):
                self._send_fn = midi_service.send_message
            else:
                self._send_fn = lambda b: showlog.warn(f"[YOUR_MODULE] No MIDI sender: {b}")
        except Exception as e:
            showlog.warn(f"[YOUR_MODULE] Could not get MIDI service: {e}")
            self._send_fn = lambda b: showlog.warn(f"[YOUR_MODULE] No MIDI sender: {b}")
        
        showlog.info("[YOUR_MODULE] Module initialized")
        
        # ---- Send initial state to hardware (optional) ----
        # self._apply_initial_state()

    def on_button(self, btn_id: str):
        """
        Handle button press.
        
        Args:
            btn_id: Button ID as string ("1"-"10")
        """
        showlog.info(f"[YOUR_MODULE] Button {btn_id} pressed")
        
        # Example: Toggle button 1
        if btn_id == "1":
            current = self.button_states.get("1", False)
            self.button_states["1"] = not current
            self._apply_button_1_state()
        
        # Example: Momentary button 2
        elif btn_id == "2":
            self._trigger_function_2()

    def on_dial_change(self, dial_index: int, value: int):
        """
        Handle dial changes.
        
        Args:
            dial_index: Dial index (0-7 for dials 1-8)
            value: New value (0-127)
        """
        showlog.debug(f"[YOUR_MODULE] Dial {dial_index} changed to {value}")
        
        # Store the value
        if dial_index < len(self.dial_values):
            self.dial_values[dial_index] = value
        
        # Send to hardware
        if dial_index == 0:
            self._apply_control_1(value)
        elif dial_index == 1:
            self._apply_control_2(value)

    # ---- Your hardware control methods ----
    
    def _apply_button_1_state(self):
        """Apply button 1 state to hardware."""
        is_on = self.button_states.get("1", False)
        # Example: Send MIDI or SysEx
        # driver.set_function_1(self._send_fn, 1 if is_on else 0)
        showlog.debug(f"[YOUR_MODULE] Applied button 1 state: {is_on}")
    
    def _trigger_function_2(self):
        """Trigger function 2 (momentary action)."""
        # Example: Send MIDI note or CC
        showlog.debug("[YOUR_MODULE] Triggered function 2")
    
    def _apply_control_1(self, value: int):
        """Send control 1 value to hardware."""
        # Example: Send MIDI CC or SysEx
        # driver.set_control_1(self._send_fn, int(max(0, min(127, value))))
        showlog.debug(f"[YOUR_MODULE] Set control 1 to {value}")
    
    def _apply_control_2(self, value: int):
        """Send control 2 value to hardware."""
        # Example: Send MIDI CC or SysEx
        # driver.set_control_2(self._send_fn, int(max(0, min(127, value))))
        showlog.debug(f"[YOUR_MODULE] Set control 2 to {value}")

    # ---- Preset save/load hooks (OPTIONAL but recommended) ----
    
    def export_state(self):
        """
        Export current state for preset saving.
        
        Returns:
            dict: State dictionary to be saved
        """
        return {
            "buttons": self.button_states.copy(),
            "dials": self.dial_values[:],
            # Add any other state you want to save
        }

    def import_state(self, state: dict):
        """
        Restore state from preset.
        
        Args:
            state: State dictionary loaded from preset
        """
        if not state:
            return
        
        # Restore button states
        btns = state.get("buttons", {})
        if isinstance(btns, dict):
            self.button_states = btns.copy()
            # Apply button states to hardware
            for btn_id in self.button_states:
                if btn_id == "1":
                    self._apply_button_1_state()
        
        # Restore dial values
        dials = state.get("dials", None)
        if isinstance(dials, list):
            self.dial_values = list(dials)
            # Apply dial values to hardware
            for i, val in enumerate(self.dial_values):
                if i == 0:
                    self._apply_control_1(val)
                elif i == 1:
                    self._apply_control_2(val)


# ------- Plugin Registration -------
class YourPlugin(PluginBase):
    """Your plugin registration class."""
    
    name = "Your Device Name"
    version = "0.1.0"
    category = "synth"  # Options: synth, effect, controller, utility
    author = "System"
    description = "Brief description of your device"
    icon = "your_icon.png"
    page_id = "your_module_main"  # Must match YourModule.page_id
    
    def on_load(self, app):
        """Register page with module_base renderer."""
        try:
            from pages import module_base as page
            
            # Rendering metadata for the system
            rendering_meta = {
                "fps_mode": "high",              # high=100fps, low=60fps
                "supports_dirty_rect": True,     # Dirty rect optimization
                "burst_multiplier": 1.0,         # Animation burst behavior
            }
            
            app.page_registry.register(
                self.page_id,
                page,
                label=self.name,
                meta={"rendering": rendering_meta}
            )
            showlog.info(f"[YourPlugin] Registered page '{self.page_id}'")
        except Exception as e:
            import traceback
            showlog.error(f"[YourPlugin] Failed to register page: {e}")
            showlog.error(traceback.format_exc())


# ------- Legacy exports for module_base compatibility -------
# These MUST be defined at module level for module_base to work
MODULE_ID = YourModule.MODULE_ID
REGISTRY = YourModule.REGISTRY
BUTTONS = YourModule.BUTTONS
SLOT_TO_CTRL = YourModule.SLOT_TO_CTRL

# Export the Plugin class for auto-discovery
Plugin = YourPlugin


# ------- CHECKLIST -------
# After copying this template:
# 
# 1. Replace all instances of:
#    - YOUR_MODULE → your actual module name (uppercase)
#    - your_module → your actual module name (lowercase)
#    - Your Device Name → your actual device name
# 
# 2. Add control definitions to config/custom_dials.json:
#    {
#      "control_1": {
#        "label": "Control 1",
#        "range": [0, 127],
#        "type": "raw",
#        "page": 0
#      },
#      "control_2": { ... }
#    }
# 
# 3. Add button to config/device_page_layout.json:
#    {
#      "id": 6,
#      "img": "icons/your_icon.png",
#      "label": "Your Device",
#      "plugin": "your_module_main"
#    }
# 
# 4. Add mode manager setup in managers/mode_manager.py:
#    - Add elif case in switch_mode()
#    - Add to navigator record list
#    - Add _setup_your_module() function
# 
# 5. Add to renderer in rendering/renderer.py:
#    - Add to page list (line ~89)
#    - Add to themed_pages (line ~118)
# 
# 6. (Optional) Create hardware driver in drivers/your_device.py
# 
# See docs/PLUGIN_CREATION_GUIDE.md for detailed instructions!
