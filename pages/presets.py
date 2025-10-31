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

# -------------------------------------------------------
# Globals
# -------------------------------------------------------

preset_buttons = []
back_rect = None
active_device = None
active_section = None
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
selected_preset = 1  # remember last highlighted preset number
preset_source = "patches"   # default mode; set to "presets" when External selected

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
        margin_y = int(getattr(cfg, "PRESET_MARGIN_Y", 60))
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
    global preset_buttons, back_rect, active_device, active_section, header_text, scroll_offset, selected_preset, preset_source
    showlog.debug("Presets.init() was called")

    try:
        showlog.info(f"Initializing presets for device: {device_name}, section: {section_name}")

        # Apply device/section and reset all scroll runtime FIRST to avoid carry-over.
        active_device = device_name
        active_section = section_name
        _reset_scroll_runtime()

        preset_buttons = []
        header_text = f"{device_name} Presets"
        screen.fill((0, 0, 0))

        # Probe patch source(s)
        try:
            patch_pairs = device_patches.list_patches(device_name)
        except Exception:
            patch_pairs = []

        if patch_pairs:
            full_labels = [f"{int(num):02d}: {name}" for num, name in patch_pairs]
            used_source = "patches"
        else:
            full_labels = device_presets.list_presets(device_name, page_id=section_name)
            used_source = "presets" if full_labels else "none"

        if used_source in ("patches", "presets"):
            preset_source = used_source

        showlog.debug(f"Source: {used_source} for {device_name}")
        count = len(full_labels)

        # Progressive loader (append buttons one-by-one)
        _start_progressive_loader(full_labels, device_name, section_name, screen)
        showlog.debug("[INIT] Presets initialized successfully (progressive)")

        # Header dropdown
        from control import presets_control
        presets_control.set_context_menu()

        showlog.debug(f"*[PRESETS_INIT] dev={device_name} section_name={section_name} count={count}")

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
                margin_y = int(getattr(cfg, "PRESET_MARGIN_Y", 60))

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
                showlog.debug(f"*[PRESETS_INIT] initial scroll plan failed: {e}")

        try:
            threading.Thread(
                target=_plan_initial_scroll,
                args=(_current_load_id, device_name, section_name, list(full_labels)),
                daemon=True,
                name="presets_initial_scroll",
            ).start()
        except Exception as e:
            showlog.debug(f"*[PRESETS_INIT] could not schedule initial scroll: {e}")

    except Exception as e:
        showlog.error(f"An error occurred in init: {e}")


def reload_presets(screen, preset_names):
    """Rebuild preset_buttons list with new source (internal/external)."""
    global preset_buttons
    preset_buttons.clear()

    # Reset runtime so swapping sources never resumes an old anim
    _reset_scroll_runtime()

    # Start progressive fill with provided names
    _start_progressive_loader(preset_names, active_device, active_section, screen)
    # Let main loop draw next frame


def _start_progressive_loader(final_labels, device_name, section_name, screen):
    """Spawn a daemon thread to populate labels with a small delay per item.
    Guards with a load_id to avoid updating after device/page changes.
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

    for i, (label, full_name) in enumerate(safe_names):
        showlog.verbose(f"Creating button for preset: {label} (full='{full_name}')")
        col = i % cols
        row = i // cols
        x = getattr(cfg, "PRESET_MARGIN_X", 40) + col * col_width + (col_width - getattr(cfg, "PRESET_BUTTON_WIDTH", 165)) // 2
        y = getattr(cfg, "PRESET_MARGIN_Y", 60) + row * (row_height + spacing_y)
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

    safe_name = 'LOADING' if not (0 <= selected_preset < len(preset_buttons)) else preset_buttons[selected_preset]['name']
    showlog.verbose(f"[PRESETS DRAW] selected={selected_preset} total={len(preset_buttons)} name={safe_name}")

    # Advance scroll animation if active + inertia
    _update_scroll_animation()
    _update_inertia(screen)

    screen.fill((0, 0, 0))
    try:
        # --- Theme-aware colour fallbacks (device + config + defaults) ---
        device_name = active_device

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
            is_selected = False
            if selected_preset is not None:
                try:
                    if b["name"].startswith(f"{selected_preset:02d}:"):
                        is_selected = True
                except Exception:
                    pass

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
            fill_color = helper.theme_rgb(device_name, "PRESET_LABEL_HIGHLIGHT", "#6666FF")
            font_color = helper.theme_rgb(device_name, "PRESET_FONT_HIGHLIGHT",  "#FFFFFF")
        else:
            fill_color = helper.theme_rgb(device_name, "PRESET_BUTTON_COLOR", "#222222")
            font_color = helper.theme_rgb(device_name, "PRESET_TEXT_COLOR",   "#FFFFFF")

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
                showlog.verbose("[UP] drag ended")

    except Exception as e:
        showlog.error(f"Handle_event crashed: {e}")
