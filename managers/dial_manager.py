"""
Dial management.

Handles dial creation, state, and MIDI CC mapping.
"""

from typing import List, Optional
import importlib

from assets.dial import Dial
import config as cfg
import dialhandlers
import showlog


class DialManager:
    """Manages dial lifecycle and state."""
    
    def __init__(self, screen_width: int = 800):
        """
        Initialize dial manager.
        
        Args:
            screen_width: Width of the screen in pixels
        """
        self.screen_width = screen_width
        self.dials: List[Dial] = []
        self.cols = 4
        self.rows = 2
        self.radius = 60
        self.last_midi_vals = [None] * 8
        
    def rebuild_dials(self, device_name: Optional[str] = None) -> List[Dial]:
        """
        Rebuild all dials with current configuration.
        
        Args:
            device_name: Optional device name for registry mapping
        
        Returns:
            List of created Dial objects
        """
        self.dials = []
        
        left_pad = cfg.DIAL_PADDING_X
        right_pad = cfg.DIAL_PADDING_X
        usable_width = self.screen_width - left_pad - right_pad
        spacing = usable_width / (self.cols - 1)
        
        dial_id = 1
        for row in range(self.rows):
            for col in range(self.cols):
                x = left_pad + col * spacing
                y = 160 + row * 180
                d = Dial(x, y)
                d.id = dial_id
                d.cc_num = cfg.DIAL_CC_START + (dial_id - 1)
                d.label = f"Dial {dial_id}"
                self.dials.append(d)
                dial_id += 1
        
        # Update dialhandlers reference
        dialhandlers.set_dials(self.dials)
        
        # Attach StateManager mapping if device provided
        if device_name:
            self._attach_state_manager_mapping(device_name)
        
        return self.dials
    
    def _attach_state_manager_mapping(self, device_name: str):
        """
        Attach StateManager source and param_id to each dial using device REGISTRY.
        
        Args:
            device_name: Name of the device
        """
        try:
            from system import cc_registry
            
            if not self.dials:
                return
            
            # Load device module
            dev_mod = importlib.import_module(f"device.{device_name.lower()}")
            reg = getattr(dev_mod, "REGISTRY", {}) or {}
            
            # Handle case-insensitive family key
            family = reg.get(device_name) or next(
                (reg[k] for k in reg if k.lower() == str(device_name).lower()),
                {}
            )
            
            if not family:
                showlog.warn(f"[DIAL_MGR] No REGISTRY family for {device_name}")
                return
            
            for d in self.dials:
                slot_key = f"{int(getattr(d, 'id', 0)):02d}"
                data = family.get(slot_key)
                if not data:
                    continue
                
                label = data.get("label")
                if not label:
                    continue
                
                # Update display label
                d.label = label
                
                # Compute param_id
                pid = cc_registry._make_param_id(device_name, label)
                d.sm_source_name = device_name
                d.sm_param_id = pid
                
                showlog.debug(f"[DIAL_MGR] slot={d.id} label='{d.label}' src={device_name} pid={pid}")
                
        except Exception as e:
            showlog.warn(f"[DIAL_MGR] Dial mapping failed: {e}")
    
    def get_dials(self) -> List[Dial]:
        """Get the current list of dials."""
        return self.dials
    
    def get_dial_by_id(self, dial_id: int) -> Optional[Dial]:
        """
        Get a specific dial by its ID.
        
        Args:
            dial_id: The dial ID to find
        
        Returns:
            The Dial object or None if not found
        """
        for d in self.dials:
            if d.id == dial_id:
                return d
        return None
    
    def update_dial_value(self, dial_id: int, value: int):
        """
        Update a dial's value.
        
        Args:
            dial_id: The dial ID to update
            value: The new value (0-127)
        """
        dial = self.get_dial_by_id(dial_id)
        if dial:
            try:
                dial.set_value(value)
            except Exception:
                dial.value = value
            dial.display_text = f"{dial.label}: {dial.value}"
    
    def clear_dials(self):
        """Clear all dials."""
        self.dials = []
        dialhandlers.set_dials(self.dials)
        showlog.debug("[DIAL_MGR] Dials cleared")
