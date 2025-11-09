# /build/pages/presets.py
import os, sys
if __package__ is None or __package__ == "":
    build_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if build_root not in sys.path:
        sys.path.insert(0, build_root)

import pygame
import threading, time
from typing import Optional

import showlog
import device_presets
import device_patches
import midiserver
import config as cfg
import helper

try:
    from plugins import drumbo_instrument_service as _drumbo_service
except Exception:
    _drumbo_service = None

_drumbo_registry_cache = {}
_drumbo_errors_cache = []

# Drumbo instrument browser UI state
_DRUMBO_BROWSER = {
    "active": False,
    "rect": None,
    "entries": [],
    "errors": [],
    "selected_id": None,
    "preset_margin_y": None,
    "empty_message": None,
}

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
active_device = None
active_section = None
header_text = ""
_current_load_id = 0  # cancels stale background label-fill workers

# Animation preset metadata (filename mapping)
_animation_files = {}  # {"ANIM: wave": "wave.drawbar.json"}

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

_DEFAULT_PRESET_MARGIN_Y = int(getattr(cfg, "PRESET_MARGIN_Y", 60))
_current_preset_margin_y: Optional[int] = None

is_dragging = False
last_mouse_y = 0
selected_preset = 1  # remember last highlighted preset number
preset_source = "patches"   # default mode; set to "presets" when External selected

_SCROLL_INVERT = bool(getattr(cfg, "PRESET_SCROLL_INVERT", False))


def _refresh_drumbo_instruments():
    """Refresh Drumbo instrument metadata when entering the loader page."""
    global _drumbo_registry_cache, _drumbo_errors_cache
    if not _drumbo_service:
        return
    try:
        result = _drumbo_service.refresh()
    except Exception as exc:
        showlog.warn(f"[Presets] Drumbo instrument refresh failed: {exc}")
        return

    _drumbo_registry_cache = result.instruments
    _drumbo_errors_cache = list(result.errors or [])

    showlog.info(
        f"[Presets] Drumbo instrument scan discovered {len(result.instruments)} entries"
    )
    for line in _drumbo_errors_cache:
        showlog.warn(f"[Presets] Drumbo instrument warning: {line}")


def get_drumbo_instruments():
    """Return the cached Drumbo instrument registry, refreshing if needed."""
    if not _drumbo_service:
        return {}
    if not _drumbo_registry_cache:
        _refresh_drumbo_instruments()
    return _drumbo_registry_cache


def get_drumbo_instrument_errors():
    """Return any errors collected during the last Drumbo instrument scan."""
    if not _drumbo_service:
        return []
    if not _drumbo_registry_cache and not _drumbo_errors_cache:
        _refresh_drumbo_instruments()
    return _drumbo_errors_cache


