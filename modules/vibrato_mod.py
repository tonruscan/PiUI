from control import vibrato_control
from system.module_core import ModuleBase
import threading, time

import showlog
from modules.mod_helper import division_label_from_index, rate_hz_from_division_label
from utils.rotating_state import RotatingState

CUSTOM_WIDGET = {
    "class": "VibratoField",
    "path": "widgets.adsr_widget",
    "grid_size": [3, 2],  # width, height in grid cells
    "state_vars": ["a_y", "b_x", "b_y"]  # Widget state variables (now handled via get_state/set_from_state)
}

# Grid layout for dials (rows, cols)
GRID_LAYOUT = {
    "rows": 2,
    "cols": 4
}

# Grid zones for debug overlay and zone-based positioning
GRID_ZONES = [
    {"id": "A", "row": 0, "col": 0, "w": 1, "h": 1, "color": (255,   0,   0, 100)},  # top-left 1×1
    {"id": "B", "row": 1, "col": 0, "w": 1, "h": 1, "color": (  0, 255,   0, 100)},  # below-left 1×1
    {"id": "C", "row": 0, "col": 1, "w": 3, "h": 2, "color": (  0,   0, 255, 100)},  # right 3×2
]



_ACTIVE_INSTANCE = None


def get_active_instance():
    """Return the live Vibrato module instance if one is active."""
    return _ACTIVE_INSTANCE


def notify_bmlpf_stereo_offset_change():
    """External hook for the BMLPF device to refresh stereo calibration."""
    inst = get_active_instance()
    if inst is not None:
        try:
            inst.on_bmlpf_stereo_offset_change()
        except Exception as exc:
            showlog.warn(f"[Vibrato] notify_bmlpf_stereo_offset_change failed: {exc}")


