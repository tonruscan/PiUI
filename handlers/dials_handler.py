"""
Dials page event handler.

Handles mouse events for the dials page (dial dragging, button clicks).
"""

import pygame
import threading
import time
from typing import List, Set, Optional

import dialhandlers
import showlog
from pages import page_dials


class DialsEventHandler:
    """Handles events for the dials page."""
    
    def __init__(self, msg_queue):
        """
        Initialize dials event handler.
        
        Args:
            msg_queue: Application message queue
        """
        self.msg_queue = msg_queue
        self.last_midi_vals = [None] * 8
    
    def handle_event(self, 
                    event: pygame.event.Event,
                    dials: List,
                    button_rects: List,
                    selected_buttons: Set,
                    active_button_behavior: dict,
                    device_button_memory: dict,
                    select_button_callback):
        """
        Handle an event on the dials page.
        
        Args:
            event: Pygame event
            dials: List of Dial objects
            button_rects: List of button rectangles
            selected_buttons: Set of selected button IDs
            active_button_behavior: Button behavior map
            device_button_memory: Device button memory
            select_button_callback: Callback to select a button
        """
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.handle_mouse_down(
                event, dials, button_rects, selected_buttons,
                active_button_behavior, device_button_memory, select_button_callback
            )
        elif event.type == pygame.MOUSEBUTTONUP:
            self.handle_mouse_up(event, dials)
        elif event.type == pygame.MOUSEMOTION:
            self.handle_mouse_motion(event, dials)
    
    def handle_mouse_down(self, 
                         event,
                         dials: List,
                         button_rects: List,
                         selected_buttons: Set,
                         active_button_behavior: dict,
                         device_button_memory: dict,
                         select_button_callback):
        """Handle mouse button down event."""
        # Check dials
        for d in dials:
            if d.label.upper() == "EMPTY":
                continue
            if (event.pos[0] - d.cx) ** 2 + (event.pos[1] - d.cy) ** 2 <= d.radius ** 2:
                d.dragging = True
                self.msg_queue.put(f"Dial {d.id} touched")
        
        # Check buttons
        for rect, name in button_rects:
            if rect.collidepoint(event.pos):
                device_name = getattr(dialhandlers, "current_device_name", None)
                
                # Get button specs from device file
                btn_specs = page_dials.get_device_button_specs(device_name)
                
                # Check if button is defined and enabled
                spec = btn_specs.get(name)
                if spec and not spec.get("enabled", True):
                    continue
                
                # Interpret button behavior
                behavior = active_button_behavior.get(name, "state")
                
                if behavior == "state":
                    if device_name:
                        device_button_memory[device_name.upper()] = name
                    showlog.debug(f"[DIALS_HANDLER] Recorded state button {name}")
                
                elif behavior == "transient":
                    showlog.debug(f"[DIALS_HANDLER] Transient button {name} pressed")
                    
                    # Flash visual highlight
                    selected_buttons.add(name)
                    pygame.display.flip()
                    threading.Timer(0.2, lambda: selected_buttons.discard(name)).start()
                    
                    # Perform action
                    try:
                        dialhandlers.on_button_press(int(name))
                    except Exception as e:
                        showlog.debug(f"[DIALS_HANDLER] Transient action error: {e}")
                    
                    return  # No selection persistence
                
                elif behavior == "nav":
                    last_state = device_button_memory.get(device_name.upper(), "?") if device_name else "?"
                    showlog.debug(f"[DIALS_HANDLER] Nav button {name} → restore {last_state} later")
                
                showlog.debug(f"*[DIALS_HANDLER] Button {name} pressed ({behavior})")
                select_button_callback(name)
                
                try:
                    idx = int(name)
                    dialhandlers.on_button_press(idx)
                except ValueError as e:
                    showlog.debug(f"[DIALS_HANDLER] ValueError: {e}")
                except Exception as e:
                    showlog.error(f"[DIALS_HANDLER] Button press error: {e}")
    
    def handle_mouse_up(self, event, dials: List):
        """Handle mouse button up event."""
        for d in dials:
            if d.dragging:
                d.dragging = False
                d.on_mouse_up()
    
    def handle_mouse_motion(self, event, dials: List):
        """Handle mouse motion event."""
        for i, d in enumerate(dials):
            if d.dragging:
                d.update_from_mouse(*event.pos)
                new_val = d.value
                if new_val != self.last_midi_vals[i]:
                    dialhandlers.on_dial_change(d.id, new_val)
                    # Also send update_dial_value message to trigger burst mode and dirty rect
                    self.msg_queue.put(("update_dial_value", d.id, new_val))
                    self.last_midi_vals[i] = new_val
