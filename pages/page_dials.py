# page_dials.py — optimized dials renderer (caching, fast blits, simple pointer)

import math
import pygame
import pygame.gfxdraw
import showlog
import helper
import config as cfg
import quadraverb_driver as qv  # (not used here directly, kept for parity)
import importlib

# --- imported shared UI assets ---
from assets import ui_button, ui_label

# globals so ui.py can import or modify them
button_rects = []
selected_buttons = set()  # keeps track of toggled/selected buttons

# -------------------------------------------------------------------------
# Cached unified BUTTONS lookup per device (modern - ONLY source of button config)
# -------------------------------------------------------------------------
_BTN_CACHE = {}


def get_device_button_specs(device_name: str):
    """
    Load BUTTONS from the current device module.
    Tries several import paths to match your layout (device.<name>, devices.<name>, <name>).
    Returns a dict { "1": spec, ..., "10": spec } or {}.
    """
    if not device_name:
        return {}

    cached = _BTN_CACHE.get(device_name)
    if cached is not None:
        return cached

    specs = {}
    lower = device_name.lower()

    # Try all likely module paths, stop at first that imports
    for modname in (f"device.{lower}", f"devices.{lower}", lower):
        try:
            mod = importlib.import_module(modname)
            # Force reload to get latest module changes (important for dev/testing)
            importlib.reload(mod)
            raw = getattr(mod, "BUTTONS", None)
            if raw:
                tmp = {}
                for item in raw:
                    try:
                        bid = str(item.get("id"))
                        if bid in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "10"):
                            tmp[bid] = item
                    except Exception:
                        continue
                specs = tmp
            break
        except Exception:
            continue

    if not specs:
        # No BUTTONS found - will use button IDs as labels
        try:
            showlog.debug(f"[DIALS] BUTTONS not found for device={device_name} (using button IDs as labels)")
        except Exception:
            pass

    _BTN_CACHE[device_name] = specs
    return specs

# =============================================================================
#                         R E N D E R  C A C H E S
# =============================================================================

# (4) Font cache — avoid rebuilding every frame
_FONT_CACHE = {}  # key: (font_path, size) -> Font

def _get_font(size: int):
    try:
        font_path = cfg.font_helper.main_font()
    except Exception:
        font_path = None  # fall back to default
    key = (font_path, int(size))
    f = _FONT_CACHE.get(key)
    if f is None:
        f = pygame.font.Font(font_path, int(size)) if font_path else pygame.font.SysFont(None, int(size))
        _FONT_CACHE[key] = f
    return f

# (1)(2) Dial face cache — pre-render panel+ring+fill as a single surface
# key: (radius, panel_color, fill_color, outline_color, outline_w, SS)
_FACE_CACHE = {}

def _build_dial_face(radius: int, panel_color, fill_color, outline_color, outline_w: int):
    """
    Pre-render dial face with optional supersampling.
    - If outline color == fill color (or width == 0) → draw one solid circle (no seam).
    - Otherwise draw ring + inner fill with a tiny overlap to avoid a 1px gap after downscale.
    """
    SS = max(1, int(getattr(cfg, "DIAL_SUPERSAMPLE", 2)))       # 1=off, 2=default
    AA_SHELLS = max(0, int(getattr(cfg, "DIAL_RING_AA_SHELLS", 0)))  # 0..2 optional extra AA

    # Base & work sizes
    panel_size = radius * 2 + 20
    work_size = panel_size * SS
    work = pygame.Surface((work_size, work_size), pygame.SRCALPHA).convert_alpha()

    # Panel background
    rect = pygame.Rect(0, 0, work_size, work_size)
    pygame.draw.rect(work, panel_color, rect, border_radius=15 * SS)

    # Circle geometry (scaled)
    cx = work_size // 2
    cy = work_size // 2
    r  = radius * SS
    ow = max(0, outline_w * SS)

    same_color = tuple(outline_color) == tuple(fill_color)
    overdraw = 1  # overlap in SS pixels to kill any subpixel seam on downscale

    if ow <= 0 or same_color:
        # No visible ring → single filled circle (no seam possible)
        pygame.gfxdraw.filled_circle(work, cx, cy, r, fill_color)
        pygame.gfxdraw.aacircle(work, cx, cy, r, fill_color)
    else:
        # Draw ring then inner fill with slight overlap
        pygame.gfxdraw.filled_circle(work, cx, cy, r, outline_color)
        inner_r = max(0, r - ow + overdraw)
        if inner_r > 0:
            pygame.gfxdraw.filled_circle(work, cx, cy, inner_r, fill_color)

        # AA edges
        pygame.gfxdraw.aacircle(work, cx, cy, r, outline_color)
        if inner_r > 0:
            pygame.gfxdraw.aacircle(work, cx, cy, inner_r, fill_color)

        # Optional extra softness on rim
        if AA_SHELLS >= 1:
            pygame.gfxdraw.aacircle(work, cx, cy, r - 1, outline_color)
        if AA_SHELLS >= 2:
            pygame.gfxdraw.aacircle(work, cx, cy, r + 1, outline_color)

    # Downsample for a crisp face
    if SS > 1:
        face = pygame.transform.smoothscale(work, (panel_size, panel_size)).convert_alpha()
    else:
        face = work

    return face