def get_selected_drumbo_instrument() -> Optional[str]:
    selected = _DRUMBO_BROWSER.get("selected_id")
    showlog.debug(f"*[DRUMBO_UI] Selected instrument requested: {selected}")
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
    """Recompute Drumbo instrument browser layout and state."""
    global _current_preset_margin_y
    if screen is None or not _drumbo_service:
        _reset_drumbo_browser_state()
        return

    registry = get_drumbo_instruments() or {}
    errors = list(get_drumbo_instrument_errors() or [])

    try:
        margin_x = int(getattr(cfg, "DRUMBO_BROWSER_MARGIN_X", 32))
        top_padding = int(getattr(cfg, "DRUMBO_BROWSER_TOP_PADDING", 12))
        bottom_padding = int(getattr(cfg, "DRUMBO_BROWSER_BOTTOM_PADDING", 12))
        entry_height = int(getattr(cfg, "DRUMBO_BROWSER_ENTRY_HEIGHT", 48))
        entry_spacing = int(getattr(cfg, "DRUMBO_BROWSER_ENTRY_SPACING", 8))
        title_height = int(getattr(cfg, "DRUMBO_BROWSER_TITLE_HEIGHT", 32))
        error_line_height = int(getattr(cfg, "DRUMBO_BROWSER_ERROR_HEIGHT", 20))
        preset_gap = int(getattr(cfg, "DRUMBO_BROWSER_PRESET_GAP", 24))
        header_height = int(getattr(cfg, "HEADER_HEIGHT", 70))
        log_bar_h = int(getattr(cfg, "LOG_BAR_HEIGHT", 20))

        sorted_specs = sorted(registry.values(), key=lambda spec: spec.display_name.lower())
        entry_count = len(sorted_specs)
        entry_block_height = max(0, entry_count * entry_height + max(0, entry_count - 1) * entry_spacing)
        empty_message = None if entry_count else "No Drumbo instruments found"
        info_block_height = entry_height if empty_message else entry_block_height
        error_block_height = max(0, len(errors) * error_line_height)

        panel_left = margin_x
        panel_width = max(0, screen.get_width() - margin_x * 2)
        panel_top = header_height + top_padding
        panel_height = title_height + info_block_height + error_block_height + bottom_padding
        available_height = max(0, screen.get_height() - log_bar_h - panel_top)
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
                showlog.warn(f"*[DRUMBO_UI] Failed to get service selection: {exc}")

        selected_id = prev_selected if prev_selected in registry else None
        if not selected_id and service_selected in registry:
            selected_id = service_selected
        if not selected_id and sorted_specs:
            selected_id = sorted_specs[0].id

        if selected_id and _drumbo_service:
            try:
                _drumbo_service.select(selected_id, auto_refresh=False)
            except Exception as exc:
                showlog.warn(f"*[DRUMBO_UI] Failed to sync service selection: {exc}")

        entries = []
        current_y = panel_top + title_height
        for spec in sorted_specs:
            rect = pygame.Rect(panel_left + 16, current_y, panel_width - 32, entry_height)
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
            f"*[DRUMBO_UI] Browser rebuilt: entries={entry_count}, errors={len(errors)}, panel_h={panel_rect.height}, selected={selected_id}"
        )
    except Exception as exc:
        showlog.warn(f"*[DRUMBO_UI] Browser rebuild failed: {exc}")
        _reset_drumbo_browser_state()


def _draw_drumbo_browser(screen, offset_y=0):
    """Render the Drumbo instrument browser if active."""
    state = _DRUMBO_BROWSER
    if not state.get("active") or not state.get("rect"):
        return

    device_name = active_device
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
        int(getattr(cfg, "DRUMBO_BROWSER_TITLE_SIZE", 22)),
    )
    entry_font = pygame.font.Font(
        cfg.font_helper.main_font(getattr(cfg, "DRUMBO_BROWSER_ENTRY_WEIGHT", cfg.PRESET_FONT_WEIGHT)),
        int(getattr(cfg, "DRUMBO_BROWSER_ENTRY_SIZE", 18)),
    )
    category_font = pygame.font.Font(
        cfg.font_helper.main_font(getattr(cfg, "DRUMBO_BROWSER_CATEGORY_WEIGHT", cfg.PRESET_FONT_WEIGHT)),
        int(getattr(cfg, "DRUMBO_BROWSER_CATEGORY_SIZE", 14)),
    )

    pygame.draw.rect(screen, panel_bg, panel_rect, border_radius=10)
    pygame.draw.rect(screen, panel_border, panel_rect, width=1, border_radius=10)

    title_surface = title_font.render("Drumbo Instruments", True, title_color)
    screen.blit(title_surface, (panel_rect.x + 16, panel_rect.y + 4))

    for entry in state.get("entries", []):
        entry_rect = entry["rect"].move(0, offset_y)
        is_selected = entry["id"] == state.get("selected_id")
        bg = entry_selected_bg if is_selected else entry_bg
        border = entry_selected_border if is_selected else entry_border
        pygame.draw.rect(screen, bg, entry_rect, border_radius=8)
        pygame.draw.rect(screen, border, entry_rect, width=1, border_radius=8)

        label_surface = entry_font.render(entry["display_name"], True, entry_text)
        screen.blit(label_surface, (entry_rect.x + 12, entry_rect.y + 10))

        category = entry.get("category")
        if category:
            category_surface = category_font.render(str(category), True, entry_category)
            screen.blit(category_surface, (entry_rect.x + 12, entry_rect.y + entry_rect.height - category_surface.get_height() - 8))

    if state.get("empty_message"):
        empty_surface = entry_font.render(state["empty_message"], True, entry_text)
        message_pos = (
            panel_rect.x + 16,
            panel_rect.y + int(panel_rect.height * 0.5) - empty_surface.get_height() // 2,
        )
        screen.blit(empty_surface, message_pos)

    error_y = panel_rect.bottom - 8
    for line in state.get("errors", []):
        error_surface = category_font.render(line, True, error_color)
        error_y -= error_surface.get_height() + 4
        screen.blit(error_surface, (panel_rect.x + 16, error_y))

    showlog.debug("*[DRUMBO_UI] Browser drawn")


