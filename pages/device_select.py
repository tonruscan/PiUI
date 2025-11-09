import pygame, json, sys, os
import showlog, config as cfg
import dialhandlers
import announce_helper

# --- ensure project root in path ---
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import device_states

# Plugin metadata for rendering system
PLUGIN_METADATA = {
    "rendering": {
        "fps_mode": "low",               # Static page, 12 FPS is enough
        "supports_dirty_rect": False,    # Grid of buttons doesn't benefit from dirty rect
        "requires_full_frame": True,     # Always redraw entire page
    }
}

# -------------------------------------------------------
# Cache
# -------------------------------------------------------

_device_buttons = []
_font = None
_current_page = 0   # starts at first page
# -------------------------------------------------------
# Pagination button scaling (single point of truth)
# -------------------------------------------------------
PAGE_BTN_SCALE = 0.5   # 1.0 = original size (60px), 0.5 = 30px, etc.


# -------------------------------------------------------
# Load device buttons
# -------------------------------------------------------

def load_buttons():
    """Load device button definitions from /config/device_page_layout.json."""
    global _device_buttons
    json_path = cfg.config_path("device_page_layout.json")
    img_dir = os.path.join(cfg.BASE_DIR, "assets", "images")

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        _device_buttons = []
        for btn in data["device_select"]["buttons"]:
            img_file = btn.get("img", "")
            img_path = os.path.join(img_dir, os.path.basename(img_file))
            image = None
            if os.path.exists(img_path):
                image = pygame.image.load(img_path).convert_alpha()
            else:
                showlog.warn(f"[DEV_SELECT] Missing image {img_path}")

            _device_buttons.append({
                "id": btn["id"],
                "label": btn["label"],
                "image": image,
                "plugin": btn.get("plugin", None),  # NEW: capture plugin page_id if present
            })

        showlog.info(f"Loaded {len(_device_buttons)} buttons")

    except Exception as e:
        showlog.error(f"JSON load error: {e}")
        _device_buttons = []


# -------------------------------------------------------
# Debug Mode Toggle
# -------------------------------------------------------
DEBUG_MODE = False  # Set to False to disable debug outlines

