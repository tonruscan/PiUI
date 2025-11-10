import json
import os
import pygame
import config as cfg
import midiserver
from helper import hex_to_rgb, apply_text_case
import pygame.gfxdraw  # make sure this import is at the top of your file
import showlog

import logit

# Plugin metadata for rendering system
PLUGIN_METADATA = {
    "rendering": {
        "fps_mode": "low",               # Static page, 12 FPS is enough
        "supports_dirty_rect": False,    # Complex wiring diagram
        "requires_full_frame": True,     # Always redraw entire page
    }
}

# --- set globals 

# --- Editing state flags ---
key_pressed = False
tab_pressed = False
active_sockets = set()
input_text = ""





# -------------------------------------------------------
# Shared layout helper so draw_ui() and handle_event() match
# -------------------------------------------------------

def get_port_layout(screen_width):
    showlog.log(None, f"[PATCHBAY] Calculating port layout.")
    logit.log(f"[PATCHBAY] Calculating port layout.")

    """Return geometry constants for patchbay layout aligned to sockets."""
    socket_radius = 14
    col_spacing = getattr(cfg, "PORT_SPACING", 42)
    row_spacing = getattr(cfg, "PORT_ROW_SPACING", 34)
    cols = 12
    rows = 4
    total_width = cols * (2 * socket_radius + col_spacing) - col_spacing
    start_x = (screen_width - total_width) // 2 + socket_radius
    start_y = getattr(cfg, "PORTS_TOP_PADDING", 100)
    bank_gap = getattr(cfg, "PORT_BANK_GAP", 40)

    # height of each 2-row bank in pixels (matches socket math)
    bank_height = (4 * socket_radius) + row_spacing

    # a little padding around each rectangle
    pad = 20

    # Y positions for top & bottom rectangles
    top_bank_y = start_y - socket_radius - pad
    bottom_bank_y = start_y + (2 * (2 * socket_radius + row_spacing)) + bank_gap - socket_radius - pad

    return {
        "socket_radius": socket_radius,
        "col_spacing": col_spacing,
        "row_spacing": row_spacing,
        "cols": cols,
        "rows": rows,
        "start_x": start_x,
        "start_y": start_y,
        "bank_gap": bank_gap,
        "bank_height": bank_height,
        "top_bank_y": top_bank_y,
        "bottom_bank_y": bottom_bank_y,
        "pad": pad,
    }



# Filepath for saving patchbay labels
PATCHBAY_LABELS_FILE = os.path.join(cfg.CONFIG_DIR, "patchbay_labels.json")

# Default labels for the patchbay sockets
default_labels = {f"Socket {i+1}": "" for i in range(48)}

