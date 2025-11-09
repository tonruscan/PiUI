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

# Plugin metadata for rendering system
PLUGIN_METADATA = {
    "rendering": {
        "fps_mode": "high",              # Needs 100 FPS for smooth dial interaction
        "supports_dirty_rect": True,     # Uses dirty rect optimization
        "burst_multiplier": 1.0,         # Standard burst behavior
    }
}

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


def _normalize_color(value, fallback):
    if value is None:
        return fallback
    try:
        if isinstance(value, (tuple, list)):
            if len(value) >= 3:
                return tuple(int(max(0, min(255, c))) for c in value[:3])
        elif isinstance(value, str):
            return helper.hex_to_rgb(value)
    except Exception:
        pass
    return fallback


# (3)(5) Per-dial text cache — only rebuild when content/colors change
# We store these on the dial objects to keep memory bounded.
def _get_label_surface_for_dial(d, main_font, text_color, unit_text):
    """
    Returns a pygame.Surface for 'Label: value [+ unit]' reusing d.cached_surface
    if nothing relevant changed.
    """
    show_value = getattr(d, "show_value_on_label", True)
    custom_label = getattr(d, "custom_label_text", None)
    uppercase_override = getattr(d, "custom_label_upper", None)
    uppercase_flag = cfg.DIAL_FONT_UPPER if uppercase_override is None else bool(uppercase_override)

    dial_radius = float(getattr(d, "radius", getattr(cfg, "DIAL_SIZE", 50)))
    base_radius = float(getattr(cfg, "DIAL_SIZE", 50))
    is_mini = dial_radius < base_radius or getattr(d, "display_mode", "").startswith("drumbo")
    base_font_size = int(cfg.DIAL_FONT_SIZE)
    font_size = base_font_size
    if is_mini:
        font_size = int(getattr(cfg, "MINI_DIAL_FONT_SIZE", base_font_size))

    if font_size <= 0:
        font_size = base_font_size

    if custom_label is not None:
        label_base = str(custom_label)
        label_str = helper.apply_text_case(label_base, uppercase_flag)
    elif not show_value:
        label_base = str(getattr(d, "label", ""))
        label_str = helper.apply_text_case(label_base, uppercase_flag)
    else:
        shown_val = getattr(d, "_shown_val_text", "")
        label_prefix = f"{getattr(d, 'label', '')}: "
        label_str = helper.apply_text_case(f"{label_prefix}{shown_val}", uppercase_flag)

    effective_unit = unit_text if show_value else ""

    # Build a cache key that captures text + relevant colors/settings
    key = (
        label_str,
        tuple(text_color),
        effective_unit or "",
        int(font_size),
        int(cfg.DIAL_FONT_SPACING),
        int(cfg.TYPE_FONT_OFFSET_Y),
        float(cfg.TYPE_FONT_SCALE),
        getattr(cfg, "TYPE_FONT_COLOR", "#FFFFFF"),
        bool(show_value),
    )

    if getattr(d, "_label_key", None) == key and getattr(d, "cached_surface", None) is not None:
        return d.cached_surface

    # Re-render
    if font_size == base_font_size:
        font_obj = main_font
    else:
        font_obj = _get_font(font_size)

    main_surf, _ = helper.render_text_with_spacing(label_str, font_obj, text_color, spacing=cfg.DIAL_FONT_SPACING)

    if effective_unit:
        unit_font_size = max(1, int(round(font_size * cfg.TYPE_FONT_SCALE)))
        small_font = _get_font(unit_font_size)
        unit_color = helper.hex_to_rgb(cfg.TYPE_FONT_COLOR)
        unit_surf = small_font.render(effective_unit, True, unit_color)
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
        visual_mode = getattr(d, "visual_mode", "default")
        if visual_mode == "hidden":
            continue
        is_empty = d.label.upper() == "EMPTY"

        # --- choose color palette (theme-aware, unified keys) ---
        dim_factor = 0.8
        bank_active = bool(getattr(d, "bank_active", True))

        def _maybe_dim(col):
            if bank_active:
                return col
            return tuple(max(0, min(255, int(round(c * dim_factor)))) for c in col)

        show_value = getattr(d, "show_value_on_label", True)

        if is_empty:
            panel_color   = helper.theme_rgb(device_name, "DIAL_OFFLINE_PANEL",  "#111111")
            fill_color    = helper.theme_rgb(device_name, "DIAL_OFFLINE_FILL",   "#000000")
            outline_color = helper.theme_rgb(device_name, "DIAL_OFFLINE_OUTLINE","#000000")
            text_color    = helper.theme_rgb(device_name, "DIAL_OFFLINE_TEXT",   "#000000")
        elif is_page_muted:
            panel_color   = helper.theme_rgb(device_name, "DIAL_MUTE_PANEL",     "#222222")
            fill_color    = helper.theme_rgb(device_name, "DIAL_MUTE_FILL",      "#000000")
            outline_color = helper.theme_rgb(device_name, "DIAL_MUTE_OUTLINE",   "#222222")
            text_color    = helper.theme_rgb(device_name, "DIAL_MUTE_TEXT",      "#555555")
        else:
            panel_color   = helper.theme_rgb(device_name, "DIAL_PANEL_COLOR",    "#0A2F65")
            fill_color    = helper.theme_rgb(device_name, "DIAL_FILL_COLOR",     "#000000")
            outline_color = helper.theme_rgb(device_name, "DIAL_OUTLINE_COLOR",  "#000000")
            text_color    = helper.theme_rgb(device_name, "DIAL_TEXT_COLOR",     "#FF8000")

        override_text = getattr(d, "label_text_color_override", None)
        text_color = _normalize_color(override_text, text_color)

        panel_color = _maybe_dim(panel_color)
        fill_color = _maybe_dim(fill_color)
        outline_color = _maybe_dim(outline_color)
        text_color = _maybe_dim(text_color)

        try:
            showlog.debug(
                f"*[DIALS] draw_ui dial={getattr(d, 'id', '?')} bank_active={bank_active} "
                f"radius={getattr(d, 'radius', 'NA')} panel={panel_color} text={text_color}"
            )
        except Exception:
            pass

        # --- determine display value (also used for label caching key) ---
        r = getattr(d, "range", [0, 127])
        opts = getattr(d, "options", None)

        if show_value:
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
        else:
            shown_val = ""

        d._shown_val_text = shown_val  # used by label cache

        # Remember radius used for label placement so dirty redraws match full draw
        d._render_radius = radius
        try:
            showlog.debug(f"*[DIALS] stored render_radius for dial {getattr(d, 'id', '?')} → {radius}")
        except Exception:
            pass

        # --- optional unit/type suffix ---
        unit = getattr(d, "type", None)
        if not show_value or not unit or str(unit).lower() in ("raw", "none"):
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
            pointer_color = _maybe_dim((255, 255, 255))
            pygame.draw.line(screen, pointer_color, (int(x0), int(y0)), (int(x1), int(y1)), 6)
            try:
                showlog.verbose2(
                    f"*[DIALS] pointer dial={getattr(d, 'id', '?')} color={pointer_color} xy0={(int(x0), int(y0))} xy1={(int(x1), int(y1))}"
                )
            except Exception:
                pass

    # ---------- draw side buttons ----------
    # Theme-aware button colors (unified naming)
    btn_fill          = helper.theme_rgb(device_name, "BUTTON_FILL",           "#071C3C")
    btn_outline       = helper.theme_rgb(device_name, "BUTTON_OUTLINE",        "#0D3A7A")
    btn_text          = helper.theme_rgb(device_name, "BUTTON_TEXT",           "#FFFFFF")
    btn_disabled_fill = helper.theme_rgb(device_name, "BUTTON_DISABLED_FILL",  "#1E1E1E")
    btn_disabled_text = helper.theme_rgb(device_name, "BUTTON_DISABLED_TEXT",  "#646464")
    btn_active_fill   = helper.theme_rgb(device_name, "BUTTON_ACTIVE_FILL",    "#0050A0")
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
    if getattr(d, "visual_mode", "default") == "hidden":
        return None
    # 1) colors (same logic as in draw_ui)
    dim_factor = 0.8
    bank_active = bool(getattr(d, "bank_active", True))

    def _maybe_dim(col):
        if bank_active:
            return col
        return tuple(max(0, min(255, int(round(c * dim_factor)))) for c in col)

    show_value = getattr(d, "show_value_on_label", True)
    is_empty = d.label.upper() == "EMPTY"
    if is_empty:
        panel_color   = helper.theme_rgb(device_name, "DIAL_OFFLINE_PANEL",  "#111111")
        fill_color    = helper.theme_rgb(device_name, "DIAL_OFFLINE_FILL",   "#000000")
        outline_color = helper.theme_rgb(device_name, "DIAL_OFFLINE_OUTLINE","#000000")
        text_color    = helper.theme_rgb(device_name, "DIAL_OFFLINE_TEXT",   "#000000")
    elif is_page_muted:
        panel_color   = helper.theme_rgb(device_name, "DIAL_MUTE_PANEL",     "#222222")
        fill_color    = helper.theme_rgb(device_name, "DIAL_MUTE_FILL",      "#000000")
        outline_color = helper.theme_rgb(device_name, "DIAL_MUTE_OUTLINE",   "#222222")
        text_color    = helper.theme_rgb(device_name, "DIAL_MUTE_TEXT",      "#555555")
    else:
        panel_color   = helper.theme_rgb(device_name, "DIAL_PANEL_COLOR",    "#0A2F65")
        fill_color    = helper.theme_rgb(device_name, "DIAL_FILL_COLOR",     "#000000")
        outline_color = helper.theme_rgb(device_name, "DIAL_OUTLINE_COLOR",  "#000000")
        text_color    = helper.theme_rgb(device_name, "DIAL_TEXT_COLOR",     "#FF8000")

    override_text = getattr(d, "label_text_color_override", None)
    text_color = _normalize_color(override_text, text_color)

    panel_color = _maybe_dim(panel_color)
    fill_color = _maybe_dim(fill_color)
    outline_color = _maybe_dim(outline_color)
    text_color = _maybe_dim(text_color)
    try:
        showlog.debug(
            f"*[DIALS] redraw_single dial={getattr(d, 'id', '?')} bank_active={bank_active} "
            f"radius={getattr(d, 'radius', 'NA')} panel={panel_color} text={text_color}"
        )
    except Exception:
        pass

    # 2) figure the shown value (same as draw_ui, condensed)
    r = getattr(d, "range", [0, 127]); opts = getattr(d, "options", None)
    if show_value:
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
    else:
        shown_val = ""
    d._shown_val_text = shown_val

    unit = getattr(d, "type", None)
    if not show_value or not unit or str(unit).lower() in ("raw", "none"):
        unit = ""

    # 3) re-blit the cached face to erase old pointer
    outline_w = max(1, int(round(cfg.DIAL_LINE_WIDTH)))
    face = _get_dial_face(int(d.radius), panel_color, fill_color, outline_color, outline_w)
    
    # For mini dials, skip the panel but still draw the dial circle
    is_mini_dial = d.radius < getattr(cfg, "DIAL_SIZE", 50)
    if is_mini_dial:
        # Mini dials render directly over the background, so blend the outline with the panel color
        outline_color = panel_color
        # Draw dial circle directly without panel background
        cx = int(round(d.cx))
        cy = int(round(d.cy + offset_y))
        r = int(round(d.radius))
        # Draw thicker outline ring first so pointer artifacts don't bleed through
        border_r = max(0, r + 2)
        pygame.gfxdraw.filled_circle(screen, cx, cy, border_r, outline_color)
        pygame.gfxdraw.aacircle(screen, cx, cy, border_r, outline_color)
        pygame.gfxdraw.aacircle(screen, cx, cy, border_r + 1, outline_color)
        # Inner fill for the actual dial face
        pygame.gfxdraw.filled_circle(screen, cx, cy, r, fill_color)
        pygame.gfxdraw.aacircle(screen, cx, cy, r, fill_color)
        pygame.gfxdraw.aacircle(screen, cx, cy, r + 1, fill_color)
        # Mini dial rect: just the circle bounds (diameter + small padding)
        dial_size = int(border_r * 2 + 4)
        panel_rect = pygame.Rect(cx - border_r - 2, cy - border_r - 2, dial_size, dial_size)
    else:
        # Normal dials - draw full face with panel background
        panel_rect = _dial_panel_rect(d, offset_y)
        screen.blit(face, panel_rect.topleft)

    try:
        if getattr(d, 'id', None) == 1:
            import showlog
            showlog.info(f"[DIALS] redraw_single_dial id={d.id}, mini={is_mini_dial}, panel_rect={panel_rect}")
    except Exception:
        pass

    # 4) label (uses your cached text path; optionally throttled)
    label_rect = None
    if update_label or force_label or getattr(d, "cached_surface", None) is None:
        # recompute shown value only when refreshing label
        r = getattr(d, "range", [0, 127]); opts = getattr(d, "options", None)
        if show_value:
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
        else:
            shown_val = ""
        d._shown_val_text = shown_val

        unit = getattr(d, "type", None)
        if not show_value or not unit or str(unit).lower() in ("raw", "none"):
            unit = ""

        font = _get_font(cfg.DIAL_FONT_SIZE)

    label_surf = _get_label_surface_for_dial(d, font, text_color, unit)
    # Match the full-draw label placement so dirty redraws stay aligned
    render_radius = getattr(d, "_render_radius", None)
    if render_radius is None:
        render_radius = getattr(d, "radius", cfg.DIAL_SIZE)
        d._render_radius = render_radius
        try:
            showlog.debug(
                f"*[DIALS] init render_radius dial={getattr(d, 'id', '?')} from radius={render_radius}"
            )
        except Exception:
            pass
    else:
        try:
            showlog.debug(
                f"*[DIALS] label redraw dial={getattr(d, 'id', '?')} render_radius={render_radius} cached_radius={getattr(d, '_render_radius', None)}"
            )
        except Exception:
            pass
    label_rect = ui_label.draw_label(screen, label_surf, (d.cx, d.cy + offset_y), render_radius)

    # 5) pointer (fast)
    if not is_empty:
        rad = math.radians(d.angle)
        x0 = d.cx + (d.radius * 0.5) * math.cos(rad)
        y0 = (d.cy + offset_y) - (d.radius * 0.5) * math.sin(rad)
        x1 = d.cx + d.radius * math.cos(rad)
        y1 = (d.cy + offset_y) - d.radius * math.sin(rad)
        pointer_color = _maybe_dim((255, 255, 255))
        pygame.draw.line(screen, pointer_color, (int(x0), int(y0)), (int(x1), int(y1)), 6)
        try:
            showlog.verbose2(
                f"*[DIALS] pointer redraw dial={getattr(d, 'id', '?')} color={pointer_color} xy0={(int(x0), int(y0))} xy1={(int(x1), int(y1))}"
            )
        except Exception:
            pass

    # 6) return union rect for display.update()
    return panel_rect.union(label_rect) if label_rect else panel_rect
