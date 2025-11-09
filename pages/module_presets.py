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
import navigator
from preset_manager import get_preset_manager
from pages import module_base

try:
    from plugins import drumbo_instrument_service as _drumbo_service
except Exception:
    _drumbo_service = None

# Plugin metadata for rendering system
PLUGIN_METADATA = {
    "rendering": {
        "fps_mode": "normal",            # 60 FPS is enough for list navigation
        "supports_dirty_rect": False,    # Complex layout with scrolling
        "requires_full_frame": True,     # Always redraw entire page
    }
}

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

# Animation preset metadata (filename mapping)
_animation_files = {}  # {"ANIM: wave": "wave.drawbar.json"}

_drumbo_registry_cache = {}
_drumbo_errors_cache = []

_DRUMBO_BROWSER = {
    "active": False,
    "rect": None,
    "entries": [],
    "errors": [],
    "selected_id": None,
    "preset_margin_y": None,
    "empty_message": None,
}

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

_DEFAULT_PRESET_MARGIN_Y = int(getattr(cfg, "PRESET_MARGIN_Y", 60))
_current_preset_margin_y: Optional[int] = None

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


def _refresh_drumbo_instruments():
    """Refresh Drumbo instrument metadata when entering module presets."""
    global _drumbo_registry_cache, _drumbo_errors_cache
    if not _drumbo_service:
        return
    try:
        result = _drumbo_service.refresh()
    except Exception as exc:
        showlog.warn(f"*[ModuleDrumbo] Instrument refresh failed: {exc}")
        return

    _drumbo_registry_cache = result.instruments
    _drumbo_errors_cache = list(result.errors or [])

    showlog.debug(
        f"*[ModuleDrumbo] Instrument scan discovered {len(result.instruments)} entries"
    )
    for line in _drumbo_errors_cache:
        showlog.warn(f"*[ModuleDrumbo] Instrument warning: {line}")


def get_drumbo_instruments():
    if not _drumbo_service:
        return {}
    if not _drumbo_registry_cache:
        _refresh_drumbo_instruments()
    return _drumbo_registry_cache


def get_drumbo_instrument_errors():
    if not _drumbo_service:
        return []
    if not _drumbo_registry_cache and not _drumbo_errors_cache:
        _refresh_drumbo_instruments()
    return _drumbo_errors_cache


def get_selected_drumbo_instrument() -> Optional[str]:
    selected = _DRUMBO_BROWSER.get("selected_id")
    showlog.debug(f"*[ModuleDrumbo] Selected instrument requested: {selected}")
    return selected


def _reset_drumbo_browser_state():
    global _current_preset_margin_y
    _DRUMBO_BROWSER.update({
        "active": False,
        "rect": None,
        "entries": [],
        "errors": [],
        "selected_id": None,
        "preset_margin_y": None,
        "empty_message": None,
    })
    _current_preset_margin_y = None