def _get_dial_face(radius: int, panel_color, fill_color, outline_color, outline_w: int):
    SS = max(1, int(getattr(cfg, "DIAL_SUPERSAMPLE", 2)))
    key = (int(radius), tuple(panel_color), tuple(fill_color), tuple(outline_color), int(outline_w), SS)
    surf = _FACE_CACHE.get(key)
    if surf is None:
        surf = _build_dial_face(int(radius), panel_color, fill_color, outline_color, int(outline_w))
        _FACE_CACHE[key] = surf
    return surf


# (3)(5) Per-dial text cache — only rebuild when content/colors change
# We store these on the dial objects to keep memory bounded.
def _get_label_surface_for_dial(d, main_font, text_color, unit_text):
    """
    Returns a pygame.Surface for 'Label: value [+ unit]' reusing d.cached_surface
    if nothing relevant changed.
    """
    label_prefix = f"{d.label}: "

    # Compose the displayed main string (with case)
    shown_val = d._shown_val_text  # computed earlier per dial
    label_str = helper.apply_text_case(f"{label_prefix}{shown_val}", cfg.DIAL_FONT_UPPER)

    # Build a cache key that captures text + relevant colors/settings
    key = (
        label_str,
        tuple(text_color),
        unit_text or "",
        int(cfg.DIAL_FONT_SIZE),
        int(cfg.DIAL_FONT_SPACING),
        int(cfg.TYPE_FONT_OFFSET_Y),
        float(cfg.TYPE_FONT_SCALE),
        getattr(cfg, "TYPE_FONT_COLOR", "#FFFFFF"),
    )

    if getattr(d, "_label_key", None) == key and getattr(d, "cached_surface", None) is not None:
        return d.cached_surface

    # Re-render
    main_surf, _ = helper.render_text_with_spacing(label_str, main_font, text_color, spacing=cfg.DIAL_FONT_SPACING)

    if unit_text:
        small_font = _get_font(int(cfg.DIAL_FONT_SIZE * cfg.TYPE_FONT_SCALE))
        unit_color = helper.hex_to_rgb(cfg.TYPE_FONT_COLOR)
        unit_surf = small_font.render(unit_text, True, unit_color)
        combined = pygame.Surface(
            (main_surf.get_width() + unit_surf.get_width() + cfg.TYPE_FONT_SPACING, main_surf.get_height()),
            pygame.SRCALPHA
        ).convert_alpha()
        combined.blit(main_surf, (0, 0))
        combined.blit(unit_surf, (main_surf.get_width() + cfg.TYPE_FONT_SPACING, cfg.TYPE_FONT_OFFSET_Y))
        d.cached_surface = combined
    else:
        d.cached_surface = main_surf.convert_alpha()

    d._label_key = key
    d.cached_rect = d.cached_surface.get_rect()
    return d.cached_surface

# =============================================================================
#                              M A I N  D R A W
# =============================================================================

