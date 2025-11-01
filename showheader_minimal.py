"""
Minimal header renderer for diagnostic purposes.
NO fancy fonts, NO theming, NO complexity.
Just basic pygame text rendering.
"""

import pygame

def show(screen, msg, device_name):
    """
    Draw a minimal header with just the title text.
    White text on black background, now with Rasegard font.
    """
    # Simple black background bar
    screen.fill((0, 0, 0), rect=(0, 0, 800, 60))
    
    # Add Rasegard font WITHOUT bold
    font = pygame.font.SysFont("Rasegard", 40, bold=False)
    
    # Simple white text
    text_surf = font.render(msg, True, (255, 255, 255))
    
    # Center it
    text_rect = text_surf.get_rect(center=(400, 30))
    
    # Draw it
    screen.blit(text_surf, text_rect)
    
    return True