def _rebuild_drumbo_browser(screen):
    global _current_preset_margin_y
    if screen is None or not _drumbo_service:
        _reset_drumbo_browser_state()
        return

    registry = get_drumbo_instruments() or {}
    errors = list(get_drumbo_instrument_errors() or [])

    try:
        margin_x = int(getattr(cfg, "MODULE_DRUMBO_MARGIN_X", 24))
        top_padding = int(getattr(cfg, "MODULE_DRUMBO_TOP_PADDING", 8))
        bottom_padding = int(getattr(cfg, "MODULE_DRUMBO_BOTTOM_PADDING", 12))
        entry_height = int(getattr(cfg, "MODULE_DRUMBO_ENTRY_HEIGHT", 44))
        entry_spacing = int(getattr(cfg, "MODULE_DRUMBO_ENTRY_SPACING", 6))
        title_height = int(getattr(cfg, "MODULE_DRUMBO_TITLE_HEIGHT", 28))
        error_line_height = int(getattr(cfg, "MODULE_DRUMBO_ERROR_HEIGHT", 18))
        preset_gap = int(getattr(cfg, "MODULE_DRUMBO_PRESET_GAP", 20))
        header_height = int(getattr(cfg, "HEADER_HEIGHT", 70))

        sorted_specs = sorted(registry.values(), key=lambda spec: spec.display_name.lower())
        entry_count = len(sorted_specs)
        entry_block_height = max(0, entry_count * entry_height + max(0, entry_count - 1) * entry_spacing)
        empty_message = None if entry_count else "No Drumbo instruments found"
        info_block_height = entry_block_height if entry_count else entry_height
        error_block_height = max(0, len(errors) * error_line_height)

        panel_left = margin_x
        panel_width = max(0, screen.get_width() - margin_x * 2)
        panel_top = header_height + top_padding
        panel_height = title_height + info_block_height + error_block_height + bottom_padding
        available_height = max(0, screen.get_height() - panel_top)
        if panel_height > available_height:
            panel_height = available_height

        panel_rect = pygame.Rect(panel_left, panel_top, panel_width, panel_height)
        preset_margin_y = panel_rect.bottom + preset_gap

        prev_selected = _DRUMBO_BROWSER.get("selected_id")
        service_selected = None
        if _drumbo_service:
            try:
                service_selected = _drumbo_service.get_selected_id()
            except Exception as exc:
                showlog.warn(f"*[ModuleDrumbo] Failed to get service selection: {exc}")

        selected_id = prev_selected if prev_selected in registry else None
        if not selected_id and service_selected in registry:
            selected_id = service_selected
        if not selected_id and sorted_specs:
            selected_id = sorted_specs[0].id

        if selected_id and _drumbo_service:
            try:
                _drumbo_service.select(selected_id, auto_refresh=False)
            except Exception as exc:
                showlog.warn(f"*[ModuleDrumbo] Failed to sync service selection: {exc}")

        entries = []
        current_y = panel_rect.y + title_height
        for spec in sorted_specs:
            rect = pygame.Rect(panel_left + 12, current_y, panel_width - 24, entry_height)
            entries.append({
                "id": spec.id,
                "display_name": spec.display_name,
                "category": spec.category,
                "rect": rect,
            })
            current_y += entry_height + entry_spacing

        _DRUMBO_BROWSER.update({
            "active": True,
            "rect": panel_rect,
            "entries": entries,
            "errors": errors,
            "selected_id": selected_id,
            "preset_margin_y": preset_margin_y,
            "empty_message": empty_message,
        })
        _current_preset_margin_y = preset_margin_y

        showlog.debug(
            f"*[ModuleDrumbo] Browser rebuilt: entries={entry_count}, errors={len(errors)}, panel_h={panel_rect.height}, selected={selected_id}"
        )
    except Exception as exc:
        showlog.warn(f"*[ModuleDrumbo] Browser rebuild failed: {exc}")
        _reset_drumbo_browser_state()


