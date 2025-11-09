# /plugins/vk8m_plugin.py
# Roland VK-8M organ controller plugin using module_base architecture

import showlog
from system.module_core import ModuleBase
from drivers import vk8m as vk
from core.plugin import Plugin as PluginBase

# Import animation API for drawbar animations
try:
    from plugins.ascii_animator_plugin import (
        get_drawbar_animations,
        load_drawbar_animation,
        get_animation_metadata
    )
    ANIMATOR_READY = True
    showlog.info("[VK8M] Animation API loaded - drawbar animations enabled")
except Exception as e:
    ANIMATOR_READY = False
    showlog.warn(f"[VK8M] Animation API not available: {e}")


class VK8M(ModuleBase):
    """Roland VK-8M organ controller module."""

    MODULE_ID = "vk8m"  # Legacy name (kept for compatibility)
    PLUGIN_ID = "vk8m"  # Modern unified terminology
    STANDALONE = True  # This module has its own identity, doesn't inherit parent device theme
    page_id = "vk8m_main"
    page_label = "VK-8M (Main)"
    
    # VK8M Theme (organ-inspired warm colors)
    THEME = {
        # --- Header bar ---
        "header_bg_color": "#FF0000",
        "header_text_color": "#FFEB9A",
        
        # --- Normal dial state ---
        "dial_panel_color": "#FF0000",
        "dial_fill_color": "#FF6B35",
        "dial_outline_color": "#FFB088",
        "dial_text_color": "#FFEB9A",
        "dial_pointer_color": "#FFEB9A",
        
        # --- Mute dial state (used by custom widgets) ---
        "dial_mute_panel": "#1A0A05",
        "dial_mute_fill": "#4A2010",
        "dial_mute_outline": "#6A3020",
        "dial_mute_text": "#8A6050",
        
        # --- Buttons ---
        "button_fill": "#FF6B35",
        "button_outline": "#FFB088",
        "button_text": "#FFFFFF",
        "button_active_fill": "#FF8855",
        "button_active_text": "#FFFFFF",
        
        # --- Preset Page Colors (using same warm theme) ---
        "preset_button_color": "#FF0000",          # dark warm background (like mute_panel)
        "preset_text_color": "#FFEB9A",            # warm yellow text (like header text)
        "preset_label_highlight": "#FFB088",       # warm orange highlight (like button fill)
        "preset_font_highlight": "#4A2010",        # white text when selected
        "scroll_bar_color": "#FF0000",             # warm orange scrollbar (like outline)
        
        # --- Animation Preset Colors (keep distinct) ---
        "preset_animation_button": "#140606",      # dark warm background
        "preset_animation_text": "#FFB088",        # warm orange text
        "preset_animation_highlight": "#FF6B35",   # bright orange highlight
    }
    
    # Initial state: multi-state buttons default to first entry; dials centered
    INIT_STATE = {
        "buttons": {
            "1": 0,  # Vibrato mode index (OFF)
            "2": 0,  # Reverb type index (R1)
            "3": 0,  # Distortion type index (D1)
            "4": 0,  # Perc harmonic (off)
            "5": 0,  # Rotary mode (fast by default)
            "8": 0,  # Tonewheel (Vintage1)
        },
        # Dial order follows SLOT_TO_CTRL below
        # Slot 1: Distortion, Slot 2: Drawbar speed, Slot 5: Reverb
        "dials": [64, 64, 0, 0, 64, 0, 0, 0],   # Distortion (64), Speed (64=center), Reverb (64)
        # Widget-specific init state (drawbar positions)
        "widget": {
            "drawbars": [8, 7, 6, 5, 4, 3, 2, 1, 0]  # Descending pattern left to right
        }
    }

    # Registry for dial-to-variable mapping (like Vibrato)
    REGISTRY = {
        "vk8m": {
            "type": "module",
            "01": {
                "label": "Distortion",
                "range": [0, 127],
                "type": "raw",
                "default_slot": 1,
                "family": "vk8m",
                "variable": "distortion_value",
            },
            "05": {
                "label": "Reverb",
                "range": [0, 127],
                "type": "raw",
                "default_slot": 5,
                "family": "vk8m",
                "variable": "reverb_value",
            },
        }
    }




    # Custom widget configuration for drawbar
    CUSTOM_WIDGET = {
        "class": "DrawBarWidget",
        "path": "widgets.drawbar_widget",
        "grid_size": [3, 2],  # 3 cells wide, 2 cells tall
        "grid_pos": [0, 1],   # Position: row 0, col 1
    }

    # Grid layout for dials (rows, cols)
    GRID_LAYOUT = {
        "rows": 2,
        "cols": 4
    }

    # Button definitions for module_base (left column standard 10-button layout)
    # IMPORTANT: state labels become method names via .lower(), so keep them Python-safe.
    BUTTONS = [
        {
            "id": "1",
            "behavior": "multi",  # Multi-state: Vibrato/Chorus
            "states": ["OFF", "V1", "V2", "V3", "C1", "C2", "C3"]
        },
        {
            "id": "2",
            "behavior": "multi",
            "states": ["R1", "R2", "R3", "R4"]  # Reverb types (0-3)
        },
        {
            "id": "3",
            "behavior": "multi",
            "states": ["D1", "D2", "D3", "D4"]  # Distortion types (0-3)
        },
        {
            # Percussion harmonic select (None / 2nd / 3rd)
            "id": "4",
            "behavior": "multi",
            "states": ["OFF", "2ND", "3RD"],
            "label": "Perc"
        },
        {
            # Rotary speed / brake
            "id": "5",
            "behavior": "multi",
            "states": ["FST", "SLW", "BRK"],
            "label": "Rotary"
        },
        {
            # Drawbar animation on/off toggle
            "id": "6",
            "behavior": "multi",
            "states": ["OFF", "ON"],
            "label": "Anim"
        },
        {"id": "7", "label": "P", "behavior": "nav", "action": "presets"},
        {
            # Tonewheel type
            "id": "8",
            "behavior": "multi",
            "states": ["V1", "V2", "CLN"],
            "label": "TW"
        },
        {"id": "9", "label": "S", "behavior": "nav", "action": "save_preset"},
        {"id": "10", "label": "10", "behavior": "nav", "action": "device_select"},
    ]

    # Map dial slots (grid) to control names UI may display
    # Your pages/module_base typically renders these as labeled dials.
    # Slot 1 = col 0, row 0; Slot 5 = col 0, row 1 (like in the image)
    SLOT_TO_CTRL = {
        1: "distortion",
        2: "drawbar_speed",  # Speed dial for animation control
        5: "reverb_level",
    }

    def __init__(self):
        super().__init__()
        
        showlog.info(f"*[VK8M] __init__ called - creating new instance")

        # ---- STATE ----
        init = self.INIT_STATE
        
        # Initialize dial instance variables (linked to REGISTRY)
        self.distortion_value = 64
        self.reverb_value = 64
        
        # Initialize from INIT_STATE dials array [slot1, slot2, ..., slot8]
        dial_init = list(init.get("dials", [64, 0, 0, 0, 64, 0, 0, 0]))
        if len(dial_init) > 0:
            self.distortion_value = dial_init[0]  # slot 1
        if len(dial_init) > 4:
            self.reverb_value = dial_init[4]  # slot 5
        
        # Initialize button states from INIT_STATE
        buttons_init = init.get("buttons", {})
        self.button_states = buttons_init.copy() if buttons_init else {
            "1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "8": 0
        }
        
        showlog.info(f"[VK8M] Initial button_states: {self.button_states}")
        showlog.info(f"[VK8M] Initial distortion_value: {self.distortion_value}")
        showlog.info(f"[VK8M] Initial reverb_value: {self.reverb_value}")

        showlog.info("[VK8M] Module initialized")

        # Push initial dial values to device
        self._apply_distortion(self.distortion_value)
        self._apply_reverb(self.reverb_value)
        
        # Apply initial button states to device
        self._apply_all_button_states()

        # -------- Multi-state handlers (names must match states.lower()) --------
        # Note: Some state names conflict (e.g., "off", "v1", "v2" used by multiple buttons)
        # So we use on_button() fallback for those cases
        
        # Button 1: Vibrato modes - use on_button fallback
        # Button 2: Reverb types
        self.r1 = lambda: self._set_reverb_type(0)
        self.r2 = lambda: self._set_reverb_type(1)
        self.r3 = lambda: self._set_reverb_type(2)
        self.r4 = lambda: self._set_reverb_type(3)

        # Button 3: Distortion types
        self.d1 = lambda: self._set_distortion_type(0)
        self.d2 = lambda: self._set_distortion_type(1)
        self.d3 = lambda: self._set_distortion_type(2)
        self.d4 = lambda: self._set_distortion_type(3)

        # Button 4: Percussion - use on_button fallback (conflicts with button 1 "off")
        # Button 5: Rotary
        self.fst = lambda: self._set_rotary(0)
        self.slw = lambda: self._set_rotary(1)
        self.brk = lambda: self._set_rotary(2)

        # Button 8: Tonewheel - use on_button fallback (conflicts with button 1 "v1", "v2")
    
    # -------- State change helpers (update button_states AND send to device) --------
    def _set_vibrato(self, on_off: int, vib_type: int = 0):
        """Set vibrato on/off and type. Updates button_states."""
        self.button_states["1"] = 0 if on_off == 0 else (vib_type + 1)
        showlog.info(f"[VK8M] _set_vibrato: on_off={on_off}, type={vib_type}, button_states[1]={self.button_states['1']}")
        vk.set_vibrato_on(on_off)
        if on_off == 1:
            vk.set_vibrato_type(vib_type)
    
    def _set_reverb_type(self, rev_type: int):
        """Set reverb type. Updates button_states."""
        self.button_states["2"] = rev_type
        showlog.info(f"[VK8M] _set_reverb_type: type={rev_type}, button_states[2]={self.button_states['2']}")
        vk.set_reverb_type(rev_type)
    
    def _set_distortion_type(self, dist_type: int):
        """Set distortion type. Updates button_states."""
        self.button_states["3"] = dist_type
        showlog.info(f"[VK8M] _set_distortion_type: type={dist_type}, button_states[3]={self.button_states['3']}")
        vk.set_distortion_type(dist_type)
    
    def _set_percussion(self, perc_idx: int):
        """Set percussion harmonic. Updates button_states."""
        self.button_states["4"] = perc_idx
        showlog.info(f"[VK8M] _set_percussion: idx={perc_idx}, button_states[4]={self.button_states['4']}")
        vk.set_percussion_2nd_3rd(perc_idx)
    
    def _set_rotary(self, rot_idx: int):
        """Set rotary mode. Updates button_states."""
        self.button_states["5"] = rot_idx
        showlog.info(f"[VK8M] _set_rotary: idx={rot_idx}, button_states[5]={self.button_states['5']}")
        if rot_idx == 0:  # Fast
            vk.set_rotary_brake(0)
            vk.set_rotary_speed(1)
        elif rot_idx == 1:  # Slow
            vk.set_rotary_brake(0)
            vk.set_rotary_speed(0)
        else:  # Brake
            vk.set_rotary_brake(1)
    
    def _set_tonewheel(self, tw_idx: int):
        """Set tonewheel type. Updates button_states."""
        self.button_states["8"] = tw_idx
        showlog.info(f"[VK8M] _set_tonewheel: idx={tw_idx}, button_states[8]={self.button_states['8']}")
        vk.set_tonewheel_type(tw_idx)

    # -------- Fallback button handler (for non-multi-state buttons) --------
    def on_button(self, btn_id: str, state_index: int = 0, state_data: dict = None):
        """Handle button press for buttons without specific state methods.
        
        This handles buttons 1, 4, and 8 which have conflicting state names.
        """
        showlog.debug(f"[VK8M] on_button called: id={btn_id}, index={state_index}, data={state_data}")
        
        btn_id = str(btn_id)
        
        # Button 1: Vibrato/Chorus
        if btn_id == "1":
            if state_index == 0:
                showlog.info(f"[VK8M] Button 1: Setting vibrato OFF")
                self._set_vibrato(0)  # OFF
            elif 1 <= state_index <= 6:
                showlog.info(f"[VK8M] Button 1: Setting vibrato type {state_index - 1}")
                self._set_vibrato(1, state_index - 1)  # V1-V3, C1-C3
        
        # Button 4: Percussion harmonic
        elif btn_id == "4":
            showlog.info(f"[VK8M] Button 4: Setting percussion to {state_index}")
            self._set_percussion(state_index)  # 0=OFF, 1=2ND, 2=3RD
        
        # Button 8: Tonewheel
        elif btn_id == "8":
            showlog.info(f"[VK8M] Button 8: Setting tonewheel to {state_index}")
            self._set_tonewheel(state_index)  # 0=V1, 1=V2, 2=CLN
        
        # Button 6: Toggle drawbar animation on/off (multi-state with OFF/ON)
        elif btn_id == "6":
            # state_index: 0=OFF, 1=ON
            is_on = (state_index == 1)
            showlog.info(f"[VK8M] Button 6: Animation toggle - state_index={state_index} ({'ON' if is_on else 'OFF'})")
            self._toggle_drawbar_animation(is_on)
        
        else:
            showlog.info(f"[VK8M] Button {btn_id} pressed - no handler implemented")

    # -------- Dials (main grid) --------
    def on_dial_change(self, dial_label: str, value: int):
        """Handle dial changes - updates instance variables linked to REGISTRY."""
        showlog.info(f"[VK8M] on_dial_change: label='{dial_label}', value={value}")
        if dial_label.lower() in ("distortion", "dist"):
            self.distortion_value = value
            self._apply_distortion(value)
        elif dial_label.lower() in ("reverb", "reverb_level", "rev"):
            self.reverb_value = value
            self._apply_reverb(value)
        elif dial_label.lower() in ("speed", "drawbar_speed"):
            # Value already scaled to 10-200 by module_base's range mapping
            self._update_drawbar_speed(value)
        else:
            showlog.warn(f"[VK8M] Unknown dial label: '{dial_label}'")

    def _apply_distortion(self, val: int):
        """Send distortion level to VK-8M."""
        vk.set_distortion(int(max(0, min(127, val))))

    def _apply_reverb(self, val: int):
        """Send reverb level to VK-8M."""
        vk.set_reverb_level(int(max(0, min(127, val))))

    def _apply_leakage(self, val: int):
        """Send leakage level to VK-8M."""
        vk.set_leakage(int(max(0, min(127, val))))
    
    def _update_drawbar_speed(self, val: int):
        """Update drawbar animation speed from external dial (value already scaled to 10-200ms by module_base)."""
        try:
            from pages import module_base
            widget = module_base._CUSTOM_WIDGET_INSTANCE
            if widget and hasattr(widget, 'preset_frame_ms'):
                # Invert the value: 10→200ms (slow), 200→10ms (fast)
                inverted_val = 210.0 - float(val)  # 210-10=200, 210-200=10
                widget.preset_frame_ms = inverted_val
                
                # Also update the speed dial's visual if it exists
                if hasattr(widget, 'speed_dial') and widget.speed_dial:
                    # Map the inverted value back to 0-127 for the dial display
                    # 200ms → 0, 10ms → 127
                    t = (inverted_val - 200.0) / (10.0 - 200.0)
                    dial_value = int(t * 127)
                    widget.speed_dial.set_value(dial_value)
                
                widget.mark_dirty()
                showlog.debug(f"[VK8M] Updated drawbar speed to {inverted_val}ms per frame (from external {val})")
            else:
                showlog.warn(f"[VK8M] No drawbar widget found")
        except Exception as e:
            showlog.error(f"[VK8M] Failed to update drawbar speed: {e}")
    
    def _toggle_drawbar_animation(self, enable: bool):
        """
        Toggle drawbar animation on/off.
        
        Args:
            enable: True to start animation, False to stop and restore live state
        """
        showlog.debug(f"[VK8M] _toggle_drawbar_animation() called with enable={enable}")
        try:
            from pages import module_base
            widget = module_base._CUSTOM_WIDGET_INSTANCE
            
            if not widget:
                showlog.warn("[VK8M] No drawbar widget found")
                return
            
            if enable:
                # Turn animation ON
                if not widget.animation_enabled:
                    # Check if widget has any animation loaded
                    has_animation = hasattr(widget, 'preset_frames') and widget.preset_frames
                    
                    if not has_animation:
                        # No animation loaded yet - load default init.drawbar.json
                        showlog.info("[VK8M] No animation loaded, loading default init.drawbar.json")
                        self.load_animation_preset("init.drawbar.json")
                        # load_animation_preset() already starts the animation and updates button state
                    else:
                        # Animation already loaded, just start it
                        widget.start_animation()
                        showlog.info("[VK8M] Animation started")
                else:
                    showlog.debug("[VK8M] Animation already running")
            else:
                # Turn animation OFF - restore live state
                if widget.animation_enabled:
                    widget.stop_animation()
                    showlog.info("[VK8M] Animation stopped, restored live state")
                else:
                    showlog.debug("[VK8M] Animation already stopped")
                    
        except Exception as e:
            showlog.error(f"[VK8M] Failed to toggle animation: {e}")
            import traceback
            showlog.error(f"[VK8M] Traceback: {traceback.format_exc()}")
    
    def load_animation_preset(self, filename: str):
        """
        Load a drawbar animation from ASCII animator preset.
        
        Args:
            filename: Name of the .drawbar.json file (e.g., "wave.drawbar.json")
        """
        showlog.debug(f"*[VK8M LOAD 1] load_animation_preset called with filename: '{filename}'")
        
        if not ANIMATOR_READY:
            showlog.warn("*[VK8M LOAD 2] Animation API not available")
            return
        
        try:
            showlog.info(f"[VK8M] Loading animation preset: {filename}")
            showlog.debug("*[VK8M LOAD 3] Calling load_drawbar_animation()")
            
            # Load frames from animation preset
            frames = load_drawbar_animation(filename)
            showlog.debug(f"*[VK8M LOAD 4] load_drawbar_animation() returned: {frames is not None}")
            
            if not frames:
                showlog.error(f"*[VK8M LOAD 5] Failed to load animation: {filename}")
                return
            
            showlog.debug(f"*[VK8M LOAD 6] Got {len(frames)} frames")
            if len(frames) > 0:
                showlog.debug(f"*[VK8M LOAD 7] First frame: {frames[0]}")
            
            # Get the drawbar widget
            showlog.debug("*[VK8M LOAD 8] Getting drawbar widget from module_base")
            from pages import module_base
            widget = module_base._CUSTOM_WIDGET_INSTANCE
            showlog.debug(f"*[VK8M LOAD 9] widget type: {type(widget)}")
            showlog.debug(f"*[VK8M LOAD 10] widget is None: {widget is None}")
            
            if not widget:
                showlog.error("*[VK8M LOAD 11] No drawbar widget found")
                return
            
            showlog.debug(f"*[VK8M LOAD 12] Widget has load_animation: {hasattr(widget, 'load_animation')}")
            
            # Load animation into widget
            if hasattr(widget, 'load_animation'):
                showlog.debug("*[VK8M LOAD 13] Calling widget.load_animation()")
                widget.load_animation(frames)
                showlog.info(f"[VK8M] Loaded {len(frames)} animation frames")
                showlog.debug("*[VK8M LOAD 14] Animation loaded into widget")
                
                # Start animation automatically
                showlog.debug(f"*[VK8M LOAD 15] Widget has start_animation: {hasattr(widget, 'start_animation')}")
                if hasattr(widget, 'start_animation'):
                    showlog.debug("*[VK8M LOAD 16] Calling widget.start_animation()")
                    widget.start_animation()
                    showlog.info("[VK8M] Animation started")
                    showlog.debug("*[VK8M LOAD 17] Animation started successfully")
                    
                    # Update button 6 state to ON (state_index=1) to match animation state
                    self.button_states["6"] = 1
                    showlog.debug("[VK8M] Button 6 state updated to ON (1)")
                    # Immediately sync UI so the toggle reflects the active animation
                    self._sync_button_states_to_ui()
            else:
                showlog.error("*[VK8M LOAD 18] Drawbar widget doesn't support animations")
        
        except Exception as e:
            showlog.error(f"*[VK8M LOAD 19] Failed to load animation preset: {e}")
            import traceback
            showlog.error(f"*[VK8M LOAD 20] Traceback: {traceback.format_exc()}")
    
    def _apply_all_button_states(self):
        """Apply all button states to the device (called on init and preset load)."""
        showlog.info(f"[VK8M] _apply_all_button_states: button_states={self.button_states}")
        
        # Button 1: Vibrato/Chorus
        vib_idx = self.button_states.get("1", 0)
        if vib_idx == 0:
            vk.set_vibrato_on(0)
        else:
            vk.set_vibrato_on(1)
            vk.set_vibrato_type(vib_idx - 1)  # 1-6 maps to types 0-5
        
        # Button 2: Reverb type
        rev_idx = self.button_states.get("2", 0)
        vk.set_reverb_type(rev_idx)
        
        # Button 3: Distortion type
        dist_idx = self.button_states.get("3", 0)
        vk.set_distortion_type(dist_idx)
        
        # Button 4: Percussion harmonic
        perc_idx = self.button_states.get("4", 0)
        vk.set_percussion_2nd_3rd(perc_idx)
        
        # Button 5: Rotary
        rot_idx = self.button_states.get("5", 0)
        if rot_idx == 0:  # Fast
            vk.set_rotary_brake(0)
            vk.set_rotary_speed(1)
        elif rot_idx == 1:  # Slow
            vk.set_rotary_brake(0)
            vk.set_rotary_speed(0)
        else:  # Brake
            vk.set_rotary_brake(1)
        
        # Button 8: Tonewheel type
        tw_idx = self.button_states.get("8", 0)
        vk.set_tonewheel_type(tw_idx)
        
        showlog.info(f"[VK8M] _apply_all_button_states complete")
    
    def on_preset_loaded(self, variables: dict, widget_state: dict = None):
        """Called by preset_manager after a preset is loaded.
        
        The preset system already restored distortion_value, reverb_value, and button_states.
        Just apply them to the hardware.
        """
        showlog.info(f"*[VK8M] on_preset_loaded called")
        showlog.info(f"*[VK8M] distortion_value={self.distortion_value}")
        showlog.info(f"*[VK8M] reverb_value={self.reverb_value}")
        showlog.info(f"*[VK8M] button_states={self.button_states}")
        showlog.info(f"*[VK8M] widget_state={widget_state}")
        
        # Sync button states to UI (_BUTTON_STATES)
        self._sync_button_states_to_ui()
        
        # Apply state to hardware
        self._apply_all_button_states()
        self._apply_distortion(self.distortion_value)
        self._apply_reverb(self.reverb_value)
        
        # Apply drawbar state to hardware
        if widget_state and "bar_values" in widget_state:
            bar_values = widget_state["bar_values"]
            showlog.info(f"*[VK8M] Applying drawbar values: {bar_values}")
            for i, value in enumerate(bar_values):
                vk.set_drawbar(i + 1, int(value))  # drawbar index is 1-based
        
        showlog.info(f"[VK8M] on_preset_loaded complete")
    
    def _sync_button_states_to_ui(self):
        """Sync module's button_states to module_base's _BUTTON_STATES for UI rendering."""
        try:
            from pages import module_base
            for btn_id, state_idx in self.button_states.items():
                module_base._BUTTON_STATES[btn_id] = state_idx
            showlog.info(f"[VK8M] Synced _BUTTON_STATES: {module_base._BUTTON_STATES}")
        except Exception as e:
            showlog.error(f"[VK8M] Failed to sync button states: {e}")