def _handle_drumbo_browser_event(pos, msg_queue) -> bool:
    """Handle pointer events targeting the Drumbo browser."""
    state = _DRUMBO_BROWSER
    if not state.get("active") or not state.get("rect"):
        return False

    hit_id = None
    for entry in state.get("entries", []):
        if entry.get("rect") and entry["rect"].collidepoint(pos):
            hit_id = entry["id"]
            break

    if hit_id is None:
        rect = state.get("rect")
        if rect and rect.collidepoint(pos):
            showlog.debug("*[DRUMBO_UI] Browser background pressed")
            return True
        return False

    previous = state.get("selected_id")
    state["selected_id"] = hit_id

    if hit_id != previous:
        if msg_queue:
            try:
                msg_queue.put(("drumbo_instrument_select", hit_id))
            except Exception as exc:
                showlog.warn(f"*[DRUMBO_UI] Queue send failed: {exc}")
        showlog.debug(f"*[DRUMBO_UI] Instrument selected: {hit_id}")
    else:
        showlog.debug(f"*[DRUMBO_UI] Instrument reselected: {hit_id}")

    return True

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
            log_bar_h = getattr(cfg, "LOG_BAR_HEIGHT", 20)
            usable_height = screen.get_height() - log_bar_h
            max_scroll = max(0, content_height - usable_height)

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


# Track a pending align so we don't queue duplicates
_pending_align = {"load_id": 0, "preset": None}

def _defer_ensure_visible(preset_num, labels_snapshot, header_h, pad_top):
    """
    Wait briefly for buttons to appear; align when target exists,
    else fall back after a max wait.
    """
    load_id_snapshot = _current_load_id
    target_prefix = f"{preset_num:02d}:"

    max_wait_ms = int(getattr(cfg, "PRESET_ALIGN_MAX_WAIT_MS", 1500))
    poll_ms = 30
    waited = 0

    while waited < max_wait_ms:
        # Abort if load changed or page changed
        if load_id_snapshot != _current_load_id or active_device is None:
            return

        # If the target button exists, align to its rect
        for b in preset_buttons:
            if b["name"].startswith(target_prefix):
                rect = b["rect"]
                target = max(0, rect.top - header_h - pad_top)
                _start_scroll_animation(target)
                return

        time.sleep(poll_ms / 1000.0)
        waited += poll_ms

    # Fallback math by row after timeout
    try:
        cols = int(getattr(cfg, "NUMBER_OF_PRESET_COLUMNS", 2))
        row_height = int(getattr(cfg, "PRESET_BUTTON_HEIGHT", 50))
        spacing_y = int(getattr(cfg, "PRESET_SPACING_Y", 12))
        margin_y = _get_preset_margin_y()
        row = (preset_num - 1) // max(1, cols)
        y_top = margin_y + row * (row_height + spacing_y)
        target = max(0, y_top - header_h - pad_top)
        _start_scroll_animation(target)
    except Exception:
        pass


# -------------------------------------------------------
# Init
# -------------------------------------------------------

