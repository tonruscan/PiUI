"""
Minimal header renderer for diagnostic purposes.
NO fancy fonts, NO theming, NO complexity.
Just basic pygame text rendering.
"""

import os
import pygame
import config as cfg


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


def _scale_y(value):
    if value is None:
        return 0
    try:
        scaled = float(value) * _get_scale_values()[1]
    except Exception:
        return int(value) if isinstance(value, int) else 0
    return int(round(scaled))


def _load_header_font(font_size: int):
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
            except Exception:
                break

    fallback_weight = getattr(cfg, "HEADER_FONT_WEIGHT", "UltraBold")
    return cfg.font_helper.load_font(font_size, weight=fallback_weight)


def show(screen, msg, device_name):
    """
    Draw a minimal header with just the title text.
    White text on black background, now with Rasegard font.
    """
    header_height = getattr(cfg, "HEADER_HEIGHT", 60)
    screen.fill((0, 0, 0), rect=(0, 0, screen.get_width(), header_height))
    
    font = _load_header_font(max(1, _scale_y(40)))
    
    # Simple white text
    text_surf = font.render(msg, True, (255, 255, 255))
    
    # Center it
    baseline_offset = _scale_y(getattr(cfg, "HEADER_TEXT_BASELINE_OFFSET", -4))
    text_rect = text_surf.get_rect(center=(screen.get_width() // 2, header_height // 2 + baseline_offset))
    
    # Draw it
    screen.blit(text_surf, text_rect)
    
    return True
