"""
Global event handler.

Handles global events like back button, exit, and header interactions.
"""

import pygame
from typing import Optional

import showheader
import navigator
import showlog
import config as cfg


class GlobalEventHandler:
    """Handles global UI events."""
    
    def __init__(self, exit_rect: pygame.Rect, msg_queue):
        """
        Initialize global event handler.
        
        Args:
            exit_rect: Rectangle for exit button
            msg_queue: Application message queue
        """
        self.exit_rect = exit_rect
        self.msg_queue = msg_queue
        self.running = True
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        """
        Handle a global event.
        
        Args:
            event: Pygame event
        
        Returns:
            True if event was handled, False otherwise
        """
        if event.type == pygame.MOUSEBUTTONDOWN and hasattr(event, "pos"):
            return self.handle_click(event.pos)
        
        return False
    
    def handle_click(self, pos: tuple) -> bool:
        """
        Handle a global click event.
        
        Args:
            pos: Click position (x, y)
        
        Returns:
            True if click was handled
        """
        showlog.verbose(f"Global click at pos={pos}")
        
        # Check header back arrow
        r = getattr(showheader, "arrow_rect", None)
        if r and r.collidepoint(pos):
            if getattr(cfg, "DEBUG", False):
                showlog.debug(f"[DEBUG] Back pressed at pos={pos} within {r}")
            
            back_page = navigator.go_back()
            if back_page:
                self.msg_queue.put(("ui_mode", back_page))
                showlog.debug(f"[GLOBAL] Back → {back_page}")
            else:
                showlog.debug("[GLOBAL] Back → no history")
            return True

        return False
    
    def is_running(self) -> bool:
        """Check if application should continue running."""
        return self.running
    
    def stop(self):
        """Stop the application."""
        self.running = False