def init(screen, device_name, section_name):
    """Load presets for the given device and section."""
    global preset_buttons, back_rect, active_device, active_section, header_text, scroll_offset, selected_preset, preset_source, _animation_files, _current_preset_margin_y
    showlog.debug("*[ANIM 1] Presets.init() called")
    showlog.debug(f"*[ANIM 2] device_name='{device_name}', section_name='{section_name}'")

    try:
        showlog.info(f"Initializing presets for device: {device_name}, section: {section_name}")

        # Apply device/section and reset all scroll runtime FIRST to avoid carry-over.
        active_device = device_name
        active_section = section_name
        _reset_scroll_runtime()

        margin_override = None

        if isinstance(device_name, str) and device_name.strip().lower() == "drumbo":
            _refresh_drumbo_instruments()
            _rebuild_drumbo_browser(screen)
            margin_override = _DRUMBO_BROWSER.get("preset_margin_y") or _DEFAULT_PRESET_MARGIN_Y
            showlog.debug(f"*[DRUMBO_UI] Drumbo presets init margin={margin_override}")
        else:
            _reset_drumbo_browser_state()
            _current_preset_margin_y = _DEFAULT_PRESET_MARGIN_Y

        preset_buttons = []
        _animation_files = {}  # Reset animation file mapping
        header_text = f"{device_name} Presets"
        log_bar_h = getattr(cfg, "LOG_BAR_HEIGHT", 20)
        screen.fill((0, 0, 0), pygame.Rect(0, 0, screen.get_width(), screen.get_height() - log_bar_h))


        showlog.debug(f"*[ANIM 3] device_name.lower()='{device_name.lower()}'")
        showlog.debug(f"*[ANIM 4] Checking if device is VK8M: {device_name.lower() == 'vk8m'}")

        # Check if device supports animations (VK8M with drawbar)
        animation_presets = []
        try:
            showlog.debug("*[ANIM 5] Attempting to import animation API")
            from plugins.vk8m_plugin import ANIMATOR_READY, get_drawbar_animations
            showlog.debug(f"*[ANIM 6] Animation API imported, ANIMATOR_READY={ANIMATOR_READY}")
            
            if ANIMATOR_READY and device_name.lower() == "vk8m":
                showlog.debug("*[ANIM 7] Device is VK8M and ANIMATOR_READY, calling get_drawbar_animations()")
                animations = get_drawbar_animations()
                showlog.debug(f"*[ANIM 8] get_drawbar_animations() returned: {animations}")
                
                # Format as: "ANIM: wave" for display, store filename mapping
                for filename, name in animations:
                    label = f"ANIM: {name}"
                    animation_presets.append(label)
                    _animation_files[label] = filename
                    showlog.debug(f"*[ANIM 9] Added animation: label='{label}', filename='{filename}'")
                
                showlog.info(f"[Presets] Found {len(animation_presets)} animation presets for VK8M")
                showlog.debug(f"*[ANIM 10] animation_presets list: {animation_presets}")
                showlog.debug(f"*[ANIM 11] _animation_files mapping: {_animation_files}")
            else:
                showlog.debug(f"*[ANIM 12] Skipping animations: ANIMATOR_READY={ANIMATOR_READY}, is_vk8m={device_name.lower() == 'vk8m'}")
        except Exception as e:
            showlog.debug(f"*[ANIM 13] Animation presets not available: {e}")
            import traceback
            showlog.debug(f"*[ANIM 14] Traceback: {traceback.format_exc()}")

        # Probe patch source(s)
        showlog.debug("*[ANIM 15] Probing patch sources")
        try:
            patch_pairs = device_patches.list_patches(device_name)
            showlog.debug(f"*[ANIM 16] Found {len(patch_pairs)} patches")
        except Exception:
            patch_pairs = []
            showlog.debug("*[ANIM 17] No patches found")

        if patch_pairs:
            full_labels = [f"{int(num):02d}: {name}" for num, name in patch_pairs]
            used_source = "patches"
            showlog.debug(f"*[ANIM 18] Using patches source, {len(full_labels)} labels")
        else:
            full_labels = device_presets.list_presets(device_name, page_id=section_name)
            used_source = "presets" if full_labels else "none"
            showlog.debug(f"*[ANIM 19] Using presets source: '{used_source}', {len(full_labels)} labels")

        if used_source in ("patches", "presets"):
            preset_source = used_source
        
        # Add animation presets to the list (at the beginning)
        showlog.debug(f"*[ANIM 20] Before merge: animation_presets count={len(animation_presets)}, full_labels count={len(full_labels)}")
        if animation_presets:
            full_labels = animation_presets + full_labels
            showlog.info(f"[Presets] Total presets with animations: {len(full_labels)}")
            showlog.debug(f"*[ANIM 21] After merge: full_labels count={len(full_labels)}")
            showlog.debug(f"*[ANIM 22] First 5 labels: {full_labels[:5]}")
        else:
            showlog.debug("*[ANIM 23] No animation presets to add")

        showlog.debug(f"Source: {used_source} for {device_name}")
        count = len(full_labels)
        showlog.debug(f"*[ANIM 24] Final preset count: {count}")

        # Progressive loader (append buttons one-by-one)
        _start_progressive_loader(full_labels, device_name, section_name, screen, margin_y_override=margin_override)
        showlog.debug("[INIT] Presets initialized successfully (progressive)")

        # Header dropdown
        from control import presets_control
        presets_control.set_context_menu()

        showlog.debug(f"[PRESETS_INIT] dev={device_name} section_name={section_name} count={count}")

        # --- Initial scroll plan: after a delay, align to current preset if known ---
        try:
            import control.global_control as gc
            info = gc.get_current_preset(device_name)
        except Exception:
            info = None

        def _plan_initial_scroll(load_id_snapshot, dev_name, sect_name, labels_snapshot):
            try:
                delay_ms = int(getattr(cfg, "PRESET_INITIAL_SCROLL_DELAY_MS", 1000))
                time.sleep(max(0, delay_ms) / 1000.0)

                # Abort if page/device changed or a new load started
                if load_id_snapshot != _current_load_id or dev_name != active_device or sect_name != active_section:
                    return

                header_h = int(getattr(cfg, "HEADER_HEIGHT", 70))
                pad_top = int(getattr(cfg, "PRESET_SELECTED_PADDING", 0))
                cols = int(getattr(cfg, "NUMBER_OF_PRESET_COLUMNS", 2))
                row_height = int(getattr(cfg, "PRESET_BUTTON_HEIGHT", 50))
                spacing_y = int(getattr(cfg, "PRESET_SPACING_Y", 12))
                margin_y = _get_preset_margin_y()

                prog_local = None
                name_local = None
                if info:
                    prog_local = info.get("program")
                    name_local = str(info.get("preset")) if info.get("preset") else None

                target_offset = None

                if isinstance(prog_local, int) and prog_local >= 1:
                    # reuse the defer logic so we wait for the actual button
                    _pending_align.update({"load_id": _current_load_id, "preset": prog_local})
                    threading.Thread(
                        target=_defer_ensure_visible,
                        args=(prog_local, list(labels_snapshot), header_h, pad_top),
                        daemon=True,
                        name=f"presets_initial_align_{prog_local:02d}"
                    ).start()


                # Else try by name against snapshot
                if target_offset is None and name_local:
                    try:
                        idx = next(i for i, lab in enumerate(labels_snapshot) if str(lab).endswith(name_local))
                        row = int(idx) // max(1, cols)
                        y_top = margin_y + row * (row_height + spacing_y)
                        target_offset = max(0, y_top - header_h - pad_top)
                    except Exception:
                        pass

                if target_offset is not None:
                    _start_scroll_animation(target_offset)
            except Exception as e:
                showlog.debug(f"[PRESETS_INIT] initial scroll plan failed: {e}")

        try:
            threading.Thread(
                target=_plan_initial_scroll,
                args=(_current_load_id, device_name, section_name, list(full_labels)),
                daemon=True,
                name="presets_initial_scroll",
            ).start()
        except Exception as e:
            showlog.debug(f"[PRESETS_INIT] could not schedule initial scroll: {e}")

    except Exception as e:
        showlog.error(f"An error occurred in init: {e}")