class Vibrato(ModuleBase):
    MODULE_ID = "vibrato"
    FAMILY = "vibrato"

    # Registry payload - now includes preset variable mapping
    REGISTRY = {
        "vibrato": {
            "type": "module",
            "01": {
                "label": "Division",
                "cc": 43,
                "range": [0, 5],
                "type": "raw",
                "options": ["1", "1/2", "1/4", "1/8", "1/16", "1/32"],
                "default_slot": 1,
                "family": "vibrato",
                "variable": "division_value",  # Links to instance variable
            },
        }
    }
    
    # Initial state for module (dials + button states)
    INIT_STATE = {
        "dials": [4, 0, 0, 0, 0, 0, 0, 0],  # division_value=4 (1/8)
        "buttons": {
            "1": 0,  # Vibrato on/off (0=off, 1=on)
            "2": 0   # Stereo mode (0=L, 1=R, 2=LR)
        }
    }
    
    BUTTONS = [
        {"id": "1", "label": "S", "behavior": "transient"},
        {"id": "2", "label": "L", "behavior": "state"},      # Rotating stereo mode (L → R → LR)
        {"id": "5", "label": "5", "behavior": "transient", "action": "bypass_toggle"},
        {"id": "6", "label": "6", "behavior": "nav", "action": "store_preset"},
        {"id": "7", "label": "P", "behavior": "nav", "action": "presets"},
        {"id": "8", "label": "8", "behavior": "transient", "action": "mute_toggle"},
        {"id": "9", "label": "S", "behavior": "transient", "action": "save_preset"},
        {"id": "10", "label": "10", "behavior": "nav", "action": "device_select"},
    ]




    def on_init(self):
        # Do NOT re-init state here; it's set in __init__
        # Sync button state (button 2) to RotatingState
        if "2" in self.button_states:
            self.stereo_mode.set_index(self.button_states["2"])
            self._update_button_label("2", self.stereo_mode.label())

        # Push current button states into dialhandlers for preset/system tracking
        self._push_button_states()

        showlog.debug(
            f"[Vibrato] on_init() — div={self.division_value}, "
            f"button_states={self.button_states}, "
            f"stereo_mode={self.stereo_mode.label()}"
        )
    
    
    def __init__(self):
        super().__init__()
        global _ACTIVE_INSTANCE
        _ACTIVE_INSTANCE = self
        
        # Rotating stereo mode (replaces buttons 2, 3, 4)
        self.stereo_mode = RotatingState([
            {"label": "L", "channels": [17]},
            {"label": "R", "channels": [16]},
            {"label": "LR", "channels": [17, 16]},
        ])
        
        # Initialize from INIT_STATE snapshot (modern dict format)
        init_state = self.INIT_STATE if isinstance(self.INIT_STATE, dict) else {}

        dials_init = init_state.get("dials") if isinstance(init_state.get("dials"), list) else None
        self.division_value = dials_init[0] if dials_init and len(dials_init) > 0 else 4  # linked to slot "01"
        self.depth_value = 50    # linked to slot "05"

        buttons_init = init_state.get("buttons") if isinstance(init_state.get("buttons"), dict) else None
        self.button_states = buttons_init.copy() if buttons_init else {"1": 0, "2": 0}

        # Sync stereo mode + button label with stored index (force valid range)
        stored_index = int(self.button_states.get("2", 0))
        stored_index = max(0, min(stored_index, self.stereo_mode.count() - 1))
        self.stereo_mode.set_index(stored_index)
        self.button_states["2"] = self.stereo_mode.index()
        self._update_button_label("2", self.stereo_mode.label())
        
        self.current_hz = 0      # calculated from division
        self._last_div_idx = None
        self._cal_baseline = {}  # key: (device, calib_key) -> (lo0, hi0)
        self._widget_state = {"low_norm": 0.25, "high_norm": 0.75, "fade_ms": 0}
        self._widget_attached = False
        self._default_calibration = {}
        self._last_offset_dac = 0
        # Register initial button states with dialhandlers
        self._push_button_states()

        showlog.debug(f"[Vibrato] Initialized with stereo mode: {self.stereo_mode.label()}, button_states: {self.button_states}")


    def _push_button_states(self):
        """Publish current button state dict to dialhandlers (for presets & UI)."""
        try:
            import dialhandlers
            state_copy = self.button_states.copy()
            dialhandlers.update_button_state(self.MODULE_ID, "button_states", state_copy)
            for btn_id, btn_state in state_copy.items():
                dialhandlers.update_button_state(self.MODULE_ID, f"button_{btn_id}", btn_state)
            dialhandlers.update_button_state(self.MODULE_ID, "stereo_mode_index", state_copy.get("2", 0))
        except Exception as exc:
            showlog.debug(f"[Vibrato] Failed to push button states: {exc}")
    
    
    def on_dial_change(self, dial_label: str, value: int):
        """
        Called whenever a dial (hardware or touchscreen) changes.
        dial_label = human-readable label from REGISTRY (e.g. 'Division')
        value      = integer 0–127 or scaled range value
        """
        showlog.verbose(f"[Vibrato] on_dial_change({dial_label}={value})")

        # Optional: call a label-specific method if it exists (e.g. self.division)
        method = getattr(self, dial_label.lower(), None)
        if callable(method):
            method(value)



    
    def _get_active_channels(self):
        """
        Get channels from rotating stereo mode.
        Returns list of channel numbers.
        """
        return self.stereo_mode.get("channels", [16])


    def on_button(self, button_id: str):
        """
        Called whenever a side button (1–10) is pressed.
        Button states are tracked numerically like dials.
        """
        showlog.debug(f"[Vibrato] on_button({button_id}) pressed")
        
        btn_num = int(button_id)

        # Button 2: Rotate stereo mode (L → R → LR)
        if btn_num == 2:
            # Advance to next mode
            self.stereo_mode.advance()
            self.button_states["2"] = self.stereo_mode.index()  # Store numeric state (0, 1, or 2)
            
            # Update button label dynamically
            self._update_button_label("2", self.stereo_mode.label())
            
            # Get channels for current mode
            channels = self.stereo_mode.get("channels")
            showlog.info(f"[Vibrato] Stereo mode: {self.stereo_mode.label()} (index {self.button_states['2']}) - channels {channels}")
            
            # Reapply calibration (automatically restarts if vibrato is active)
            self._restart_vibrato()
            self._push_button_states()
            return

        # Button 1: Vibrato on/off toggle
        if btn_num == 1:
            self.button_states["1"] = 1 - self.button_states["1"]  # Toggle 0 ↔ 1
            showlog.info(f"[Vibrato] Button 1 state = {self.button_states['1']}")

            if self.button_states["1"] == 1:  # button 1 is ON
                label = division_label_from_index(self.REGISTRY, "01", self.division_value)
                bpm   = 120.0  # TODO: read from your clock
                hz    = rate_hz_from_division_label(bpm, label)
                param = int(round(hz))
                self.current_hz = param
                self._apply_widget_calibration()
                channels = self._get_active_channels()
                showlog.info(f"[Vibrato] ON @ division {param} ({label} at {bpm} BPM) on channels {channels}")
            else:
                # Turn off all possible channels
                for ch in [16, 17]:
                    self.cv_send(f"VIBEOFF {ch}")
                showlog.info("[Vibrato] OFF")
                self._restore_default_calibrations()

            self._push_button_states()
            return
    
    
    def _update_button_label(self, button_id, new_label):
        """Update button label in BUTTONS schema and trigger UI refresh."""
        for button in self.BUTTONS:
            if button["id"] == button_id:
                button["label"] = new_label
                showlog.debug(f"[Vibrato] Updated button {button_id} label to '{new_label}'")
                break
        
        # Trigger UI refresh
        try:
            import dialhandlers
            if hasattr(dialhandlers, 'msg_queue') and dialhandlers.msg_queue:
                dialhandlers.msg_queue.put(("force_redraw", 10))
        except Exception as e:
            showlog.debug(f"[Vibrato] UI refresh skipped: {e}")
    
    
    def _restart_vibrato(self):
        """Helper to reapply calibration and restart vibrato if active."""
        self._apply_widget_calibration()


    def _restore_default_calibrations(self):
        """Return DAC calibrations and outputs to their pre-vibrato state."""
        try:
            import importlib
            import sys
            import dialhandlers
            import cv_client

            dev_name = getattr(dialhandlers, "current_device_name", None)
            if not dev_name:
                return

            mod_path = f"device.{dev_name.lower()}"
            dev_module = sys.modules.get(mod_path)
            if dev_module is None:
                dev_module = importlib.import_module(mod_path)

            defaults = dict(self._default_calibration)

            if not defaults:
                # Fallback to device-defined calibration ranges
                if dev_name.lower() == "bmlpf" and hasattr(dev_module, "CV_CALIB_STEREO"):
                    base_cal = getattr(dev_module, "CV_CALIB_STEREO", {})
                    cal_entry = base_cal.get("01", {})
                    base_tuple = (int(cal_entry.get("cal_lo", 0)), int(cal_entry.get("cal_hi", 4095)))
                    defaults = {17: base_tuple, 16: base_tuple}
                else:
                    base_cal = getattr(dev_module, "CV_CALIB", {})
                    if base_cal:
                        first_key = next(iter(base_cal.keys()), None)
                        if first_key:
                            entry = base_cal.get(first_key, {})
                            base_tuple = (int(entry.get("cal_lo", 0)), int(entry.get("cal_hi", 4095)))
                            defaults = {16: base_tuple}

            if not defaults:
                return

            self._default_calibration = {int(k): (int(v[0]), int(v[1])) for k, v in defaults.items()}

            for ch, (base_lo, base_hi) in defaults.items():
                cv_client.send_cal(int(ch), int(base_lo), int(base_hi))

            showlog.info(f"[Vibrato] Restored base calibration for channels {list(defaults.keys())}: {defaults}")

        except Exception as exc:
            showlog.warn(f"[Vibrato] Failed to restore default calibration: {exc}")


    def on_bmlpf_stereo_offset_change(self):
        """Called when the BMLPF stereo offset dial changes."""
        if not self._widget_state:
            return
        showlog.debug("[Vibrato] BMLPF offset change detected — refreshing calibration")
        self._apply_widget_calibration()


    def division(self, value: int):
        """Update only when moving to the next discrete division."""
        idx = int(round(value))
        
        # Always update the stored value for presets
        self.division_value = idx
        
        # Only send CV updates when actually changing segments
        if idx == self._last_div_idx:
            return  # still within same segment, do nothing

        self._last_div_idx = idx
        label = division_label_from_index(self.REGISTRY, "01", idx)
        showlog.debug(f"[Vibrato] Division changed → {label} (idx={idx})")

        # Check if button 1 is ON (vibrato is active)
        if self.button_states.get("1", 0) == 1:  # button 1 is the vibrato on/off
            bpm = 120.0
            hz = rate_hz_from_division_label(bpm, label)
            self.current_hz = int(round(hz))
            
            # Turn off all channels
            for ch in [16, 17]:
                self.cv_send(f"VIBEOFF {ch}")
            
            time.sleep(0.05)
            
            # Turn on active channels with new rate
            channels = self._get_active_channels()
            for ch in channels:
                self.cv_send(f"VIBEON {ch} {self.current_hz}")
            
            showlog.debug(f"[Vibrato] Updated rate to {self.current_hz} Hz ({label} @ {bpm} BPM) on channels {channels}")



 





    # def depth(self, value: int):
    #     """
    #     Non-destructive depth: read device's original calib once, cache it,
    #     and send adjusted (lo, new_hi) to the DAC server without mutating CV_CALIB.
    #     """
    #     # Store the depth value for preset system
    #     self.depth_value = value
        
    #     showlog.verbose(f"[Vibrato] depth() ENTER value={value!r}")
    #     try:
    #         import importlib, sys, dialhandlers, cv_client

    #         # 1) Active device
    #         dev_name = getattr(dialhandlers, "current_device_name", None)
    #         showlog.verbose(f"[Vibrato] current_device_name={dev_name!r}")
    #         if not dev_name:
    #             showlog.warn("[Vibrato] No active device — cannot adjust calibration")
    #             return

    #         # 2) Force fresh import (avoid stale module contents)
    #         mod_path = f"device.{dev_name.lower()}"
    #         if mod_path in sys.modules:
    #             showlog.verbose(f"[Vibrato] Forcing reload of {mod_path}")
    #             importlib.reload(sys.modules[mod_path])
    #         dev_module = importlib.import_module(mod_path)
    #         showlog.verbose(f"[Vibrato] Imported module → {dev_module}")

    #         # 3) Read maps
    #         cv_calib = getattr(dev_module, "CV_CALIB", {})
    #         cv_map   = getattr(dev_module, "CV_MAP", {})
    #         showlog.verbose(f"[Vibrato] CV_CALIB keys={list(cv_calib.keys())!r}")
    #         showlog.verbose(f"[Vibrato] CV_MAP   ={cv_map!r}")

    #         # 4) pick which param vibrato modulates:
    #         # prefer human label "Cutoff", else fallback to numeric "01"
    #         target_label = "Cutoff"
    #         if target_label in cv_calib:
    #             calib_key = target_label
    #         elif "01" in cv_calib:
    #             calib_key = "01"
    #         else:
    #             calib_key = next(iter(cv_calib.keys()), None)

    #         cal_entry = cv_calib.get(calib_key) if calib_key else None
    #         showlog.verbose(f"[Vibrato] calib_key={calib_key!r} cal_entry={cal_entry!r}")
    #         if not isinstance(cal_entry, dict):
    #             showlog.warn("[Vibrato] No calibration entry found — abort")
    #             return

    #         # 5) establish BASELINE lo/hi (never mutate this)
    #         base_key = (dev_name, calib_key)
    #         if base_key not in self._cal_baseline:
    #             lo0 = int(cal_entry.get("cal_lo", 0))
    #             hi0 = int(cal_entry.get("cal_hi", 4095))
    #             if hi0 < lo0:
    #                 lo0, hi0 = hi0, lo0
    #             self._cal_baseline[base_key] = (lo0, hi0)
    #             showlog.verbose(f"[Vibrato] cached baseline[{base_key}] = lo0={lo0} hi0={hi0}")
    #         else:
    #             lo0, hi0 = self._cal_baseline[base_key]
    #             showlog.verbose(f"[Vibrato] using cached baseline[{base_key}] = lo0={lo0} hi0={hi0}")

    #         span0 = hi0 - lo0
    #         showlog.verbose(f"[Vibrato] baseline span0={span0}")

    #         # 6) normalise dial to 0..1 (respect registry range if needed)
    #         # Depth registry is [0,100], but if 0..127 arrives, handle gracefully
    #         denom = 100 if value <= 100 else 127
    #         depth_frac = max(0.0, min(1.0, float(value) / float(denom)))
    #         showlog.verbose(f"[Vibrato] value={value} denom={denom} depth_frac={depth_frac:.4f}")

    #         # 7) compute new_hi relative to BASELINE (not current mutable cal)
    #         new_hi_float = lo0 + span0 * depth_frac
    #         new_hi = max(lo0, min(hi0, int(round(new_hi_float))))
    #         showlog.verbose(f"[Vibrato] new_hi_float={new_hi_float:.3f} → new_hi={new_hi}")

    #         # 8) resolve DAC channel (prefer numeric '01' → channel)
    #         if "01" in cv_map:
    #             channel = cv_map.get("01")
    #             channel_src = "cv_map['01']"
    #         else:
    #             # take first mapping deterministically
    #             try:
    #                 channel = next(iter(cv_map.values()))
    #                 channel_src = "cv_map[first]"
    #             except Exception:
    #                 channel, channel_src = None, "none"

    #         showlog.verbose(f"[Vibrato] channel={channel!r} (src={channel_src})")

    #         if channel is None:
    #             showlog.warn(" [Vibrato] No DAC channel resolved — cannot send calibration")
    #             return

    #         # 9) send ONLY to server; DO NOT mutate device.CV_CALIB in memory
    #         showlog.debug(f"[Vibrato] cv_client.send_cal(ch={channel}, lo={lo0}, hi={new_hi})")
            
    #         # Only stop/restart vibrato if it's currently active (button 1 is ON)
    #         was_active = self.button_states[0]
    #         if was_active:
    #             cv_client.send_raw("VIBEOFF 16")
            
    #         cv_client.send_cal(int(channel), int(lo0), int(new_hi))
            
    #         if was_active:
    #             cv_client.send_raw(f"VIBEON 16 {self.current_hz}")
            
    #         showlog.verbose(f"[Vibrato] Calibration updated (non-destructive): ch={channel} → {lo0}–{new_hi} "
    #                     f"(depth_frac={depth_frac:.3f}, baseline_hi={hi0})")

    #     except Exception as e:
    #         showlog.error(f"[Vibrato] depth() exception: {e}")
    #     finally:
    #         showlog.verbose("[Vibrato] depth() EXIT")






    # --------------------------------------------------------------
    # UI integration hook — connects generic widgets to this module
    # --------------------------------------------------------------
    def _apply_widget_calibration(self, state=None):
        """Apply current widget bounds to the active DAC channels."""
        state = state or {}
        stored = self._widget_state or {}
        low_frac = float(state.get("low_norm", stored.get("low_norm", 0.0)))
        high_frac = float(state.get("high_norm", stored.get("high_norm", 1.0)))
        fade_ms = state.get("fade_ms", stored.get("fade_ms", 0))

        # Persist latest widget settings for reuse (e.g., when offsets change)
        self._widget_state.update({
            "low_norm": low_frac,
            "high_norm": high_frac,
            "fade_ms": fade_ms,
        })

        try:
            import importlib
            import sys
            import dialhandlers
            import cv_client

            dev_name = getattr(dialhandlers, "current_device_name", None)
            if not dev_name:
                showlog.warn("[Vibrato] No active device — cannot send calibration")
                return

            mod_path = f"device.{dev_name.lower()}"
            dev_module = sys.modules.get(mod_path)
            if dev_module is None:
                dev_module = importlib.import_module(mod_path)

            is_bmlpf = dev_name.lower() == "bmlpf"
            if is_bmlpf and hasattr(dev_module, "CV_CALIB_STEREO"):
                cv_calib = getattr(dev_module, "CV_CALIB_STEREO", {})
            else:
                cv_calib = getattr(dev_module, "CV_CALIB", {})

            if not cv_calib:
                showlog.warn("[Vibrato] No CV calibration data available")
                return

            if is_bmlpf and "01" in cv_calib:
                calib_key = "01"
            else:
                calib_key = next(iter(cv_calib.keys()), None)

            cal_entry = cv_calib.get(calib_key, {}) if calib_key else {}
            if not cal_entry:
                showlog.warn("[Vibrato] No calibration entry found for active device")
                return

            lo0 = int(cal_entry.get("cal_lo", 0))
            hi0 = int(cal_entry.get("cal_hi", 4095))
            span = hi0 - lo0

            new_lo = lo0 + int(round(span * low_frac))
            new_hi = lo0 + int(round(span * high_frac))
            if new_hi < new_lo:
                new_hi = new_lo

            channels = list(dict.fromkeys(self._get_active_channels()))
            if not channels:
                channels = [16]

            # Remember original calibration so we can restore when vibrato stops
            if is_bmlpf:
                self._default_calibration.setdefault(17, (int(lo0), int(hi0)))
                self._default_calibration.setdefault(16, (int(lo0), int(hi0)))
            for ch in channels:
                self._default_calibration.setdefault(int(ch), (int(lo0), int(hi0)))

            offset_dac = 0
            if is_bmlpf and hasattr(dev_module, "get_stereo_offset_dac"):
                try:
                    offset_dac = int(dev_module.get_stereo_offset_dac("cutoff_offset"))
                except Exception as exc:
                    showlog.warn(f"[Vibrato] Failed to read BMLPF offset: {exc}")
                    offset_dac = 0
            self._last_offset_dac = offset_dac

            clamp = lambda val: max(0, min(4095, int(val)))
            left_lo = clamp(new_lo - offset_dac)
            left_hi = clamp(new_hi - offset_dac)
            right_lo = clamp(new_lo + offset_dac)
            right_hi = clamp(new_hi + offset_dac)

            was_active = bool(self.button_states.get("1", 0))
            if was_active:
                for ch in [16, 17]:
                    self.cv_send(f"VIBEOFF {ch}")

            sent = []
            for ch in channels:
                if ch == 17:
                    cv_client.send_cal(17, left_lo, left_hi)
                    sent.append(f"L17:{left_lo}-{left_hi}")
                elif ch == 16:
                    cv_client.send_cal(16, right_lo, right_hi)
                    sent.append(f"R16:{right_lo}-{right_hi}")
                else:
                    cv_client.send_cal(int(ch), int(new_lo), int(new_hi))
                    sent.append(f"CH{ch}:{new_lo}-{new_hi}")

            summary = ", ".join(sent)
            if is_bmlpf:
                showlog.info(f"[Vibrato] Stereo calibration sent (offset={offset_dac}): {summary}")
            else:
                showlog.debug(f"[Vibrato] Calibration sent: {summary}")

            if was_active:
                for ch in channels:
                    self.cv_send(f"VIBEON {ch} {self.current_hz}")

        except Exception as e:
            import traceback
            showlog.error(f"[Vibrato] calibration apply failed: {e}")
            showlog.error(f"[Vibrato] Traceback: {traceback.format_exc()}")

    def attach_widget(self, widget):
        """Wire the vibrato widget to calibration updates (including stereo offsets)."""

        def _on_field_change(state):
            self._apply_widget_calibration(state)

        widget.on_change = _on_field_change
        self._widget_attached = True

        # Capture initial widget state and apply calibration immediately if possible
        try:
            params = widget.get_params()
            self._apply_widget_calibration({
                "low_norm": params.get("low_norm"),
                "high_norm": params.get("high_norm"),
                "fade_ms": params.get("fade_frac", 0),
            })
        except Exception as exc:
            showlog.debug(f"[Vibrato] Initial widget calibration skipped: {exc}")

        showlog.debug("[Vibrato] attach_widget(): low/high bound wiring active (stereo aware)")








    def cv_send(self, command: str):
        showlog.debug(f"[Vibrato] CV → {command}")
        try:
            import cv_client
            if hasattr(cv_client, "send_raw"):
                cv_client.send_raw(command)
            else:
                # Fallback if only .send exists AND it wants a single string
                cv_client.send(command)  # remove if it still errors
        except Exception as e:
            showlog.warn(f"[Vibrato] CV send failed: {e}")







# ---- Legacy bridge functions ----

def apply(ctrl_id: str, value: int):
    """
    Legacy bridge for backward compatibility.
    Routes to the appropriate dial method on the Vibrato instance.
    """
    try:
        instance = Vibrato()
        label_map = {
            "vibrato_time_fraction": "division",
            "vibrato_depth": "depth",
        }
        method_name = label_map.get(ctrl_id)
        if method_name and hasattr(instance, method_name):
            getattr(instance, method_name)(value)
        else:
            showlog.warn(f"[Vibrato] apply() unknown ctrl_id: {ctrl_id}")
    except Exception as e:
        showlog.error(f"[Vibrato] apply() failed: {e}")




# Legacy exports so existing code like module_base can still access these
MODULE_ID = Vibrato.MODULE_ID
REGISTRY  = Vibrato.REGISTRY
BUTTONS   = Vibrato.BUTTONS
SLOT_TO_CTRL = {
    1: "vibrato_time_fraction",
}