def draw_ui(screen, dials, radius, exit_rect, header_text, pressed_button=None, offset_y=0):
    """Draw the main dial page UI (8 dials + 10 buttons + header/footer)."""
    screen.fill((0, 0, 0))
    # Fast font fetch (cached)
    font = _get_font(cfg.DIAL_FONT_SIZE)

    # match Presets pattern: content slides by header dropdown offset
    def sy(y):
        return y + offset_y

    # check current page mute state (device-specific)
    import dialhandlers
    is_page_muted = False
    try:
        current_pid = getattr(dialhandlers, "current_page_id", "01")
        device_name = getattr(dialhandlers, "current_device_name", None)
        device_mute_states = dialhandlers.get_page_mute_states(device_name)
        is_page_muted = device_mute_states.get(current_pid, False)
        showlog.debug(
            f"[DIALS RENDER] device={device_name}, page={current_pid}, is_page_muted={is_page_muted}, device_mute_states={device_mute_states}"
        )
    except Exception as exc:
        showlog.debug(f"[DIALS RENDER] Exception checking mute state: {exc}")
        pass

    # ---------- draw dials ----------
    device_name = getattr(dialhandlers, "current_device_name", None)

    for d in dials:
        is_empty = d.label.upper() == "EMPTY"

        # --- choose color palette (theme-aware, unified keys) ---
        if is_empty:
            panel_color   = helper.theme_rgb(device_name, "DIAL_OFFLINE_PANEL",  "#101010")
            fill_color    = helper.theme_rgb(device_name, "DIAL_OFFLINE_FILL",   "#303030")
            outline_color = helper.theme_rgb(device_name, "DIAL_OFFLINE_OUTLINE","#505050")
            text_color    = helper.theme_rgb(device_name, "DIAL_OFFLINE_TEXT",   "#707070")
        elif is_page_muted:
            panel_color   = helper.theme_rgb(device_name, "DIAL_MUTE_PANEL",     "#100010")
            fill_color    = helper.theme_rgb(device_name, "DIAL_MUTE_FILL",      "#4A004A")
            outline_color = helper.theme_rgb(device_name, "DIAL_MUTE_OUTLINE",   "#804080")
            text_color    = helper.theme_rgb(device_name, "DIAL_MUTE_TEXT",      "#B088B0")
        else:
            panel_color   = helper.theme_rgb(device_name, "DIAL_PANEL_COLOR",    "#301020")
            fill_color    = helper.theme_rgb(device_name, "DIAL_FILL_COLOR",     "#FF0090")
            outline_color = helper.theme_rgb(device_name, "DIAL_OUTLINE_COLOR",  "#FFB0D0")
            text_color    = helper.theme_rgb(device_name, "DIAL_TEXT_COLOR",     "#FFFFFF")

        # --- determine display value (also used for label caching key) ---
        r = getattr(d, "range", [0, 127])
        opts = getattr(d, "options", None)

        if opts:
            steps = len(opts)
            if steps > 0:
                step_size = 127 / (steps - 1)
                idx = int(round(d.value / step_size))
                idx = max(0, min(steps - 1, idx))
                shown_val = str(opts[idx])
            else:
                shown_val = str(int(d.value))
        else:
            if isinstance(r, (list, tuple)) and len(r) == 2:
                rmin, rmax = float(r[0]), float(r[1])
                step = (rmax - rmin) / 254.0
                scaled = rmin + step * (d.value * 2)
                if (rmax - rmin) <= 10:
                    shown_val = str(int(round(scaled)))
                elif abs(rmin) == 60 and rmax == 0:
                    shown_val = f"{round(scaled, 1)}"
                else:
                    shown_val = str(int(round(scaled)))
            else:
                shown_val = str(int(d.value))

        d._shown_val_text = shown_val  # used by label cache

        # --- optional unit/type suffix ---
        unit = getattr(d, "type", None)
        if not unit or str(unit).lower() in ("raw", "none"):
            unit = ""

        # ---------- label (cached) ----------
        label_surf = _get_label_surface_for_dial(d, font, text_color, unit)
        # Position label background & text
        ui_label.draw_label(screen, label_surf, (d.cx, sy(d.cy)), radius)

        # ---------- dial face (cached surface) ----------
        outline_w = max(1, int(round(cfg.DIAL_LINE_WIDTH)))
        face = _get_dial_face(int(d.radius), panel_color, fill_color, outline_color, outline_w)
        # center this pre-rendered panel onto (d.cx, sy(d.cy))
        panel_size = face.get_width()
        top_left = (int(d.cx - panel_size / 2), int(sy(d.cy) - panel_size / 2))
        screen.blit(face, top_left)

        # ---------- pointer (simple + fast) ----------
        if not is_empty:
            rad = math.radians(d.angle)
            x0 = d.cx + (d.radius * 0.5) * math.cos(rad)
            y0 = sy(d.cy) - (d.radius * 0.5) * math.sin(rad)
            x1 = d.cx + d.radius * math.cos(rad)
            y1 = sy(d.cy) - d.radius * math.sin(rad)
            # ⚡ simple wide line (fast)
            pygame.draw.line(screen, (255, 255, 255), (int(x0), int(y0)), (int(x1), int(y1)), 6)

    # ---------- draw side buttons ----------
    # Theme-aware button colors (unified naming)
    btn_fill          = helper.theme_rgb(device_name, "BUTTON_FILL",           "#3C3C3C")
    btn_outline       = helper.theme_rgb(device_name, "BUTTON_OUTLINE",        "#646464")
    btn_text          = helper.theme_rgb(device_name, "BUTTON_TEXT",           "#FFFFFF")
    btn_disabled_fill = helper.theme_rgb(device_name, "BUTTON_DISABLED_FILL",  "#1E1E1E")
    btn_disabled_text = helper.theme_rgb(device_name, "BUTTON_DISABLED_TEXT",  "#646464")
    btn_active_fill   = helper.theme_rgb(device_name, "BUTTON_ACTIVE_FILL",    "#960096")
    btn_active_text   = helper.theme_rgb(device_name, "BUTTON_ACTIVE_TEXT",    "#FFFFFF")

    font_label = pygame.font.SysFont("arial", 20)  # labels are tiny; sysfont is fine/cached internally
    btn_w, btn_h = 50, 50
    global button_rects
    button_rects.clear()
    button_rects_map = {}

    # Get BUTTONS from device file (ONLY source of button config)
    btn_specs = get_device_button_specs(device_name)          # {"1": {...}, ...} or {}

    # LEFT column (1–5)
    for i, btn_id in enumerate(["1", "2", "3", "4", "5"]):
        x = cfg.BUTTON_OFFSET_X
        y = sy(cfg.BUTTON_OFFSET_Y + i * (btn_h + cfg.BUTTON_SPACING_Y))
        rect = pygame.Rect(x, y, btn_w, btn_h)
        button_rects.append((rect, btn_id))
        button_rects_map[btn_id] = rect

        spec = btn_specs.get(btn_id)
        if spec:
            display_label = spec.get("label", btn_id)
            is_disabled = not spec.get("enabled", True)
        else:
            # Button not in BUTTONS list - show as disabled
            display_label = btn_id
            is_disabled = True  # Disable buttons not listed in BUTTONS

        ui_button.draw_button(
            screen, rect, display_label, font_label,
            pressed_button, selected_buttons,
            button_id=btn_id, disabled=is_disabled,
            fill_color=btn_fill, outline_color=btn_outline,
            text_color=btn_text,
            disabled_fill=btn_disabled_fill, disabled_text=btn_disabled_text,
            active_fill=btn_active_fill,   active_text=btn_active_text
        )

    # RIGHT column (buttons 6–10)
    for i, btn_id in enumerate(["6", "7", "8", "9", "10"]):
        x = screen.get_width() - cfg.BUTTON_OFFSET_X - btn_w
        y = sy(cfg.BUTTON_OFFSET_Y + i * (btn_h + cfg.BUTTON_SPACING_Y))
        rect = pygame.Rect(x, y, btn_w, btn_h)
        button_rects.append((rect, btn_id))
        button_rects_map[btn_id] = rect

        spec = btn_specs.get(btn_id)
        if spec:
            display_label = spec.get("label", btn_id)
            is_disabled = not spec.get("enabled", True)
        else:
            # Button not in BUTTONS list - show as disabled
            display_label = btn_id
            is_disabled = True  # Disable buttons not listed in BUTTONS

        ui_button.draw_button(
            screen, rect, display_label, font_label,
            pressed_button, selected_buttons,
            button_id=btn_id, disabled=is_disabled,
            fill_color=btn_fill, outline_color=btn_outline,
            text_color=btn_text,
            disabled_fill=btn_disabled_fill, disabled_text=btn_disabled_text,
            active_fill=btn_active_fill,   active_text=btn_active_text
        )

    # expose per-id rects for hit-testing
    globals()["button_rects_map"] = button_rects_map


