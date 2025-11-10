# showheader.py — helper for drawing a header bar at the top of the screen
import pygame
import helper
import config as cfg
import os
from helper import hex_to_rgb
import showlog
import datetime


font = None
header_text = ""
screen_ref = None
letter_spacing = 0
arrow_img = None  # back-button image surface
arrow_rect = None
burger_img = None  # back-button image surface
burger_rect = None
screenshot_img = None  # screenshot button image surface
screenshot_rect = None
msg_queue = None  # assigned by ui.py at init

# -------------------------------------------------------
# Animated offset for dropdown / content shift
# -------------------------------------------------------
_header_offset_y = 0.0      # current animated offset (pixels)
_target_offset_y = 0.0      # target (0 or header height)
_ANIM_SPEED = getattr(cfg, "MENU_ANIM_SPEED", 0.25)


_menu_open = False
_pressed_button = None  # currently pressed dropdown button label
_pressed_time = 0   # timestamp for highlight flash


_current_theme = None
_current_device = None
_cached_header_bg = None
_cached_header_text = None

# -------------------------------------------------------
# Context menu button storage
# -------------------------------------------------------
_context_buttons = []  # Holds buttons shown in the dropdown menu


def _get_scale_values():
    try:
        scale_x = float(getattr(cfg, "UI_SCALE", 1.0))
    except Exception:
        scale_x = 1.0
    if scale_x <= 0:
        scale_x = 1.0

    try:
        scale_y = float(getattr(cfg, "UI_SCALE_Y", scale_x))
    except Exception:
        scale_y = scale_x
    if scale_y <= 0:
        scale_y = scale_x

    return scale_x, scale_y


def _scale_x(value):
    if value is None:
        return 0
    try:
        scaled = float(value) * _get_scale_values()[0]
    except Exception:
        return int(value) if isinstance(value, int) else 0
    return int(round(scaled))


def _scale_y(value):
    if value is None:
        return 0
    try:
        scaled = float(value) * _get_scale_values()[1]
    except Exception:
        return int(value) if isinstance(value, int) else 0
    return int(round(scaled))


def _scale_icon_size(value):
    _, scale_y = _get_scale_values()
    factor = scale_y
    try:
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            width = max(1, int(round(float(value[0]) * factor)))
            height = max(1, int(round(float(value[1]) * factor)))
            return width, height
        dim = max(1, int(round(float(value) * factor)))
        return dim, dim
    except Exception:
        dim = max(1, int(round(36 * factor)))
        return dim, dim


def clear_theme_cache():
    """Force reload of theme on next render (call when switching devices/modules)."""
    global _current_theme, _current_device, _cached_header_bg, _cached_header_text
    _current_theme = None
    _current_device = None
    _cached_header_bg = None
    _cached_header_text = None

def set_context_buttons(buttons):
    global _context_buttons
    _context_buttons = buttons or []


def _load_header_font(font_size: int):
    """Load header font from bundled assets, fallback to UI default."""
    filename = getattr(cfg, "HEADER_FONT_FILE", "Rasegard-Regular.ttf")
    search_dirs = [
        os.path.join(getattr(cfg, "BASE_DIR", os.path.dirname(__file__)), "assets", "fonts"),
        os.path.join(os.path.dirname(__file__), "assets", "fonts"),
    ]

    for directory in search_dirs:
        font_path = os.path.join(directory, filename)
        if os.path.isfile(font_path):
            try:
                return pygame.font.Font(font_path, font_size)
            except Exception as exc:
                try:
                    showlog.warn(f"[HEADER] Failed to load {filename}: {exc}")
                except Exception:
                    pass
            break

    fallback_weight = getattr(cfg, "HEADER_FONT_WEIGHT", "UltraBold")
    return cfg.font_helper.load_font(font_size, weight=fallback_weight)


# def hex_to_rgb(value):
#     value = value.lstrip("#")
#     return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))

