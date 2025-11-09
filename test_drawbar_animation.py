#!/usr/bin/env python3
"""Quick test for drawbar animation feature."""

import pygame
import sys
import time

# Initialize pygame
pygame.init()
screen = pygame.display.set_mode((800, 600))
pygame.display.set_caption("Drawbar Animation Test")

# Mock modules for testing
class MockConfig:
    DIAL_SIZE = 50
    DIAL_PANEL_COLOR = "#2C1810"
    DIAL_FILL_COLOR = "#FF6B35"
    DIAL_OUTLINE_COLOR = "#FFB088"
    DIAL_TEXT_COLOR = "#FFEB9A"
    DIAL_FONT_SIZE = 14
    MIXER_MUTE_WIDTH = 28
    MIXER_CORNER_RADIUS = 6
    BUTTON_FILL = "#FF6B35"
    BUTTON_OUTLINE = "#FFB088"

class MockShowlog:
    @staticmethod
    def info(msg): print(f"[INFO] {msg}")
    @staticmethod
    def warn(msg): print(f"[WARN] {msg}")
    @staticmethod
    def error(msg): print(f"[ERROR] {msg}")
    @staticmethod
    def verbose(msg): pass

class MockHelper:
    @staticmethod
    def hex_to_rgb(hex_str):
        hex_str = hex_str.lstrip('#')
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
    
    class device_theme:
        @staticmethod
        def get(device, key, default):
            return default

class MockDialhandlers:
    current_device_name = "test_device"

# Replace imports
sys.modules['config'] = MockConfig
sys.modules['showlog'] = MockShowlog
sys.modules['helper'] = MockHelper
sys.modules['dialhandlers'] = MockDialhandlers

# Now import the widget
from widgets.drawbar_widget import DrawBarWidget

# Create widget
rect = pygame.Rect(50, 50, 700, 500)
widget = DrawBarWidget(rect)

# Main loop
clock = pygame.time.Clock()
running = True
animation_active = False

print("\n=== Drawbar Animation Test ===")
print("Press SPACE to toggle animation")
print("Press ESC to quit\n")

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            elif event.key == pygame.K_SPACE:
                widget.toggle_animation()
                animation_active = widget.animation_enabled
                print(f"Animation {'ENABLED' if animation_active else 'DISABLED'}")
        
        # Let widget handle mouse events
        widget.handle_event(event)
    
    # Clear screen
    
    # Draw widget
    widget.draw(screen)
    
    # Draw instructions
    font = pygame.font.Font(None, 24)
    status_text = f"Animation: {'ON' if animation_active else 'OFF'} - Press SPACE to toggle"
    text_surf = font.render(status_text, True, (255, 255, 255))
    screen.blit(text_surf, (50, 10))
    
    pygame.display.flip()
    clock.tick(60)

pygame.quit()
print("\nTest complete!")
