"""
Debug Overlay for Performance Monitoring
Displays FPS and queue metrics during development.
"""

import pygame


def draw_overlay(screen, fps: float, queue_size: int, mode: str = "production"):
    """
    Draw performance overlay on screen.
    
    Args:
        screen: Pygame screen surface
        fps: Current frames per second
        queue_size: Current message queue size
        mode: Active profile mode (production/development/safe)
    """
    font = pygame.font.Font(None, 24)
    
    # FPS text
    fps_color = (0, 255, 0) if fps >= 55 else (255, 165, 0) if fps >= 30 else (255, 0, 0)
    fps_text = font.render(f"FPS: {int(fps)}", True, fps_color)
    
    # Queue size text
    queue_color = (0, 255, 0) if queue_size < 50 else (255, 165, 0) if queue_size < 100 else (255, 0, 0)
    queue_text = font.render(f"Q: {queue_size}", True, queue_color)
    
    # Mode text
    mode_color = (100, 100, 255) if mode == "development" else (255, 100, 100) if mode == "safe" else (150, 150, 150)
    mode_text = font.render(f"[{mode.upper()}]", True, mode_color)
    
    # Draw with semi-transparent background
    overlay_rect = pygame.Rect(5, 5, 200, 85)
    overlay_surface = pygame.Surface((overlay_rect.width, overlay_rect.height))
    overlay_surface.set_alpha(180)
    overlay_surface.fill((0, 0, 0))
    screen.blit(overlay_surface, overlay_rect)
    
    # Draw text
    screen.blit(fps_text, (10, 10))
    screen.blit(queue_text, (10, 35))
    screen.blit(mode_text, (10, 60))
