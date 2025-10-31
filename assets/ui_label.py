# assets/ui_label.py
import pygame
import helper
import config as cfg

def draw_label(screen, text_surface, dial_center, radius):
    """
    Draw the colored rectangle behind a dial label and blit the rendered text.
    text_surface: pre-rendered text surface (already has color & spacing)
    """
    bg_rect = pygame.Rect(0, 0, cfg.LABEL_RECT_WIDTH, cfg.LABEL_RECT_HEIGHT)
    bg_rect.midtop = (dial_center[0], dial_center[1] + radius + 10)
    pygame.draw.rect(screen, helper.hex_to_rgb(cfg.LABEL_COLOR), bg_rect)

    text_rect = text_surface.get_rect()
    text_rect.midleft = (bg_rect.left + 5, bg_rect.centery - 2)
    screen.blit(text_surface, text_rect)
    return bg_rect.union(text_rect)
