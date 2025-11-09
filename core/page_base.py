"""
Base class for UI pages.

Optional base class that pages can inherit from for standardized interface.
"""

from typing import Optional
import pygame
import queue


class Page:
    """Base class for UI pages."""
    
    # Class attributes (override in subclasses)
    id: str = "unnamed"
    label: str = "Unnamed Page"
    
    def __init__(self):
        """Initialize page."""
        pass
    
    def handle_event(self, event: pygame.event.Event, msg_queue: queue.Queue, screen: Optional[pygame.Surface] = None) -> None:
        """
        Handle pygame events for this page.
        
        Args:
            event: Pygame event
            msg_queue: Message queue
            screen: Optional pygame screen surface
        """
        pass
    
    def draw(self, screen: pygame.Surface, offset_y: int = 0, **kwargs) -> None:
        """
        Draw this page.
        
        Args:
            screen: Pygame screen surface
            offset_y: Y offset for header animation
            **kwargs: Additional draw parameters
        """
        pass
    
    def draw_ui(self, screen: pygame.Surface, *args, **kwargs) -> None:
        """
        Alternative draw method (some pages use draw_ui).
        
        Args:
            screen: Pygame screen surface
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments
        """
        pass
    
    def update(self) -> None:
        """Update page state (called each frame)."""
        pass
    
    def init(self, *args, **kwargs) -> None:
        """
        Initialize/reinitialize page with context.
        
        Args:
            *args: Initialization arguments
            **kwargs: Initialization keyword arguments
        """
        pass
    
    def on_enter(self) -> None:
        """Called when page becomes active."""
        pass
    
    def on_exit(self) -> None:
        """Called when page becomes inactive."""
        pass
    
    def __repr__(self) -> str:
        """String representation."""
        return f"<Page id={self.id} label={self.label}>"