def _draw_drumbo_browser(screen, device_name, offset_y=0):
    state = _DRUMBO_BROWSER
    if not state.get("active") or not state.get("rect"):
        return

    panel_rect = state["rect"].move(0, offset_y)

    panel_bg = helper.theme_rgb(device_name, "DRUMBO_BROWSER_BG", "#141414")
    panel_border = helper.theme_rgb(device_name, "DRUMBO_BROWSER_BORDER", "#2A2A2A")
    title_color = helper.theme_rgb(device_name, "DRUMBO_BROWSER_TITLE_COLOR", "#FFFFFF")
    entry_bg = helper.theme_rgb(device_name, "DRUMBO_BROWSER_ENTRY_BG", "#1F1F1F")
    entry_border = helper.theme_rgb(device_name, "DRUMBO_BROWSER_ENTRY_BORDER", "#323232")
    entry_selected_bg = helper.theme_rgb(device_name, "DRUMBO_BROWSER_ENTRY_SELECTED_BG", "#2E4F87")
    entry_selected_border = helper.theme_rgb(device_name, "DRUMBO_BROWSER_ENTRY_SELECTED_BORDER", "#4974C2")
    entry_text = helper.theme_rgb(device_name, "DRUMBO_BROWSER_ENTRY_TEXT", "#FFFFFF")
    entry_category = helper.theme_rgb(device_name, "DRUMBO_BROWSER_ENTRY_CATEGORY", "#C0C0C0")
    error_color = helper.theme_rgb(device_name, "DRUMBO_BROWSER_ERROR_COLOR", "#FF7A79")

    title_font = pygame.font.Font(
        cfg.font_helper.main_font(getattr(cfg, "DRUMBO_BROWSER_TITLE_WEIGHT", cfg.PRESET_FONT_WEIGHT)),
        int(getattr(cfg, "DRUMBO_BROWSER_TITLE_SIZE", 20)),
    )
    entry_font = pygame.font.Font(
        cfg.font_helper.main_font(getattr(cfg, "DRUMBO_BROWSER_ENTRY_WEIGHT", cfg.PRESET_FONT_WEIGHT)),
        int(getattr(cfg, "DRUMBO_BROWSER_ENTRY_SIZE", 16)),
    )
    category_font = pygame.font.Font(
        cfg.font_helper.main_font(getattr(cfg, "DRUMBO_BROWSER_CATEGORY_WEIGHT", cfg.PRESET_FONT_WEIGHT)),
        int(getattr(cfg, "DRUMBO_BROWSER_CATEGORY_SIZE", 13)),
    )

    pygame.draw.rect(screen, panel_bg, panel_rect, border_radius=10)
    pygame.draw.rect(screen, panel_border, panel_rect, width=1, border_radius=10)

    title_surface = title_font.render("Drumbo Instruments", True, title_color)
    screen.blit(title_surface, (panel_rect.x + 14, panel_rect.y + 4))

    for entry in state.get("entries", []):
        entry_rect = entry["rect"].move(0, offset_y)
        is_selected = entry["id"] == state.get("selected_id")
        bg = entry_selected_bg if is_selected else entry_bg
        border = entry_selected_border if is_selected else entry_border
        pygame.draw.rect(screen, bg, entry_rect, border_radius=8)
        pygame.draw.rect(screen, border, entry_rect, width=1, border_radius=8)

        label_surface = entry_font.render(entry["display_name"], True, entry_text)
        screen.blit(label_surface, (entry_rect.x + 10, entry_rect.y + 8))

        category = entry.get("category")
        if category:
            category_surface = category_font.render(str(category), True, entry_category)
            screen.blit(category_surface, (entry_rect.x + 10, entry_rect.bottom - category_surface.get_height() - 6))

    if state.get("empty_message"):
        empty_surface = entry_font.render(state["empty_message"], True, entry_text)
        screen.blit(empty_surface, (
            panel_rect.x + 14,
            panel_rect.y + int(panel_rect.height * 0.5) - empty_surface.get_height() // 2,
        ))

    error_y = panel_rect.bottom - 6
    for line in state.get("errors", []):
        error_surface = category_font.render(line, True, error_color)
        error_y -= error_surface.get_height() + 4
        screen.blit(error_surface, (panel_rect.x + 14, error_y))

    showlog.debug("*[ModuleDrumbo] Browser drawn")


def _handle_drumbo_browser_event(pos, msg_queue) -> bool:
    state = _DRUMBO_BROWSER
    if not state.get("active") or not state.get("rect"):
        return False

    hit_id = None
    for entry in state.get("entries", []):
        rect = entry.get("rect")
        if rect and rect.collidepoint(pos):
            hit_id = entry["id"]
            break

    if hit_id is None:
        rect = state.get("rect")
        if rect and rect.collidepoint(pos):
            showlog.debug("*[ModuleDrumbo] Browser background pressed")
            return True
        return False

    previous = state.get("selected_id")
    state["selected_id"] = hit_id

    if hit_id != previous:
        showlog.debug(f"*[ModuleDrumbo] Instrument selected: {hit_id}")
        if msg_queue:
            try:
                msg_queue.put(("drumbo_instrument_select", hit_id))
            except Exception as exc:
                showlog.warn(f"*[ModuleDrumbo] Queue send failed: {exc}")
    else:
        showlog.debug(f"*[ModuleDrumbo] Instrument reselected: {hit_id}")

    return True


