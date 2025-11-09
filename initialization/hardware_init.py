"""
Hardware initialization.

Sets up MIDI, CV, network, and other hardware connections.
"""

import threading
import queue
from typing import Callable, Optional

import midiserver
import network
import cv_client
import remote_typing_server
import showlog


class HardwareInitializer:
    """Initializes and manages hardware connections."""
    
    def __init__(self, msg_queue: queue.Queue):
        """
        Initialize hardware manager.
        
        Args:
            msg_queue: The application message queue
        """
        self.msg_queue = msg_queue
        self.midi_initialized = False
        self.cv_initialized = False
        self.network_initialized = False
        self.remote_typing_initialized = False
    
    def initialize_all(self, 
                       midi_cc_callback: Optional[Callable] = None,
                       midi_sysex_callback: Optional[Callable] = None,
                       midi_note_callback: Optional[Callable] = None,
                       screen: Optional[object] = None):
        """
        Initialize all hardware subsystems.
        
        Args:
            midi_cc_callback: Callback for MIDI CC messages
            midi_sysex_callback: Callback for MIDI SysEx messages
            midi_note_callback: Callback for MIDI Note messages
            screen: Pygame screen surface for remote typing
        """
        self.initialize_midi(midi_cc_callback, midi_sysex_callback, midi_note_callback)
        self.initialize_cv()
        self.initialize_network()
        if screen:
            self.initialize_remote_typing(screen)
    
    def initialize_midi(self, 
                       cc_callback: Optional[Callable] = None,
                       sysex_callback: Optional[Callable] = None,
                       note_callback: Optional[Callable] = None):
        """
        Initialize MIDI server.
        
        Args:
            cc_callback: Callback for MIDI CC messages
            sysex_callback: Callback for MIDI SysEx messages
            note_callback: Callback for MIDI Note messages
        """
        try:
            midiserver.init(
                dial_cb=cc_callback,
                sysex_cb=sysex_callback,
                note_cb=note_callback
            )
            self.midi_initialized = True
            showlog.debug("[HARDWARE] MIDI server initialized")
        except Exception as e:
            showlog.error(f"[HARDWARE] Failed to initialize MIDI: {e}")
    
    def initialize_cv(self):
        """Initialize CV (Control Voltage) client."""
        try:
            cv_client.init()
            self.cv_initialized = True
            showlog.debug("[HARDWARE] CV client initialized")
        except Exception as e:
            showlog.error(f"[HARDWARE] Failed to initialize CV: {e}")
    
    def initialize_network(self):
        """Initialize network TCP server."""
        try:
            thread = threading.Thread(
                target=network.tcp_server,
                args=(self.msg_queue,),
                daemon=True
            )
            thread.start()
            self.network_initialized = True
            showlog.debug("[HARDWARE] Network server initialized")
        except Exception as e:
            showlog.error(f"[HARDWARE] Failed to initialize network: {e}")
    
    def initialize_remote_typing(self, screen):
        """
        Initialize remote typing server.
        
        Args:
            screen: Pygame screen surface
        """
        try:
            thread = threading.Thread(
                target=remote_typing_server.run_server,
                args=(self.msg_queue, screen),
                daemon=True
            )
            thread.start()
            self.remote_typing_initialized = True
            showlog.debug("[HARDWARE] Remote typing server initialized")
        except Exception as e:
            showlog.error(f"[HARDWARE] Failed to initialize remote typing: {e}")
    
    def get_status(self) -> dict:
        """
        Get initialization status of all hardware.
        
        Returns:
            Dictionary with status of each hardware component
        """
        return {
            "midi": self.midi_initialized,
            "cv": self.cv_initialized,
            "network": self.network_initialized,
            "remote_typing": self.remote_typing_initialized
        }
