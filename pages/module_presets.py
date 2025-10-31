# /build/pages/module_presets.py
"""
Module preset loader page.
Displays and loads presets for module-based pages (like vibrato, tremolo, etc.)
Uses preset_manager for loading presets instead of device_presets/device_patches.
"""
import os, sys
if __package__ is None or __package__ == "":
    build_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if build_root not in sys.path:
        sys.path.insert(0, build_root)

import pygame
import threading, time
from typing import Optional

import showlog
import config as cfg
import helper
from preset_manager import get_preset_manager
from pages import module_base

# -------------------------------------------------------
# Globals
# -------------------------------------------------------

preset_buttons = []
back_rect = None
active_module_id = None  # Module ID (e.g., "vibrato")
active_module_instance = None  # Reference to the live module instance
active_widget = None  # Reference to the widget if any
header_text = ""
_current_load_id = 0  # cancels stale background label-fill workers

# Scroll state
scroll_offset = 0

# Simple scroll animation state
_scroll_anim = {
    "active": False,
    "start_ms": 0,
    "duration": 0,
    "from": 0,
    "to": 0,
}

# Inertia (deceleration) state for finger scroll
_inertia = {
    "active": False,
    "vy": 0.0,          # px/ms
    "last_ms": 0,
}
_drag_vy_samples = []      # recent velocity samples during drag (px/ms)
_drag_last_ms = 0

is_dragging = False
last_mouse_y = 0
selected_preset = None  # Currently selected preset name (for highlighting)

_SCROLL_INVERT = bool(getattr(cfg, "PRESET_SCROLL_INVERT", False))

# -------------------------------------------------------
# Utilities: scroll / inertia
# -------------------------------------------------------

def _reset_scroll_runtime():
    """Kill any carry-over animation, inertia, and drag state."""
    global scroll_offset, _scroll_anim, _inertia
    global _drag_vy_samples, _drag_last_ms, is_dragging, last_mouse_y

    scroll_offset = 0

    _scroll_anim.update({
        "active": False,
        "start_ms": 0,
        "duration": 0,
        "from": 0,
        "to": 0,
    })

    _inertia.update({"active": False, "vy": 0.0, "last_ms": 0})
    try:
        _drag_vy_samples.clear()
    except Exception:
        _drag_vy_samples = []
    _drag_last_ms = 0
    is_dragging = False
    last_mouse_y = 0


def _start_scroll_animation(target_offset: int, duration_ms: Optional[int] = None, from_offset: Optional[int] = None):
    """Begin a smooth scroll from current (or provided) offset to target_offset."""
    global _scroll_anim, scroll_offset, _inertia
    try:
        if duration_ms is None:
            duration_ms = int(getattr(cfg, "PRESET_SCROLL_DURATION_MS", 900))
        if from_offset is None:
            from_offset = int(max(0, scroll_offset))

        # Cancel inertia when starting programmatic scroll
        _inertia["active"] = False

        _scroll_anim["active"] = True
        _scroll_anim["start_ms"] = pygame.time.get_ticks()
        _scroll_anim["duration"] = max(1, int(duration_ms))
        _scroll_anim["from"] = int(max(0, from_offset))
        _scroll_anim["to"] = int(max(0, target_offset))
    except Exception:
        # Fallback: jump immediately
        scroll_offset = int(max(0, target_offset))
        _scroll_anim["active"] = False


def _update_scroll_animation():
    """Advance scroll animation if active, using configurable easing (default ease-out cubic)."""
    global _scroll_anim, scroll_offset
    try:
        if not _scroll_anim.get("active"):
            return
        now = pygame.time.get_ticks()
        start = _scroll_anim.get("start_ms", 0)
        dur = max(1, int(_scroll_anim.get("duration", 1)))
        t = (now - start) / dur
        if t >= 1.0:
            scroll_offset = int(max(0, _scroll_anim.get("to", 0)))
            _scroll_anim["active"] = False
            return

        # easing selection
        ease_mode = str(getattr(cfg, "PRESET_AUTO_SCROLL_EASE", "ease_out")).lower()
        def ease(x: float) -> float:
            x = max(0.0, min(1.0, x))
            if ease_mode == "ease_in_out":
                if x < 0.5:
                    return 4 * x * x * x
                xr = (2 * x - 2)
                return 0.5 * xr * xr * xr + 1
            # default ease-out cubic
            return 1 - pow(1 - x, 3)

        a = float(_scroll_anim.get("from", 0))
        b = float(_scroll_anim.get("to", 0))
        s = ease(max(0.0, min(1.0, t)))
        scroll_offset = int(max(0, a + (b - a) * s))
    except Exception:
        # Stop anim on any error
        _scroll_anim["active"] = False


