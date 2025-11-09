# /build/widgets/drawbar_widget.py
import pygame
import math
import time
import config as cfg
import showlog
import helper
from widgets.dirty_mixin import DirtyWidgetMixin
from typing import Optional, Callable, Dict, Tuple


class DrawBarWidget(DirtyWidgetMixin):
    """
    A DrawBarWidget is an organ style widget that displays horizontal draw bars.
    """
    
    # Default initialization state (can be overridden by plugin)
    INIT_STATE = {
        "drawbars": [8, 7, 6, 5, 4, 3, 2, 1, 0]
    }
    
    def __init__(
        self,
        rect: pygame.Rect,
        on_change: Optional[Callable[[Dict], None]] = None,
        theme: Optional[Dict[str, Tuple[int, int, int]]] = None,
        init_state: Optional[Dict] = None,
    ):
        super().__init__()
        self.rect = pygame.Rect(rect)
        self.on_change = on_change
        self.on_change = on_change
        
        showlog.info(f"[DrawBarWidget] __init__ called! rect={rect}, theme={theme}")
        
        # Theme colors (with fallbacks)
        th = theme or {}
        
        showlog.info(f"[DrawBarWidget] Raw theme dict: {th}")
        
        def _rgb3(c):
            return tuple(c[:3]) if isinstance(c, (list, tuple)) else c
        
        # Use theme colors if provided, otherwise fall back to config
        self.col_panel = _rgb3(th.get("bg")) if "bg" in th else helper.hex_to_rgb(cfg.DIAL_PANEL_COLOR)
        showlog.info(f"*[DrawBarWidget] Using col_panel: {self.col_panel} (from {'theme' if 'bg' in th else 'config'})")
        
        # Fill and outline from theme
        self.col_fill = _rgb3(th.get("fill")) if "fill" in th else helper.hex_to_rgb(cfg.DIAL_FILL_COLOR)
        self.col_outline = _rgb3(th.get("outline")) if "outline" in th else helper.hex_to_rgb(cfg.DIAL_OUTLINE_COLOR)
        
        showlog.info(f"*[DrawBarWidget] Colors - fill: {self.col_fill}, outline: {self.col_outline}")
        
        # Get button colors from theme (for drawbar sticks)
        # The sticks should match the button colors from the active theme
        from helper import device_theme
        import dialhandlers
        device_name = getattr(dialhandlers, "current_device_name", None)
        
        # Try to get button colors from theme first, fall back to config
        button_fill_hex = device_theme.get(device_name, "button_fill", cfg.BUTTON_FILL if hasattr(cfg, 'BUTTON_FILL') else '#071C3C')
        button_outline_hex = device_theme.get(device_name, "button_outline", cfg.BUTTON_OUTLINE if hasattr(cfg, 'BUTTON_OUTLINE') else '#0D3A7A')
        
        self.col_button_fill = helper.hex_to_rgb(button_fill_hex)
        self.col_button_outline = helper.hex_to_rgb(button_outline_hex)
        self.button_outline_width = 2  # Same as buttons
        
        showlog.info(f"*[DrawBarWidget] Button colors - fill: {self.col_button_fill}, outline: {self.col_button_outline}")
        
        # Get dial label styling for numbers - use theme color
        dial_text_hex = device_theme.get(device_name, "dial_text_color", cfg.DIAL_TEXT_COLOR if hasattr(cfg, 'DIAL_TEXT_COLOR') else '#FFFFFF')
        self.label_color = helper.hex_to_rgb(dial_text_hex)
        
        import utils.font_helper as font_helper
        font_path = font_helper.main_font("Bold")
        self.label_font = pygame.font.Font(font_path, cfg.DIAL_FONT_SIZE)
        
        # Title font for "DRAWBAR" label - slightly bigger and white
        self.title_font_size = cfg.DIAL_FONT_SIZE + 6  # Adjust this number to change size
        self.title_font = pygame.font.Font(font_path, self.title_font_size)
        self.title_color = (255, 255, 255)  # White
        
        self.col_fill = _rgb3(th.get("fill", helper.hex_to_rgb(cfg.DIAL_FILL_COLOR)))
        
        outline_src = th.get("outline", helper.hex_to_rgb(cfg.DIAL_OUTLINE_COLOR))
        if isinstance(outline_src, str) and outline_src.startswith("#"):
            outline_src = helper.hex_to_rgb(outline_src)
        self.col_outline = _rgb3(outline_src)
        
        showlog.info(f"[DrawBarWidget] Colors: panel={self.col_panel}, fill={self.col_fill}, outline={self.col_outline}")

        # Absolute dimensions based on dial sizing for visual coherence
        self.dial_panel_height = (cfg.DIAL_SIZE * 2) + 20  # 120px - matches dial panel
        
        # Blue background rectangle - NO padding since rect already accounts for dial panel size
        # The rect from grid system already has the dial panel boundaries
        self.background_rect = pygame.Rect(
            self.rect.x,
            self.rect.y,
            self.rect.width,
            self.dial_panel_height
        )
        
        showlog.info(f"[DrawBarWidget] background_rect={self.background_rect}")
        
        # Drawbar configuration
        self.num_bars = 9
        self.bar_width = 18
        self.bar_height = 220
        self.bar_spacing = self.rect.width / self.num_bars  # Evenly distribute across widget width
        
        # Organ drawbar labels (footage markings) - using decimals for simplicity
        self.bar_labels = ["16", "5.3", "8", "4", "2.7", "2", "1.6", "1.3", "1"]
        
        # Square at bottom (same as mixer mute button)
        self.square_size = cfg.MIXER_MUTE_WIDTH  # 28x28
        self.square_radius = cfg.MIXER_CORNER_RADIUS  # 6
        
        # Initialize bar values (0-8 range for organ drawbars, 8 = fully out)
        self.bar_values = [8] * self.num_bars  # Start with all bars fully out
        
        # Calculate bar positions
        self.bars = []
        
        # Use init_state if provided, otherwise use class default
        init = init_state or self.INIT_STATE
        initial_values = init.get("drawbars", [8, 7, 6, 5, 4, 3, 2, 1, 0])
        
        showlog.info(f"[DrawBarWidget] Initializing drawbars with values: {initial_values}")
        
        for i in range(self.num_bars):
            bar_x = self.background_rect.x + (i + 0.5) * self.bar_spacing - self.bar_width / 2
            bar_rect = pygame.Rect(int(bar_x), 0, self.bar_width, self.bar_height)
            
            # Square at bottom of bar
            square_x = bar_x + (self.bar_width - self.square_size) / 2
            square_rect = pygame.Rect(int(square_x), 0, self.square_size, self.square_size)
            
            self.bars.append({
                "bar_rect": bar_rect,
                "square_rect": square_rect,
                "value": initial_values[i]
            })
        
        showlog.info(f"[DrawBarWidget] Created {self.num_bars} drawbars")
        
        # Simple interaction state
        self.dragging = False
        self.dragging_bar = None  # Which bar is being dragged
        
        # Animation system
        self.animation_enabled = False
        self.animation_pattern = "off"  # Current pattern: "off", "wave", "bounce", "pulse", "chase", "random", "preset"
        self.animation_speed = 1  # Speed multiplier: 1=normal, 2=half speed, 4=quarter speed
        self.animation_frame_counter = 0  # Frame skip counter (increments every frame at 100 FPS)
        self.animation_logic_counter = 0  # Logic counter (increments only when processing at reduced FPS)
        self.saved_bar_values = None  # Store original values before animation
        self.last_sent_values = [None] * self.num_bars  # Track last SysEx value sent per bar
        
        # Preset animation data (loaded from external files)
        self.preset_frames = None  # List of frames: [[val0,val1,...,val8], [val0,val1,...], ...]
        self.preset_frame_index = 0  # Current frame being played
        self.preset_frame_ms = 2.0  # Fixed at 80ms per frame (matches ASCII animator)
        self.preset_last_advance_ms = 0.0  # Timestamp of last frame advance
        self.next_frame_time = 0.0  # When the next frame should arrive
        
        # SysEx send queue for staggered transmission
        self.sysex_send_queue = []  # List of (send_time_ms, bar_index, value) tuples
        
        # Speed dial (mini dial in top left corner for animation speed control)
        from assets.dial import Dial
        speed_dial_radius = cfg.DIAL_SIZE // 2  # Half size (50 / 2 = 25)
        speed_dial_x = self.background_rect.x + 35  # 25px from left edge
        speed_dial_y = self.background_rect.y + 35  # 25px from top edge
        self.speed_dial = Dial(speed_dial_x, speed_dial_y, radius=speed_dial_radius)
        self.speed_dial.id = 2  # ID 2 so it responds to dial 2 CC messages
        self.speed_dial.label = "SPEED"
        self.speed_dial.range = [0, 127]  # Standard MIDI range
        self.speed_dial.value = 2  # Default to 2 (maps to ~25ms)
        try:
            self.speed_dial.set_visual_mode("hidden")  # Skip default dial rendering pipeline
        except ValueError:
            self.speed_dial.visual_mode = "hidden"
        self.speed_dial_dragging = False
        
        # Initialize animation speed from dial's initial value
        self._update_speed_from_dial()

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------
    
    def start_animation(self):
        """Start the animation sequence."""
        import time
        start_time_ms = time.time() * 1000.0
        if not self.animation_enabled:
            # Save current bar values
            self.saved_bar_values = [bar["value"] for bar in self.bars]
            # Reset tracking so first frame sends current positions
            self.last_sent_values = [None] * self.num_bars
            self.animation_enabled = True
            self.animation_logic_counter = 0  # Reset logic counter for smooth start
            
            # Initialize timing for preset animations - set to past so first frame advances immediately
            self.preset_last_advance_ms = start_time_ms - self.preset_frame_ms
            self._animation_start_time = start_time_ms  # Store for timing measurement
            self._second_frame_reached = False
            
            showlog.info(f"*[TIMER 1] Animation start_animation() called at {start_time_ms:.2f}ms")
    
    def stop_animation(self):
        """Stop the animation and restore original values."""
        showlog.info("[DrawBarWidget] stop_animation() called")
        if self.animation_enabled:
            self.animation_enabled = False
            # Restore saved values
            if self.saved_bar_values:
                for i, value in enumerate(self.saved_bar_values):
                    self.bars[i]["value"] = value
                showlog.info(f"[DrawBarWidget] Restored values: {self.saved_bar_values}")
                self.saved_bar_values = None
            showlog.info("[DrawBarWidget] Animation stopped!")
        else:
            showlog.info("[DrawBarWidget] Animation not running, ignoring stop request")
    
    def toggle_animation(self):
        """Toggle animation on/off."""
        showlog.info(f"[DrawBarWidget] toggle_animation() called, current state={self.animation_enabled}")
        if self.animation_enabled:
            self.stop_animation()
        else:
            self.start_animation()
    
    def cycle_pattern(self):
        """Cycle through animation patterns."""
        patterns = ["off", "wave", "bounce", "pulse", "chase", "random"]
        current_index = patterns.index(self.animation_pattern) if self.animation_pattern in patterns else 0
        next_index = (current_index + 1) % len(patterns)
        self.animation_pattern = patterns[next_index]
        
        # Stop animation if pattern is "off"
        if self.animation_pattern == "off":
            self.stop_animation()
        elif not self.animation_enabled:
            self.start_animation()
        
        showlog.info(f"[DrawBarWidget] Pattern changed to: {self.animation_pattern}")
        return self.animation_pattern
    
    def get_pattern_label(self):
        """Get display label for current pattern."""
        labels = {
            "off": "OFF",
            "wave": "A1", 
            "bounce": "A2", 
            "pulse": "A3",
            "chase": "A4",
            "random": "A5",
            "preset": "ANIM"
        }
        return labels.get(self.animation_pattern, "OFF")
    
    def load_animation(self, frames):
        """
        Load animation frames from external source (e.g., ASCII animator preset).
        
        Args:
            frames: List of frames, where each frame is a list of 9 drawbar values (0-8).
                    Example: [[4,7,8,7,5,3,1,0,1], [4,7,8,7,5,2,0,0,2], ...]
        """
        showlog.info(f"*[DRAWBAR LOAD 1] load_animation() called with {len(frames) if frames else 0} frames")
        if not frames:
            showlog.warn("*[DRAWBAR LOAD 2] No frames provided to load_animation()")
            return
        
        showlog.debug(f"*[DRAWBAR LOAD 3] First frame: {frames[0]}")
        
        self.preset_frames = frames
        self.preset_frame_index = 0
        self.animation_pattern = "preset"  # Switch to preset playback mode
        
        showlog.info(f"[DrawBarWidget] Loaded {len(frames)} animation frames, pattern set to 'preset'")
        showlog.debug(f"*[DRAWBAR LOAD 4] Animation pattern now: {self.animation_pattern}")
    
    def update_speed_dial(self, value: int):
        """
        Update speed dial from external source (e.g., MIDI CC).
        
        Args:
            value: MIDI CC value (0-127)
        """
        self.speed_dial.set_value(value)
        self._update_speed_from_dial()
        self.mark_dirty()

    def set_speed_dial_visible(self, visible: bool):
        """Toggle the stock dial renderer for the speed control."""
        mode = "visible" if visible else "hidden"
        try:
            self.speed_dial.set_visual_mode(mode)
        except ValueError:
            self.speed_dial.visual_mode = "default" if visible else "hidden"

        # Also update the grid dial so the UI reflects the change
        try:
            from pages import module_base
            module_base.set_dial_visibility(getattr(self.speed_dial, "id", 0), visible)
        except Exception as exc:
            showlog.warn(f"[DrawBarWidget] Failed to sync dial visibility: {exc}")

        self.mark_dirty()
    
    def get_speed_dial(self):
        """Get the speed dial for external registration (e.g., MIDI mapping)."""
        return self.speed_dial
    
    def update_animation(self):
        """Update animation state - call this each frame."""
        if not self.animation_enabled:
            return
        
        # Log the FIRST time update_animation is called after starting
        if hasattr(self, '_animation_start_time') and not hasattr(self, '_first_update_logged'):
            import time
            now = time.time() * 1000.0
            elapsed = now - self._animation_start_time
            showlog.info(f"[TIMER 1.5] First update_animation() call! Elapsed: {elapsed:.2f}ms from start_animation()")
            self._first_update_logged = True
            self._last_update_time = now
        
        # Log every update_animation call to see the gaps
        if hasattr(self, '_last_update_time'):
            import time
            now = time.time() * 1000.0
            gap = now - self._last_update_time
            if gap > 50:  # Only log if gap is > 50ms (abnormal)
                showlog.warn(f"[UPDATE GAP] update_animation() called after {gap:.2f}ms gap (abnormal!)")
            self._last_update_time = now
        
        # Only preset animations are supported
        if self.animation_pattern == "preset":
            self.anim_preset()
            return
    
    def anim_preset(self):
        """Pattern: Preset - play through animation frames at fixed rate controlled by preset_frame_ms."""
        if not self.preset_frames:
            return
        
        now = time.time() * 1000.0
        
        # FIRST: Process any pending sysex sends from the queue (send ONE per frame call)
        if self.sysex_send_queue:
            # Send the FIRST message that is due
            send_time, bar_index, value = self.sysex_send_queue[0]
            if now >= send_time:
                # Send the sysex
                try:
                    from drivers import vk8m
                    vk8m.set_drawbar(bar_index + 1, value)
                    self.last_sent_values[bar_index] = value
                    elapsed_since_scheduled = now - send_time
                    showlog.debug(f"*[SYSEX SENT] t={now:.2f}ms | bar={bar_index} | val={value} | delay={elapsed_since_scheduled:.2f}ms")
                except Exception as e:
                    showlog.error(f"[DrawBarWidget] Failed to send queued sysex for bar {bar_index}: {e}")
                
                # Remove only this message
                self.sysex_send_queue.pop(0)
        
        # SECOND: Check if it's time to advance to next frame
        if self.preset_last_advance_ms == 0.0:
            self.preset_last_advance_ms = now
        
        elapsed = now - self.preset_last_advance_ms
        
        if elapsed < self.preset_frame_ms:
            return  # Not time to advance yet
        
        # Check for frame overlap (should never happen)
        if self.sysex_send_queue:
            showlog.warn(f"[DrawBarWidget] Frame overlap detected! {len(self.sysex_send_queue)} unsent messages. Clearing queue.")
            self.sysex_send_queue.clear()
        
        # Time to advance frame
        old_frame = self.preset_frame_index
        self.preset_last_advance_ms = now
        self.next_frame_time = now + self.preset_frame_ms
        
        # Get current frame (format: [frame_idx, val0, val1, ..., val8] or just [val0, val1, ..., val8])
        frame = self.preset_frames[self.preset_frame_index]
        
        # Skip first element if it's the frame index (detect by checking if we have 10 elements)
        start_idx = 1 if len(frame) > 9 else 0
        
        # Update all bar visual values immediately
        changed_bars = []
        for i in range(min(self.num_bars, len(frame) - start_idx)):
            new_value = int(frame[i + start_idx])
            new_value = max(0, min(8, new_value))  # Clamp to 0-8
            
            self.bars[i]["value"] = new_value
            
            # Track which bars changed (compared to last SENT value, not current visual)
            if self.last_sent_values[i] != new_value:
                changed_bars.append((i, new_value))
        
        # Schedule sysex sends for changed bars
        if changed_bars:
            num_changes = len(changed_bars)
            bar_indices = [idx for idx, _ in changed_bars]
            
            if num_changes == 1:
                # Single bar: send immediately
                bar_idx, value = changed_bars[0]
                self.sysex_send_queue.append((now, bar_idx, value))
                showlog.debug(f"*[QUEUE] Frame {old_frame}: {num_changes} change | bars={bar_indices} | interval=0ms (immediate)")
            else:
                # Multiple bars: spread across frame duration
                interval = self.preset_frame_ms / num_changes
                for idx, (bar_idx, value) in enumerate(changed_bars):
                    send_time = now + (idx * interval)
                    self.sysex_send_queue.append((send_time, bar_idx, value))
                
                showlog.debug(f"*[QUEUE] Frame {old_frame}: {num_changes} changes | bars={bar_indices} | interval={interval:.2f}ms")
        
        # Advance to next frame
        self.preset_frame_index = (self.preset_frame_index + 1) % len(self.preset_frames)
        
        # Debug every 10 frames
        if old_frame % 10 == 0:
            showlog.debug(f"*[FRAME ADVANCE] Frame {old_frame} -> {self.preset_frame_index} at t={now:.2f}ms")
        
        # Timing debug for frame 1
        if hasattr(self, '_animation_start_time') and not self._second_frame_reached and old_frame == 1:
            time_to_second_frame = now - self._animation_start_time
            showlog.info(f"*[TIMER 2] Second frame displayed! Elapsed: {time_to_second_frame:.2f}ms from start_animation()")
            self._second_frame_reached = True
    
    
    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------
    def handle_event(self, event) -> bool:
        """Return True if the event was consumed."""
        if event.type == pygame.MOUSEBUTTONDOWN and hasattr(event, "pos"):
            showlog.info(f"[DrawBarWidget] MOUSE DOWN at {event.pos}, rect={self.rect}")
            
            # Check if click hits speed dial first
            dx = event.pos[0] - self.speed_dial.cx
            dy = event.pos[1] - self.speed_dial.cy
            if (dx * dx + dy * dy) <= (self.speed_dial.radius * self.speed_dial.radius):
                showlog.info("[DrawBarWidget] HIT SPEED DIAL!")
                self.speed_dial_dragging = True
                self.speed_dial.dragging = True
                self.speed_dial.update_from_mouse(event.pos[0], event.pos[1])
                self._update_speed_from_dial()
                self.mark_dirty()
                return True
            
            # Check if click hits any bar
            for i, bar in enumerate(self.bars):
                if self._hit_bar(event.pos, i):
                    showlog.info(f"[DrawBarWidget] HIT BAR {i}!")
                    self.dragging = True
                    self.dragging_bar = i
                    # Update value immediately on click
                    self._update_bar_from_mouse(i, event.pos[1])
                    showlog.info(f"[DrawBarWidget] MOUSE DOWN returning True, dirty={self.is_dirty()}")
                    return True
            showlog.info(f"[DrawBarWidget] No bar hit")
        elif event.type == pygame.MOUSEBUTTONUP:
            showlog.info(f"[DrawBarWidget] MOUSE UP, was dragging={self.dragging}")
            if self.speed_dial_dragging:
                self.speed_dial_dragging = False
                self.speed_dial.dragging = False
                self.speed_dial.on_mouse_up()
            self.dragging = False
            self.dragging_bar = None
        elif event.type == pygame.MOUSEMOTION:
            if self.speed_dial_dragging:
                # Update speed dial while dragging
                self.speed_dial.update_from_mouse(event.pos[0], event.pos[1])
                self._update_speed_from_dial()
                self.mark_dirty()
                return True
            elif self.dragging and self.dragging_bar is not None:
                # Update bar position while dragging
                showlog.info(f"[DrawBarWidget] MOUSE MOTION while dragging bar {self.dragging_bar}")
                self._update_bar_from_mouse(self.dragging_bar, event.pos[1])
                self.mark_dirty()
                showlog.info(f"[DrawBarWidget] MOTION returning True, dirty={self.is_dirty()}")
                return True
        return False
    
    def _update_speed_from_dial(self):
        """Update preset_frame_ms from speed dial value (200ms to 10ms for slow-to-fast)."""
        # Invert: dial 0 = slow (200ms), dial 127 = fast (10ms)
        t = self.speed_dial.value / 127.0
        old_frame_ms = self.preset_frame_ms
        self.preset_frame_ms = 200.0 - (t * 190.0)  # 200 - (0→190) = 200→10
        showlog.info(f"[DrawBarWidget] Speed updated from {old_frame_ms:.1f}ms to {self.preset_frame_ms:.1f}ms per frame")
        
        # If there are unsent messages in the queue, reschedule them with new timing
        if self.sysex_send_queue:
            now = time.time() * 1000.0
            
            # Recalculate when next frame will arrive with NEW timing
            self.next_frame_time = self.preset_last_advance_ms + self.preset_frame_ms
            remaining_time = self.next_frame_time - now
            
            if remaining_time <= 0:
                # No time left - send all immediately
                showlog.warn(f"[DrawBarWidget] Speed change leaves no time! Sending {len(self.sysex_send_queue)} messages immediately")
                for send_time, bar_idx, value in self.sysex_send_queue:
                    try:
                        from drivers import vk8m
                        vk8m.set_drawbar(bar_idx + 1, value)
                        self.last_sent_values[bar_idx] = value
                    except Exception as e:
                        showlog.error(f"[DrawBarWidget] Failed to send immediate sysex for bar {bar_idx}: {e}")
                self.sysex_send_queue.clear()
            else:
                # Reschedule unsent messages across remaining time
                unsent_messages = []
                messages_to_send_now = []
                
                for send_time, bar_idx, value in self.sysex_send_queue:
                    if now >= send_time:
                        # This message is overdue - send immediately
                        messages_to_send_now.append((bar_idx, value))
                    else:
                        # Keep for rescheduling
                        unsent_messages.append((bar_idx, value))
                
                # Send overdue messages immediately
                for bar_idx, value in messages_to_send_now:
                    try:
                        from drivers import vk8m
                        vk8m.set_drawbar(bar_idx + 1, value)
                        self.last_sent_values[bar_idx] = value
                        showlog.debug(f"[DrawBarWidget] Sent overdue message: bar {bar_idx}")
                    except Exception as e:
                        showlog.error(f"[DrawBarWidget] Failed to send overdue sysex for bar {bar_idx}: {e}")
                
                # Reschedule remaining messages
                if unsent_messages:
                    num_unsent = len(unsent_messages)
                    new_interval = remaining_time / num_unsent
                    bar_indices = [bar_idx for bar_idx, _ in unsent_messages]
                    
                    self.sysex_send_queue.clear()
                    for idx, (bar_idx, value) in enumerate(unsent_messages):
                        new_send_time = now + (idx * new_interval)
                        self.sysex_send_queue.append((new_send_time, bar_idx, value))
                    
                    showlog.info(f"*[RESCHEDULE] Speed {old_frame_ms:.1f}→{self.preset_frame_ms:.1f}ms | {num_unsent} unsent bars={bar_indices} | new_interval={new_interval:.2f}ms | remaining={remaining_time:.2f}ms")
                else:
                    # All messages were sent
                    self.sysex_send_queue.clear()
    
    def _hit_bar(self, pos, bar_index) -> bool:
        """Check if position hits a specific bar's horizontal region in the drawable area."""
        # Check X position (horizontal hit test)
        bar_x_center = self.background_rect.x + (bar_index + 0.5) * self.bar_spacing
        hit_width = self.bar_spacing  # Allow clicking anywhere in the bar's column
        x_hit = abs(pos[0] - bar_x_center) < hit_width / 2
        
        # Check Y position (must be in the area below the blue rect where bars can move)
        bar_area_top = self.background_rect.bottom
        bar_area_bottom = self.rect.bottom
        y_hit = bar_area_top <= pos[1] <= bar_area_bottom
        
        return x_hit and y_hit
    
    def _update_bar_from_mouse(self, bar_index: int, mouse_y: int):
        """Update bar value based on mouse Y position and send SysEx. Snaps to nearest position 0-8."""
        # Calculate the drawable area positions (matching the draw method)
        top_position = self.background_rect.bottom + 12  # 12px below blue rect (position 0)
        bottom_position = self.rect.bottom  # Flush with grid bottom (position 8)
        
        # Calculate travel range (where square bottoms can be)
        travel_range = bottom_position - top_position - self.square_size
        
        # Clamp mouse Y to valid range
        clamped_y = max(top_position, min(bottom_position - self.square_size, mouse_y))
        
        # Map Y position to value 0-8 (0 = top/fully out, 8 = bottom/fully in)
        # Calculate relative position
        relative_y = clamped_y - top_position
        t = relative_y / travel_range if travel_range > 0 else 0.0
        
        # Snap to nearest integer position 0-8
        new_value = int(round(t * 8))
        new_value = max(0, min(8, new_value))
        
        # Only update if value changed
        if self.bars[bar_index]["value"] != new_value:
            showlog.info(f"[DrawBarWidget] BEFORE UPDATE: bar {bar_index} value in array = {self.bars[bar_index]['value']}")
            self.bars[bar_index]["value"] = new_value
            showlog.info(f"[DrawBarWidget] AFTER UPDATE: bar {bar_index} value in array = {self.bars[bar_index]['value']}")
            showlog.info(f"[DrawBarWidget] Updating bar {bar_index}: old → {new_value}")
            
            # Send SysEx to VK-8M (index is 1-9, not 0-8)
            try:
                from drivers import vk8m
                vk8m.set_drawbar(bar_index + 1, new_value)
                showlog.info(f"[DrawBarWidget] Drawbar {bar_index + 1} set to {new_value}")
            except Exception as e:
                showlog.warn(f"[DrawBarWidget] Failed to send drawbar SysEx: {e}")
            
            self.mark_dirty()
            showlog.info(f"[DrawBarWidget] Marked dirty! is_dirty={self.is_dirty()}")
            
            # Call on_change callback if provided
            if self.on_change:
                self.on_change({"bar_index": bar_index, "value": new_value})
        else:
            showlog.info(f"[DrawBarWidget] Bar {bar_index} already at value {new_value}, no update")

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def draw(self, surface: pygame.Surface, device_name=None, offset_y=0):
        """
        Draw the drawbar widget with blue background panel.
        Returns the dirty rect that was drawn.
        """
        import pygame.gfxdraw  # Import at method level to avoid scope issues
        
        # Log during the critical first 500ms after animation starts
        if hasattr(self, '_animation_start_time') and not hasattr(self, '_draw_log_done'):
            import time
            now = time.time() * 1000.0
            elapsed = now - self._animation_start_time
            if elapsed < 500:
                showlog.info(f"*[DRAW] draw() called at {elapsed:.2f}ms, frame_index={self.preset_frame_index}")
            else:
                self._draw_log_done = True
        
        try:
            # Apply offset if provided
            draw_rect = self.background_rect.move(0, offset_y)
            full_rect = self.rect.copy()
            full_rect.y += offset_y
            
            showlog.debug(f"[DrawBarWidget] DRAWING! rect={draw_rect}, color={self.col_panel}, animating={self.animation_enabled}")
            
            # Clear the entire widget area first by filling with black (or background color)
            from helper import theme_rgb
            bg_color = theme_rgb(device_name, "PAGE_BG_COLOR", default=(0, 0, 0))
            pygame.draw.rect(surface, bg_color, full_rect)
            
            # Draw each drawbar FIRST (so top rect overlays them)
            for i, bar in enumerate(self.bars):
                # Position bar vertically based on value (0 = fully out/top, 8 = fully in/bottom)
                value = bar["value"]
                if i == 0:
                    showlog.verbose(f"[DrawBarWidget] Drawing bar {i}: value={value}")
                
                # Calculate drawable area positions (use draw_rect which has offset applied)
                # Value 0: square bottom at 12px below blue rect
                # Value 8: square bottom flush with rect.bottom (no padding)
                top_position = draw_rect.bottom + 12  # 12px below blue rect (with offset)
                bottom_position = self.rect.bottom + offset_y  # Flush with grid bottom (with offset)
                
                # Calculate where the square bottom should be
                travel_range = bottom_position - top_position - self.square_size
                square_bottom_y = top_position + self.square_size + (travel_range * value / 8.0)
                square_y = square_bottom_y - self.square_size
                
                if i == 0:
                    showlog.verbose(f"[DrawBarWidget] Bar {i}: square_y={int(square_y)}, travel_range={int(travel_range)}, value={value}")
                
                # Calculate bar height: shrink as it moves up so it doesn't poke out the top
                max_bar_height = self.bar_height
                current_bar_height = square_y - self.background_rect.bottom + self.square_size / 2
                current_bar_height = min(max_bar_height, max(0, current_bar_height))

                bar_y = square_y - current_bar_height + self.square_size / 2 - 5  # Move up 5px
                
                if i == 0:
                    showlog.verbose(f"[DrawBarWidget] Bar {i}: bar_y={int(bar_y)}, bar_height={int(current_bar_height)}")

                bar_rect = bar["bar_rect"].copy()
                bar_rect.y = int(bar_y)
                bar_rect.height = int(current_bar_height)
                
                # Draw bar stick (dark grey button fill color with outline)
                pygame.draw.rect(
                    surface,
                    self.col_button_fill,
                    bar_rect
                )
                
                # Draw bar outline
                pygame.draw.rect(
                    surface,
                    self.col_button_outline,
                    bar_rect,
                    width=self.button_outline_width
                )
                
                # Draw square at bottom of bar (use dial panel color from theme)
                square_rect = bar["square_rect"].copy()
                square_rect.y = int(square_y)
                
                pygame.draw.rect(
                    surface,
                    self.col_panel,  # Use dial panel background color (brown rect behind dial)
                    square_rect,
                    border_radius=self.square_radius
                )
                
                # Draw number inside square (dial label style) - show current value 0-8
                number_text = self.label_font.render(str(bar["value"]), True, self.label_color)
                text_rect = number_text.get_rect(center=square_rect.center)
                surface.blit(number_text, text_rect)
            
            # Draw rounded rectangle at top (use dial panel background color - overlays the bars)
            pygame.draw.rect(
                surface,
                self.col_panel,  # Use dial panel background (brown rect behind dial)
                draw_rect,
                border_radius=15
            )
            
            # Draw "DRAWBAR" title in top right corner of blue rect
            title_text = self.title_font.render("DRAWBAR", True, self.title_color)
            title_padding = 10
            title_x = draw_rect.right - title_text.get_width() - title_padding
            title_y = draw_rect.top + title_padding
            surface.blit(title_text, (title_x, title_y))
            
            # Draw speed dial in top left corner (always visible)
            # Apply offset to dial position
            dial_cx = self.speed_dial.cx
            dial_cy = self.speed_dial.cy + offset_y
            dial_r = int(self.speed_dial.radius)
            
            # Dial colors (use theme colors)
            dial_fill = self.col_fill
            dial_outline = self.col_outline
            dial_text = self.label_color
            
            # Draw small panel behind dial (same style as big dials, scaled down)
            panel_size = dial_r * 2 + 5  # Smaller padding for mini dial
            panel_rect = pygame.Rect(0, 0, panel_size, panel_size)
            panel_rect.center = (dial_cx, dial_cy)
            pygame.draw.rect(surface, self.col_panel, panel_rect, border_radius=4)
            
            # Draw dial circle
            pygame.gfxdraw.filled_circle(surface, dial_cx, dial_cy, dial_r, dial_fill)
            pygame.gfxdraw.aacircle(surface, dial_cx, dial_cy, dial_r, dial_outline)
            
            # Draw pointer
            rad = math.radians(self.speed_dial.angle)
            x0 = dial_cx + (dial_r * 0.5) * math.cos(rad)
            y0 = dial_cy - (dial_r * 0.5) * math.sin(rad)
            x1 = dial_cx + dial_r * math.cos(rad)
            y1 = dial_cy - dial_r * math.sin(rad)
            pygame.draw.line(surface, dial_text, (int(x0), int(y0)), (int(x1), int(y1)), 2)
            
            # Draw label squares AFTER the blue rect so they appear on top
            for i, bar in enumerate(self.bars):
                # Draw label square at top (black square INSIDE the blue rect near bottom)
                label_padding = 12  # Padding from bottom of blue rect
                square_rect = bar["square_rect"].copy()
                label_square_rect = square_rect.copy()
                # Position inside the blue rectangle: bottom edge minus square height minus padding
                label_square_rect.y = draw_rect.bottom - self.square_size - label_padding
                
                pygame.draw.rect(
                    surface,
                    (0, 0, 0),  # Black
                    label_square_rect,
                    border_radius=self.square_radius
                )
                
                # Draw number in label square (same font/color as other numbers)
                label_number_text = self.label_font.render(self.bar_labels[i], True, self.label_color)
                label_text_rect = label_number_text.get_rect(center=label_square_rect.center)
                surface.blit(label_number_text, label_text_rect)
            
            showlog.verbose(f"[DrawBarWidget] Draw complete!")
            
            # Return the full widget rect (not just the blue background rect)
            # so the dirty rect system updates the entire area including the moving bars
            full_rect = self.rect.copy()
            full_rect.y += offset_y
            
            # Draw frame counter if we're in preset animation mode
            # Position below the entire widget area, aligned with where dial labels would be
            if self.animation_pattern == "preset" and self.preset_frames:
                frame_text = f"[ {self.preset_frame_index + 1:03d} / {len(self.preset_frames):03d} ]"
                frame_surf = self.label_font.render(frame_text, True, self.label_color)
                # Position below the full widget rect (where dial labels appear)
                # Dial labels are: dial_center.y + radius + 10
                # For drawbar: full_rect.bottom + 10 (same 10px spacing)
                frame_x = full_rect.right - frame_surf.get_width() - 10
                frame_y = full_rect.bottom + 10  # 10px below widget bottom (dial label spacing)
                
                # Draw black background rect behind counter (with small padding)
                counter_bg_rect = pygame.Rect(
                    frame_x - 3,
                    frame_y - 2,
                    frame_surf.get_width() + 6,
                    frame_surf.get_height() + 4
                )
                pygame.draw.rect(surface, (0, 0, 0), counter_bg_rect)
                
                # Draw counter text on top
                surface.blit(frame_surf, (frame_x, frame_y))
                
                # Expand dirty rect to include frame counter
                full_rect = full_rect.union(counter_bg_rect)
            
            return full_rect
        except Exception as e:
            showlog.warn(f"[DrawBarWidget] Draw failed: {e}")
            import traceback
            showlog.warn(traceback.format_exc())
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    
    def is_dirty(self):
        """Override to keep widget dirty during animation."""
        # If animating, always return True so we keep redrawing
        if self.animation_enabled:
            # Log during the critical first 500ms after animation starts
            if hasattr(self, '_animation_start_time') and not hasattr(self, '_dirty_check_done'):
                import time
                now = time.time() * 1000.0
                elapsed = now - self._animation_start_time
                if elapsed < 500:
                    showlog.info(f"*[DIRTY CHECK] is_dirty() called at {elapsed:.2f}ms, returning True (animating)")
                else:
                    self._dirty_check_done = True
            return True
        # Otherwise use parent's dirty flag
        return super().is_dirty()
    
    def clear_dirty(self):
        """Override to prevent clearing dirty flag during animation."""
        # If animating, don't clear the dirty flag (stay dirty for continuous redraw)
        if self.animation_enabled:
            return
        # Otherwise clear normally
        super().clear_dirty()
    
    def get_state(self) -> Dict:
        """Return current widget state for persistence."""
        return {
            "bar_values": [bar["value"] for bar in self.bars],
            "speed_dial_value": int(self.speed_dial.value) if hasattr(self.speed_dial, 'value') else 64
        }

    def set_from_state(self, **kwargs):
        """
        Restore widget state from saved data.
        
        If animation is running, updates both the live bars AND the saved values
        so that when animation stops, it shows the preset values, not pre-animation values.
        """
        bar_values = kwargs.get("bar_values", None)
        if bar_values and len(bar_values) == self.num_bars:
            for i, value in enumerate(bar_values):
                self.bars[i]["value"] = max(0, min(8, int(value)))
            
            # CRITICAL: If animation is running, update saved_bar_values too
            # so when animation stops, it restores to these preset values
            if self.animation_enabled and self.saved_bar_values is not None:
                self.saved_bar_values = [max(0, min(8, int(v))) for v in bar_values]
                showlog.info(f"[DrawBarWidget] Preset loaded during animation - updated saved_bar_values: {self.saved_bar_values}")
            
            self.mark_dirty()
        
        # Restore speed dial value
        speed_dial_value = kwargs.get("speed_dial_value", None)
        if speed_dial_value is not None and hasattr(self, 'speed_dial'):
            try:
                self.speed_dial.set_value(int(speed_dial_value))
                showlog.verbose(f"[DrawBarWidget] Restored speed dial to {speed_dial_value}")
            except Exception as e:
                showlog.warn(f"[DrawBarWidget] Failed to restore speed dial: {e}")
