# /plugins/ascii_animator_plugin.py
# Standalone ASCII Animator plugin with custom widget
# Uses ModuleBase architecture for proper integration

import showlog
import os
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from system.module_core import ModuleBase
from core.plugin import Plugin

PLUGIN_ID = "ascii_animator"
PLUGIN_NAME = "ASCII Animator"
PLUGIN_DESC = "ASCII animation editor with frame sequencing"


# ======================================================================
# ANIMATION API - For other plugins to load drawbar animations
# ======================================================================

def _decode_frames_from_preset(widget_state: dict, target_rows: int = 9, target_cols: int = 9) -> List[List[int]]:
    """
    Decode frames from ASCII animator preset format to drawbar positions.
    
    Handles both formats:
    - RAW: {"raw": [[frame_idx, position1, ..., positionN], ...]}
      → Skip frame index and return position values directly.
    - frames: {"frames": [["*........", ".*.......", ...], ...]}
      → Find the glowing cell in each column and convert it to a 1-9 position
        (9 = top/fully out, 1 = bottom/fully in, 0 = off).
    
    Args:
        widget_state: The widget_state dict from the preset JSON.
        target_rows: Expected grid height (default 9 for drawbar).
        target_cols: Expected grid width (default 9 for drawbar).
    
    Returns:
        List of frames, where each frame is a list of drawbar positions (0-9).
        Example: [[9,7,5,4,2,2,4,5,7], [8,6,4,3,1,3,5,6,8], ...]
    """
    rows = int(widget_state.get("rows", target_rows))
    cols = int(widget_state.get("cols", target_cols))
    
    # RAW format: [[frame_idx, pos1, pos2, ..., posN], ...]
    raw_data = widget_state.get("raw")
    if raw_data is not None:
        showlog.info("[AnimAPI] Decoding RAW format (direct positions)")
        frames = []
        for row in raw_data:
            positions = []
            # Skip the first element (frame index), keep next `cols` entries
            for value in row[1:1 + cols]:
                try:
                    positions.append(int(value))
                except (TypeError, ValueError):
                    positions.append(0)
            frames.append(positions or [0] * cols)
        return frames
    
    # Frames format: list of ASCII grids
    frs = widget_state.get("frames")
    if isinstance(frs, list) and frs:
        showlog.info("[AnimAPI] Decoding frames format (column tip positions)")
        frames = []
        for frame in frs:
            positions: List[int] = []
            for col in range(cols):
                position = 0
                # Search from top row downwards for the first lit cell
                for row_idx in range(min(rows, len(frame))):
                    line = frame[row_idx]
                    if col < len(line) and line[col] == '*':
                        # Convert row index (0=top) to drawbar position (9=top)
                        position = rows - row_idx
                        break
                positions.append(position)
            frames.append(positions)
        return frames
    
    showlog.warn("[AnimAPI] No valid frame data found in preset")
    return [[0] * cols]


def get_drawbar_animations() -> List[Tuple[str, str]]:
    """
    Scan for *.drawbar.json files in ascii_animator presets folder.
    
    Returns:
        List of tuples: [(filename, display_name), ...]
        Example: [("wave.drawbar.json", "wave"), ...]
    """
    try:
        presets_path = Path("config/presets/ascii_animator")
        if not presets_path.exists():
            return []
        
        animations = []
        for file in presets_path.glob("*.drawbar.json"):
            display_name = file.stem.replace(".drawbar", "")
            animations.append((file.name, display_name))
        
        return sorted(animations)
    
    except Exception as e:
        showlog.error(f"[AnimAPI] Failed to scan animations: {e}")
        return []


