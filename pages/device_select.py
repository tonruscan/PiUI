import pygame, json, sys, os
import showlog, config as cfg
import dialhandlers
import announce_helper

# --- ensure project root in path ---
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import device_states

# -------------------------------------------------------
# Cache
# -------------------------------------------------------

_device_buttons = []
_font = None


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

    screen.fill(cfg.COLOR_BG if hasattr(cfg, "COLOR_BG") else (0, 0, 0))

    # match Presets/Dials/Patchbay pattern: slide content by header dropdown offset
    def sy(y):
        return y + offset_y

    total = len(_device_buttons)
    if total == 0:
        load_buttons()
        total = len(_device_buttons)

    # --- Uniform two-row layout in JSON order ---
    w = screen.get_width()
    device_select_top = getattr(cfg, "DEVICE_BUTTON_TOP_PADDING", 60)
    row_gap = 180
    row_y = [device_select_top, device_select_top + row_gap]

    tile_w = 140
    tile_h = 160
    img_size = 120
    gap_x = 40

    # Split into two rows: first up to 4, remainder in second row
    row1_count = min(4, total)
    row2_count = max(0, total - row1_count)

    rows = [
        (0, row1_count),               # (start_index, count)
        (row1_count, row2_count),
    ]

    # Compute a common left X based on the wider row so both rows align left
    base_cols = max(row1_count, row2_count, 1)
    total_base_w = base_cols * tile_w + (base_cols - 1) * gap_x
    grid_left_x = (w - total_base_w) // 2

    # Clear previous rects
    for btn in _device_buttons:
        btn.pop("_rect", None)

    idx_global = 0
    for r, (start_idx, count) in enumerate(rows):
        if count <= 0:
            continue
        # Use a fixed left edge so shorter rows align left under the top row
        start_x = grid_left_x
        y_top = sy(row_y[r])

        for i in range(count):
            btn = _device_buttons[start_idx + i]
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

    #showlog.log(screen, showlog.last())



# -------------------------------------------------------
# Handle clicks
# -------------------------------------------------------

def handle_click(pos, msg_queue):
    """Check if any device button was tapped and post action messages."""
    showlog.debug("handle_click triggered")

    for btn in _device_buttons:
        rect = btn.get("_rect")
        if rect and rect.collidepoint(pos):
            device_name = btn["label"].upper()
            showlog.info(f"{device_name} selected")

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
            # showlog.debug(f"*[DEVICE_SELECT] Queued ENTITY_SELECT for {device_name}")

            return device_name

    return False

