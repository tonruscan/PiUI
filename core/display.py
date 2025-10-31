"""
Display and screen management.

Handles pygame display setup and configuration.
"""

import pygame
from typing import Tuple


class DisplayManager:
    """Manages the pygame display and screen."""
    
    def __init__(self, width: int = 800, height: int = 480, fullscreen: bool = True):
        """
        Initialize the display manager.
        
        Args:
            width: Screen width in pixels
            height: Screen height in pixels
            fullscreen: Whether to use fullscreen mode
        """
        self.width = width
        self.height = height
        self.fullscreen = fullscreen
        self.screen = None
        
    def initialize(self) -> pygame.Surface:
        """
        Initialize pygame and create the display surface.
        
        Returns:
            The pygame screen surface
        """
        pygame.init()
        
        flags = pygame.FULLSCREEN if self.fullscreen else 0
        self.screen = pygame.display.set_mode((self.width, self.height), flags)
        
        # Hide cursor
        pygame.mouse.set_visible(True)
        pygame.mouse.set_cursor((8, 8), (0, 0), (0,) * 8, (0,) * 8)
        
        return self.screen
    
    def get_screen(self) -> pygame.Surface:
        """Get the screen surface."""
        return self.screen
    
    def get_size(self) -> Tuple[int, int]:
        """Get the screen dimensions."""
        return (self.width, self.height)
    
    def cleanup(self):
        """Clean up pygame display."""
        pygame.quit()
