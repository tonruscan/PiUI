"""
Hardware initialization mixin.

Handles MIDI, CV, network, and hardware-related initialization/cleanup.
"""

import showlog
import dialhandlers


class HardwareMixin:
    """Mixin for hardware initialization and cleanup."""
    
    def _init_hardware(self):
        """Initialize hardware connections."""
        from initialization import HardwareInitializer
        
        self.hardware_initializer = HardwareInitializer(self.msg_queue)
        self.hardware_initializer.initialize_all(
            midi_cc_callback=dialhandlers.on_midi_cc,
            midi_sysex_callback=dialhandlers.on_midi_sysex,
            screen=self.screen
        )
        
        status = self.hardware_initializer.get_status()
        showlog.debug(f"[HARDWARE_MIXIN] Hardware status: {status}")
        
        # Register hardware services
        if hasattr(self, 'services'):
            self.services.register('hardware_initializer', self.hardware_initializer)
    
    def _cleanup_hardware(self):
        """Cleanup hardware connections."""
        if hasattr(self, 'hardware_initializer'):
            showlog.debug("[HARDWARE_MIXIN] Cleaning up hardware...")
            # Add specific cleanup logic here when needed
            # e.g., MIDI port closing, network socket cleanup, etc.
