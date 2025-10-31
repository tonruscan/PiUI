# utils/rotating_state.py
"""
Elegant rotating state manager for buttons that cycle through multiple states.

Usage:
    # Define states with labels and optional data
    stereo_mode = RotatingState([
        {"label": "L", "channels": [17]},
        {"label": "R", "channels": [16]},
        {"label": "LR", "channels": [17, 16]},
    ])
    
    # On button press
    stereo_mode.advance()
    
    # Get current state
    current = stereo_mode.current()  # Returns {"label": "L", "channels": [17]}
    label = stereo_mode.label()      # Returns "L"
    channels = stereo_mode.get("channels")  # Returns [17]
    
    # For presets - serialize/deserialize
    state_dict = stereo_mode.to_dict()
    stereo_mode.from_dict(state_dict)
"""

import showlog


class RotatingState:
    """
    Manages a cyclic state machine for a single button that rotates through N states.
    
    States can be:
    - Simple strings: ["L", "R", "LR"]
    - Dictionaries with data: [{"label": "L", "channels": [17]}, ...]
    
    Thread-safe for single-threaded UI environments (no mutex needed).
    """
    
    def __init__(self, states, initial_index=0):
        """
        Initialize rotating state manager.
        
        Args:
            states: List of state definitions (strings or dicts with "label" key)
            initial_index: Starting state index (default: 0)
        """
        if not states:
            raise ValueError("RotatingState requires at least one state")
        
        self._states = self._normalize_states(states)
        self._index = initial_index % len(self._states)
        
        showlog.debug(f"[RotatingState] Initialized with {len(self._states)} states, index={self._index}")
    
    def _normalize_states(self, states):
        """Convert all states to dict format for consistency."""
        normalized = []
        for state in states:
            if isinstance(state, str):
                # Simple string -> {"label": "str"}
                normalized.append({"label": state})
            elif isinstance(state, dict):
                # Already a dict, ensure it has a label
                if "label" not in state:
                    raise ValueError(f"State dict must have 'label' key: {state}")
                normalized.append(state.copy())
            else:
                raise ValueError(f"Invalid state type: {type(state)}")
        return normalized
    
    def advance(self):
        """Move to next state (wraps around to 0 after last state)."""
        self._index = (self._index + 1) % len(self._states)
        showlog.debug(f"[RotatingState] Advanced to index {self._index}: {self.label()}")
        return self.current()
    
    def current(self):
        """Get current state dict."""
        return self._states[self._index]
    
    def label(self):
        """Get current state label (for button display)."""
        return self._states[self._index]["label"]
    
    def index(self):
        """Get current state index."""
        return self._index
    
    def get(self, key, default=None):
        """Get a value from current state dict (like dict.get())."""
        return self._states[self._index].get(key, default)
    
    def set_index(self, index):
        """Set specific state by index (for preset restoration)."""
        if 0 <= index < len(self._states):
            self._index = index
            showlog.debug(f"[RotatingState] Set index to {self._index}: {self.label()}")
        else:
            showlog.warn(f"[RotatingState] Invalid index {index}, keeping {self._index}")
    
    def set_label(self, label):
        """Set state by label (for preset restoration by name)."""
        for i, state in enumerate(self._states):
            if state["label"] == label:
                self._index = i
                showlog.debug(f"[RotatingState] Set to label '{label}' (index {i})")
                return True
        showlog.warn(f"[RotatingState] Label '{label}' not found")
        return False
    
    def count(self):
        """Get total number of states."""
        return len(self._states)
    
    def to_dict(self):
        """Serialize for presets (returns minimal state for saving)."""
        return {
            "index": self._index,
            "label": self.label()  # For human readability
        }
    
    def from_dict(self, state_dict):
        """Restore from preset data."""
        if isinstance(state_dict, dict):
            # Prefer index (reliable), fall back to label
            if "index" in state_dict:
                self.set_index(state_dict["index"])
            elif "label" in state_dict:
                self.set_label(state_dict["label"])
        else:
            showlog.warn(f"[RotatingState] Invalid state_dict: {state_dict}")
    
    def __repr__(self):
        return f"RotatingState({self._index}/{len(self._states)}: {self.label()})"


# ---- Convenience factory functions ----

def create_simple_rotation(labels, initial=0):
    """
    Quick factory for simple label rotation.
    
    Example:
        mode = create_simple_rotation(["L", "R", "LR"])
    """
    return RotatingState(labels, initial)


def create_multi_button_rotation(button_configs):
    """
    Create multiple RotatingState instances for multiple buttons.
    
    Args:
        button_configs: Dict mapping button_id -> list of states
        
    Example:
        buttons = create_multi_button_rotation({
            "2": ["L", "R", "LR"],
            "3": ["Fast", "Slow"],
        })
        
        # On button press
        buttons["2"].advance()
        
    Returns:
        Dict of {button_id: RotatingState}
    """
    return {
        btn_id: RotatingState(states)
        for btn_id, states in button_configs.items()
    }


# ---- Integration helpers ----

def apply_rotation_to_buttons(buttons_schema, rotating_configs):
    """
    Update BUTTONS schema to use rotating state labels.
    
    Args:
        buttons_schema: List of button dicts (module's BUTTONS list)
        rotating_configs: Dict of {button_id: RotatingState}
        
    Example:
        BUTTONS = [
            {"id": "2", "label": "MODE", "behavior": "state"},
        ]
        
        rotators = {"2": create_simple_rotation(["L", "R", "LR"])}
        apply_rotation_to_buttons(BUTTONS, rotators)
        # Now BUTTONS[0]["label"] will be "L" (current state)
    """
    for button in buttons_schema:
        btn_id = button.get("id")
        if btn_id in rotating_configs:
            rotator = rotating_configs[btn_id]
            button["label"] = rotator.label()
            showlog.debug(f"[RotatingState] Updated button {btn_id} label to '{rotator.label()}'")
