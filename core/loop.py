"""
Main event loop coordinator.

Handles the pygame event loop, frame timing, and event delegation.
"""

import pygame
from typing import Callable, Optional


class EventLoop:
    """Main application event loop."""
    
    def __init__(self):
        """Initialize the event loop."""
        self.running = False
        self.clock = pygame.time.Clock()
        self.event_handlers = []
        
    def add_handler(self, handler: Callable):
        """
        Add an event handler to the loop.
        
        Args:
            handler: A callable that takes a pygame event
        """
        self.event_handlers.append(handler)
    
    def run(self, 
            update_callback: Callable,
            render_callback: Callable,
            target_fps: int = 60):
        """
        Run the main event loop.
        
        Args:
            update_callback: Called each frame for updates
            render_callback: Called each frame for rendering
            target_fps: Target frames per second
        """
        self.running = True
        
        while self.running:
            # Process pygame events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.stop()
                    continue
                    
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self.stop()
                    continue
                
                # Delegate to registered handlers
                for handler in self.event_handlers:
                    handler(event)
            
            # Update application state
            update_callback()
            
            # Render frame
            render_callback()
            
            # Control frame rate
            self.clock.tick(target_fps)
    
    def stop(self):
        """Stop the event loop."""
        self.running = False
    
    def get_fps(self) -> float:
        """Get current FPS."""
        return self.clock.get_fps()