def load_drawbar_animation(filename: str) -> Optional[List[List[int]]]:
    """
    Load a drawbar animation preset and return frames as drawbar values.
    
    Uses standalone decoder to handle both RAW and frames formats.
    
    Args:
        filename: Name of the .drawbar.json file (e.g., "wave.drawbar.json")
    
    Returns:
        List of frames, where each frame is a list of 9 drawbar values (0-9).
        Example: [[4,7,8,7,5,3,1,0,1], [4,7,8,7,5,2,0,0,2], ...]
        Returns None on error.
    """
    try:
        # Load the preset file
        preset_path = Path("config/presets/ascii_animator") / filename
        if not preset_path.exists():
            showlog.error(f"[AnimAPI] Animation file not found: {filename}")
            return None
        
        with open(preset_path, 'r') as f:
            data = json.load(f)
        
        widget_state = data.get("widget_state", {})
        
        # Decode frames - returns list of height arrays directly
        frames = _decode_frames_from_preset(widget_state, target_rows=9, target_cols=9)
        
        showlog.info(f"[AnimAPI] Loaded {len(frames)} frames from {filename}")
        return frames
    
    except Exception as e:
        showlog.error(f"[AnimAPI] Failed to load animation {filename}: {e}")
        import traceback
        showlog.error(f"[AnimAPI] Traceback: {traceback.format_exc()}")
        return None


def get_animation_metadata(filename: str) -> Optional[Dict]:
    """
    Get metadata about an animation preset without loading all frames.
    
    Args:
        filename: Name of the .drawbar.json file
    
    Returns:
        Dict with keys: frame_count, rows, cols, preset_name
        Returns None on error.
    """
    try:
        preset_path = Path("config/presets/ascii_animator") / filename
        if not preset_path.exists():
            return None
        
        with open(preset_path, 'r') as f:
            data = json.load(f)
        
        widget_state = data.get("widget_state", {})
        
        return {
            "frame_count": len(widget_state.get("raw", [])),
            "rows": widget_state.get("rows", 9),
            "cols": widget_state.get("cols", 9),
            "preset_name": data.get("preset_name", filename.replace(".drawbar.json", ""))
        }
    
    except Exception as e:
        showlog.error(f"[AnimAPI] Failed to get metadata for {filename}: {e}")
        return None