def _update_inertia(screen):
    """
    Advance inertial scrolling when the finger/mouse is up.
    Uses a small exponential decay so it settles quickly.
    Safe to call even if there are no buttons.
    """
    global _inertia, scroll_offset

    try:
        if not _inertia.get("active"):
            return

        now = pygame.time.get_ticks()
        last = int(_inertia.get("last_ms", 0))
        if last == 0:
            _inertia["last_ms"] = now
            return

        dt_ms = max(1, now - last)               # elapsed time
        vy = float(_inertia.get("vy", 0.0))      # px/ms

        if abs(vy) < 0.001:
            _inertia["active"] = False
            _inertia["vy"] = 0.0
            return

        # compute content bounds
        if preset_buttons:
            last_btn = preset_buttons[-1]["rect"]
            content_height = last_btn.bottom + int(getattr(cfg, "PRESET_MARGIN_Y", 60))
            max_scroll = max(0, content_height - screen.get_height())
        else:
            max_scroll = 0

        # integrate motion (negative vy means scrolling up visually)
        scroll_offset = min(max(scroll_offset - vy * dt_ms, 0), max_scroll)

        # decay velocity (ease out)
        decay = float(getattr(cfg, "PRESET_INERTIA_DECAY", 0.92))
        vy *= decay

        # stop if nearly still or at edges
        if scroll_offset <= 0 and vy > 0:
            vy = 0.0
        if scroll_offset >= max_scroll and vy < 0:
            vy = 0.0

        _inertia["vy"] = vy
        _inertia["last_ms"] = now
        if abs(vy) < 0.001:
            _inertia["active"] = False
            _inertia["vy"] = 0.0
    except Exception:
        # never allow inertia to crash draw
        _inertia["active"] = False
        _inertia["vy"] = 0.0


# -------------------------------------------------------
# Init
# -------------------------------------------------------

def init(screen, module_id, module_instance, widget=None):
    """
    Load presets for the given module.
    
    Args:
        screen: Pygame screen surface
        module_id: Module identifier (e.g., "vibrato")
        module_instance: The live module instance (e.g., VibratoModule)
        widget: Optional widget instance if the module has a custom widget
    """
    global preset_buttons, back_rect, active_module_id, active_module_instance, active_widget
    global header_text, scroll_offset, selected_preset
    
    showlog.debug(f"[ModulePresets] init() called for module: {module_id}")

    try:
        # Apply module context and reset all scroll runtime FIRST to avoid carry-over
        active_module_id = module_id
        active_module_instance = module_instance
        active_widget = widget
        _reset_scroll_runtime()

        preset_buttons = []
        header_text = f"{module_id.title()} Presets"
        screen.fill((0, 0, 0))

        # Get preset list from preset_manager
        pm = get_preset_manager()
        preset_names = pm.list_presets(module_id)
        
        if not preset_names:
            showlog.info(f"[ModulePresets] No presets found for {module_id}")
            preset_names = []
        
        showlog.debug(f"[ModulePresets] Found {len(preset_names)} presets for {module_id}")

        # Progressive loader (append buttons one-by-one)
        _start_progressive_loader(preset_names, module_id, screen)
        showlog.debug("[ModulePresets] Initialized successfully (progressive)")

    except Exception as e:
        showlog.error(f"[ModulePresets] Error in init: {e}")


def _start_progressive_loader(final_labels, module_id, screen):
    """Spawn a daemon thread to populate labels with a small delay per item.
    Guards with a load_id to avoid updating after module/page changes.
    """
    global _current_load_id
    _current_load_id += 1
    load_id = _current_load_id

    delay_ms = int(getattr(cfg, "PRESET_LOAD_DELAY_MS", 25))
    max_len = int(getattr(cfg, "PRESET_NAME_MAX_LENGTH", 22))

    # Capture geometry/constants once for thread
    cols = int(getattr(cfg, "NUMBER_OF_PRESET_COLUMNS", 2))
    col_width = (screen.get_width() - getattr(cfg, "PRESET_MARGIN_X", 40) * 2) // max(1, cols)
    row_height = int(getattr(cfg, "PRESET_BUTTON_HEIGHT", 50))
    spacing_y = int(getattr(cfg, "PRESET_SPACING_Y", 12))
    btn_w = int(getattr(cfg, "PRESET_BUTTON_WIDTH", 165))
    btn_h = int(getattr(cfg, "PRESET_BUTTON_HEIGHT", 50))
    margin_x = int(getattr(cfg, "PRESET_MARGIN_X", 40))
    margin_y = int(getattr(cfg, "PRESET_MARGIN_Y", 60))

    def worker():
        try:
            for idx, label in enumerate(final_labels):
                # Abort if a new load started or module changed
                if load_id != _current_load_id or module_id != active_module_id:
                    return

                full = str(label)
                disp = (full[:max_len].rstrip()) if isinstance(label, str) else full

                # Compute position for this index
                col = idx % max(1, cols)
                row = idx // max(1, cols)
                x = margin_x + col * col_width + (col_width - btn_w) // 2
                y = margin_y + row * (row_height + spacing_y)
                rect = pygame.Rect(x, y, btn_w, btn_h)

                preset_buttons.append({
                    "rect": rect,
                    "name": disp,
                    "full_name": full,
                })

                time.sleep(max(0, delay_ms) / 1000.0)
        except Exception as e:
            showlog.error(f"[ModulePresets] progressive loader error: {e}")

    t = threading.Thread(target=worker, name="module_presets_loader", daemon=True)
    t.start()