def reload_presets(screen, preset_names):
    """Rebuild preset_buttons list with new source (internal/external)."""
    global preset_buttons, _current_preset_margin_y
    preset_buttons.clear()

    # Reset runtime so swapping sources never resumes an old anim
    _reset_scroll_runtime()

    margin_override = None
    if active_device and isinstance(active_device, str) and active_device.strip().lower() == "drumbo":
        _rebuild_drumbo_browser(screen)
        margin_override = _DRUMBO_BROWSER.get("preset_margin_y") or _DEFAULT_PRESET_MARGIN_Y
        showlog.debug(f"*[DRUMBO_UI] Drumbo reload margin={margin_override}")
    else:
        _reset_drumbo_browser_state()
        _current_preset_margin_y = _DEFAULT_PRESET_MARGIN_Y

    # Start progressive fill with provided names
    _start_progressive_loader(preset_names, active_device, active_section, screen, margin_y_override=margin_override)
    # Let main loop draw next frame


def _start_progressive_loader(final_labels, device_name, section_name, screen, *, margin_y_override: Optional[int] = None):
    """Spawn a daemon thread to populate labels with a small delay per item.
    Guards with a load_id to avoid updating after device/page changes.
    """
    global _current_load_id, _current_preset_margin_y
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
    margin_y = margin_y_override if margin_y_override is not None else _DEFAULT_PRESET_MARGIN_Y
    _current_preset_margin_y = margin_y

    showlog.debug(
        f"*[PRESETS_LOADER] load_id={load_id} count={len(final_labels)} margin_y={margin_y}"
    )

    def worker():
        try:
            for idx, label in enumerate(final_labels):
                # Abort if a new load started or device/page changed
                if load_id != _current_load_id or device_name != active_device or section_name != active_section:
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
            showlog.debug(f"*[PRESETS_LOADER] load_id={load_id} worker done")
        except Exception as e:
            showlog.error(f"[PRESETS] progressive loader error: {e}")

    t = threading.Thread(target=worker, name="presets_loader", daemon=True)
    t.start()


