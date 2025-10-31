"""
Button management.

Handles button selection, behavior, and per-device memory.
"""

from typing import Dict, Set, Optional

import showlog


class ButtonManager:
    """Manages button state and behavior."""
    
    def __init__(self):
        """Initialize button manager."""
        self.pressed_button: Optional[str] = None
        self.selected_buttons: Set[str] = set()
        self.last_left_page_button: Optional[str] = None
        
        # Per-device button memory (which button was last active on dials page)
        self.device_button_memory: Dict[str, str] = {}
        
        # Active button behavior map (loaded per device)
        self.active_button_behavior: Dict[str, str] = {}
    
    def select_button(self, which: Optional[str]):
        """
        Select a button.
        
        Args:
            which: Button identifier or None to deselect all
        """
        self.pressed_button = which
        self.selected_buttons.clear()
        if which:
            self.selected_buttons.add(which)
        showlog.debug(f"[BUTTON_MGR] Selected button: {which}")
    
    def get_selected_left_page_or_none(self) -> Optional[str]:
        """
        Get the selected left page button (1-4) if any.
        
        Returns:
            Button ID or None
        """
        for btn in ("1", "2", "3", "4"):
            if btn in self.selected_buttons:
                return btn
        return None
    
    def remember_left_page(self):
        """Remember the currently selected left page button."""
        self.last_left_page_button = self.get_selected_left_page_or_none()
        showlog.debug(f"[BUTTON_MGR] Remembered left page: {self.last_left_page_button}")
    
    def restore_left_page(self, default: str = "1") -> str:
        """
        Restore the last selected left page button.
        
        Args:
            default: Default button if none remembered
        
        Returns:
            The button ID that was restored
        """
        which = self.last_left_page_button or default
        self.select_button(which)
        showlog.debug(f"[BUTTON_MGR] Restored left page: {which}")
        return which
    
    def set_button_behavior_map(self, behavior_map: Dict[str, str]):
        """
        Set the active button behavior map.
        
        Args:
            behavior_map: Dictionary mapping button IDs to behaviors
        """
        self.active_button_behavior = behavior_map
        showlog.debug(f"[BUTTON_MGR] Button behavior map set ({len(behavior_map)} entries)")
    
    def get_button_behavior(self, button_id: str) -> str:
        """
        Get the behavior type for a button.
        
        Args:
            button_id: Button identifier
        
        Returns:
            Behavior type ("state", "nav", "transient") or "state" as default
        """
        return self.active_button_behavior.get(button_id, "state")
    
    def remember_device_button(self, device_name: str, button_id: str):
        """
        Remember which button was last active for a device.
        
        Args:
            device_name: Device name
            button_id: Button identifier
        """
        if device_name:
            self.device_button_memory[device_name.upper()] = button_id
            showlog.debug(f"[BUTTON_MGR] Remembered button '{button_id}' for {device_name}")
    
    def get_device_button(self, device_name: str) -> Optional[str]:
        """
        Get the last remembered button for a device.
        
        Args:
            device_name: Device name
        
        Returns:
            Button ID or None
        """
        return self.device_button_memory.get(device_name.upper())
    
    def set_default_device_button(self, device_name: str, button_id: str):
        """
        Set a default button for a device if none exists.
        
        Args:
            device_name: Device name
            button_id: Button identifier
        """
        device_upper = device_name.upper()
        if device_upper not in self.device_button_memory:
            self.device_button_memory[device_upper] = button_id
            showlog.debug(f"[BUTTON_MGR] Default button '{button_id}' set for {device_name}")
    
    def get_pressed_button(self) -> Optional[str]:
        """Get the currently pressed button."""
        return self.pressed_button
    
    def get_selected_buttons(self) -> Set[str]:
        """Get the set of selected buttons."""
        return self.selected_buttons