# Load existing labels or use defaults
def load_labels():

    if os.path.exists(PATCHBAY_LABELS_FILE):
        with open(PATCHBAY_LABELS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return default_labels

def save_labels(labels):
    with open(PATCHBAY_LABELS_FILE, "w", encoding="utf-8") as f:
        json.dump(labels, f, indent=4)


logit.log("[PATCHBAY] Loading labels.")

labels = load_labels()


# --- Custom connections (manual links) -------------------------
# File lives alongside labels.json

PATCHBAY_CONNECTIONS_FILE = os.path.join(cfg.CONFIG_DIR, "patchbay_connections.json")

def _socket_str(n: int) -> str:
    return f"Socket {n}"

def _socket_num(s: str) -> int:
    try:
        # accepts "Socket 12" (case/space tolerant)
        if isinstance(s, str) and s.strip().lower().startswith("socket"):
            return int(s.split()[-1])
    except Exception:
        pass
    return None

def load_connections() -> dict[int, int]:
    """Load JSON as {'Socket 5':'Socket 11', ...} → {5:11, ...}."""
    showlog.log(None, f"[PATCHBAY] Loading connections file")
    logit.log(f"[PATCHBAY] Loading connections file")
    data = {}
    try:
        if os.path.exists(PATCHBAY_CONNECTIONS_FILE):
            with open(PATCHBAY_CONNECTIONS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f) or {}
            for k, v in raw.items():
                src = _socket_num(k)
                dst = _socket_num(v)
                if src and dst and 1 <= src <= 48 and 1 <= dst <= 48:
                    data[src] = dst
    except Exception as e:
        showlog.error(None, f"[PATCHBAY] Failed to load connections: {e}")
    if not data:
        showlog.log(None, f"[PATCHBAY] No connections found.")
        logit.log(f"[PATCHBAY] No connections found.")
    return data


custom_links: dict[int, int] = load_connections()



def save_connections(mapping: dict[int, int]) -> None:
    """Save {5:11, ...} → {'Socket 5':'Socket 11', ...} (pretty, stable)."""
    try:
        # sort by source socket
        items = sorted(mapping.items(), key=lambda kv: kv[0])
        out = {_socket_str(src): _socket_str(dst) for src, dst in items}
        os.makedirs(cfg.CONFIG_DIR, exist_ok=True)
        with open(PATCHBAY_CONNECTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=4)
    except Exception as e:
        import showlog
        showlog.log(None, f"[PATCHBAY] Failed to save connections: {e}")





def draw_ui(screen, exit_rect, header_text, pressed_button=None, offset_y=0):
    """Draw the Patchbay page with dropdown offset support."""
    global active_sockets, input_text
    
    # --- Clear background (avoid log bar area) ---
    log_bar_h = getattr(cfg, "LOG_BAR_HEIGHT", 20)
    screen.fill((30, 30, 30), pygame.Rect(0, 0, screen.get_width(), screen.get_height() - log_bar_h))

    # --- Restrict drawing area to avoid covering log bar ---
    log_bar_h = getattr(cfg, "LOG_BAR_HEIGHT", 20)
    clip_rect = pygame.Rect(0, 0, screen.get_width(), screen.get_height() - log_bar_h)
    screen.set_clip(clip_rect)


    # --- match Presets/Dials pattern: slide content by header dropdown offset ---
    def sy(y):
        return y + offset_y

    # --- Fonts ---
    font_weight = getattr(cfg, "PATCHBAY_LABEL_FONT_WEIGHT", "SemiBold")
    font_label = cfg.font_helper.load_font(cfg.PORT_NUMBER_SIZE, weight=font_weight)
    font = cfg.font_helper.load_font(cfg.DIAL_FONT_SIZE)

    # --- Layout constants (driven by cfg) ---
    layout = get_port_layout(screen.get_width())
    socket_radius = layout["socket_radius"]
    col_spacing = layout["col_spacing"]
    row_spacing = layout["row_spacing"]
    cols = layout["cols"]
    rows = layout["rows"]
    start_x = layout["start_x"]
    start_y = sy(layout["start_y"])  # shift whole layout
    bank_gap = layout["bank_gap"]
    bank_height = layout["bank_height"]
    top_bank_y = sy(layout["top_bank_y"])
    bottom_bank_y = sy(layout["bottom_bank_y"])

    # --- Draw bank backgrounds ---
    bank_height = 2 * (2 * socket_radius + row_spacing) - row_spacing

    # --- Top bank rectangle ---
    top_rect = pygame.Rect(
        start_x - socket_radius - 20,
        top_bank_y,
        (cols * (2 * socket_radius + col_spacing)) - col_spacing + 40,
        bank_height + 40,
    )
    pygame.draw.rect(
        screen,
        hex_to_rgb(getattr(cfg, "PORT_BANK_TOP_COLOR", "#252525")),
        top_rect,
        border_radius=getattr(cfg, "PORT_BANK_BORDER_RADIUS", 10)
    )

    # --- Bottom bank rectangle ---
    bottom_rect = pygame.Rect(
        start_x - socket_radius - 20,
        bottom_bank_y,
        (cols * (2 * socket_radius + col_spacing)) - col_spacing + 40,
        bank_height + 40,
    )
    pygame.draw.rect(
        screen,
        hex_to_rgb(getattr(cfg, "PORT_BANK_BOTTOM_COLOR", "#252525")),
        bottom_rect,
        border_radius=getattr(cfg, "PORT_BANK_BORDER_RADIUS", 10)
    )

    # --- DP88 highlight rectangle ---
    dp88_start_col = 4
    dp88_cols = 8
    dp88_offset_x = getattr(cfg, "PORT_BANK_DP88_OFFSET_X", -33)
    dp88_x = start_x + dp88_start_col * (2 * socket_radius + col_spacing) + dp88_offset_x
    dp88_width = dp88_cols * (2 * socket_radius + col_spacing) - col_spacing
    dp88_y = bottom_bank_y
    dp88_height = bank_height + 40

    pygame.draw.rect(
        screen,
        hex_to_rgb(getattr(cfg, "PORT_BANK_DP88_COLOR", "#414141")),
        pygame.Rect(dp88_x, dp88_y, dp88_width + 40, dp88_height),
        border_radius=getattr(cfg, "PORT_BANK_BORDER_RADIUS", 10)
    )

    # --- Pass 1: Draw sockets ---
    centers = {}
    for i in range(48):
        row = i // cols
        col = i % cols  
        y_offset = bank_gap if row >= 2 else 0
        x = start_x + col * (2 * socket_radius + col_spacing)
        y = start_y + row * (2 * socket_radius + row_spacing) + y_offset
        socket_center = (x, y)
        centers[i + 1] = socket_center

        label = labels.get(f"Socket {i + 1}", "")
        fill_color = hex_to_rgb(cfg.PORT_COLOR_USED) if label else hex_to_rgb(cfg.PORT_COLOR_UNUSED)
        border_col = hex_to_rgb(getattr(cfg, "PORT_BORDER_COLOR", "#141414"))
        border_w = getattr(cfg, "PORT_BORDER_WIDTH", 2)
        cx, cy = int(x), int(y)
        r = int(socket_radius)

        try:
            pygame.gfxdraw.filled_circle(screen, cx, cy, r, fill_color)
            pygame.gfxdraw.aacircle(screen, cx, cy, r, border_col)
            # [MULTI-SELECT MOD] highlight all selected sockets
            if i in active_sockets:
                pygame.gfxdraw.aacircle(screen, cx, cy, r + 3, (255, 255, 0))
                pygame.gfxdraw.aacircle(screen, cx, cy, r + 4, (255, 255, 0))
        except Exception as e:
            import showlog
            showlog.log(None, f"[PATCHBAY] gfxdraw error on socket {i+1}: {e}")
            pygame.draw.circle(screen, fill_color, (cx, cy), r)
            pygame.draw.circle(screen, border_col, (cx, cy), r, border_w)

    # --- Pass 2: Draw connection lines ---
    try:
        RACK_OUT = set(range(1, 13)) | set(range(25, 29))
        RACK_IN  = set(range(13, 25)) | set(range(37, 41))
        DP88_OUT = set(range(29, 37))
        DP88_IN  = set(range(41, 49))
        
        def norm(label: str) -> str:
            return label.strip().upper() if isinstance(label, str) else ""

        by_label = {}
        for idx in range(1, 49):
            raw = labels.get(f"Socket {idx}", "")
            L = norm(raw)
            if not L:
                continue
            if idx in RACK_OUT:
                grp = "RACK_OUT"
            elif idx in RACK_IN:
                grp = "RACK_IN"
            elif idx in DP88_OUT:
                grp = "DP88_OUT"
            elif idx in DP88_IN:
                grp = "DP88_IN"
            else:
                continue
            by_label.setdefault(L, []).append({"idx": idx, "group": grp})

        def pair_in_order(src_indices, dst_indices):
            src_sorted = sorted(src_indices)
            dst_sorted = sorted(dst_indices)
            return list(zip(src_sorted, dst_sorted))

        edges = set()
        for L, recs in by_label.items():
            src_A = [r["idx"] for r in recs if r["group"] == "RACK_OUT"]
            dst_A = [r["idx"] for r in recs if r["group"] == "DP88_IN"]
            for s, d in pair_in_order(src_A, dst_A):
                edges.add((s, d))
            src_B = [r["idx"] for r in recs if r["group"] == "DP88_OUT"]
            dst_B = [r["idx"] for r in recs if r["group"] == "RACK_IN"]
            for s, d in pair_in_order(src_B, dst_B):
                edges.add((s, d))

        color_rack_to_dp88 = hex_to_rgb(getattr(cfg, "LINE_COLOR_RACK_TO_DP88", "#40FF40"))
        color_dp88_to_rack = hex_to_rgb(getattr(cfg, "LINE_COLOR_DP88_TO_RACK", "#D32222"))
        color_default      = hex_to_rgb(getattr(cfg, "LINE_COLOR_DEFAULT", "#FFFFFF"))
        line_width         = int(getattr(cfg, "PORT_LINK_WIDTH", 3))

        for (src, dst) in edges:
            p1, p2 = centers.get(src), centers.get(dst)
            if not (p1 and p2):
                continue
            if src in RACK_OUT and dst in DP88_IN:
                line_color = color_rack_to_dp88
            elif src in DP88_OUT and dst in RACK_IN:
                line_color = color_dp88_to_rack
            else:
                line_color = color_default
            pygame.draw.line(screen, line_color, p1, p2, line_width)

        # [CUSTOM CONNECTIONS MOD] Draw manual connections from patchbay_connections.json
        try:
            if custom_links:
                custom_color = hex_to_rgb(getattr(cfg, "CUSTOM_LINK_COLOR", "#00FFFF"))
                lw_custom = int(getattr(cfg, "CUSTOM_LINK_WIDTH", line_width))
                for src, dst in custom_links.items():
                    p1, p2 = centers.get(src), centers.get(dst)
                    if not (p1 and p2):
                        continue
                    pygame.draw.line(screen, custom_color, p1, p2, lw_custom)
        except Exception as e:
            import showlog
            showlog.log(screen, f"[PATCHBAY] Custom link draw error: {e}")


    except Exception as e:
        import showlog
        showlog.log(screen, f"[PATCHBAY] Link-draw error: {e}")

    # --- Label positions and text (IN/OUT labels) ---
    row_y_positions = []
    for row in range(4):
        y_offset = bank_gap if row >= 2 else 0
        y = start_y + row * (2 * socket_radius + row_spacing) + y_offset
        row_y_positions.append(y)

    try:
        label_size = int(getattr(cfg, "INOUT_LABEL_SIZE", 20))
        label_weight = getattr(cfg, "INOUT_LABEL_FONT_WEIGHT", "Bold")
        font_b = cfg.font_helper.load_font(label_size, weight=label_weight)
    except Exception:
        fallback_path = cfg.font_helper.main_font()
        font_b = pygame.font.Font(fallback_path, int(getattr(cfg, "INOUT_LABEL_SIZE", 20)))
    rotation_left = getattr(cfg, "INOUT_LABEL_ROTATION_LEFT", 90)
    rotation_right = getattr(cfg, "INOUT_LABEL_ROTATION_RIGHT", -90)
    offset_x = getattr(cfg, "INOUT_LABEL_OFFSET_X", 2.8)
    draw_both_banks = getattr(cfg, "INOUT_LABEL_BANKS", True)
    letter_spacing = getattr(cfg, "INOUT_LABEL_LETTER_SPACING", 0)
    draw_right_side = getattr(cfg, "INOUT_LABEL_MIRROR", True)
    color_in_left  = hex_to_rgb(getattr(cfg, "IN_TEXT_LEFT_COLOR",  "#00FFAA"))
    color_out_left = hex_to_rgb(getattr(cfg, "OUT_TEXT_LEFT_COLOR", "#FFAA00"))
    color_in_right  = hex_to_rgb(getattr(cfg, "IN_TEXT_RIGHT_COLOR",  "#00CCFF"))
    color_out_right = hex_to_rgb(getattr(cfg, "OUT_TEXT_RIGHT_COLOR", "#FF6699"))

    def render_text_with_spacing(text, font, color, spacing):
        surfaces = [font.render(ch, True, color) for ch in text]
        widths = [s.get_width() for s in surfaces]
        height = max(s.get_height() for s in surfaces)
        total_width = sum(widths) + spacing * (len(surfaces) - 1)
        surface = pygame.Surface((total_width, height), pygame.SRCALPHA)
        x = 0
        for s in surfaces:
            surface.blit(s, (x, 0))
            x += s.get_width() + spacing
        return surface

    bank_positions = [(row_y_positions[0], "OUT"), (row_y_positions[1], "IN")]
    if draw_both_banks:
        bank_positions += [(row_y_positions[2], "OUT"), (row_y_positions[3], "IN")]

    first_socket_x = start_x
    last_socket_x = start_x + (cols - 1) * (2 * socket_radius + col_spacing)
    label_x_left = first_socket_x - int(socket_radius * offset_x)
    label_x_right = last_socket_x + int(socket_radius * offset_x)

    for y, text in bank_positions:
        color = color_out_left if text == "OUT" else color_in_left
        text_surf = render_text_with_spacing(text, font_b, color, letter_spacing)
        rotated = pygame.transform.rotate(text_surf, rotation_left)
        rect = rotated.get_rect(center=(label_x_left, int(sy(y))))
        screen.blit(rotated, rect)

    if draw_right_side:
        for y, text in bank_positions:
            color = color_out_right if text == "OUT" else color_in_right
            text_surf = render_text_with_spacing(text, font_b, color, letter_spacing)
            rotated = pygame.transform.rotate(text_surf, rotation_right)
            rect = rotated.get_rect(center=(label_x_right, int(sy(y))))
            screen.blit(rotated, rect)

    # --- Pass 3: Numbers and labels (with multi-select) ---
    for i in range(48):
        row = i // cols
        col = i % cols
        y_offset = bank_gap if row >= 2 else 0
        x = start_x + col * (2 * socket_radius + col_spacing)
        y = start_y + row * (2 * socket_radius + row_spacing) + y_offset
        socket_center = (x, y)
        label = labels.get(f"Socket {i + 1}", "")
        num_color = hex_to_rgb(cfg.PORT_NUMBER_USED_COLOR) if label else hex_to_rgb(cfg.PORT_NUMBER_UNUSED_COLOR)
        port_number = col + 1 if row < 2 else col + 13
        num_surface = font_label.render(str(port_number), True, num_color)
        num_rect = num_surface.get_rect(center=socket_center)
        screen.blit(num_surface, num_rect)

        if i in active_sockets:
            # Always show the current input buffer, even if empty
            display_text = input_text
        else:
            display_text = labels.get(f"Socket {i + 1}", "")
       

        if display_text:
            offset = getattr(cfg, "PORT_LABEL_OFFSET", 18)
            color = (255, 255, 0) if i in active_sockets else hex_to_rgb(cfg.PORT_LABEL_COLOR)
            label_surface = font.render(display_text, True, color)
            label_rect = label_surface.get_rect(center=(x, y - socket_radius - offset))
            screen.blit(label_surface, label_rect)
        
        # --- Restore full drawing area ---
    screen.set_clip(None)


           


# -------------------------------------------------------
# Event handling (multi-select toggle + shared typing)
# -------------------------------------------------------

def handle_event(event, msg_queue):

    global active_sockets, input_text, key_pressed, tab_pressed

    layout = get_port_layout(800)
    socket_radius = layout["socket_radius"]
    col_spacing = layout["col_spacing"]
    row_spacing = layout["row_spacing"]
    cols = layout["cols"]
    start_x = layout["start_x"]
    start_y = layout["start_y"]
    bank_gap = layout["bank_gap"]

    if event.type == pygame.MOUSEBUTTONDOWN:
        for i in range(48):
            row = i // cols
            col = i % cols
            y_offset = bank_gap if row >= 2 else 0
            x = start_x + col * (2 * socket_radius + col_spacing)
            y = start_y + row * (2 * socket_radius + row_spacing) + y_offset

            if (event.pos[0] - x) ** 2 + (event.pos[1] - y) ** 2 <= socket_radius ** 2:
                # toggle selection
                if i in active_sockets:
                    active_sockets.remove(i)
                else:
                    active_sockets.add(i)

                # restore the original preload logic
                if active_sockets:
                    first = next(iter(active_sockets))
                    input_text = labels.get(f"Socket {first + 1}", "")
                else:
                    input_text = ""

                return



    elif event.type == pygame.KEYDOWN:
        key_pressed = True
        import logit
        logit.log(f"KEYDOWN: {event.key}")
        if active_sockets:
            # [CUSTOM CONNECTIONS MOD] -- Create connection when pressing Tab



            if event.key == pygame.K_RETURN:
                logit.log("[PATCHBAY] Enter pressed - saving labels.")
                for i in active_sockets:
                    labels[f"Socket {i + 1}"] = input_text
                save_labels(labels)
                active_sockets.clear()
                input_text = ""
            elif event.key == pygame.K_BACKSPACE:
                input_text = input_text[:-1]
            elif event.key == pygame.K_ESCAPE:
                active_sockets.clear()
                input_text = ""
            else:
                if len(input_text) < 20 and event.unicode.isprintable():
                    input_text += apply_text_case(event.unicode, uppercase=True)


def init_patchbay():
    showlog.log(None, "[PATCHBAY] init_patchbay.")
    """Send CC code when entering the patchbay screen."""
    midiserver.send_cc_raw(119, 127)




# ------------------ Remote Input Handling ------------------

def handle_remote_input(data):
    """Remote typing works for all selected sockets."""
    global active_sockets, input_text

    if not active_sockets:
        return

    # Backspace
    if data == "\b":
        input_text = input_text[:-1]

    # BACKTICK (`) → Create a custom connection (instead of TAB)
    elif data == "`":
        toggle_custom_connection()
        input_text = ""

    # Enter key
    elif data == "\n":
        for i in active_sockets:
            labels[f"Socket {i + 1}"] = apply_text_case(input_text, uppercase=True)
        save_labels(labels)
        active_sockets.clear()
        input_text = ""

    # Normal typing
    elif len(data) == 1 and data.isprintable():
        if len(input_text) < 20:
            input_text += data

# ------------------ Custom Connection Toggling ------------------

def toggle_custom_connection():
    """Toggle custom connections between selected sockets (create or remove)."""
    import showlog
    global custom_links, active_sockets

    RACK_OUT = set(range(1, 13)) | set(range(25, 29))
    RACK_IN  = set(range(13, 25)) | set(range(37, 41))
    DP88_OUT = set(range(29, 37))
    DP88_IN  = set(range(41, 49))

    outs = sorted([i + 1 for i in active_sockets if (i + 1) in (RACK_OUT | DP88_OUT)])
    ins  = sorted([i + 1 for i in active_sockets if (i + 1) in (RACK_IN  | DP88_IN)])

    if not outs or not ins:
        showlog.log(None, "[PATCHBAY] Need both OUT and IN sockets selected for a connection.")
        return

    pairs = list(zip(outs, ins))
    toggled = []

    for src, dst in pairs:
        if src in custom_links and custom_links[src] == dst:
            # Connection already exists → remove it
            del custom_links[src]
            toggled.append((src, dst, "removed"))
        else:
            # Add new connection
            custom_links[src] = dst
            toggled.append((src, dst, "added"))

    save_connections(custom_links)
    for src, dst, action in toggled:
        showlog.log(None, f"[PATCHBAY] {action.title()} custom link: {src} → {dst}")

    active_sockets.clear()