def draw_ui(screen, exit_rect, header_text, pressed_button, offset_y=0):
    """Draw the device selection page with dropdown offset support."""
    global _font
    if _font is None:
        _font = pygame.font.SysFont("Arial", 26, bold=True)

    # ✅ only clear the main area (leave bottom 20px intact for log/status)
    bg_color = cfg.COLOR_BG if hasattr(cfg, "COLOR_BG") else (0, 0, 0)
    screen.fill(bg_color, (0, 0, screen.get_width(), screen.get_height() - 20))


    # match Presets/Dials/Patchbay pattern: slide content by header dropdown offset
    def sy(y):
        return y + offset_y

    global _current_page

    total = len(_device_buttons)
    if total == 0:
        load_buttons()
        total = len(_device_buttons)

    # pagination
    page_size = 8
    total_pages = max(1, (total + page_size - 1) // page_size)
    _current_page = max(0, min(_current_page, total_pages - 1))

    start_index = _current_page * page_size
    end_index = start_index + page_size
    buttons_to_draw = _device_buttons[start_index:end_index]


    # --- Uniform two-row layout in JSON order ---
    w = screen.get_width()
    device_select_top = getattr(cfg, "DEVICE_BUTTON_TOP_PADDING", 60)
    row_gap = 180
    row_y = [device_select_top, device_select_top + row_gap]

    tile_w = 140
    tile_h = 160
    img_size = 120
    gap_x = 40

    # Split the current page's buttons into two rows
    visible = len(buttons_to_draw)
    row1_count = min(4, visible)
    row2_count = max(0, visible - row1_count)

    rows = [
        (0, row1_count),
        (row1_count, row2_count),
    ]

    # Compute a common left X based on the wider row so both rows align left
    base_cols = max(row1_count, row2_count, 1)
    
    total_base_w = base_cols * tile_w + (base_cols - 1) * gap_x
    grid_left_x = (w - total_base_w) // 2

    # Clear previous rects
    for btn in buttons_to_draw:
        btn.pop("_rect", None)


    idx_global = 0
    for r, (start_idx, count) in enumerate(rows):
        if count <= 0:
            continue
        # Use a fixed left edge so shorter rows align left under the top row
        start_x = grid_left_x
        y_top = sy(row_y[r])

        for i in range(count):
            btn = buttons_to_draw[start_idx + i]
            x_left = start_x + i * (tile_w + gap_x)
            # Image rect centered within tile area
            if btn["image"]:
                img = pygame.transform.smoothscale(btn["image"], (img_size, img_size))
                img_rect = img.get_rect()
                img_rect.center = (x_left + tile_w // 2, y_top + img_size // 2)
                screen.blit(img, img_rect)
            else:
                img_rect = pygame.Rect(x_left + (tile_w - img_size) // 2, y_top, img_size, img_size)
                pygame.draw.rect(screen, (60, 60, 60), img_rect, border_radius=12)
                label = _font.render(btn["label"], True, (200, 200, 200))
                screen.blit(label, label.get_rect(center=img_rect.center))
            
            # Store hit rect for clicks using the tile area (labels are hidden)
            tile_rect = pygame.Rect(x_left, y_top, tile_w, tile_h)
            hit_rect = tile_rect.inflate(10, 10)
            btn["_rect"] = hit_rect

            # Highlight if pressed
            if pressed_button == str(btn["id"]):
                pygame.draw.rect(screen, (255, 200, 0), hit_rect, 3, border_radius=10)

            if DEBUG_MODE:
                pygame.draw.rect(screen, (255, 255, 0), hit_rect, 1)


    # -------------------------------------------------------
    # Pagination buttons (image-based, precisely positioned)
    # -------------------------------------------------------
    if total > 8:

        # Cache loaded image
        if not hasattr(draw_ui, "_arrow_img"):
            img_path = os.path.join(cfg.BASE_DIR, "assets", "images", "downarrow.png")
            try:
                draw_ui._arrow_img = pygame.image.load(img_path).convert_alpha()
                showlog.debug(f"[DEVICE_SELECT] Loaded arrow image {img_path}")
            except Exception as e:
                showlog.error(f"[DEVICE_SELECT] Failed to load {img_path}: {e}")
                draw_ui._arrow_img = None

        arrow_img = draw_ui._arrow_img
        if arrow_img:
            # Mirror for UP
            arrow_up_img = pygame.transform.flip(arrow_img, False, True)

            screen_w, screen_h = screen.get_size()
            tile_w = 140
            tile_h = 123
            gap_x = 33

            # --- layout reference for last row ---
            device_select_top = getattr(cfg, "DEVICE_BUTTON_TOP_PADDING", 60)
            row_gap = 180
            last_row_y = device_select_top + row_gap
            bottom_y = last_row_y + tile_h  # bottom of last device tile

            # --- arrow sizing ---
            arrow_scale = 1  # adjust to taste
            arrow_w = int(arrow_img.get_width() * arrow_scale)
            arrow_h = int(arrow_img.get_height() * arrow_scale)
            arrow_img = pygame.transform.smoothscale(arrow_img, (arrow_w, arrow_h))
            arrow_up_img = pygame.transform.smoothscale(arrow_up_img, (arrow_w, arrow_h))

            # --- positioning ---
            # Horizontal center: midway between last button right edge and screen edge
            last_btn_right = (
                (w - (4 * tile_w + 3 * gap_x)) // 2 + 3 * (tile_w + gap_x) + tile_w
            )
            center_x = last_btn_right + (screen_w - last_btn_right) // 2

            # Down arrow: its BOTTOM flush with last tile's bottom edge
            down_rect = arrow_img.get_rect()
            down_rect.midbottom = (center_x, bottom_y)

            # Up arrow: sits above with 10 px edge-to-edge gap
            up_rect = arrow_up_img.get_rect()
            up_rect.midbottom = (center_x, down_rect.top - 10)

            # --- draw ---
            screen.blit(arrow_img, down_rect)
            screen.blit(arrow_up_img, up_rect)

            # --- click rects ---
            globals()["_page_down_rect"] = down_rect
            globals()["_page_up_rect"] = up_rect
        else:
            globals()["_page_down_rect"] = None
            globals()["_page_up_rect"] = None
    else:
        globals()["_page_down_rect"] = None
        globals()["_page_up_rect"] = None




    #showlog.log(screen, showlog.last())



# -------------------------------------------------------
# Handle clicks
# -------------------------------------------------------

def handle_click(pos, msg_queue):
    """Check if any device button was tapped and post action messages."""
    showlog.debug("handle_click triggered")
    global _current_page


    if globals().get("_page_up_rect") and globals()["_page_up_rect"].collidepoint(pos):
        if _current_page > 0:
            _current_page -= 1
            showlog.info(f"[DEVICE_SELECT] Page Up → now {_current_page+1}")
            msg_queue.put(("force_redraw", 2))  # ask for 2 frames of full redraw


        return True

    if globals().get("_page_down_rect") and globals()["_page_down_rect"].collidepoint(pos):
        total = len(_device_buttons)
        max_page = (total - 1) // 8
        if _current_page < max_page:
            _current_page += 1
            showlog.info(f"[DEVICE_SELECT] Page Down → now {_current_page+1}")
            msg_queue.put(("force_redraw", 2))  # ask for 2 frames of full redraw

        return True


    page_size = 8
    start_index = _current_page * page_size
    end_index = start_index + page_size
    visible_buttons = _device_buttons[start_index:end_index]

    for btn in visible_buttons:
        rect = btn.get("_rect")
        if rect and rect.collidepoint(pos):
            ...

            device_name = btn["label"].upper()
            showlog.info(f"{device_name} selected")

            # --- Check if this is a plugin page ---
            plugin_page_id = btn.get("plugin")
            if plugin_page_id:
                showlog.info(f"[DEV_SELECT] Plugin page detected: {plugin_page_id}")
                msg_queue.put(("ui_mode", plugin_page_id))
                return True

            # --- Handle Patchbay button ---
            if device_name.lower() == "patchbay":
                import midiserver
                midiserver.send_cc_raw(119, 127)
                msg_queue.put(("ui_mode", "patchbay"))
                showlog.debug("[UI] Patchbay button pressed, switching to patchbay page")
                return True

            # --- Reset any cached states ---
            if device_name in dialhandlers.live_states:
                del dialhandlers.live_states[device_name]
                showlog.info(f"[STATE] Cleared live memory states for {device_name}")

            # --- Register current device (INIT push handled centrally in ui.py queue handler) ---
            dialhandlers.current_device_name = device_name
            
            # --- Determine default page ---
            import devices
            dev_info = devices.get_by_name(device_name)
            default_page = dev_info.get("default_page", "presets") if dev_info else "presets"
            showlog.debug(f"[MAP] {device_name} → default page '{default_page}'")

            # --- Send announce message (silent) ---
            try:
                announce_helper.send_device_announce(device_name)
            except Exception as e:
                showlog.error(f"[DEV_SELECT] Announce helper error: {e}")

            # --- Load and switch ---

            msg_queue.put(("device_selected", device_name))
            # showlog.debug(f"[DEVICE_SELECT] Queued ENTITY_SELECT for {device_name}")

            return device_name

    return False