def init(screen, font_name=None, font_size=40, spacing=None):
    """Initialize the header font, load arrow icon, and keep reference to screen."""
    global font, screen_ref, letter_spacing, arrow_img, burger_img, screenshot_img
    
    # Rasegard has no bold variant, so pygame synthesizes it which causes blur
    # Use regular weight to keep text sharp
    font_px = max(1, _scale_y(font_size))
    if isinstance(font_name, str) and font_name:
        if os.path.isfile(font_name):
            font = pygame.font.Font(font_name, font_px)
        else:
            font = cfg.font_helper.load_font(font_px, weight=font_name)
    else:
        font = _load_header_font(font_px)
    
    screen_ref = screen
    spacing_value = cfg.HEADER_LETTER_SPACING if spacing is None else spacing
    letter_spacing = _scale_x(spacing_value) if spacing_value else 0

    # --- Load and scale the arrow icon using config size ---
    try:
        arrow_path = os.path.join(os.path.dirname(__file__), "assets", "images", "arrow.png")
        img = pygame.image.load(arrow_path).convert_alpha()

        # Use BACK_BUTTON_SIZE from config (tuple or int)
        size = getattr(cfg, "BACK_BUTTON_SIZE", 36)
        arrow_img = pygame.transform.smoothscale(img, _scale_icon_size(size))

    except Exception as e:
        arrow_img = None
        showlog.log(None, f"[HEADER] Warning: Could not load arrow.png: {e}")


    # --- Load and scale the hamburger icon (mirror setup) ---
    try:
        burger_path = os.path.join(os.path.dirname(__file__), "assets", "images", "burger.png")
        burger_img_raw = pygame.image.load(burger_path).convert_alpha()

        burger_size = getattr(cfg, "BURGER_BUTTON_SIZE", 50)
        burger_img = pygame.transform.smoothscale(burger_img_raw, _scale_icon_size(burger_size))
    except Exception as e:
        burger_img = None
        showlog.log(None, f"[HEADER] Burger icon unavailable: {e}")

    # --- Load and scale the screenshot icon ---
    try:
        # Try screenshot.png first, then fallback to save.png
        screenshot_path = os.path.join(os.path.dirname(__file__), "assets", "images", "screenshot.png")
        if not os.path.exists(screenshot_path):
            screenshot_path = os.path.join(os.path.dirname(__file__), "assets", "images", "save.png")
        
        screenshot_img_raw = pygame.image.load(screenshot_path).convert_alpha()

        screenshot_size = getattr(cfg, "SCREENSHOT_BUTTON_SIZE", 50)
        screenshot_img = pygame.transform.smoothscale(screenshot_img_raw, _scale_icon_size(screenshot_size))
        showlog.verbose(f"[HEADER] Screenshot icon loaded from {os.path.basename(screenshot_path)}")
    except Exception as e:
        # Create a simple fallback icon if image doesn't exist
        try:
            size = getattr(cfg, "SCREENSHOT_BUTTON_SIZE", 50)
            w, h = _scale_icon_size(size)
            
            # Create a simple camera-like icon
            screenshot_img = pygame.Surface((w, h), pygame.SRCALPHA)
            # Draw a simple rectangle with a smaller rectangle inside (camera-like)
            pygame.draw.rect(screenshot_img, (255, 255, 255), (2, 4, w-4, h-8), 2)
            pygame.draw.rect(screenshot_img, (255, 255, 255), (6, 8, w-12, h-16), 2)
            pygame.draw.circle(screenshot_img, (255, 255, 255), (w//2, h//2), 3)
            showlog.debug(f"[HEADER] Screenshot icon created (fallback)")
        except Exception:
            screenshot_img = None
        showlog.log(None, f"[HEADER] Screenshot icon fallback used: {e}")


def init_queue(msg_q):
    """Called once from ui.py to share the message queue."""
    global msg_queue
    msg_queue = msg_q


def take_screenshot():
    """Take a screenshot and save it to screenshots folder with timestamp."""
    try:
        # Create screenshots directory if it doesn't exist
        screenshot_dir = os.path.join(os.path.dirname(__file__), "screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"
        filepath = os.path.join(screenshot_dir, filename)
        
        # Save the screenshot
        if screen_ref:
            pygame.image.save(screen_ref, filepath)
            showlog.debug(f"[HEADER] Screenshot saved: {filename}")
            return True
        else:
            showlog.error("[HEADER] No screen reference for screenshot")
            return False
    except Exception as e:
        showlog.error(f"[HEADER] Screenshot failed: {e}")
        return False





def set_menu_open(is_open: bool):
    """Tell the header whether the dropdown menu is open or closed."""
    global _target_offset_y
    try:
        menu_h = float(getattr(cfg, "MENU_HEIGHT", 200.00))
    except Exception:
        menu_h = 200.0
    _target_offset_y = float(max(0, _scale_y(menu_h))) if is_open else 0.0    # height of your dropdown in px


def update(dt: float = 0.0):
    """Call once per frame to animate toward the target offset."""
    global _header_offset_y
    _header_offset_y += (_target_offset_y - _header_offset_y) * _ANIM_SPEED


def get_offset() -> int:
    """Return current header offset (rounded int) for page drawing."""
    return int(round(_header_offset_y))










def handle_event(event):
    """Handle clicks on header elements like the burger or back arrow."""
    global _menu_open, _context_buttons
    
    # Disable header event handling if configured
    if getattr(cfg, "DISABLE_HEADER", False):
        return None

    if event.type == pygame.MOUSEBUTTONDOWN and hasattr(event, "pos"):
        try:
            pos = event.pos
            x, y = pos
        except:
            return None
            
        if not screen_ref:
            return None
        w, h = screen_ref.get_width(), screen_ref.get_height()
        if x >= w or y >= h or x < 0 or y < 0:
            return None

        # --- Burger icon tap (toggle dropdown) ---
        try:
            if burger_rect and burger_rect.collidepoint(pos):
                _menu_open = not _menu_open
                set_menu_open(_menu_open)
                if msg_queue:
                    msg_queue.put(("force_redraw", 50))
                return "toggle_menu"
        except:
            return None

        # --- Back arrow tap (go back) ---
        try:
            if arrow_rect and arrow_rect.collidepoint(pos):
                return "go_back"
        except:
            pass
        
        # --- Screenshot button tap ---
        try:
            if screenshot_rect and screenshot_rect.collidepoint(pos):
                take_screenshot()
                return "screenshot_taken"
        except:
            pass
        
        # --- Dropdown buttons (when menu is open) ---
        if _menu_open:
            for btn in _context_buttons:
                if "_rect" in btn and btn["_rect"].collidepoint(pos):
                    global _pressed_button, _pressed_time
                    _pressed_button = btn["label"]
                    _pressed_time = pygame.time.get_ticks()
                    _menu_open = False
                    set_menu_open(False)
                    
                    return btn["action"]




    return None



def show(screen, msg, device_name=None):
    """Draw the fixed header bar, optional burger/back icons, and animated dropdown with per-device theme."""
    
    # Disable header rendering if configured
    if getattr(cfg, "DISABLE_HEADER", False):
        return

    import devices
    global header_text, screen_ref, letter_spacing
    global arrow_img, burger_img, arrow_rect, burger_rect, screenshot_img, screenshot_rect, _context_buttons
    global _current_theme, _current_device, _cached_header_bg, _cached_header_text

    # --- Auto-clear pressed highlight after 120ms ---
    global _pressed_button, _pressed_time
    if _pressed_button and pygame.time.get_ticks() - _pressed_time > 120:
        _pressed_button = None

    if screen is None:
        screen = screen_ref
    if not screen or not font:
        return

    # --- Cache theme colors on device change (only resolve once per device) ---
    if device_name != _current_device or _cached_header_bg is None:
        showlog.debug(f"[HEADER] Theme cache miss - resolving colors for device_name='{device_name}'")
        
        # Cache the theme dict
        try:
            _current_theme = devices.get_theme(device_name) if device_name else {}
        except Exception:
            _current_theme = {}
        
        # Resolve and cache the actual RGB colors
        if device_name:
            _cached_header_bg = helper.theme_rgb(device_name, "HEADER_BG_COLOR", "#0B1C34")
            _cached_header_text = helper.theme_rgb(device_name, "HEADER_TEXT_COLOR", "#BCBCBC")
        else:
            # Use config defaults directly for non-device pages
            _cached_header_bg = helper.hex_to_rgb(getattr(cfg, "HEADER_BG_COLOR", "#0B1C34"))
            _cached_header_text = helper.hex_to_rgb(getattr(cfg, "HEADER_TEXT_COLOR", "#BCBCBC"))
        
        _current_device = device_name
        showlog.debug(f"[HEADER] Theme cached: bg={_cached_header_bg}, text={_cached_header_text}")

    # --- Use cached colors (no per-frame lookup) ---
    bg_rgb = _cached_header_bg
    text_rgb = _cached_header_text

    # --- Draw header background ---
    header_text = str(msg)
    header_height = getattr(cfg, "HEADER_HEIGHT", 60)
    header_rect = pygame.Rect(0, 0, screen.get_width(), header_height)
    pygame.draw.rect(screen, bg_rgb, header_rect)

    # --- Centered header text ---
    # Use direct render when spacing is zero to avoid any mixed spacing artifacts
    if int(letter_spacing) == 0:
        text_surf = font.render(header_text, True, text_rgb, bg_rgb)
        text_rect = text_surf.get_rect()
    else:
        text_surf, text_rect = helper.render_text_with_spacing(
            header_text, font, text_rgb, spacing=letter_spacing
        )

    baseline_offset = _scale_y(getattr(cfg, "HEADER_TEXT_BASELINE_OFFSET", -4))
    text_rect.center = (screen.get_width() // 2, header_rect.centery + baseline_offset)
    
    # DEBUG: Log before blitting
    if device_name:
        showlog.debug(f"[HEADER DEBUG {device_name}] About to blit text_surf size={text_surf.get_size()}, pos={text_rect.topleft}")
    
    screen.blit(text_surf, text_rect)

    # --- Back arrow (left) ---
    if arrow_img:
        arrow_rect = arrow_img.get_rect()
        arrow_rect.left = _scale_x(getattr(cfg, "BACK_BUTTON_LEFT_PAD", 12))
        arrow_rect.centery = header_rect.centery + _scale_y(getattr(cfg, "BACK_BUTTON_TOP_PAD", -2))
        screen.blit(arrow_img, arrow_rect)

    # --- Screenshot button (between back arrow and burger menu) ---
    global screenshot_rect
    if screenshot_img:
        screenshot_rect = screenshot_img.get_rect()
        # Position to the right of the back arrow with some spacing
        if arrow_rect:
            screenshot_rect.left = arrow_rect.right + _scale_x(getattr(cfg, "SCREENSHOT_BUTTON_GAP", 16))
        else:
            fallback_left = getattr(cfg, "BACK_BUTTON_LEFT_PAD", 12) + 50
            screenshot_rect.left = _scale_x(fallback_left)
        screenshot_rect.centery = header_rect.centery + _scale_y(getattr(cfg, "SCREENSHOT_BUTTON_TOP_PAD", -2))
        screen.blit(screenshot_img, screenshot_rect)

    # --- Burger menu (right) ---
    if burger_img:
        burger_rect = burger_img.get_rect()
        burger_rect.right = screen.get_width() - _scale_x(getattr(cfg, "BURGER_BUTTON_RIGHT_PAD", 12))
        burger_rect.centery = header_rect.centery + _scale_y(getattr(cfg, "BURGER_BUTTON_TOP_PAD", 0))
        screen.blit(burger_img, burger_rect)

    # --- Dropdown (unchanged) ---
    offset_y = int(round(_header_offset_y))
    if offset_y > 1:
        menu_rect = pygame.Rect(0, header_rect.bottom, screen.get_width(), offset_y)
        menu_rect.height = min(menu_rect.height, screen.get_height() - header_rect.bottom)
        pygame.draw.rect(screen, hex_to_rgb(getattr(cfg, "MENU_COLOR", "#1A1A1A")), menu_rect)

        if _context_buttons:
            btn_w = max(1, _scale_x(getattr(cfg, "MENU_BUTTON_WIDTH", 140)))
            btn_h = max(1, _scale_y(getattr(cfg, "MENU_BUTTON_HEIGHT", 44)))
            gap = max(0, _scale_x(getattr(cfg, "MENU_BUTTON_GAP", 12)))
            radius = max(0, _scale_y(getattr(cfg, "MENU_BUTTON_RADIUS", 10)))
            top_pad = _scale_y(getattr(cfg, "MENU_BUTTON_TOP_PAD", 8))

            btn_color = hex_to_rgb(getattr(cfg, "MENU_BUTTON_COLOR", "#43658E"))
            btn_pressed_color = hex_to_rgb(getattr(cfg, "MENU_BUTTON_PRESSED_COLOR", "#FFFFFF"))
            btn_border_color = hex_to_rgb(getattr(cfg, "MENU_BUTTON_BORDER_COLOR", "#000000"))
            btn_border_w = max(0, _scale_y(getattr(cfg, "MENU_BUTTON_BORDER_WIDTH", 0)))

            font_path = getattr(cfg, "MENU_BUTTON_FONT", getattr(cfg, "MENU_FONT", cfg.font_helper.main_font("UltraBold")))
            font_size = max(1, _scale_y(getattr(cfg, "MENU_BUTTON_FONT_SIZE", getattr(cfg, "MENU_FONT_SIZE", 20))))
            font_color = hex_to_rgb(getattr(cfg, "MENU_BUTTON_TEXT_COLOR", getattr(cfg, "MENU_FONT_COLOR", "#FFFFFF")))

            try:
                if isinstance(font_path, str) and os.path.isfile(font_path):
                    menu_font = pygame.font.Font(font_path, font_size)
                else:
                    weight = font_path if isinstance(font_path, str) else None
                    menu_font = cfg.font_helper.load_font(font_size, weight=weight)
            except Exception as e:
                showlog.log(None, f"[HEADER] MENU_FONT fallback ({type(e).__name__}: {e})")
                menu_font = cfg.font_helper.load_font(font_size)

            total_width = len(_context_buttons) * (btn_w + gap) - gap
            start_x = (screen.get_width() - total_width) // 2
            anchor = str(getattr(cfg, "MENU_BUTTON_ANCHOR", "center")).lower()
            if anchor == "top":
                y = header_rect.bottom + top_pad
            else:
                y = header_rect.bottom + max(0, (offset_y - btn_h) // 2)

            old_clip = screen.get_clip()
            screen.set_clip(menu_rect)

            for i, btn in enumerate(_context_buttons):
                bx = start_x + i * (btn_w + gap)
                btn_rect = pygame.Rect(bx, y, btn_w, btn_h)
                btn["_rect"] = btn_rect
                is_pressed = (_pressed_button == btn["label"])
                fill_col = btn_pressed_color if is_pressed else btn_color

                pygame.draw.rect(screen, fill_col, btn_rect, border_radius=radius)
                if btn_border_w > 0:
                    pygame.draw.rect(screen, btn_border_color, btn_rect, width=btn_border_w, border_radius=radius)

                text_surface = menu_font.render(btn["label"], True, font_color)
                text_rect = text_surface.get_rect(center=btn_rect.center)
                screen.blit(text_surface, text_rect)

            screen.set_clip(old_clip)

    # UI loop is responsible for flipping/updating the display; avoid double updates here