# =============================================================================
#                 F A S T   S I N G L E - D I A L   R E D R A W
# =============================================================================

def _dial_panel_rect(d, offset_y=0):
    """Return the screen rect that contains the pre-rendered panel face for dial d."""
    panel_size = int(d.radius * 2 + 20)
    x = int(d.cx - panel_size / 2)
    y = int((d.cy + offset_y) - panel_size / 2)
    return pygame.Rect(x, y, panel_size, panel_size)


def redraw_single_dial(screen, d, offset_y=0, device_name=None, is_page_muted=False,
                       update_label=True, force_label=True):
    """
    Repaint just one dial: face + label + pointer. Returns a union rect we can pass to pygame.display.update().
    """
    # 1) colors (same logic as in draw_ui)
    is_empty = d.label.upper() == "EMPTY"
    if is_empty:
        panel_color   = helper.theme_rgb(device_name, "DIAL_OFFLINE_PANEL",  "#101010")
        fill_color    = helper.theme_rgb(device_name, "DIAL_OFFLINE_FILL",   "#303030")
        outline_color = helper.theme_rgb(device_name, "DIAL_OFFLINE_OUTLINE","#505050")
        text_color    = helper.theme_rgb(device_name, "DIAL_OFFLINE_TEXT",   "#707070")
    elif is_page_muted:
        panel_color   = helper.theme_rgb(device_name, "DIAL_MUTE_PANEL",     "#100010")
        fill_color    = helper.theme_rgb(device_name, "DIAL_MUTE_FILL",      "#4A004A")
        outline_color = helper.theme_rgb(device_name, "DIAL_MUTE_OUTLINE",   "#804080")
        text_color    = helper.theme_rgb(device_name, "DIAL_MUTE_TEXT",      "#B088B0")
    else:
        panel_color   = helper.theme_rgb(device_name, "DIAL_PANEL_COLOR",    "#301020")
        fill_color    = helper.theme_rgb(device_name, "DIAL_FILL_COLOR",     "#FF0090")
        outline_color = helper.theme_rgb(device_name, "DIAL_OUTLINE_COLOR",  "#FFB0D0")
        text_color    = helper.theme_rgb(device_name, "DIAL_TEXT_COLOR",     "#FFFFFF")

    # 2) figure the shown value (same as draw_ui, condensed)
    r = getattr(d, "range", [0, 127]); opts = getattr(d, "options", None)
    if opts:
        steps = max(1, len(opts))
        step_size = 127 / (steps - 1) if steps > 1 else 127
        idx = max(0, min(steps - 1, int(round(d.value / step_size))))
        shown_val = str(opts[idx])
    else:
        if isinstance(r, (list, tuple)) and len(r) == 2:
            rmin, rmax = float(r[0]), float(r[1])
            step = (rmax - rmin) / 254.0
            scaled = rmin + step * (d.value * 2)
            if (rmax - rmin) <= 10:
                shown_val = str(int(round(scaled)))
            elif abs(rmin) == 60 and rmax == 0:
                shown_val = f"{round(scaled, 1)}"
            else:
                shown_val = str(int(round(scaled)))
        else:
            shown_val = str(int(d.value))
    d._shown_val_text = shown_val

    unit = getattr(d, "type", None)
    if not unit or str(unit).lower() in ("raw", "none"):
        unit = ""

    # 3) re-blit the cached face to erase old pointer
    outline_w = max(1, int(round(cfg.DIAL_LINE_WIDTH)))
    face = _get_dial_face(int(d.radius), panel_color, fill_color, outline_color, outline_w)
    panel_rect = _dial_panel_rect(d, offset_y)
    screen.blit(face, panel_rect.topleft)

    # 4) label (uses your cached text path; optionally throttled)
    label_rect = None
    if update_label or force_label or getattr(d, "cached_surface", None) is None:
        # recompute shown value only when refreshing label
        r = getattr(d, "range", [0, 127]); opts = getattr(d, "options", None)
        if opts:
            steps = max(1, len(opts))
            step_size = 127 / (steps - 1) if steps > 1 else 127
            idx = max(0, min(steps - 1, int(round(d.value / step_size))))
            shown_val = str(opts[idx])
        else:
            if isinstance(r, (list, tuple)) and len(r) == 2:
                rmin, rmax = float(r[0]), float(r[1])
                step = (rmax - rmin) / 254.0
                scaled = rmin + step * (d.value * 2)
                if (rmax - rmin) <= 10:
                    shown_val = str(int(round(scaled)))
                elif abs(rmin) == 60 and rmax == 0:
                    shown_val = f"{round(scaled, 1)}"
                else:
                    shown_val = str(int(round(scaled)))
            else:
                shown_val = str(int(d.value))
        d._shown_val_text = shown_val

        unit = getattr(d, "type", None)
        if not unit or str(unit).lower() in ("raw", "none"):
            unit = ""

        font = _get_font(cfg.DIAL_FONT_SIZE)

    label_surf = _get_label_surface_for_dial(d, font, text_color, unit)
    # Hard-coded 10px Y offset for partial (dirty) redraw alignment
    label_rect = ui_label.draw_label(screen, label_surf, (d.cx, d.cy + offset_y + 10), d.radius)

    # 5) pointer (fast)
    if not is_empty:
        rad = math.radians(d.angle)
        x0 = d.cx + (d.radius * 0.5) * math.cos(rad)
        y0 = (d.cy + offset_y) - (d.radius * 0.5) * math.sin(rad)
        x1 = d.cx + d.radius * math.cos(rad)
        y1 = (d.cy + offset_y) - d.radius * math.sin(rad)
        pygame.draw.line(screen, (255, 255, 255), (int(x0), int(y0)), (int(x1), int(y1)), 6)

    # 6) return union rect for display.update()
    return panel_rect.union(label_rect) if label_rect else panel_rect