# -------------------------------------------------------
# Draw
# -------------------------------------------------------

def draw(screen, offset_y=0):
    """Render preset buttons, header, and log, with optional vertical offset."""
    global selected_preset

    # Advance scroll animation if active + inertia
    _update_scroll_animation()
    _update_inertia(screen)

    screen.fill((0, 0, 0))
    try:
        # --- Theme-aware colour fallbacks (use parent device theme for modules) ---
        import dialhandlers
        device_name = getattr(dialhandlers, "current_device_name", None)

        fill_sel         = helper.theme_rgb(device_name, "PRESET_LABEL_HIGHLIGHT", "#6666FF")
        font_sel         = helper.theme_rgb(device_name, "PRESET_FONT_HIGHLIGHT",  "#FFFFFF")
        fill_norm        = helper.theme_rgb(device_name, "PRESET_BUTTON_COLOR",    "#222222")
        font_norm        = helper.theme_rgb(device_name, "PRESET_TEXT_COLOR",      "#FFFFFF")
        scroll_bar_color = helper.theme_rgb(device_name, "SCROLL_BAR_COLOR",       "#232323")

        # --- Draw buttons ---
        font = pygame.font.Font(
            cfg.font_helper.main_font(cfg.PRESET_FONT_WEIGHT),
            int(getattr(cfg, "PRESET_FONT_SIZE", 20))
        )

        for b in preset_buttons:
            scrolled_rect = b["rect"].move(0, -scroll_offset + offset_y)
            if scrolled_rect.bottom < 0 or scrolled_rect.top > screen.get_height():
                continue  # skip off-screen

            # Check if this preset should be highlighted
            is_selected = (selected_preset is not None and b["full_name"] == selected_preset)

            fill_color = fill_sel if is_selected else fill_norm
            font_color = font_sel if is_selected else font_norm

            pygame.draw.rect(screen, fill_color, scrolled_rect, border_radius=6)
            text_surface = font.render(b["name"], True, font_color)
            screen.blit(
                text_surface,
                (scrolled_rect.x + 10,
                 scrolled_rect.y + (getattr(cfg, "PRESET_BUTTON_HEIGHT", 50) - text_surface.get_height()) // 2)
            )

        # --- Draw simple scroll bar (optional) ---
        if preset_buttons:
            last_btn = preset_buttons[-1]["rect"]
            content_height = last_btn.bottom + getattr(cfg, "PRESET_MARGIN_Y", 60)
            view_height = screen.get_height()
            if content_height > view_height:
                bar_height = max(30, int(view_height * (view_height / content_height)))
                # use content_height for ratio (not max_scroll) to avoid div-by-zero and jitter
                bar_y = int((scroll_offset / max(1, content_height)) * view_height) + offset_y
                pygame.draw.rect(
                    screen,
                    scroll_bar_color,
                    (screen.get_width() - 8, bar_y, 5, bar_height),
                    border_radius=3
                )

        # --- Partial display update (exclude header + log bar) ---
        log_bar_h = getattr(cfg, "LOG_BAR_HEIGHT", 20)
        preset_area_rect = pygame.Rect(
            0,
            getattr(cfg, "HEADER_HEIGHT", 70),
            screen.get_width(),
            screen.get_height() - (getattr(cfg, "HEADER_HEIGHT", 70) + log_bar_h)
        )
        if is_dragging:
            pygame.display.update(preset_area_rect)

    except Exception as e:
        showlog.error(f"[ModulePresets] Error in draw: {e}")


# -------------------------------------------------------
# Event Handling (Touch Scroll + Selection)
# -------------------------------------------------------

def handle_event(event, msg_queue, screen=None):
    """Handle touchscreen or mouse scrolling and preset selection."""
    global scroll_offset, is_dragging, last_mouse_y, selected_preset, _drag_last_ms, _inertia

    try:
        if screen is None:
            screen = pygame.display.get_surface()

        # --- Resolve pointer position (mouse or finger) ---
        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
            pos = event.pos
        elif event.type in (pygame.FINGERDOWN, pygame.FINGERUP, pygame.FINGERMOTION):
            sw, sh = pygame.display.get_surface().get_size()
            pos = (int(event.x * sw), int(event.y * sh))
        else:
            return  # irrelevant event

        # ------------------------------------------------------------------
        # 1️⃣  Press
        # ------------------------------------------------------------------
        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN):
            last_mouse_y = pos[1]
            is_dragging = True

            # Cancel any ongoing auto-scroll animation when user interacts
            _scroll_anim["active"] = False

            # Also kill inertia on fresh press
            _inertia["active"] = False
            _inertia["vy"] = 0.0

            showlog.verbose(f"[ModulePresets] DOWN at {pos}")

            # --- Back button ---
            if back_rect and back_rect.collidepoint(pos):
                msg_queue.put(("ui_mode", "dials"))
                return

            # --- Detect preset press ---
            for b in preset_buttons:
                scrolled_rect = b["rect"].move(0, -scroll_offset)
                if scrolled_rect.collidepoint(pos):
                    preset_name = b.get("full_name", b["name"])
                    showlog.debug(f"[ModulePresets] Button pressed: {preset_name}")

                    # --- Send LED/LCD feedback ---
                    try:
                        dev1_msg = f"DEV1 TXT:{active_module_id}"
                        dev2_msg = f"DEV2 TXT:{preset_name}"
                        if getattr(cfg, "LED_IS_NETWORK", False):
                            from network import forward_to_pico
                            forward_to_pico(dev1_msg)
                            forward_to_pico(dev2_msg)
                        else:
                            from get_patch_and_send_local import output_msg
                            output_msg(dev1_msg)
                            output_msg(dev2_msg)
                    except Exception as e:
                        showlog.error(f"[ModulePresets] LED/LCD send failed: {e}")

                    # --- Load the preset using preset_manager ---
                    try:
                        success = module_base.load_preset(
                            preset_name,
                            msg_queue=msg_queue
                        )
                        if success:
                            showlog.info(f"[ModulePresets] Loaded preset: {preset_name}")
                            selected_preset = preset_name
                        else:
                            showlog.warn(f"[ModulePresets] Failed to load preset: {preset_name}")
                    except Exception as e:
                        showlog.error(f"[ModulePresets] Error loading preset: {e}")

                    return  # done handling press

        # ------------------------------------------------------------------
        # 2️⃣  Drag (scroll)
        # ------------------------------------------------------------------
        elif (event.type in (pygame.MOUSEMOTION, pygame.FINGERMOTION)) and is_dragging:
            current_y = int(event.y * screen.get_height()) if event.type == pygame.FINGERMOTION else event.pos[1]
            delta_y = current_y - last_mouse_y
            last_mouse_y = current_y

            if preset_buttons:
                last_btn = preset_buttons[-1]["rect"]
                content_height = last_btn.bottom + getattr(cfg, "PRESET_MARGIN_Y", 60)
                max_scroll = max(0, content_height - screen.get_height())
            else:
                max_scroll = 0

            # update state only — drawing handled next tick by main loop
            scroll_offset = min(
                max(scroll_offset - delta_y * getattr(cfg, "PRESET_SCROLL_SPEED", 1.0), 0),
                max_scroll
            )

            # track velocity for inertia
            now = pygame.time.get_ticks()
            dt = max(1, now - (_drag_last_ms or now))
            vy = (delta_y * getattr(cfg, "PRESET_SCROLL_SPEED", 1.0)) / dt  # px/ms
            _inertia["vy"] = vy
            _inertia["last_ms"] = now

        # ------------------------------------------------------------------
        # 3️⃣  Release
        # ------------------------------------------------------------------
        elif event.type in (pygame.MOUSEBUTTONUP, pygame.FINGERUP):
            is_dragging = False
            # enable inertia if there is velocity
            if abs(float(_inertia.get("vy", 0.0))) > 0.001:
                _inertia["active"] = True
                _inertia["last_ms"] = pygame.time.get_ticks()
            if getattr(cfg, "DEBUG", False):
                showlog.verbose("[ModulePresets] UP - drag ended")

    except Exception as e:
        showlog.error(f"[ModulePresets] handle_event crashed: {e}")

