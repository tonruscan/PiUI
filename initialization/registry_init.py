"""
Registry initialization.

Handles CC registry and entity registry setup.
"""

import showlog


class RegistryInitializer:
    """Initializes registry systems."""
    
    def __init__(self):
        """Initialize registry manager."""
        self.cc_registry_initialized = False
        self.entity_registry_initialized = False
    
    def initialize_cc_registry(self):
        """Initialize the CC (Control Change) registry."""
        try:
            from system import cc_registry
            cc_registry.init()
            self.cc_registry_initialized = True
            showlog.debug("[REGISTRY] CC registry initialized")
        except Exception as e:
            showlog.error(f"[REGISTRY] Failed to initialize CC registry: {e}")
    
    def load_device_registry(self, device_name: str):
        """
        Load CC registry entries for a specific device.
        
        Args:
            device_name: Name of the device to load
        """
        try:
            from system import cc_registry
            cc_registry.load_from_device(device_name)
            showlog.debug(f"[REGISTRY] Loaded CC registry for '{device_name}'")
        except Exception as e:
            showlog.warn(f"[REGISTRY] Failed to load CC registry for {device_name}: {e}")
    
    def initialize_entity_registry(self):
        """Initialize the entity registry."""
        try:
            from system import entity_registry
            # Entity registry may auto-initialize on import
            self.entity_registry_initialized = True
            showlog.debug("[REGISTRY] Entity registry initialized")
        except Exception as e:
            showlog.error(f"[REGISTRY] Failed to initialize entity registry: {e}")
    
    def get_status(self) -> dict:
        """
        Get initialization status of registries.
        
        Returns:
            Dictionary with status of each registry
        """
        return {
            "cc_registry": self.cc_registry_initialized,
            "entity_registry": self.entity_registry_initialized
        }