class ASCIIAnimatorModule(ModuleBase):
    """ASCII Animator module using ModuleBase architecture."""
    
    MODULE_ID = "ascii_animator"
    STANDALONE = True  # Has its own identity
    page_id = "ascii_animator"
    page_label = "ASCII Animator"
    
    # Empty registry - no dials needed
    REGISTRY = {}
    
    # Tell preset system to save widget state
    PRESET_VARS = []  # No variables to save
    WIDGET_STATE = ["widget"]  # Save widget state via export_state/import_state
    
    # Initial state
    INIT_STATE = {
        "buttons": {"1": 0},  # Play/pause state
        "dials": [],
    }
    
    # Button definitions
    BUTTONS = [
        {
            "id": "1",
            "behavior": "multi",  # Multi-state: Play/Pause/RTZ
            "states": ["▶", "||"]  # Play, Pause
        },
        {"id": "2", "label": "→", "behavior": "transient"},  # Next frame
        {"id": "3", "label": "←", "behavior": "transient"},  # Previous frame
        {"id": "4", "label": "+", "behavior": "transient"},  # Add frame
        {"id": "5", "label": "−", "behavior": "transient"},  # Delete frame
        {"id": "6", "label": "6", "behavior": "nav", "action": "store_preset"},
        {"id": "7", "label": "P", "behavior": "nav", "action": "presets"},
        {"id": "8", "label": "8", "behavior": "transient", "action": "mute_toggle"},
        {"id": "9", "label": "S", "behavior": "nav", "action": "save_preset"},
        {"id": "10", "label": "10", "behavior": "nav", "action": "device_select"},
    ]
    

    # VK8M Theme (organ-inspired warm colors)
    THEME = {
        # --- Header bar ---
        "header_bg_color": "#5c5c5c",
        "header_text_color": "#E8E8E8",
        
        # --- Normal dial state ---
        "dial_panel_color": "#001504",
        "dial_fill_color": "#FF6B35",
        "dial_outline_color": "#FFB088",
        "dial_text_color": "#00FF33",
        "dial_pointer_color": "#FFEB9A",
        
        # --- Mute dial state (used by custom widgets) ---
        "dial_mute_panel": "#1A0A05",
        "dial_mute_fill": "#4A2010",
        "dial_mute_outline": "#6A3020",
        "dial_mute_text": "#7C7C7C",
        
        # --- Buttons ---
        "button_fill": "#083d1a",
        "button_outline": "#00fd00",
        "button_text": "#00fd00",
        "button_active_fill": "#00fd00",
        "button_active_text": "#083d1a",

        # --- Preset Page Colors (using same warm theme) ---
        "preset_button_color": "#001504",          # dark warm background (like mute_panel)
        "preset_text_color": "#00fd00",            # warm yellow text (like header text)
        "preset_label_highlight": "#083d1a",       # warm orange highlight (like button fill)
        "preset_font_highlight": "#00fd00",        # white text when selected
        "scroll_bar_color": "#00fd00",             # warm orange scrollbar (like outline)
    }

    # No dials
    SLOT_TO_CTRL = {}
    
    # Custom widget configuration - THIS IS THE KEY!
    CUSTOM_WIDGET = {
        "class": "ASCIIAnimatorWidget",
        "path": "widgets.ascii_animator_widget",
        "grid_size": [4, 2],  # Full 4x2 grid area
        "grid_pos": [0, 0],   # Start at top-left
    }
    
    # Grid layout
    GRID_LAYOUT = {
        "rows": 2,
        "cols": 4
    }

    def __init__(self):
        super().__init__()
        self.widget = None  # Will be set by module_base via attach_widget()
        
        # Initialize button states
        self.button_states = {"1": 0}  # 0 = Play (▶), 1 = Pause (⏸)
        
        showlog.info("[ASCIIAnimator] Module initialized")
    
    def attach_widget(self, widget):
        """Called by module_base after widget is instantiated."""
        self.widget = widget
        # Give widget a reference to this module so it can sync button state
        if widget:
            widget._module = self
        showlog.info("[ASCIIAnimator] Widget attached")
    
    def _sync_button_1_state(self):
        """Sync button 1 state to match widget play state."""
        if self.widget:
            # 0 = stopped (▶), 1 = playing (⏸)
            new_state = 1 if self.widget.playing else 0
            if self.button_states.get("1") != new_state:
                self.button_states["1"] = new_state
                # Trigger UI refresh via module_base's button state system
                try:
                    import dialhandlers
                    if hasattr(dialhandlers, 'msg_queue') and dialhandlers.msg_queue:
                        dialhandlers.msg_queue.put(("force_redraw", 10))
                except Exception as e:
                    showlog.debug(f"[ASCIIAnimator] UI refresh skipped: {e}")
    
    def on_button(self, btn_id: str, state_index: int = 0, state_data: dict = None):
        """Handle button presses - forward to widget."""
        showlog.info(f"*[MODULE 1] on_button() called: btn_id={btn_id}, state_index={state_index}")
        
        if self.widget and hasattr(self.widget, 'handle_button'):
            # Button 1 is special - it's multi-state for play/pause
            # ModuleBase already advanced the state, so we need to sync widget to match
            if btn_id == "1":
                showlog.info(f"*[MODULE 2] Button 1: state_index={state_index} (0=Play, 1=Pause)")
                # state_index: 0=Play(▶), 1=Pause(⏸)
                # Set widget playing state to match
                showlog.info(f"*[MODULE 3] Setting widget.playing to {state_index == 1}")
                self.widget.playing = (state_index == 1)
                
                # Initialize timing properly for smooth start
                if self.widget.playing:
                    import time
                    button_press_time = time.time() * 1000.0
                    self.widget._last_advance_ms = button_press_time
                    # Set timer marker for measuring to second frame
                    self.widget._button_press_time = button_press_time
                    self.widget._second_frame_reached = False
                    showlog.info(f"*[MODULE 4a] Starting playback, _last_advance_ms={self.widget._last_advance_ms}")
                    showlog.info(f"*[TIMER START] Button press at {button_press_time:.2f}ms")
                else:
                    self.widget._last_advance_ms = 0.0
                    showlog.info(f"*[MODULE 4b] Stopping playback, _last_advance_ms=0.0")
                
                showlog.info(f"*[MODULE 5] Calling widget.mark_dirty()")
                self.widget.mark_dirty()
                showlog.info(f"*[MODULE 6] widget.playing={self.widget.playing}")
            else:
                # For other buttons, just forward to widget
                showlog.info(f"*[MODULE 7] Forwarding button {btn_id} to widget")
                self.widget.handle_button(int(btn_id))
        showlog.info(f"*[MODULE 8] on_button() complete")
    
    def on_dial_change(self, dial_index: int, value: int):
        """Handle dial changes (none for this module)."""
        pass
    
    def export_state(self):
        """Export state for preset saving."""
        widget_state = {}
        if self.widget and hasattr(self.widget, 'get_state'):
            widget_state = self.widget.get_state()
        
        return {
            "buttons": {},
            "widget": widget_state
        }
    
    def import_state(self, state: dict):
        """Restore state from preset."""
        showlog.debug("*[STEP 0a] import_state called")
        if not state:
            return
        
        widget_state = state.get("widget", {})
        showlog.debug(f"*[STEP 0b] import_state widget_state: {widget_state.get('frames', 'NO FRAMES')[:50] if widget_state else 'NO STATE'}...")
        if self.widget and hasattr(self.widget, 'set_state') and widget_state:
            showlog.debug("*[STEP 0c] import_state calling widget.set_state()")
            self.widget.set_state(widget_state)
    
    def on_preset_loaded(self, variables: dict, widget_state: dict = None):
        """Called after preset restored from file - ensure widget is refreshed."""
        showlog.debug("*[STEP 1] on_preset_loaded called")
        showlog.debug(f"*[STEP 2] widget_state type: {type(widget_state)}")
        showlog.debug(f"*[STEP 3] widget_state keys: {widget_state.keys() if isinstance(widget_state, dict) else 'N/A'}")
        if widget_state and isinstance(widget_state, dict) and 'frames' in widget_state:
            showlog.debug(f"*[STEP 4] Number of frames in data: {len(widget_state['frames'])}")
            if len(widget_state['frames']) > 0:
                showlog.debug(f"*[STEP 5] First frame type: {type(widget_state['frames'][0])}")
                showlog.debug(f"*[STEP 6] First frame length: {len(widget_state['frames'][0])}")
                if len(widget_state['frames'][0]) > 1:
                    showlog.debug(f"*[STEP 7] First frame, row 1: '{widget_state['frames'][0][1]}'")
        
        # Restore widget state manually since preset_manager doesn't know about set_state()
        if self.widget and widget_state and hasattr(self.widget, 'set_state'):
            showlog.debug("*[STEP 8] Calling widget.set_state()")
            self.widget.set_state(widget_state)
            showlog.debug(f"*[STEP 9] Widget.set_state() completed")
        
        if self.widget:
            self.widget.mark_dirty()
            
        # Force full frame redraws to show loaded preset
        try:
            import dialhandlers
            if hasattr(dialhandlers, 'msg_queue') and dialhandlers.msg_queue:
                dialhandlers.msg_queue.put(("force_redraw", 3))
        except Exception as e:
            showlog.debug(f"[ASCIIAnimator] UI refresh skipped: {e}")