class VK8MPlugin(PluginBase):
    
    def _sync_button_states_to_ui(self):
        """Sync module's button_states to module_base's _BUTTON_STATES for UI rendering."""
        try:
            from pages import module_base
            for btn_id, state_idx in self.button_states.items():
                module_base._BUTTON_STATES[btn_id] = state_idx
            showlog.info(f"*[VK8M] Synced _BUTTON_STATES: {module_base._BUTTON_STATES}")
        except Exception as e:
            showlog.error(f"*[VK8M] Failed to sync button states: {e}")
    
    def _sync_ui_dials(self):
        """Update on-screen dial positions to match dial_values."""
        try:
            import dialhandlers
            dials = getattr(dialhandlers, "dials", None)
            showlog.info(f"[VK8M] _sync_ui_dials: dials={dials}, len={len(dials) if dials else 0}")
            showlog.info(f"[VK8M] _sync_ui_dials: dial_values={self.dial_values}")
            
            if not dials:
                showlog.warn(f"[VK8M] No dials found in dialhandlers")
                return
                
            # VK8M uses slot 1 (index 0) for distortion and slot 5 (index 4) for reverb
            if len(dials) > 0 and len(self.dial_values) > 0:
                dials[0].set_value(self.dial_values[0])
                showlog.info(f"[VK8M] Set dial slot 1 (index 0) to {self.dial_values[0]}")
                
            if len(dials) > 4 and len(self.dial_values) > 1:
                dials[4].set_value(self.dial_values[1])
                showlog.info(f"[VK8M] Set dial slot 5 (index 4) to {self.dial_values[1]}")
                
        except Exception as e:
            showlog.error(f"[VK8M] Failed to sync UI dials: {e}", exc_info=True)

    # -------- Preset save/load hooks --------
    def export_state(self):
        """Export current state for preset saving (not used - preset_manager uses button_states)."""
        # The preset_manager will automatically capture self.button_states
        # This method is kept for compatibility but not actually used
        return {
            "buttons": self.button_states.copy(),
            "dials": self.dial_values[:],
        }

    def import_state(self, state: dict):
        """Restore state from preset (not used - preset_manager handles this)."""
        # The preset_manager will automatically restore self.button_states
        # This method is kept for compatibility but not actually used
        pass


