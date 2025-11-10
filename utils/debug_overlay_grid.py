import pygame
import config as cfg

def draw_debug_grid(screen, grid_geom, grid_zones):
    """
    Visualize composite zones using the *tight* grid geometry.

    Args:
        screen: pygame surface to draw on
        grid_geom: dict containing grid geometry data (_GRID_GEOM from module_base)
        grid_zones: list of zone definitions (GRID_ZONES from module_base)

    Rules:
      • Every zone: colored rect of its (row, col, w, h) extent, mapped into the tight frame.
      • Zones with w>1 or h>1: thin white equal dividers inside the zone (ignore dial gaps).
      • Yellow spacers ONLY between adjacent 1×1 cells, centered at boundaries and
        with thickness = dial_gap_x / dial_gap_y (tight to dial edges).
    """
    geom = grid_geom
    if not geom:
        return

    # --- tight frame (the surface we draw on) ---
    GX, GY = geom["GRID_X"], geom["GRID_Y"]
    GW, GH = geom["GRID_W"], geom["GRID_H"]

    # canonical grid metrics (from full cells)
    cell_w, cell_h     = geom["cell_w"], geom["cell_h"]
    total_rows         = geom["total_rows"]
    total_cols         = geom["total_cols"]

    # dial/gap metrics (for spacer thickness)
    DIAL_DIAMETER      = geom.get("DIAL_DIAMETER", int(min(cell_w, cell_h) * 0.85))
    dial_gap_x         = geom.get("dial_gap_x", cell_w - DIAL_DIAMETER)
    dial_gap_y         = geom.get("dial_gap_y", cell_h - DIAL_DIAMETER)

    # helper: map (row,col,w,h) to a rect in *tight-surface local coords*
    # tight left/top = full left/top minus half the gap; so subtract half-gap then clamp.
    def _map_local(r, c, w, h):
        # dial-edge mapping in tight local space (0..GW / 0..GH)
        x1 = c * cell_w
        y1 = r * cell_h
        x2 = (c + w) * cell_w - dial_gap_x
        y2 = (r + h) * cell_h - dial_gap_y

        # clamp into tight surface
        x1 = max(0.0, x1); y1 = max(0.0, y1)
        x2 = min(GW,  x2); y2 = min(GH,  y2)

        return pygame.Rect(int(round(x1)), int(round(y1)),
                        int(round(x2 - x1)), int(round(y2 - y1)))


    # surface for the tight area
    surf = pygame.Surface((int(GW), int(GH)), pygame.SRCALPHA)

    # ------------------------------------------------------------------
    # Occupancy grid: which zone covers each base cell (for 1×1 adjacency)
    # ------------------------------------------------------------------
    occ = [[None for _ in range(total_cols)] for _ in range(total_rows)]
    for z in grid_zones:
        zr, zc, zw, zh = z["row"], z["col"], z["w"], z["h"]
        for rr in range(zr, zr + zh):
            for cc in range(zc, zc + zw):
                if 0 <= rr < total_rows and 0 <= cc < total_cols:
                    occ[rr][cc] = z

    # ------------------------------------------------------------------
    # Draw zones + internal equal dividers for multi-cell zones
    # ------------------------------------------------------------------
    try:
        label_font = cfg.font_helper.load_font(18, weight=getattr(cfg, "DEBUG_GRID_FONT_WEIGHT", "SemiBold"))
    except Exception:
        fallback_path = cfg.font_helper.main_font()
        label_font = pygame.font.Font(fallback_path, 18)

    for z in grid_zones:
        zr, zc, zw, zh = z["row"], z["col"], z["w"], z["h"]
        color = z.get("color", (255, 0, 0, 100))

        rect = _map_local(zr, zc, zw, zh)

        pygame.draw.rect(surf, color, rect, 0)  # width=0 for filled rectangle
        # outline_w = 2
        # inner = surf.get_rect().inflate(-outline_w, -outline_w)   # stroke fully inside
        # pygame.draw.rect(surf, (255, 255, 255, 230), inner, outline_w)


        # zone label
        label = label_font.render(z.get("id", "?"), True, (255, 255, 255))
        surf.blit(label, label.get_rect(center=rect.center))

        # internal equal dividers (pure fractional splits inside the zone)
        if zw > 1 or zh > 1:
            for k in range(1, zw):
                x = int(round(rect.x + rect.width * (k / float(zw))))
                pygame.draw.line(surf, (255, 255, 255, 150),
                                 (x, rect.y), (x, rect.y + rect.height), 1)
            for k in range(1, zh):
                y = int(round(rect.y + rect.height * (k / float(zh))))
                pygame.draw.line(surf, (255, 255, 255, 150),
                                 (rect.x, y), (rect.x + rect.width, y), 1)

    # ------------------------------------------------------------------
    # Yellow spacers ONLY between adjacent 1×1 cells (tight to dial edges)
    # ------------------------------------------------------------------
    # === Yellow spacers: per 1×1 cell, anchored to the DIAL (not the cell rect) ===
    # This avoids the half-gap overlap that made C/D look too narrow.
    for r in range(total_rows):
        for c in range(total_cols):
            Z = occ[r][c]
            if not (Z and Z.get("w") == 1 and Z.get("h") == 1):
                continue

            # Dial position in *tight* local coords
            dial_left   = c * cell_w
            dial_top    = r * cell_h
            dial_right  = dial_left + DIAL_DIAMETER
            dial_bottom = dial_top  + DIAL_DIAMETER

            # vertical spacer immediately to the RIGHT of the dial (unless at right edge)
            if c < total_cols - 1:
                sx = int(round(dial_right))
                sy = int(round(dial_top))
                sw = int(round(dial_gap_x))
                sh = int(round(DIAL_DIAMETER))   # height = dial height (tight to dial edges)
                spacer_v = pygame.Rect(sx, sy, sw, sh)
                pygame.draw.rect(surf, (255, 255, 0, 120), spacer_v)
                pygame.draw.rect(surf, (255, 255, 255, 120), spacer_v, 1)

            # horizontal spacer immediately BELOW the dial (unless at bottom edge)
            if r < total_rows - 1:
                sx = int(round(dial_left))
                sy = int(round(dial_bottom))
                sw = int(round(DIAL_DIAMETER))   # width = dial width (tight to dial edges)
                sh = int(round(dial_gap_y))
                spacer_h = pygame.Rect(sx, sy, sw, sh)
                pygame.draw.rect(surf, (255, 255, 0, 120), spacer_h)
                pygame.draw.rect(surf, (255, 255, 255, 120), spacer_h, 1)


    # outer outline of tight frame
    # pygame.draw.rect(surf, (255, 255, 255, 230), surf.get_rect(), 2)

    # blit tight overlay into screen at tight origin
    screen.blit(surf, (int(round(GX)), int(round(GY))))