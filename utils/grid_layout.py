"""
Grid layout system for positioning dials and widgets in a uniform grid.

Provides functions to calculate dial positions and multi-cell zone rectangles
that can be used across different pages/modules.
"""

import pygame
import config as cfg
from typing import Optional, Dict, Any

# Cache for grid geometry to avoid recalculation
_GRID_GEOM: Optional[Dict[str, Any]] = None


def get_grid_cell_rect(row: int, col: int, total_rows: int = 2, total_cols: int = 4) -> pygame.Rect:
    """
    Compute the dial's bounding rect inside a centered grid region.
    The grid covers only the dial area (labels excluded) and supports
    a top padding offset for fine vertical adjustment.
    Also stores its layout geometry for debug overlays.
    
    Args:
        row: Grid row (0-based)
        col: Grid column (0-based)
        total_rows: Total number of rows in grid
        total_cols: Total number of columns in grid
        
    Returns:
        pygame.Rect representing the dial's bounding box
    """
    global _GRID_GEOM

    # --- base screen size ---
    screen_w = getattr(cfg, "SCREEN_WIDTH", 800)
    screen_h = getattr(cfg, "SCREEN_HEIGHT", 480)

    # --- adjustable layout parameters ---
    GRID_W = 586
    GRID_H_ORIG = 360
    GRID_TOP_PADDING = 10

    # --- grid cell geometry (original, for dial math) ---
    cell_w = GRID_W / total_cols
    cell_h = GRID_H_ORIG / total_rows

    # --- dial size (use the actual config size that dials use) ---
    DIAL_RADIUS = cfg.DIAL_SIZE  # This is 50 from config.py
    DIAL_DIAMETER = DIAL_RADIUS * 2  # This is 100
    DIAL_HALF = DIAL_DIAMETER / 2.0

    # --- compute dial centre (positions unchanged from original) ---
    # Use original grid Y for dial placement
    orig_GRID_X = (screen_w - GRID_W) / 2
    orig_GRID_Y = (screen_h - GRID_H_ORIG) / 2 + GRID_TOP_PADDING
    cell_center_x = orig_GRID_X + (col + 0.5) * cell_w
    cell_center_y = orig_GRID_Y + (row + 0.5) * cell_h

    # --- rect representing full dial area (including background panel) ---
    # Match dial.py: panel_size = radius * 2 + 20 (10px padding around circle)
    PANEL_SIZE = DIAL_DIAMETER + 20
    rect = pygame.Rect(0, 0, PANEL_SIZE, PANEL_SIZE)
    rect.center = (int(cell_center_x), int(cell_center_y))

    top_dial_center_y    = orig_GRID_Y + 0.5 * cell_h
    bottom_dial_center_y = orig_GRID_Y + (total_rows - 0.5) * cell_h

    tight_GRID_Y  = int(round(top_dial_center_y - DIAL_HALF))
    tight_GRID_H  = int(round((bottom_dial_center_y + DIAL_HALF) - (top_dial_center_y - DIAL_HALF)))

    first_dial_center_x  = orig_GRID_X + 0.5 * cell_w
    last_dial_center_x   = orig_GRID_X + (total_cols - 0.5) * cell_w

    tight_GRID_X  = int(round(first_dial_center_x - DIAL_HALF))
    tight_GRID_W  = int(round((last_dial_center_x + DIAL_HALF) - (first_dial_center_x - DIAL_HALF)))

    # --- expose shared geometry for debug/other functions ---
    # PRIMARY frame = TIGHT dial-span area (no padding above/below/left/right).
    # Also expose FULL frame + dial/gap metrics for overlays & spacers.
    _GRID_GEOM = dict(
        # tight dial-span (use these for all overlay surfaces & zone rects)
        GRID_W=tight_GRID_W,
        GRID_H=tight_GRID_H,
        GRID_X=tight_GRID_X,
        GRID_Y=tight_GRID_Y,

        # canonical cell metrics (based on full grid)
        cell_w=cell_w,
        cell_h=cell_h,
        total_rows=total_rows,
        total_cols=total_cols,

        # full cell frame (reference only)
        FULL_W=GRID_W,
        FULL_H=GRID_H_ORIG,
        FULL_X=orig_GRID_X,
        FULL_Y=orig_GRID_Y,

        # dial & gaps (used for spacer thickness and tight mapping)
        DIAL_DIAMETER=DIAL_DIAMETER,
        dial_gap_x=(cell_w - DIAL_DIAMETER),
        dial_gap_y=(cell_h - DIAL_DIAMETER),
    )

    return rect


def get_zone_rect_tight(row: int, col: int, w: int, h: int, geom: Optional[Dict[str, Any]] = None) -> pygame.Rect:
    """
    Map (row, col, w, h) in base grid cells into a pygame.Rect that matches
    the visual boundaries of individual dials.
    
    Uses the same calculation method as get_grid_cell_rect for perfect alignment.
    
    Args:
        row: Starting grid row (0-based)
        col: Starting grid column (0-based)
        w: Width in grid cells
        h: Height in grid cells
        geom: Optional pre-computed grid geometry dict. If None, uses cached geometry.
        
    Returns:
        pygame.Rect spanning the specified grid cells
    """
    g = geom or _GRID_GEOM or {}
    if not g:
        return pygame.Rect(0, 0, 0, 0)

    # Use the same parameters as get_grid_cell_rect
    screen_w = getattr(cfg, "SCREEN_WIDTH", 800)
    screen_h = getattr(cfg, "SCREEN_HEIGHT", 480)
    
    GRID_W = 586
    GRID_H_ORIG = 360
    GRID_TOP_PADDING = 10
    
    cell_w = GRID_W / 4  # total_cols = 4
    cell_h = GRID_H_ORIG / 2  # total_rows = 2
    
    DIAL_DIAMETER = g["DIAL_DIAMETER"]
    
    # Account for dial panel padding (dial.py: panel_size = radius * 2 + 20)
    PANEL_SIZE = DIAL_DIAMETER + 20
    PANEL_HALF = PANEL_SIZE / 2.0
    
    # Use the exact same coordinate system as get_grid_cell_rect
    orig_GRID_X = (screen_w - GRID_W) / 2
    orig_GRID_Y = (screen_h - GRID_H_ORIG) / 2 + GRID_TOP_PADDING
    
    # Calculate the span from first dial panel edge to last dial panel edge
    start_center_x = orig_GRID_X + (col + 0.5) * cell_w
    start_center_y = orig_GRID_Y + (row + 0.5) * cell_h
    end_center_x = orig_GRID_X + (col + w - 0.5) * cell_w
    end_center_y = orig_GRID_Y + (row + h - 0.5) * cell_h
    
    # Calculate bounding box from panel edges
    x1 = start_center_x - PANEL_HALF
    y1 = start_center_y - PANEL_HALF
    x2 = end_center_x + PANEL_HALF
    y2 = end_center_y + PANEL_HALF
    
    return pygame.Rect(int(round(x1)), int(round(y1)), 
                       int(round(x2 - x1)), int(round(y2 - y1)))


def get_grid_geometry() -> Optional[Dict[str, Any]]:
    """
    Get the cached grid geometry dictionary.
    
    Returns:
        Dict containing grid layout parameters, or None if not yet calculated.
        Call get_grid_cell_rect() first to initialize the geometry.
    """
    return _GRID_GEOM


def clear_grid_cache():
    """Clear the cached grid geometry. Useful when screen dimensions change."""
    global _GRID_GEOM
    _GRID_GEOM = None