def _get_preset_margin_y() -> int:
    return _current_preset_margin_y if _current_preset_margin_y is not None else _DEFAULT_PRESET_MARGIN_Y


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
            content_height = last_btn.bottom + _get_preset_margin_y()
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
    global header_text, scroll_offset, selected_preset, _animation_files, _current_preset_margin_y
    
    showlog.debug(f"*[ANIM 1] [ModulePresets] init() called for module: {module_id}")

    try:
        # Apply module context and reset all scroll runtime FIRST to avoid carry-over
        active_module_id = module_id
        active_module_instance = module_instance
        active_widget = widget
        _reset_scroll_runtime()

        margin_override = None

        if isinstance(module_id, str) and module_id.strip().lower() == "drumbo":
            _refresh_drumbo_instruments()
            _rebuild_drumbo_browser(screen)
            margin_override = _DRUMBO_BROWSER.get("preset_margin_y") or _DEFAULT_PRESET_MARGIN_Y
            showlog.debug(f"*[ModuleDrumbo] init margin={margin_override}")
        else:
            _reset_drumbo_browser_state()
            _current_preset_margin_y = _DEFAULT_PRESET_MARGIN_Y

        if margin_override is not None:
            _current_preset_margin_y = margin_override

        preset_buttons = []
        _animation_files = {}  # Reset animation file mapping
        header_text = f"{module_id.title()} Presets"
        screen.fill((0, 0, 0))

        showlog.debug(f"*[ANIM 2] module_id='{module_id}'")
        showlog.debug(f"*[ANIM 3] Checking if module is VK8M: {module_id.lower() == 'vk8m'}")

        # Check if module supports animations (VK8M with drawbar)
        animation_presets = []
        try:
            showlog.debug("*[ANIM 5] Attempting to import animation API")
            from plugins.ascii_animator_plugin import get_drawbar_animations
            from plugins.vk8m_plugin import ANIMATOR_READY
            showlog.debug(f"*[ANIM 6] Animation API imported, ANIMATOR_READY={ANIMATOR_READY}")
            
            if ANIMATOR_READY and module_id.lower() == "vk8m":
                showlog.debug("*[ANIM 7] Module is VK8M and ANIMATOR_READY, calling get_drawbar_animations()")
                animations = get_drawbar_animations()
                showlog.debug(f"*[ANIM 8] get_drawbar_animations() returned: {animations}")
                
                # Format as: "ANIM: wave" for display, store filename mapping
                for filename, name in animations:
                    label = f"ANIM: {name}"
                    animation_presets.append(label)
                    _animation_files[label] = filename
                    showlog.debug(f"*[ANIM 9] Added animation: label='{label}', filename='{filename}'")
                
                showlog.info(f"[ModulePresets] Found {len(animation_presets)} animation presets for VK8M")
                showlog.debug(f"*[ANIM 10] animation_presets list: {animation_presets}")
                showlog.debug(f"*[ANIM 11] _animation_files mapping: {_animation_files}")
            else:
                showlog.debug(f"*[ANIM 12] Skipping animations: ANIMATOR_READY={ANIMATOR_READY}, is_vk8m={module_id.lower() == 'vk8m'}")
        except Exception as e:
            showlog.debug(f"*[ANIM 13] Animation presets not available: {e}")
            import traceback
            showlog.debug(f"*[ANIM 14] Traceback: {traceback.format_exc()}")

        # Get preset list from preset_manager
        showlog.debug("*[ANIM 15] Getting preset list from preset_manager")
        pm = get_preset_manager()
        preset_names = pm.list_presets(module_id)
        
        if not preset_names:
            showlog.info(f"[ModulePresets] No presets found for {module_id}")
            preset_names = []
        
        showlog.debug(f"*[ANIM 16] Found {len(preset_names)} regular presets for {module_id}")

        # Add animation presets to the list (at the beginning)
        showlog.debug(f"*[ANIM 20] Before merge: animation_presets count={len(animation_presets)}, preset_names count={len(preset_names)}")
        if animation_presets:
            preset_names = animation_presets + preset_names
            showlog.info(f"[ModulePresets] Total presets with animations: {len(preset_names)}")
            showlog.debug(f"*[ANIM 21] After merge: preset_names count={len(preset_names)}")
            showlog.debug(f"*[ANIM 22] First 5 presets: {preset_names[:5]}")
        else:
            showlog.debug("*[ANIM 23] No animation presets to add")
        
        showlog.debug(f"*[ANIM 24] Final preset count: {len(preset_names)}")

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
    margin_y = _get_preset_margin_y()
    showlog.debug(f"*[ModuleDrumbo] loader load_id={load_id} margin_y={margin_y} count={len(final_labels)}")

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

        fill_sel         = helper.theme_rgb(device_name, "PRESET_LABEL_HIGHLIGHT", "#202020")
        font_sel         = helper.theme_rgb(device_name, "PRESET_FONT_HIGHLIGHT",  "#FFFFFF")
        fill_norm        = helper.theme_rgb(device_name, "PRESET_BUTTON_COLOR",    "#090909")
        font_norm        = helper.theme_rgb(device_name, "PRESET_TEXT_COLOR",      "#FF8000")
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
            
            # Check if this is an animation preset (starts with "ANIM:")
            is_animation = b["name"].startswith("ANIM:")

            # Use animation colors if it's an animation preset
            if is_animation:
                fill_color = helper.theme_rgb(device_name, "PRESET_ANIMATION_HIGHLIGHT", "#140606") if is_selected else helper.theme_rgb(device_name, "PRESET_ANIMATION_BUTTON", "#140606")
                font_color = helper.theme_rgb(device_name, "PRESET_FONT_HIGHLIGHT", "#000000") if is_selected else helper.theme_rgb(device_name, "PRESET_ANIMATION_TEXT", "#FFB088")
            else:
                fill_color = fill_sel if is_selected else fill_norm
                font_color = font_sel if is_selected else font_norm

            pygame.draw.rect(screen, fill_color, scrolled_rect, border_radius=6)
            text_surface = font.render(b["name"], True, font_color)
            screen.blit(
                text_surface,
                (scrolled_rect.x + 10,
                 scrolled_rect.y + (getattr(cfg, "PRESET_BUTTON_HEIGHT", 50) - text_surface.get_height()) // 2)
            )

        _draw_drumbo_browser(screen, device_name, offset_y)

        # --- Draw simple scroll bar (optional) ---
        if preset_buttons:
            last_btn = preset_buttons[-1]["rect"]
            content_height = last_btn.bottom + _get_preset_margin_y()
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

        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN):
            if _handle_drumbo_browser_event(pos, msg_queue):
                return

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
                target_mode = "dials"
                try:
                    previous_mode = navigator.go_back()
                    if previous_mode and previous_mode != "module_presets":
                        target_mode = previous_mode
                    elif previous_mode == "module_presets":
                        showlog.debug("[ModulePresets] navigator returned module_presets; falling back to dials")
                except Exception as nav_err:
                    showlog.debug(f"[ModulePresets] navigator.go_back() failed: {nav_err}")

                if active_widget and hasattr(active_widget, "mark_dirty"):
                    try:
                        active_widget.mark_dirty()
                    except Exception as mark_err:
                        showlog.debug(f"[ModulePresets] active_widget.mark_dirty() failed: {mark_err}")

                try:
                    module_base.request_custom_widget_redraw(include_overlays=True)
                except Exception as deferred_err:
                    showlog.debug(f"[ModulePresets] request_custom_widget_redraw failed: {deferred_err}")

                if msg_queue:
                    msg_queue.put(("ui_mode", target_mode))
                    msg_queue.put(("invalidate", None))
                    msg_queue.put(("force_redraw", 3))
                else:
                    showlog.warn("[ModulePresets] Back button pressed without msg_queue")
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

                    # --- Check if this is an animation preset ---
                    if preset_name.startswith("ANIM:"):
                        showlog.debug(f"*[ANIM LOAD 1] Detected animation preset click: '{preset_name}'")
                        try:
                            showlog.debug("*[ANIM LOAD 2] Attempting to import VK8M plugin")
                            from plugins.vk8m_plugin import ANIMATOR_READY
                            showlog.debug(f"*[ANIM LOAD 3] ANIMATOR_READY={ANIMATOR_READY}")
                            showlog.debug(f"*[ANIM LOAD 4] active_module_id='{active_module_id}'")
                            showlog.debug(f"*[ANIM LOAD 5] Is VK8M: {active_module_id and active_module_id.lower() == 'vk8m'}")
                            
                            if ANIMATOR_READY and active_module_id and active_module_id.lower() == "vk8m":
                                showlog.debug("*[ANIM LOAD 6] Conditions met, getting animation filename")
                                
                                # Get the animation filename from global mapping
                                anim_filename = _animation_files.get(preset_name)
                                showlog.debug(f"*[ANIM LOAD 7] Looking up '{preset_name}' in _animation_files")
                                showlog.debug(f"*[ANIM LOAD 8] _animation_files mapping: {_animation_files}")
                                showlog.debug(f"*[ANIM LOAD 9] Found filename: {anim_filename}")
                                
                                if not anim_filename:
                                    # Fallback: try to reconstruct from name
                                    display_name = preset_name.replace("ANIM:", "").strip()
                                    anim_filename = f"{display_name}.drawbar.json"
                                    showlog.debug(f"*[ANIM LOAD 10] Using fallback filename: {anim_filename}")
                                
                                showlog.info(f"[ModulePresets] Loading animation: {anim_filename}")
                                showlog.debug(f"*[ANIM LOAD 11] active_module_instance type: {type(active_module_instance)}")
                                showlog.debug(f"*[ANIM LOAD 12] Has load_animation_preset: {hasattr(active_module_instance, 'load_animation_preset')}")
                                
                                # Load animation via VK8M module
                                if active_module_instance and hasattr(active_module_instance, 'load_animation_preset'):
                                    showlog.debug(f"*[ANIM LOAD 13] Calling load_animation_preset('{anim_filename}')")
                                    active_module_instance.load_animation_preset(anim_filename)
                                    showlog.info(f"[ModulePresets] Animation loaded successfully")
                                    showlog.debug("*[ANIM LOAD 14] Animation load completed")
                                    selected_preset = preset_name
                                    
                                    # Trigger UI update to reflect button state change
                                    if msg_queue:
                                        msg_queue.put(("invalidate", None))
                                else:
                                    showlog.error("*[ANIM LOAD 15] VK8M module doesn't support animations")
                            else:
                                showlog.debug(f"*[ANIM LOAD 16] Conditions NOT met: ANIMATOR_READY={ANIMATOR_READY}, module={active_module_id}")
                        except Exception as e:
                            showlog.error(f"*[ANIM LOAD 17] Animation preset handling failed: {e}")
                            import traceback
                            showlog.error(f"*[ANIM LOAD 18] Traceback: {traceback.format_exc()}")
                        return  # Don't process as regular preset

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
                content_height = last_btn.bottom + _get_preset_margin_y()
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

