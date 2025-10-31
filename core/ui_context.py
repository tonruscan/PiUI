"""
UI context dataclass.

Type-safe container for UI state passed between components.
"""

from dataclasses import dataclass
from typing import Optional, Callable
import pygame
import queue


@dataclass
class UIContext:
    """Context object containing UI state."""
    
    ui_mode: str
    screen: pygame.Surface
    msg_queue: queue.Queue
    dials: list
    select_button: Callable
    header_text: str
    
    # Optional fields for extended context
    prev_mode: Optional[str] = None
    selected_buttons: Optional[set] = None
    device_name: Optional[str] = None
    page_id: Optional[str] = None
