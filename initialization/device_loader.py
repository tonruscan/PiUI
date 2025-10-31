"""
Device loading and initialization.

Handles loading device configurations and button behaviors.
"""

import importlib
from typing import Dict, Optional

import devices
import showlog


class DeviceLoader:
    """Loads and manages device configurations."""
    
    def __init__(self):
        """Initialize device loader."""
        self.loaded_devices = {}
        self.device_behavior_map = {}
    
    def load_all_devices(self):
        """Load all device configurations from devices module."""
        try:
            devices.load()
            showlog.debug("[DEVICE_LOADER] All devices loaded")
        except Exception as e:
            showlog.error(f"[DEVICE_LOADER] Failed to load devices: {e}")
    
    def load_device_module(self, device_name: str) -> Optional[object]:
        """
        Load a device module dynamically.
        
        Args:
            device_name: Name of the device (e.g., "QUADRAVERB")
        
        Returns:
            The loaded device module or None if failed
        """
        try:
            module_path = f"device.{device_name.lower()}"
            device_module = importlib.import_module(module_path)
            self.loaded_devices[device_name.upper()] = device_module
            showlog.debug(f"[DEVICE_LOADER] Loaded module for {device_name}")
            return device_module
        except Exception as e:
            showlog.error(f"[DEVICE_LOADER] Failed to load {device_name}: {e}")
            return None
    
    def get_button_behavior(self, device_name: str) -> Dict:
        """
        Get button behavior map for a device.
        
        Args:
            device_name: Name of the device
        
        Returns:
            Dictionary mapping button IDs to behaviors
        """
        device_name_upper = device_name.upper()
        
        # Return cached if available
        if device_name_upper in self.device_behavior_map:
            return self.device_behavior_map[device_name_upper]
        
        # Try to load from device module
        try:
            device_module = self.loaded_devices.get(device_name_upper)
            if not device_module:
                device_module = self.load_device_module(device_name)
            
            if not device_module:
                return {}
            
            # Try new BUTTONS schema first
            buttons_list = getattr(device_module, "BUTTONS", None)
            if buttons_list:
                behavior_map = self._convert_buttons_to_behavior_map(buttons_list)
                showlog.debug(f"[DEVICE_LOADER] Converted BUTTONS schema for {device_name}")
            else:
                # Fall back to legacy BUTTON_BEHAVIOR
                behavior_map = getattr(device_module, "BUTTON_BEHAVIOR", {})
                if behavior_map:
                    showlog.debug(f"[DEVICE_LOADER] Using legacy BUTTON_BEHAVIOR for {device_name}")
            
            # Cache it
            self.device_behavior_map[device_name_upper] = behavior_map
            return behavior_map
            
        except Exception as e:
            showlog.error(f"[DEVICE_LOADER] Failed to get button behavior for {device_name}: {e}")
            return {}
    
    def _convert_buttons_to_behavior_map(self, buttons_list: list) -> Dict:
        """
        Convert new BUTTONS schema to old BUTTON_BEHAVIOR dict format.
        
        Args:
            buttons_list: List of button dictionaries
        
        Returns:
            Dictionary mapping button IDs to behaviors
        """
        if not buttons_list:
            return {}
        
        behavior_map = {}
        for btn in buttons_list:
            if isinstance(btn, dict) and "id" in btn and "behavior" in btn:
                behavior_map[btn["id"]] = btn["behavior"]
        
        return behavior_map
    
    def send_cv_calibration(self, device_name: str):
        """
        Send CV calibration for a device if it uses CV transport.
        
        Args:
            device_name: Name of the device
        """
        try:
            device_module = self.loaded_devices.get(device_name.upper())
            if not device_module:
                return
            
            # Check if device uses CV transport
            transport = getattr(device_module, "TRANSPORT", None)
            if transport != "cv":
                return
            
            cv_map = getattr(device_module, "CV_MAP", {})
            cv_calib = getattr(device_module, "CV_CALIB", {})
            
            if not cv_map or not cv_calib:
                showlog.debug(f"[DEVICE_LOADER] No CV calibration data for {device_name}")
                return
            
            import cv_client
            for name, ch in cv_map.items():
                cal = cv_calib.get(name)
                if cal:
                    lo = cal.get("cal_lo", 0)
                    hi = cal.get("cal_hi", 4095)
                    cv_client.send_cal(ch, lo, hi)
                    showlog.debug(f"[DEVICE_LOADER] Sent CAL for {device_name}:{name} (ch{ch}) → {lo}-{hi}")
                    
        except Exception as e:
            showlog.warn(f"[DEVICE_LOADER] CV calibration failed for {device_name}: {e}")
    
    def get_device_info(self, device_name: str) -> Optional[Dict]:
        """
        Get device information from devices registry.
        
        Args:
            device_name: Name of the device
        
        Returns:
            Device info dictionary or None
        """
        try:
            return devices.get_by_name(device_name)
        except Exception as e:
            showlog.error(f"[DEVICE_LOADER] Failed to get device info for {device_name}: {e}")
            return None