# ------- Plugin Registration -------
class VK8MPlugin(PluginBase):
    """Roland VK-8M plugin (standalone device controller)."""

    name = "Roland VK-8M"
    version = "0.2.0"
    category = "synth"
    author = "System"
    description = "VK-8M organ controller"
    icon = "vk8m.png"
    page_id = VK8M.page_id

    def on_load(self, app):
        """Register VK-8M page with module_base."""
        try:
            from pages import module_base as vk8m_page
            
            # Plugin rendering metadata
            rendering_meta = {
                "fps_mode": "high",              # Match vibrato for smooth rendering
                "supports_dirty_rect": True,     # Uses dirty rect optimization
                "burst_multiplier": 1.0,         # Standard burst behavior
            }
            
            app.page_registry.register(
                self.page_id,
                vk8m_page,
                label=self.name,
                meta={"rendering": rendering_meta}
            )
            showlog.info(f"[VK8MPlugin] Registered page '{self.page_id}'")
            
            # Register speed dial hook for external control
            # We'll add the dial to dialhandlers.dials in draw_ui when widget is created
            
        except Exception as e:
            import traceback
            showlog.error(f"[VK8MPlugin] Failed to register page: {e}")
            showlog.error(traceback.format_exc())


# Legacy exports for module_base compatibility
MODULE_ID = VK8M.MODULE_ID
REGISTRY = VK8M.REGISTRY
BUTTONS = VK8M.BUTTONS
SLOT_TO_CTRL = VK8M.SLOT_TO_CTRL

# Export the Plugin class for auto-discovery
Plugin = VK8MPlugin