# -------------------------------------------------------
# Shared builder (formatting + layout like init) (kept for parity)
# -------------------------------------------------------

def _build_preset_buttons(screen, preset_names):
    """Apply init-style formatting and build button rects for given names."""
    global preset_buttons

    max_len = getattr(cfg, "PRESET_NAME_MAX_LENGTH", 22)
    safe_names = []
    for name in preset_names:
        full = str(name)
        label = (full[:max_len].rstrip()) if isinstance(name, str) else full
        safe_names.append((label, full))

    font = pygame.font.Font(cfg.font_helper.main_font(cfg.PRESET_FONT_WEIGHT), int(getattr(cfg, "PRESET_FONT_SIZE", 20)))
    text_color = helper.hex_to_rgb(getattr(cfg, "PRESET_TEXT_COLOR", "#FFFFFF"))
    cols = getattr(cfg, "NUMBER_OF_PRESET_COLUMNS", 2)
    col_width = (screen.get_width() - getattr(cfg, "PRESET_MARGIN_X", 40) * 2) // cols
    row_height = getattr(cfg, "PRESET_BUTTON_HEIGHT", 50)
    spacing_y = getattr(cfg, "PRESET_SPACING_Y", 12)
    margin_y = _get_preset_margin_y()

    for i, (label, full_name) in enumerate(safe_names):
        showlog.verbose(f"Creating button for preset: {label} (full='{full_name}')")
        col = i % cols
        row = i // cols
        x = getattr(cfg, "PRESET_MARGIN_X", 40) + col * col_width + (col_width - getattr(cfg, "PRESET_BUTTON_WIDTH", 165)) // 2
        y = margin_y + row * (row_height + spacing_y)
        rect = pygame.Rect(x, y, getattr(cfg, "PRESET_BUTTON_WIDTH", 165), getattr(cfg, "PRESET_BUTTON_HEIGHT", 50))
        text_surface = font.render(label, True, text_color)
        preset_buttons.append({
            "rect": rect,
            "text": text_surface,
            "name": label,          # display label (possibly truncated)
            "full_name": full_name  # original full name for lookups
        })


# -------------------------------------------------------
# Draw
# -------------------------------------------------------

def draw(screen, offset_y=0):
    """Render preset buttons, header, and log, with optional vertical offset."""
    global selected_preset
    log_bar_h = getattr(cfg, "LOG_BAR_HEIGHT", 20)
    usable_height = screen.get_height() - log_bar_h

    safe_name = 'LOADING' if not (0 <= selected_preset < len(preset_buttons)) else preset_buttons[selected_preset]['name']
    showlog.verbose(f"[PRESETS DRAW] selected={selected_preset} total={len(preset_buttons)} name={safe_name}")

    # Advance scroll animation if active + inertia
    _update_scroll_animation()
    _update_inertia(screen)

    log_bar_h = getattr(cfg, "LOG_BAR_HEIGHT", 20)
    screen.fill((0, 0, 0), pygame.Rect(0, 0, screen.get_width(), screen.get_height() - log_bar_h))

    try:
        # --- Theme-aware colour fallbacks (device + config + defaults) ---
        device_name = active_device

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
            if scrolled_rect.bottom <= 0 or scrolled_rect.top >= usable_height - getattr(cfg, "PRESET_BUTTON_HEIGHT", 50):
                continue


            # Check if this preset should be highlighted
            is_selected = False
            if selected_preset is not None:
                try:
                    if b["name"].startswith(f"{selected_preset:02d}:"):
                        is_selected = True
                except Exception:
                    pass
            
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

        _draw_drumbo_browser(screen, offset_y)

        # --- Draw simple scroll bar (optional) ---
        if preset_buttons:
            last_btn = preset_buttons[-1]["rect"]
            content_height = last_btn.bottom + _get_preset_margin_y()
            view_height = usable_height
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
        showlog.error(f"An error occurred in draw: {e}")


