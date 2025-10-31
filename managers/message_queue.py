"""
Message queue processing.

Handles processing of queued UI messages and routing to control modules.
"""

import queue
import importlib
from typing import Dict, Callable, Optional

import showlog
import showheader
import pygame


class MessageQueueProcessor:
    """Processes messages from the application queue."""
    
    # Control module routing configuration
    CONTROL_ROUTING = {
        "device_selected": "global",
        "load_device": "global",
        "ui_mode": "global",
        "sysex_update": "page",
        "update_dial_value": "page",
        "select_button": "page",
        "remote_char": "page",
        "mixer_value": "page",
    }
    
    CONTROL_MODULES = {
        "global": "control.global_control",
        "dials": "control.dials_control",
        "presets": "control.presets_control",
        "patchbay": "control.patchbay_control",
        "text_input": "control.text_input_control",
        "mixer": "control.mixer_control",
        "vibrato": "control.vibrato_control",
    }
    
    def __init__(self, msg_queue: queue.Queue):
        """
        Initialize message queue processor.
        
        Args:
            msg_queue: The application message queue
        """
        self.msg_queue = msg_queue
        self._loaded_controls = {}
        
        # Callbacks will be set by the application
        self.on_header_text_change: Optional[Callable] = None
        self.on_button_select: Optional[Callable] = None
        self.on_dial_update: Optional[Callable] = None
        self.on_mode_change: Optional[Callable] = None
        self.on_device_selected: Optional[Callable] = None
        self.on_entity_select: Optional[Callable] = None
        self.on_force_redraw: Optional[Callable] = None
        self.on_remote_char: Optional[Callable] = None
        self.on_patch_select: Optional[Callable] = None
    
    def get_control(self, name: str):
        """
        Lazy-load a control module by short name.
        
        Args:
            name: Control module name (e.g., 'global', 'dials')
        
        Returns:
            The loaded control module or None
        """
        if name not in self._loaded_controls:
            try:
                self._loaded_controls[name] = importlib.import_module(
                    self.CONTROL_MODULES[name]
                )
                showlog.debug(f"[MSG_QUEUE] Loaded {self.CONTROL_MODULES[name]}")
            except Exception as e:
                showlog.debug(f"[MSG_QUEUE] Failed to load {name}: {e}")
                self._loaded_controls[name] = None
        return self._loaded_controls.get(name)
    
    def process_all(self, ui_context: Dict):
        """
        Process all queued messages.
        
        Args:
            ui_context: Dictionary with UI state (ui_mode, screen, etc.)
        """
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                self.process_message(msg, ui_context)
        except queue.Empty:
            pass
    
    def process_message(self, msg, ui_context: Dict):
        """
        Process a single message.
        
        Args:
            msg: The message to process
            ui_context: Dictionary with UI state
        """
        # Handle tuple messages (structured)
        if isinstance(msg, tuple):
            self._process_tuple_message(msg, ui_context)
        # Handle string messages
        else:
            self._process_string_message(msg, ui_context)
    
    def _process_tuple_message(self, msg: tuple, ui_context: Dict):
        """
        Process a tuple message.
        
        Args:
            msg: Tuple message (tag, *args)
            ui_context: UI context dictionary
        """
        tag = msg[0]
        
        # Route to specific handlers
        if tag == "sysex_update":
            self._handle_sysex_update(msg, ui_context)
        elif tag == "update_dial_value":
            self._handle_dial_value_update(msg, ui_context)
        elif tag == "select_button":
            self._handle_button_select(msg)
        elif tag == "remote_char":
            self._handle_remote_char(msg, ui_context)
        elif tag == "entity_select":
            self._handle_entity_select(msg)
        elif tag == "device_selected":
            self._handle_device_selected(msg)
        elif tag == "ui_mode":
            self._handle_ui_mode(msg, ui_context)
        elif tag == "force_redraw":
            self._handle_force_redraw(msg)
        elif tag == "invalidate":
            # Force full redraw
            pass
        elif tag == "invalidate_rect":
            # Redraw specific rect
            pass
        else:
            # Unknown tag
            if tag not in self.CONTROL_ROUTING:
                showlog.debug(f"[MSG_QUEUE] Unknown tuple: {msg}")
        
        # Forward to control modules
        self._route_to_controls(tag, msg, ui_context)
    
    def _handle_sysex_update(self, msg: tuple, ui_context: Dict):
        """Handle sysex_update message."""
        _, new_header_text, page_button = msg
        
        # Update header text
        if self.on_header_text_change:
            try:
                if new_header_text and str(new_header_text).strip():
                    self.on_header_text_change(new_header_text)
            except Exception:
                pass
        
        # Select button
        if page_button and self.on_button_select:
            self.on_button_select(page_button)
    
    def _handle_dial_value_update(self, msg: tuple, ui_context: Dict):
        """Handle update_dial_value message."""
        _, dial_id, value = msg
        
        if self.on_dial_update:
            self.on_dial_update(dial_id, value, ui_context)
    
    def _handle_button_select(self, msg: tuple):
        """Handle select_button message."""
        _, which = msg
        if self.on_button_select:
            self.on_button_select(which)
    
    def _handle_remote_char(self, msg: tuple, ui_context: Dict):
        """Handle remote_char message."""
        if self.on_remote_char:
            self.on_remote_char(msg, ui_context)
    
    def _handle_entity_select(self, msg: tuple):
        """Handle entity_select message."""
        if self.on_entity_select:
            self.on_entity_select(msg)
    
    def _handle_device_selected(self, msg: tuple):
        """Handle device_selected message."""
        if self.on_device_selected:
            self.on_device_selected(msg)
    
    def _handle_ui_mode(self, msg: tuple, ui_context: Dict):
        """Handle ui_mode message."""
        _, new_mode = msg
        
        # Ignore no-op transitions
        if new_mode != ui_context.get("ui_mode"):
            if self.on_mode_change:
                self.on_mode_change(new_mode)
        else:
            showlog.debug(f"[MSG_QUEUE] Ignored redundant ui_mode → {new_mode}")
    
    def _handle_force_redraw(self, msg: tuple):
        """Handle force_redraw message."""
        if self.on_force_redraw:
            self.on_force_redraw(msg)
    
    def _process_string_message(self, msg: str, ui_context: Dict):
        """
        Process a string message.
        
        Args:
            msg: String message
            ui_context: UI context dictionary
        """
        # Handle [PATCH_SELECT] messages
        if msg.startswith("[PATCH_SELECT]") or msg.startswith("[PATCH_SELECT_UI]"):
            if self.on_patch_select:
                self.on_patch_select(msg, ui_context)
        else:
            # Default: log normal text
            showlog.main(msg)
    
    def _route_to_controls(self, tag: str, msg: tuple, ui_context: Dict):
        """
        Route message to appropriate control modules.
        
        Args:
            tag: Message tag
            msg: Full message tuple
            ui_context: UI context dictionary
        """
        try:
            route = self.CONTROL_ROUTING.get(tag, "both")
            
            if route in ("global", "both"):
                global_ctrl = self.get_control("global")
                if global_ctrl and hasattr(global_ctrl, "handle_message"):
                    global_ctrl.handle_message(tag, msg, ui_context)
            
            ui_mode = ui_context.get("ui_mode")
            if route in ("page", "both") and ui_mode in self.CONTROL_MODULES:
                page_ctrl = self.get_control(ui_mode)
                if page_ctrl and hasattr(page_ctrl, "handle_message"):
                    page_ctrl.handle_message(tag, msg, ui_context)
                    
        except Exception as e:
            showlog.error(f"[MSG_QUEUE] Control routing error: {e}")
