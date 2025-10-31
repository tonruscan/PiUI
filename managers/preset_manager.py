"""
Unified preset page manager.

Handles presets for both devices and modules through a single interface.
"""

from typing import Optional
import showlog


class UnifiedPresetManager:
    """Manages preset pages for both devices and modules."""
    
    def __init__(self, screen):
        """
        Initialize unified preset manager.
        
        Args:
            screen: Pygame screen surface
        """
        self.screen = screen
        self.current_entity_type = None  # "device" or "module"
        self.current_entity_name = None
        self.current_page_id = None
        
    def init_for_device(self, device_name: str, page_id: str):
        """
        Initialize preset page for a device.
        
        Args:
            device_name: Name of the device
            page_id: Current page ID
        """
        from pages import presets
        
        self.current_entity_type = "device"
        self.current_entity_name = device_name
        self.current_page_id = page_id
        
        try:
            presets.init(self.screen, device_name, page_id)
            showlog.debug(f"[UNIFIED_PRESETS] Initialized device presets for {device_name}:{page_id}")
            return True
        except Exception as e:
            showlog.error(f"[UNIFIED_PRESETS] Failed to init device presets: {e}")
            return False
    
    def init_for_module(self, module_name: str, module_instance, widget_instance):
        """
        Initialize preset page for a module.
        
        Args:
            module_name: Name of the module (e.g., "vibrato")
            module_instance: The module instance
            widget_instance: The widget instance
        """
        from pages import module_presets
        
        self.current_entity_type = "module"
        self.current_entity_name = module_name
        
        try:
            module_presets.init(self.screen, module_name, module_instance, widget_instance)
            showlog.debug(f"[UNIFIED_PRESETS] Initialized module presets for {module_name}")
            return True
        except Exception as e:
            showlog.error(f"[UNIFIED_PRESETS] Failed to init module presets: {e}")
            return False
    
    def draw(self, offset_y: int = 0):
        """
        Draw the appropriate preset page.
        
        Args:
            offset_y: Y offset for header animation
        """
        try:
            if self.current_entity_type == "device":
                from pages import presets
                presets.draw(self.screen, offset_y=offset_y)
            elif self.current_entity_type == "module":
                from pages import module_presets
                module_presets.draw(self.screen, offset_y=offset_y)
        except Exception as e:
            showlog.error(f"[UNIFIED_PRESETS] Draw error: {e}")
    
    def handle_event(self, event, msg_queue):
        """
        Handle events for the appropriate preset page.
        
        Args:
            event: Pygame event
            msg_queue: Message queue
        """
        try:
            if self.current_entity_type == "device":
                from pages import presets
                presets.handle_event(event, msg_queue, self.screen)
            elif self.current_entity_type == "module":
                from pages import module_presets
                module_presets.handle_event(event, msg_queue, self.screen)
        except Exception as e:
            showlog.error(f"[UNIFIED_PRESETS] Event handling error: {e}")
    
    def get_current_type(self) -> Optional[str]:
        """Get current entity type ("device" or "module")."""
        return self.current_entity_type
    
    def get_current_name(self) -> Optional[str]:
        """Get current entity name."""
        return self.current_entity_name