# ----------------------------------------------------------------------
# Plugin registration
# ----------------------------------------------------------------------
class ASCIIAnimatorPlugin(Plugin):
    """ASCII Animator plugin registration."""
    
    name = PLUGIN_NAME
    version = "0.1.0"
    category = "utility"
    author = "System"
    description = PLUGIN_DESC
    icon = "ascii.png"
    page_id = PLUGIN_ID
    
    def on_load(self, app):
        """Register page with module_base."""
        try:
            from pages import module_base as page
            
            rendering_meta = {
                "fps_mode": "high",              # Match VK8M for smooth overlay rendering
                "supports_dirty_rect": True,
                "burst_multiplier": 1.0,
            }
            
            app.page_registry.register(
                self.page_id,
                page,  # Register module_base, NOT a custom page!
                label=self.name,
                meta={"rendering": rendering_meta}
            )
            showlog.info(f"[ASCIIAnimatorPlugin] Registered page '{self.page_id}'")
        except Exception as e:
            import traceback
            showlog.error(f"[ASCIIAnimatorPlugin] Failed to register: {e}")
            showlog.error(traceback.format_exc())


# Legacy exports for module_base compatibility
MODULE_ID = ASCIIAnimatorModule.MODULE_ID
REGISTRY = ASCIIAnimatorModule.REGISTRY
BUTTONS = ASCIIAnimatorModule.BUTTONS
SLOT_TO_CTRL = ASCIIAnimatorModule.SLOT_TO_CTRL

# Export Plugin class for auto-discovery
Plugin = ASCIIAnimatorPlugin

