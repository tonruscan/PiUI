# /widgets/ascii_animator_widget.py
# ASCII Animator Widget (4x2-capable), variable grid, play/pause/rtz, next/prev, add/del, preset hooks
# - Touch toggle per cell (tap = ON/OFF)
# - Drag paint (continues last toggle state)
# - ASCII box-drawing frame around a character-cell grid
# - Top-right overlay: [01 / 05]
# - Button map: 1(play/pause/rtz dbl tap), 2(next), 3(prev), 4(add), 5(del), 6(preset page), 7(preset saver)

from __future__ import annotations
import time
from typing import Callable, List, Optional, Tuple

import pygame
from widgets.dirty_mixin import DirtyWidgetMixin
import showlog
import config.styling as cfg

# Import grid system for proper positioning
try:
    from utils.grid_layout import get_zone_rect_tight
except Exception:
    def get_zone_rect_tight(row, col, w, h, geom=None):
        # Fallback if grid system not available
        return pygame.Rect(0, 0, 100, 100)

# Optional theming (same pattern used in your other widgets)
try:
    from helper import theme_rgb, hex_to_rgb
except Exception:
    def theme_rgb(device_name, key, default="#000000"):
        return (0, 0, 0)



class ASCIIAnimatorWidget(DirtyWidgetMixin):
    """
    ASCII animation editor/player for variable matrix sizes.
    Integrates with side-button map:
      1: play/pause (single tap), RTZ (double tap)
      2: next, 3: prev, 4: add (duplicate+append), 5: delete
      6: open preset page (external UI), 7: open preset saver (external UI)

    Public hooks (optional):
      on_open_preset_page: Callable[[], None]
      on_open_preset_saver: Callable[[], None]
    """

    def __init__(
        self,
        rect: pygame.Rect,
        on_change: Optional[Callable] = None,
        theme: Optional[dict] = None,
        grid_rows: int = 9,
        grid_cols: int = 9,
        fps: int = 24,
    ):
        super().__init__()
        self.rect = pygame.Rect(rect)
        self.on_change = on_change  # Callback for value changes
        self.theme = theme or {}    # Theme colors (optional)
        self.grid_rows = max(1, int(grid_rows))
        self.grid_cols = max(1, int(grid_cols))

        # Frames: each frame is rows x cols of bool (True="on")
        self.frames: List[List[List[bool]]] = [self._blank_frame(self.grid_rows, self.grid_cols)]
        self.current = 0
        self.playing = False
        self.loop = True
        self.fps = int(max(1, fps))
        self._frame_ms = 10.0  # Fixed at 10ms (0.01 seconds) per frame
        self._last_advance_ms = 0.0

        # Timer for measuring button press to second frame
        self._button_press_time = 0.0
        self._second_frame_reached = False

        # Input state
        self._drag_paint: Optional[bool] = None
        self._last_mouse_cell: Optional[Tuple[int, int]] = None

        # Double tap detection on button 1
        self._tap_time_ms = 0.0
        self._tap_gap_ms = 300.0

        # Frame list paging (show 20 frames at a time)
        self._frame_list_page = 0  # Current page (0 = frames 1-20, 1 = frames 21-40, etc.)
        self._frames_per_page = 20

        # Preset hooks (you can wire your standard preset UI here)
        self.on_open_preset_page: Optional[Callable[[], None]] = None
        self.on_open_preset_saver: Optional[Callable[[], None]] = None
        
        # Module reference for button label updates
        self._module = None

        # Font for ASCII rendering
        self._font: Optional[pygame.font.Font] = None
        self._ensure_font()

        # Geometry cache (computed per draw)
        self._cell_w = self._cell_h = 0
        self._grid_origin = (0, 0)  # top-left pixel of first cell
        self._char_w = self._char_h = 0
        
        # Container geometry for hit-testing
        self._container_rects: List[List[pygame.Rect]] = []  # [row][col] -> Rect
        self._container_cols = 0
        self._container_rows = 0
        
        # Frame list geometry for hit-testing
        self._frame_rects: List[pygame.Rect] = []  # [frame_index] -> Rect

        # A little padding inside rect for the CRT bezel
        self._pad = 10

        # Make redraws a bit forgiving
        self.set_dirty_padding(8, 8)
        self.mark_dirty()

    # ---------------------------------------------------------------------
    # Frame/state helpers
    # ---------------------------------------------------------------------
    def _blank_frame(self, r: int, c: int) -> List[List[bool]]:
        return [[False for _ in range(c)] for _ in range(r)]
    
    def _load_from_raw(self, raw_data, target_rows=None, target_cols=None):
        """
        Load frames from RAW CSV format.
        
        Accepts multiple formats:
        1. Array of arrays: [[0,4,7,8,...], [1,4,7,8,...], ...]
        2. String with newlines: "0,4,7,8,...\n1,4,7,8,...\n..."
        3. List of strings: ["0,4,7,8,...", "1,4,7,8,...", ...]
        
        Format: frame_idx,val0,val1,val2,...,val80
        OR: [frame_idx,val0,val1,val2,...,val80]
        
        Each row represents one frame's flattened 9x9 grid (81 values).
        Non-zero values = active cells.
        """
        try:
            showlog.debug(f"*[RAW 1] _load_from_raw called, data type: {type(raw_data)}, target grid: {target_rows}x{target_cols}")
            if isinstance(raw_data, list) and len(raw_data) > 0:
                showlog.debug(f"*[RAW 2] List with {len(raw_data)} items, first item type: {type(raw_data[0])}")
                if len(raw_data[0]) > 0:
                    showlog.debug(f"*[RAW 3] First item preview: {raw_data[0][:5] if isinstance(raw_data[0], (list, str)) else raw_data[0]}")
            
            frame_data = {}
            
            # Handle array of arrays (cleanest format)
            if isinstance(raw_data, list) and len(raw_data) > 0 and isinstance(raw_data[0], list):
                showlog.debug(f"*[RAW 4] Detected array-of-arrays format")
                # [[0,4,7,8,...], [1,4,7,8,...], ...]
                for idx, row in enumerate(raw_data):
                    if len(row) < 2:
                        showlog.debug(f"*[RAW 5] Skipping row {idx}: too short ({len(row)} items)")
                        continue
                    frame_idx = int(row[0])
                    values = [int(v) for v in row[1:]]
                    frame_data[frame_idx] = values
                    if idx < 3:  # Debug first 3 frames
                        showlog.debug(f"*[RAW 6] Frame {frame_idx}: {len(values)} values")
            
            # Handle string with newlines or list of strings
            else:
                showlog.debug(f"*[RAW 7] Using string/CSV parsing")
                if isinstance(raw_data, list):
                    lines = raw_data
                else:
                    lines = raw_data.strip().split('\n')
                
                # Parse CSV lines
                for idx, line in enumerate(lines):
                    if isinstance(line, str):
                        line = line.strip()
                    else:
                        line = str(line).strip()
                        
                    if not line:
                        continue
                        
                    parts = line.split(',')
                    if len(parts) < 2:
                        continue
                    
                    frame_idx = int(parts[0])
                    values = [int(v) for v in parts[1:]]
                    frame_data[frame_idx] = values
                    if idx < 3:  # Debug first 3 frames
                        showlog.debug(f"*[RAW 8] Frame {frame_idx}: {len(values)} values")
            
            if not frame_data:
                showlog.warn("*[RAW 9] No valid data found in raw input")
                return
            
            showlog.debug(f"*[RAW 10] Parsed {len(frame_data)} frames")
            
            # Determine grid size - use target if provided, otherwise infer
            max_len = max(len(vals) for vals in frame_data.values())
            
            if target_rows is not None and target_cols is not None:
                rows = target_rows
                cols = target_cols
                showlog.debug(f"*[RAW 11] Using target grid size: {rows}x{cols}, max_len={max_len}")
            else:
                rows = self.grid_rows
                cols = self.grid_cols
                expected = rows * cols
                
                showlog.debug(f"*[RAW 11] Max data length: {max_len}, expected: {expected} ({rows}x{cols})")
                
                if max_len != expected:
                    # Try to infer grid dimensions
                    # Assume square or 9x9 by default
                    import math
                    side = int(math.sqrt(max_len))
                    if side * side == max_len:
                        rows = cols = side
                        showlog.debug(f"*[RAW 12] Auto-detected square grid: {rows}x{cols}")
                    else:
                        # Try 9x9 if it fits
                        if max_len <= 81:
                            rows = cols = 9
                            showlog.debug(f"*[RAW 13] Using default 9x9 grid")
                        else:
                            showlog.warn(f"*[RAW 14] Unexpected data length {max_len}, using current grid {rows}x{cols}")
            
            self.set_grid_size(rows, cols, keep=False)
            showlog.debug(f"*[RAW 15] Grid size set to {rows}x{cols}")
            
            # Check if this is column-position format (9 values for 9x9 grid)
            is_column_position = (max_len == cols and rows == 9 and cols == 9)
            if is_column_position:
                showlog.debug(f"*[RAW 15b] Detected COLUMN-POSITION format (single cell per column)")
            
            # Convert to frames
            new_frames = []
            for frame_idx in sorted(frame_data.keys()):
                values = frame_data[frame_idx]
                nf = self._blank_frame(rows, cols)
                
                if is_column_position:
                    # Column-position format: each value is the row position (from bottom) for that column
                    # Value 4 means row 8-4+1 = row 5 (counting from bottom: 0=row8, 1=row8, 4=row5)
                    active_count = 0
                    for col_idx, position in enumerate(values):
                        if col_idx >= cols:
                            break
                        if position > 0:  # 0 means no cell in this column
                            row_idx = rows - int(position)  # Convert bottom-up to top-down index
                            if 0 <= row_idx < rows:
                                nf[row_idx][col_idx] = True
                                active_count += 1
                                if frame_idx == 0:  # Debug frame 0 only
                                    showlog.debug(f"*[RAW 16b] Frame 0, Col {col_idx}: position={position} -> row_idx={row_idx}")
                    
                    if frame_idx < 3:  # Debug first 3 frames
                        showlog.debug(f"*[RAW 16] Frame {frame_idx}: {active_count} active cells (positions: {values})")
                else:
                    # Flattened grid format: fill row by row
                    active_count = 0
                    for i, val in enumerate(values):
                        if i >= rows * cols:
                            break
                        row = i // cols
                        col = i % cols
                        nf[row][col] = (val != 0)  # Non-zero = active
                        if val != 0:
                            active_count += 1
                    
                    if frame_idx < 3:  # Debug first 3 frames
                        showlog.debug(f"*[RAW 16] Frame {frame_idx}: {active_count} active cells")
                
                new_frames.append(nf)
            
            self.frames = new_frames
            showlog.info(f"*[RAW 17] SUCCESS: Loaded {len(new_frames)} frames from RAW format ({rows}x{cols})")
            showlog.debug(f"*[RAW 18] self.frames[0][0][0] = {self.frames[0][0][0]} (type={type(self.frames[0][0][0])})")
            
        except Exception as e:
            showlog.error(f"[ASCIIAnim] Failed to parse RAW format: {e}")
            import traceback
            showlog.error(traceback.format_exc())

    def set_grid_size(self, rows: int, cols: int, keep: bool = True):
        """Change grid size; optionally remap current frames."""
        rows = max(1, int(rows))
        cols = max(1, int(cols))
        if (rows, cols) == (self.grid_rows, self.grid_cols):
            return

        new_frames: List[List[List[bool]]] = []
        for fr in self.frames:
            if keep:
                # Copy overlap region
                nf = self._blank_frame(rows, cols)
                rr = min(rows, len(fr))
                cc = min(cols, len(fr[0]) if fr else 0)
                for y in range(rr):
                    for x in range(cc):
                        nf[y][x] = bool(fr[y][x])
                new_frames.append(nf)
            else:
                new_frames.append(self._blank_frame(rows, cols))

        self.frames = new_frames or [self._blank_frame(rows, cols)]
        self.grid_rows, self.grid_cols = rows, cols
        self.current = min(self.current, len(self.frames) - 1)
        self.mark_dirty()

    def add_frame(self, duplicate_current: bool = True):
        base = self.frames[self.current]
        nf = [row[:] for row in base] if duplicate_current else self._blank_frame(self.grid_rows, self.grid_cols)
        self.frames.append(nf)
        self.current = len(self.frames) - 1
        self.mark_dirty()

    def delete_frame(self):
        if len(self.frames) <= 1:
            # keep at least one frame
            self.frames[0] = self._blank_frame(self.grid_rows, self.grid_cols)
            self.current = 0
        else:
            del self.frames[self.current]
            self.current = max(0, min(self.current, len(self.frames) - 1))
        self.mark_dirty()

    def next_frame(self, auto_create: bool = True):
        if self.current + 1 < len(self.frames):
            # Navigate to existing next frame
            old_frame = self.current
            self.current += 1
            
            # Check if we just reached frame 1 (second frame, 0-indexed)
            if hasattr(self, '_button_press_time') and self._button_press_time > 0 and not hasattr(self, '_second_frame_reached'):
                self._second_frame_reached = True
            if hasattr(self, '_button_press_time') and self._button_press_time > 0 and not self._second_frame_reached and self.current == 1:
                elapsed = time.time() * 1000.0 - self._button_press_time
                showlog.info(f"*[TIMER END] Second frame reached! Time from button press: {elapsed:.2f}ms")
                self._second_frame_reached = True
            
            # Update page if we've moved to a new page
            self._update_frame_page()
        elif auto_create:
            # At last frame, create new frame by duplicating current (only when manually triggered)
            base = self.frames[self.current]
            new_frame = [row[:] for row in base]  # Deep copy
            self.frames.append(new_frame)
            self.current = len(self.frames) - 1
            # Update page for the new frame
            self._update_frame_page()
        elif self.loop:
            # During playback, loop back to start
            self.current = 0
            self._frame_list_page = 0  # Reset to first page
        self.mark_dirty()

    def prev_frame(self):
        if self.current > 0:
            self.current -= 1
            # Update page if we've moved to a previous page
            self._update_frame_page()
        # No loop-back behavior - just stop at frame 0
        self.mark_dirty()
    
    def _update_frame_page(self):
        """Update the frame list page to show the current frame."""
        if self._frames_per_page > 0:
            new_page = self.current // self._frames_per_page
            if new_page != self._frame_list_page:
                self._frame_list_page = new_page
                showlog.debug(f"[ASCIIAnim] Frame page changed to {new_page} (showing frames {new_page * self._frames_per_page + 1}-{(new_page + 1) * self._frames_per_page})")

    def play_toggle(self):
        showlog.info(f"*[PLAY 1] play_toggle() called, current playing={self.playing}")
        self.playing = not self.playing
        showlog.info(f"*[PLAY 2] playing toggled to: {self.playing}")
        if self.playing:
            # When starting playback, initialize timing to start immediately
            now = time.time() * 1000.0
            showlog.info(f"*[PLAY 3] Starting playback, setting _last_advance_ms={now}")
            self._last_advance_ms = now
        else:
            # When stopping, reset timing
            showlog.info(f"*[PLAY 4] Stopping playback, resetting _last_advance_ms=0.0")
            self._last_advance_ms = 0.0
        showlog.info(f"*[PLAY 5] Calling mark_dirty()")
        self.mark_dirty()
        # Sync button state to module (for multi-state button)
        showlog.info(f"*[PLAY 6] Calling _sync_button_1_state()")
        self._sync_button_1_state()
        showlog.info(f"*[PLAY 7] play_toggle() complete")

    def rtz(self):
        self.current = 0
        self.playing = False
        self._last_advance_ms = 0.0  # Reset timing
        self.mark_dirty()
        # Sync button state to module
        self._sync_button_1_state()
    
    def _sync_button_1_state(self):
        """Sync button 1 state with module's button_states."""
        showlog.debug(f"*[SYNC 1] _sync_button_1_state() called, self._module={self._module is not None}")
        if hasattr(self, '_module') and self._module:
            try:
                showlog.debug(f"*[SYNC 2] Calling module._sync_button_1_state()")
                self._module._sync_button_1_state()
                showlog.debug(f"*[SYNC 3] module._sync_button_1_state() returned")
            except Exception as e:
                showlog.debug(f"[ASCIIAnim] Button state sync failed: {e}")

    # ---------------------------------------------------------------------
    # External button map (1..7)
    # ---------------------------------------------------------------------
    def handle_button(self, btn_id: int):
        """
        Wire your side buttons to this, e.g. from your page or module.
          1: tap = play/pause; double-tap = RTZ
          2: next
          3: prev
          4: add
          5: del
          6: open preset page (external)
          7: open preset saver (external)
        """
        showlog.info(f"*[BTN 1] handle_button() called with btn_id={btn_id}")
        now = time.time() * 1000.0
        if btn_id == 1:
            showlog.info(f"*[BTN 2] Button 1 pressed (play/pause/rtz)")
            if now - self._tap_time_ms <= self._tap_gap_ms:
                # double-tap => RTZ
                showlog.info(f"*[BTN 3] Double-tap detected, calling rtz()")
                self.rtz()
                self._tap_time_ms = 0.0
                return
            # single tap tentative; arm for double, but act immediately as play/pause
            showlog.info(f"*[BTN 4] Single tap, calling play_toggle()")
            self.play_toggle()
            self._tap_time_ms = now
            showlog.info(f"*[BTN 5] handle_button() complete for button 1")
            return
        elif btn_id == 2:
            self.next_frame(); return
        elif btn_id == 3:
            self.prev_frame(); return
        elif btn_id == 4:
            self.add_frame(duplicate_current=True); return
        elif btn_id == 5:
            self.delete_frame(); return
        elif btn_id == 6:
            if callable(self.on_open_preset_page):
                try: self.on_open_preset_page()
                except Exception as e: showlog.warn(f"[ASCIIAnim] preset page hook failed: {e}")
            else:
                self._fallback_open_preset_page()
            return
        elif btn_id == 7:
            if callable(self.on_open_preset_saver):
                try: self.on_open_preset_saver()
                except Exception as e: showlog.warn(f"[ASCIIAnim] preset saver hook failed: {e}")
            else:
                self._fallback_open_preset_saver()
            return

    def _fallback_open_preset_page(self):
        # Minimal non-crashy fallback; prefer wiring a real hook from your page
        try:
            import dialhandlers
            if hasattr(dialhandlers, "msg_queue") and dialhandlers.msg_queue:
                dialhandlers.msg_queue.put(("nav", "presets"))
            showlog.info("[ASCIIAnim] Requested: open preset page")
        except Exception:
            showlog.info("[ASCIIAnim] (no preset page hook)")

    def _fallback_open_preset_saver(self):
        try:
            import dialhandlers
            if hasattr(dialhandlers, "msg_queue") and dialhandlers.msg_queue:
                dialhandlers.msg_queue.put(("nav", "save_preset"))
            showlog.info("[ASCIIAnim] Requested: open preset saver")
        except Exception:
            showlog.info("[ASCIIAnim] (no preset saver hook)")

    # ---------------------------------------------------------------------
    # Input: touch/mouse to toggle & drag-paint
    # ---------------------------------------------------------------------
    def handle_event(self, event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and hasattr(event, "pos"):
            # Check if clicking on a frame in the frame list first
            # Frame rects are indexed relative to the current page
            start_frame = self._frame_list_page * self._frames_per_page
            for rect_idx, frame_rect in enumerate(self._frame_rects):
                if frame_rect and frame_rect.collidepoint(event.pos):
                    # Calculate the actual frame index from page + position
                    actual_frame_idx = start_frame + rect_idx
                    if actual_frame_idx < len(self.frames):
                        self.current = actual_frame_idx
                        self.mark_dirty()
                        return True
            
            # Otherwise check for container clicks
            cell = self._cell_from_pos(event.pos)
            if cell:
                y, x = cell
                frame = self.frames[self.current]
                cur = frame[y][x]
                
                # Only one active container per column rule
                if cur:
                    # If clicking an already active cell, turn it off
                    frame[y][x] = False
                    self._drag_paint = False
                else:
                    # Turn off all other cells in this column
                    for row in range(len(frame)):
                        frame[row][x] = False
                    # Turn on the clicked cell
                    frame[y][x] = True
                    self._drag_paint = True
                
                self._last_mouse_cell = cell
                self.mark_dirty()
                return True
        elif event.type == pygame.MOUSEMOTION and hasattr(event, "pos"):
            if self._drag_paint is None:
                return False
            cell = self._cell_from_pos(event.pos)
            if cell and cell != self._last_mouse_cell:
                y, x = cell
                frame = self.frames[self.current]
                
                # Apply one-per-column rule during drag
                if self._drag_paint:
                    # Turn off all cells in this column
                    for row in range(len(frame)):
                        frame[row][x] = False
                    # Turn on the dragged cell
                    frame[y][x] = True
                else:
                    # Just turn off if dragging "off" state
                    frame[y][x] = False
                
                self._last_mouse_cell = cell
                self.mark_dirty()
                return True
        elif event.type == pygame.MOUSEBUTTONUP:
            self._drag_paint = None
            self._last_mouse_cell = None
            return False
        return False

    # ---------------------------------------------------------------------
    # Drawing
    # ---------------------------------------------------------------------
    def draw(self, surface: pygame.Surface, device_name: Optional[str] = None, offset_y: int = 0):
        # Advance playback at fixed frame intervals
        if self.playing:
            now = time.time() * 1000.0
            elapsed = now - self._last_advance_ms
            showlog.debug(f"*[DRAW 1] Drawing while playing: now={now:.2f}, last_advance={self._last_advance_ms:.2f}, elapsed={elapsed:.2f}ms, frame_ms={self._frame_ms}")
            if (now - self._last_advance_ms) >= self._frame_ms:
                showlog.info(f"*[DRAW 2] Time to advance! Elapsed {elapsed:.2f}ms >= {self._frame_ms}ms")
                self._last_advance_ms = now
                showlog.info(f"*[DRAW 3] Calling next_frame()")
                self.next_frame(auto_create=False)  # Don't auto-create during playback
                showlog.info(f"*[DRAW 4] next_frame() returned, now on frame {self.current}")
            else:
                showlog.debug(f"*[DRAW 5] Not advancing yet: {elapsed:.2f}ms < {self._frame_ms}ms")

        # Resolve theme colors (use only real defined theme colors)
        panel_color = theme_rgb(device_name, "DIAL_PANEL_COLOR")  # Background panel (dark blue)
        text_bright = theme_rgb(device_name, "DIAL_TEXT_COLOR")   # Bright text (on cells, frame counter)
        text_dim = theme_rgb(device_name, "DIAL_MUTE_TEXT")       # Dimmed text (off cells)

        # Compute rect with vertical offset
        outer = self.rect.copy()
        outer.y += offset_y

        # Try to calculate the two separate panel positions using grid system
        # This ensures exact match with dial spacing and sizing
        try:
            # Left panel: 1×2 at column 0
            left_rect = get_zone_rect_tight(row=0, col=0, w=1, h=2)
            left_rect.y += offset_y
            
            # Right panel: 3×2 at column 1
            right_rect = get_zone_rect_tight(row=0, col=1, w=3, h=2)
            right_rect.y += offset_y
        except Exception as e:
            # Fallback if grid system fails
            showlog.warn(f"*[ASCIIAnimator] Grid system failed, using fallback: {e}")
            left_width = 120
            gap = 7
            left_rect = pygame.Rect(outer.x, outer.y, left_width, outer.height)
            right_rect = pygame.Rect(outer.x + left_width + gap, outer.y, 
                                     outer.width - left_width - gap, outer.height)

        # Draw left column background (dial panel)
        pygame.draw.rect(surface, panel_color, left_rect, border_radius=15)

        # Draw right area background (dial panel)
        pygame.draw.rect(surface, panel_color, right_rect, border_radius=15)

        # Draw frame list on left
        self._draw_frame_list(surface, left_rect, text_bright, text_dim, panel_color)

        self.draw_containers(surface, right_rect, 9, 9, text_bright=text_bright, text_dim=text_dim)
        # All done
        self.clear_dirty()
        return self.get_dirty_rect(offset_y)

    def _draw_frame_list(self, surface: pygame.Surface, rect: pygame.Rect, 
                         text_bright, text_dim, panel_color):
        """Draw frame list thumbnails on the left side (20 frames per page)."""
        import config as cfg
        self._ensure_font()
        self._frame_rects = []

        pad = 8
        inner = rect.inflate(-pad * 2, -pad * 2)
        frame_height = 28
        start_frame = self._frame_list_page * self._frames_per_page
        end_frame = start_frame + self._frames_per_page   # always show full 20 slots
        total_frames = len(self.frames)
        use_two_columns = True

        # Split into two half-width columns
        col_gap = 4
        col_width = (inner.width - col_gap) // 2
        left_col_rect = pygame.Rect(inner.left, inner.top, col_width, inner.height)
        right_col_rect = pygame.Rect(inner.left + col_width + col_gap, inner.top, col_width, inner.height)

        # Draw helper
        def draw_cell(i, frame_rect, active, used):
            if active:
                pygame.draw.rect(surface, text_bright, frame_rect, border_radius=4)
                pygame.draw.rect(surface, panel_color, frame_rect.inflate(-4, -4), border_radius=3)
                text_color = text_bright
            elif used:
                pygame.draw.rect(surface, text_dim, frame_rect, width=1, border_radius=4)
                text_color = text_dim
            else:
                # unused (greyed out)
                try:
                    mute_color = hex_to_rgb(getattr(cfg, "DIAL_MUTE_TEXT", "#555555"))
                    mute_color = hex_to_rgb("#222222")
                except Exception:
                    mute_color = (85, 85, 85)  # fallback RGB if conversion fails

                # unused (greyed out)
                pygame.draw.rect(surface, mute_color, frame_rect, width=1, border_radius=4)
                text_color = mute_color
                
            label = f"{i + 1:02d}"
            text_surf = self._font.render(label, True, text_color)
            text_x = frame_rect.centerx - text_surf.get_width() // 2
            text_y = frame_rect.centery - text_surf.get_height() // 2
            surface.blit(text_surf, (text_x, text_y))

        # left column
        y_pos = left_col_rect.top
        for idx in range(start_frame, start_frame + 10):
            frame_rect = pygame.Rect(left_col_rect.left, y_pos, col_width, frame_height - 4)
            self._frame_rects.append(frame_rect.copy())

            is_active = idx == self.current
            is_used = idx < total_frames
            draw_cell(idx, frame_rect, is_active, is_used)
            y_pos += frame_height

        # right column
        y_pos = right_col_rect.top
        for idx in range(start_frame + 10, end_frame):
            frame_rect = pygame.Rect(right_col_rect.left, y_pos, col_width, frame_height - 4)
            self._frame_rects.append(frame_rect.copy())

            is_active = idx == self.current
            is_used = idx < total_frames
            draw_cell(idx, frame_rect, is_active, is_used)
            y_pos += frame_height


    # ---------------------------------------------------------------------
    # Container rendering helpers
    # ---------------------------------------------------------------------
    def container(self, surface, rect, text_color_active, text_color_inactive, fill_char=" ", is_active=False):
        """Draws a single container box (╔ ╗ ╚ ╝) within the given rect."""
        self._ensure_font()
        
        # Use appropriate color based on active state
        text_color = text_color_active if is_active else text_color_inactive
        
        corner_tl = self._font.render("╔", True, text_color)
        corner_tr = self._font.render("╗", True, text_color)
        corner_bl = self._font.render("╚", True, text_color)
        corner_br = self._font.render("╝", True, text_color)

        # Calculate top-left and bottom-right corners
        tl = (rect.left, rect.top)
        tr = (rect.right - corner_tr.get_width(), rect.top)
        bl = (rect.left, rect.bottom - corner_bl.get_height())
        br = (rect.right - corner_br.get_width(), rect.bottom - corner_br.get_height())

        surface.blit(corner_tl, tl)
        surface.blit(corner_tr, tr)
        surface.blit(corner_bl, bl)
        surface.blit(corner_br, br)

        # Draw active state overlay with larger font
        if is_active:
            # Use a larger font for the asterisk
            large_font = pygame.font.SysFont("DejaVu Sans Mono", 28, bold=True)
            txt = large_font.render("*", True, text_color_active)
            center_x = rect.centerx - txt.get_width() // 2
            center_y = rect.centery - txt.get_height() // 2 + 4 
            surface.blit(txt, (center_x, center_y))
        # Optional: draw the fill character centered (when not active)
        elif fill_char.strip():
            txt = self._font.render(fill_char, True, text_color)
            center_x = rect.centerx - txt.get_width() // 2
            center_y = rect.centery - txt.get_height() // 2
            surface.blit(txt, (center_x, center_y))

    def draw_containers(self, surface, area_rect, cols=4, rows=4, text_bright=(0,255,0), text_dim=(100,100,100)):
        """
        Draws a grid of container boxes inside area_rect.
        Each container = 4 floating corners with padding between them.
        Containers will scale to fill the available space.
        Active containers (with *) use text_bright, inactive use text_dim.
        """
        showlog.debug(f"[STEP 19f] draw_containers called, self.frames type={type(self.frames)}, len={len(self.frames)}")
        if len(self.frames) > 0:
            showlog.debug(f"[STEP 19g] self.frames[0] type={type(self.frames[0])}, len={len(self.frames[0])}")
            if len(self.frames[0]) > 0:
                showlog.debug(f"[STEP 19h] self.frames[0][0] type={type(self.frames[0][0])}")
                if len(self.frames[0][0]) > 0:
                    showlog.debug(f"[STEP 19i] self.frames[0][0][0] value={self.frames[0][0][0]}, type={type(self.frames[0][0][0])}")
        
        self._ensure_font()
        
        # Store dimensions for hit-testing
        self._container_cols = cols
        self._container_rows = rows
        self._container_rects = [[None for _ in range(cols)] for _ in range(rows)]
        
        # Add padding inside the area to match frame list styling
        pad = 8
        inner = area_rect.inflate(-pad * 2, -pad * 2)
        
        # Calculate gap as a percentage of available space
        # Increase these values for more spacing between containers
        gap_ratio_x = 0.15  # 15% of horizontal space for column gaps
        gap_ratio_y = 0.12  # 12% of vertical space for row gaps
        
        # Calculate total gap space
        total_gap_x = inner.width * gap_ratio_x
        total_gap_y = inner.height * gap_ratio_y
        
        # Divide gaps evenly between containers
        gap_x = int(total_gap_x / max(1, cols - 1)) if cols > 1 else 0
        gap_y = int(total_gap_y / max(1, rows - 1)) if rows > 1 else 0
        
        # Calculate container sizes to fill remaining space
        container_w = (inner.width - (cols - 1) * gap_x) // cols
        container_h = (inner.height - (rows - 1) * gap_y) // rows
        
        # Recalculate total size (accounting for integer division)
        total_w = cols * container_w + (cols - 1) * gap_x
        total_h = rows * container_h + (rows - 1) * gap_y
        
        # Center the grid in the available space
        start_x = inner.left + (inner.width - total_w) // 2
        start_y = inner.top + (inner.height - total_h) // 2

        # Get current frame state
        frame = self.frames[self.current]
        
        # Always debug to see what we're rendering
        true_count = sum(sum(1 for cell in row if cell) for row in frame)
        showlog.debug(f"[STEP 20] RENDERING frame {self.current}: {true_count} True cells")
        if len(frame) > 1:
            showlog.debug(f"[STEP 21] Frame {self.current} row 0: {frame[0]}")
            showlog.debug(f"[STEP 22] Frame {self.current} row 1: {frame[1]}")

        for r in range(rows):
            for c in range(cols):
                x = start_x + c * (container_w + gap_x)
                y = start_y + r * (container_h + gap_y)
                rect = pygame.Rect(x, y, container_w, container_h)
                
                # Store rect for hit-testing
                self._container_rects[r][c] = rect
                
                # Check if this cell is active
                is_active = frame[r][c] if r < len(frame) and c < len(frame[r]) else False
                
                # Debug first few cells
                if r == 0 and c < 3:
                    showlog.debug(f"[STEP 23] Cell [{r},{c}]: is_active={is_active}")
                
                self.container(surface, rect, text_bright, text_dim, fill_char=" ", is_active=is_active)



    
    def _draw_ascii_section(self, surface: pygame.Surface, rect: pygame.Rect,
                           text_bright, text_dim):
        """Draw the ASCII grid editor on the right side."""
        # Inner area for grid (with padding)
        pad = self._pad
        crt = rect.inflate(-pad * 2, -pad * 2)

        # Compute grid geometry and character cell size
        self._layout_text_grid(crt)

        # Draw ASCII border (box drawing)
        self._draw_box(surface, crt, text_bright, style=self.border_style)

        # Draw grid contents as characters
        self._draw_ascii_grid(surface, crt, text_bright, text_dim)

        # Overlay frame counter in top-right (inside CRT)
        self._draw_frame_counter(surface, crt, text_bright)

    def _ensure_font(self):
        if self._font is None:
            try:
                # Monospace is important so the ASCII grid aligns
                self._font = pygame.font.SysFont("DejaVu Sans Mono", 12, bold=False)
            except Exception:
                self._font = pygame.font.Font(None, 18)

    def _layout_text_grid(self, crt: pygame.Rect):
        # Measure a character to infer char cell size
        self._ensure_font()
        metrics = self._font.size("W")
        self._char_w, self._char_h = metrics[0], metrics[1]

        # Compute a suitable character matrix to host the grid cells & borders
        # We want cells with at least one char column each; optionally add spaces between columns for readability
        # For simplicity: one char per cell; borders consume 1 char around
        need_cols = self.grid_cols + 2  # border left/right
        need_rows = self.grid_rows + 2  # border top/bottom

        # Compute how many chars fit horizontally/vertically
        fit_cols = max(need_cols, min(120, crt.width // self._char_w))
        fit_rows = max(need_rows, min(60, crt.height // self._char_h))

        # Compute pixel size of that char grid and center it inside CRT area
        grid_px_w = fit_cols * self._char_w
        grid_px_h = fit_rows * self._char_h

        gx = crt.left + (crt.width - grid_px_w) // 2
        gy = crt.top + (crt.height - grid_px_h) // 2

        # We’ll map our logical cells into this char grid; store origin for hit-testing
        self._grid_origin = (gx, gy)

        # For drawing symbols, one char per logical cell (inside the border)
        self._cell_w = self._char_w
        self._cell_h = self._char_h

    def _draw_ascii_grid(self, surf: pygame.Surface, crt: pygame.Rect, on_col, off_col):
        # Inside the border, draw either '*' or '.' per cell
        frame = self.frames[self.current]
        gx, gy = self._grid_origin
        for y in range(self.grid_rows):
            for x in range(self.grid_cols):
                ch = "*" if frame[y][x] else "."
                col = on_col if ch == "*" else off_col
                img = self._font.render(ch, True, col)
                # +1,+1 to account for border columns/rows
                px = gx + (x + 1) * self._char_w
                py = gy + (y + 1) * self._char_h
                surf.blit(img, (px, py))

    def _draw_frame_counter(self, surf: pygame.Surface, crt: pygame.Rect, color):
        # Text: [01 / 05]
        cur = self.current + 1
        total = len(self.frames)
        text = f"[{cur:02d} / {total:02d}]"
        img = self._font.render(text, True, color)
        # Place in top-right inside the CRT, with a small inset
        inset = 6
        pos = (crt.right - img.get_width() - inset, crt.top + inset)
        surf.blit(img, pos)

    # ---------------------------------------------------------------------
    # Hit-testing: map pixel → logical cell (y,x)
    # ---------------------------------------------------------------------
    def _cell_from_pos(self, pos: Tuple[int, int]) -> Optional[Tuple[int, int]]:
        # Check container-based grid first (if available)
        if self._container_rects:
            x, y = pos
            for r in range(len(self._container_rects)):
                for c in range(len(self._container_rects[r])):
                    rect = self._container_rects[r][c]
                    if rect and rect.collidepoint(x, y):
                        return (r, c)
        
        # Fallback to old ASCII grid method (only if char dimensions are set)
        if self._char_w > 0 and self._char_h > 0:
            gx, gy = self._grid_origin
            x, y = pos
            # Border consumes 1 char all around; detect within inner region
            rel_x = x - gx
            rel_y = y - gy
            if rel_x < 0 or rel_y < 0:
                return None
            cx = rel_x // self._char_w
            cy = rel_y // self._char_h
            # inner cell space is [1 .. cols], [1 .. rows]
            if cx < 1 or cy < 1:
                return None
            lx = cx - 1
            ly = cy - 1
            if lx >= self.grid_cols or ly >= self.grid_rows:
                return None
            return (ly, lx)
        
        # No valid hit-testing available
        return None

    # ---------------------------------------------------------------------
    # State (de)serialization for presets
    # ---------------------------------------------------------------------
    def is_dirty(self):
        """Override to keep widget dirty during playback."""
        # If playing, always return True so we keep redrawing
        if self.playing:
            return True
        # Otherwise use parent's dirty flag
        return super().is_dirty()
    
    def clear_dirty(self):
        """Override to prevent clearing dirty flag during playback."""
        # If playing, don't clear the dirty flag (stay dirty for continuous redraw)
        if self.playing:
            return
        # Otherwise clear normally
        super().clear_dirty()
    
    def get_state(self) -> dict:
        showlog.debug(f"*[STEP 25] get_state() called, self.frames[0][0][0] = {self.frames[0][0][0]} (type={type(self.frames[0][0][0])})")
        result = {
            "frame_total": len(self.frames),
            "rows": self.grid_rows,
            "cols": self.grid_cols,
            "frames": [
                ["".join("*" if v else "." for v in row) for row in fr]
                for fr in self.frames
            ],
        }
        showlog.debug(f"*[STEP 26] get_state() returning, self.frames[0][0][0] = {self.frames[0][0][0]} (type={type(self.frames[0][0][0])})")
        return result
    
    def set_from_state(self, **kwargs):
        """
        Called by preset_manager to restore widget state.
        This prevents the raw setattr() fallback that would corrupt self.frames!
        """
        showlog.debug(f"*[STEP 27] set_from_state() called with keys: {kwargs.keys()}")
        self.set_state(kwargs)

    def set_state(self, data: dict):
        import traceback
        showlog.debug("*[STEP 10] Widget.set_state() called")
        showlog.debug(f"*[STEP 10b] Called from: {traceback.format_stack()[-2]}")
        try:
            showlog.debug("*[STEP 10] Widget.set_state() called")
            showlog.debug(f"*[STEP 11] Data keys: {data.keys()}")
            
            # Get grid size first (if specified in data)
            rows = int(data.get("rows", self.grid_rows))
            cols = int(data.get("cols", self.grid_cols))
            
            # Check for RAW format (CSV-style number data)
            raw_data = data.get("raw")
            if raw_data is not None:
                showlog.info("[ASCIIAnim] Loading from RAW format")
                self._load_from_raw(raw_data, target_rows=rows, target_cols=cols)
                self.current = 0
                self.mark_dirty()
                return
            frs = data.get("frames")
            showlog.debug(f"*[STEP 12] rows={rows}, cols={cols}, frames count={len(frs) if frs else 0}")
            
            self.set_grid_size(rows, cols, keep=False)
            if isinstance(frs, list) and frs:
                new_frames: List[List[List[bool]]] = []
                for frame_idx, fr in enumerate(frs):
                    showlog.debug(f"*[STEP 13] Processing frame {frame_idx}, type={type(fr)}, len={len(fr) if isinstance(fr, list) else 'N/A'}")
                    if frame_idx == 0 and len(fr) > 0:
                        showlog.debug(f"*[STEP 14] Frame 0, row 0: '{fr[0]}' (type={type(fr[0])})")
                        showlog.debug(f"*[STEP 15] Frame 0, row 1: '{fr[1]}' (should be '.*.......')")
                    
                    nf = self._blank_frame(rows, cols)
                    for y in range(min(rows, len(fr))):
                        line = fr[y]
                        for x in range(min(cols, len(line))):
                            char = line[x]
                            result = (char == "*")
                            nf[y][x] = result
                            if frame_idx == 0 and y == 1 and x == 1:
                                showlog.debug(f"*[STEP 16] Frame 0, cell [1,1]: char='{char}' (ord={ord(char)}), comparison result={result}")
                    new_frames.append(nf)
                    # Debug the parsed frame
                    if frame_idx == 0:
                        true_count = sum(sum(1 for cell in row if cell) for row in nf)
                        showlog.debug(f"*[STEP 17] Frame 0 after parsing: {true_count} cells are True (expected: 2)")
                        showlog.debug(f"*[STEP 18] Frame 0 row 1 parsed: {nf[1]}")
                self.frames = new_frames
                showlog.debug(f"*[STEP 19] Loaded {len(new_frames)} frames into self.frames")
                # Verify it was actually stored correctly
                showlog.debug(f"*[STEP 19b] self.frames type: {type(self.frames)}")
                showlog.debug(f"*[STEP 19c] self.frames[0] type: {type(self.frames[0])}")
                showlog.debug(f"*[STEP 19d] self.frames[0][0] type: {type(self.frames[0][0])}")
                showlog.debug(f"*[STEP 19e] self.frames[0][0][0] value: {self.frames[0][0][0]} (type={type(self.frames[0][0][0])})")
            # Reset to first frame when loading preset
            self.current = 0
            self.mark_dirty()
        except Exception as e:
            showlog.warn(f"[ASCIIAnim] set_state failed: {e}")
            import traceback
            showlog.warn(f"[ASCIIAnim] Traceback: {traceback.format_exc()}")
