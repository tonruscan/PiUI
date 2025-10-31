"""
Device select page event handler.

Handles device selection events.
"""

import pygame

from pages import device_select


class DeviceSelectEventHandler:
    """Handles events for the device select page."""
    
    def __init__(self, msg_queue):
        """
        Initialize device select event handler.
        
        Args:
            msg_queue: Application message queue
        """
        self.msg_queue = msg_queue
    
    def handle_event(self, event: pygame.event.Event):
        """
        Handle an event on the device select page.
        
        Args:
            event: Pygame event
        """
        if event.type == pygame.MOUSEBUTTONDOWN and hasattr(event, "pos"):
            device_select.handle_click(event.pos, self.msg_queue)