# -------------------------------------------------------
# Highlight + ensure visible
# -------------------------------------------------------

def highlight_preset(screen, raw_message: str):
    """
    React to a [PATCH_SELECT] PSR-36|17.Sax style message.
    Highlights the matching preset button and redraws the page.
    """
    if not raw_message.startswith("[PATCH_SELECT]"):
        return  # ignore unrelated messages

    core = raw_message[len("[PATCH_SELECT]"):].strip()

    # Parse "DEVICE|NN.Name"
    try:
        dev, rest = core.split("|", 1)
        num_str, name = rest.split(".", 1)
        preset_num = int(num_str)
    except Exception:
        return  # bad format, ignore

    target_prefix = f"{preset_num:02d}:"
    font = pygame.font.Font(cfg.font_helper.main_font(cfg.PRESET_FONT_WEIGHT), int(getattr(cfg, "PRESET_FONT_SIZE", 20)))

    for b in preset_buttons:
        rect = b["rect"].move(0, -scroll_offset)
        name_text = b["name"]

        is_selected = name_text.startswith(target_prefix)

        device_name = active_device

        if is_selected:
            fill_color = helper.theme_rgb(device_name, "PRESET_LABEL_HIGHLIGHT", "#202020")
            font_color = helper.theme_rgb(device_name, "PRESET_FONT_HIGHLIGHT",  "#FFFFFF")
        else:
            fill_color = helper.theme_rgb(device_name, "PRESET_BUTTON_COLOR", "#090909")
            font_color = helper.theme_rgb(device_name, "PRESET_TEXT_COLOR",   "#FF8000")

        pygame.draw.rect(screen, fill_color, rect, border_radius=6)
        text_surface = font.render(name_text, True, font_color)
        screen.blit(
            text_surface,
            (rect.x + 10, rect.y + (getattr(cfg, "PRESET_BUTTON_HEIGHT", 50) - text_surface.get_height()) // 2),
        )

    showlog.debug(f"[HIGHLIGHT] {dev} preset {preset_num}: {name}")


def ensure_visible(preset_num, screen):
    """Align so the target preset's row sits just below the header, with defer until buttons exist."""
    header_height = int(getattr(cfg, "HEADER_HEIGHT", 70))
    pad_top = int(getattr(cfg, "PRESET_SELECTED_PADDING", 0))
    target_prefix = f"{preset_num:02d}:"

    # If button already exists, align now
    for b in preset_buttons:
        if b["name"].startswith(target_prefix):
            rect = b["rect"]
            target = max(0, rect.top - header_height - pad_top)
            _start_scroll_animation(target)
            return

    # Otherwise: spawn a one-shot waiter (avoid duplicates for the same load/preset)
    if _pending_align["load_id"] != _current_load_id or _pending_align["preset"] != preset_num:
        _pending_align["load_id"] = _current_load_id
        _pending_align["preset"] = preset_num
        threading.Thread(
            target=_defer_ensure_visible,
            args=(preset_num, [b.get("full_name", b["name"]) for b in preset_buttons], header_height, pad_top),
            daemon=True,
            name=f"presets_align_{preset_num:02d}"
        ).start()


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

            showlog.verbose(f"[DOWN] at {pos}")

            # --- Back button ---
            if back_rect and back_rect.collidepoint(pos):
                msg_queue.put(("ui_mode", "dials"))
                return

            # --- Detect preset press ---
            for b in preset_buttons:
                scrolled_rect = b["rect"].move(0, -scroll_offset)
                if scrolled_rect.collidepoint(pos):
                    showlog.debug(f"Button pressed: {b['name']}")

                    # --- Send LED/LCD feedback ---
                    try:
                        full = b.get("full_name", b["name"]).strip()
                        label = full.replace(":", ".", 1)
                        dev1_msg = f"DEV1 TXT:{active_device}"
                        dev2_msg = f"DEV2 TXT:{label}"
                        if getattr(cfg, "LED_IS_NETWORK", False):
                            from network import forward_to_pico
                            forward_to_pico(dev1_msg)
                            forward_to_pico(dev2_msg)
                        else:
                            from get_patch_and_send_local import output_msg
                            output_msg(dev1_msg)
                            output_msg(dev2_msg)
                    except Exception as e:
                        showlog.error(f"LED/LCD send failed: {e}")

                    # --- Handle preset activation logic ---
                    preset_name = b.get("full_name", b["name"])
                    
                    # Check if this is an animation preset
                    if preset_name.startswith("ANIM:"):
                        # Extract the actual filename from animation preset
                        try:
                            from plugins.vk8m_plugin import ANIMATOR_READY
                            if ANIMATOR_READY and active_device and active_device.lower() == "vk8m":
                                # Get the animation filename from global mapping
                                anim_filename = _animation_files.get(preset_name)
                                if not anim_filename:
                                    # Fallback: try to reconstruct from name
                                    display_name = preset_name.replace("ANIM:", "").strip()
                                    anim_filename = f"{display_name}.drawbar.json"
                                
                                showlog.info(f"[Presets] Loading animation: {anim_filename}")
                                
                                # Get the VK8M module and load animation
                                try:
                                    import control.global_control as gc
                                    vk8m_module = gc.get_module_instance("vk8m")
                                    if vk8m_module and hasattr(vk8m_module, 'load_animation_preset'):
                                        vk8m_module.load_animation_preset(anim_filename)
                                        showlog.info(f"[Presets] Animation loaded successfully")
                                    else:
                                        showlog.error("[Presets] VK8M module not found or doesn't support animations")
                                except Exception as e:
                                    showlog.error(f"[Presets] Failed to load animation: {e}")
                                    import traceback
                                    showlog.error(traceback.format_exc())
                        except Exception as e:
                            showlog.error(f"[Presets] Animation preset handling failed: {e}")
                        return  # Don't process as regular preset
                    
                    # Regular preset handling
                    from pages import presets as presets_page
                    if active_device and active_device.lower().startswith("quadraverb") and presets_page.preset_source == "presets":
                        preset_name = b.get("full_name", b["name"])
                        values = device_presets.get_pi_preset(active_device, active_section, preset_name)
                        used_page = active_section
                        if not values:
                            try:
                                for pg in device_presets.list_presets(active_device):
                                    if pg == active_section:
                                        continue
                                    v = device_presets.get_pi_preset(active_device, pg, preset_name)
                                    if v:
                                        values = v
                                        used_page = pg
                                        break
                            except Exception:
                                pass
                        if values:
                            midiserver.send_preset_values(active_device, used_page, values)
                            try:
                                import control.global_control as gc
                                gc.set_current_preset(preset_name, values)
                            except Exception:
                                pass
                        else:
                            showlog.warn(f"No External preset found for {preset_name}")
                    else:
                        patch = device_presets.get_patch(active_device, b.get("full_name", b["name"]))
                        if patch:
                            prog_num = patch["program"]
                            midiserver.send_program_change(prog_num)
                            try:
                                import control.global_control as gc
                                gc.set_current_preset(patch['name'], values=None, program=prog_num)
                            except Exception:
                                pass
                            msg_queue.put(f"[PATCH_SELECT_UI] {active_device}|{prog_num}.{patch['name']}")
                        else:
                            showlog.warn(f"[PRESETS] Patch not found for {active_device}: {b['name']}")

                    # --- Update highlight only (draw handled next frame) ---
                    name_str = b["name"].strip()
                    if ":" in name_str:
                        prefix = name_str.split(":", 1)[0].strip()
                        if prefix.isdigit():
                            try:
                                selected_preset = int(prefix)
                            except ValueError:
                                pass
                    return  # done handling press

        # ------------------------------------------------------------------
        # 2️⃣  Drag (scroll)
        # ------------------------------------------------------------------
        elif (event.type in (pygame.MOUSEMOTION, pygame.FINGERMOTION)) and is_dragging:
            current_y = int(event.y * screen.get_height()) if event.type == pygame.FINGERMOTION else event.pos[1]
            delta_y = current_y - last_mouse_y
            last_mouse_y = current_y
            
            # --- Compute scroll boundaries (exclude bottom log bar) ---
            log_bar_h = getattr(cfg, "LOG_BAR_HEIGHT", 20)
            usable_height = screen.get_height() - log_bar_h

            if preset_buttons:
                last_btn = preset_buttons[-1]["rect"]
                content_height = last_btn.bottom + _get_preset_margin_y()
                max_scroll = max(0, content_height - usable_height)
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
                showlog.verbose("[UP] drag ended")

    except Exception as e:
        showlog.error(f"Handle_event crashed: {e}")
