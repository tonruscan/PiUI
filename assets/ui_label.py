# assets/ui_label.py
import pygame
import helper
import config as cfg

def draw_label(screen, text_surface, dial_center, radius):
    """
    Draw the colored rectangle behind a dial label and blit the rendered text.
    text_surface: pre-rendered text surface (already has color & spacing)
    """
    dial_panel_width = int(round(radius * 2 + 20))
    is_mini_dial = radius < getattr(cfg, "DIAL_SIZE", radius)
    label_height = cfg.LABEL_RECT_HEIGHT

    if is_mini_dial:
        label_height = getattr(cfg, "MINI_DIAL_LABEL_HEIGHT", label_height)

    if is_mini_dial:
        padding_y = getattr(cfg, "MINI_DIAL_LABEL_PADDING_Y", 10) or 10
        circle_top = float(dial_center[1]) + float(radius) + float(padding_y)

        text_rect = text_surface.get_rect()
        right_padding = max(0, int(round(getattr(cfg, "MINI_DIAL_LABEL_PADDING_X", 6))))
        extra_width = max(0, int(round(getattr(cfg, "MINI_DIAL_LABEL_EXTRA_WIDTH", 0))))

        base_width = int(round(radius * 2.0 + extra_width))
        text_right_requirement = int(round(2 * max(radius, text_rect.width + right_padding)))
        bg_width = max(base_width, text_right_requirement)

        bg_left = int(round(dial_center[0] - bg_width / 2.0))
        bg_top = int(round(circle_top))
        bg_rect = pygame.Rect(bg_left, bg_top, bg_width, label_height)

        text_left = int(round(dial_center[0] - radius))
        text_rect.midleft = (text_left, bg_rect.centery - 2)
    else:
        bg_rect = pygame.Rect(0, 0, cfg.LABEL_RECT_WIDTH, label_height)
        bg_rect.midtop = (int(round(dial_center[0])), int(round(dial_center[1] + radius + 10)))
        text_rect = text_surface.get_rect()
        padding_x = getattr(cfg, "DIAL_LABEL_PADDING_X", 5) if hasattr(cfg, "DIAL_LABEL_PADDING_X") else 5
        text_rect.midleft = (bg_rect.left + padding_x, bg_rect.centery - 2)

    # Prefer theme-provided value (supports standalone module THEME and device THEME).
    # helper.device_theme.get will fall back to config values if theme key is missing.
    default_color = getattr(cfg, "DIAL_LABEL_COLOR", getattr(cfg, "LABEL_COLOR", "#000000"))
    theme_key = "dial_label_color"
    if is_mini_dial:
        theme_key = "mini_dial_label_color"
        default_color = getattr(cfg, "MINI_DIAL_LABEL_COLOR", default_color)
    label_color = helper.device_theme.get("", theme_key, default_color)
    pygame.draw.rect(screen, helper.hex_to_rgb(label_color), bg_rect)

    screen.blit(text_surface, text_rect)
    return bg_rect.union(text_rect)
