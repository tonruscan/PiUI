"""
Message handling mixin.

Handles all message queue processing and callback routing.
"""

import showlog
import dialhandlers


class MessageMixin:
    """Mixin for message queue handling."""
    
    def _handle_dial_update(self, dial_id: int, value: int, ui_context: dict):
        """Handle dial value update message."""
        self.dial_manager.update_dial_value(dial_id, value)
        
        # Persist to state manager if configured
        dial = self.dial_manager.get_dial_by_id(dial_id)
        if dial:
            try:
                from system import state_manager, cc_registry
                sm = getattr(state_manager, "manager", None)
                if sm:
                    src = getattr(dial, "sm_source_name", None)
                    pid = getattr(dial, "sm_param_id", None)
                    if src and pid:
                        sm.set_value(src, pid, int(value))
            except Exception as e:
                showlog.warn(f"[MESSAGE_MIXIN] Dial persist failed: {e}")
        
        # Trigger redraw
        self.dirty_rect_manager.start_burst()
        
        # Publish event
        if hasattr(self, 'event_bus'):
            self.event_bus.publish('dial_update', {'dial_id': dial_id, 'value': value})
    
    def _handle_mode_change(self, new_mode: str):
        """Handle mode change request."""
        self.mode_manager.switch_mode(
            new_mode,
            persist_callback=self._persist_current_page_dials,
            device_behavior_map=self.device_behavior_map
        )
        
        # Publish event
        if hasattr(self, 'event_bus'):
            self.event_bus.publish('mode_change', new_mode)
    
    def _handle_device_selected(self, msg: tuple):
        """Handle device selection message."""
        _, device_name = msg
        showlog.debug(f"[MESSAGE_MIXIN] Device selected: {device_name}")
        
        # Load device
        dialhandlers.load_device(device_name)
        
        # Load button behavior
        behavior_map = self.device_loader.get_button_behavior(device_name)
        if behavior_map:
            self.device_behavior_map[device_name.upper()] = behavior_map
            self.button_manager.set_button_behavior_map(behavior_map)
        
        # Load registry
        from initialization import RegistryInitializer
        registry_init = RegistryInitializer()
        registry_init.load_device_registry(device_name)
        
        # Send CV calibration if needed
        self.device_loader.send_cv_calibration(device_name)
        
        # Get device info for default page
        dev_info = self.device_loader.get_device_info(device_name)
        start_page = dev_info.get("default_page", "dials") if dev_info else "dials"
        
        # Switch to device page
        self.mode_manager.switch_mode(
            start_page,
            persist_callback=self._persist_current_page_dials,
            device_behavior_map=self.device_behavior_map
        )
        
        # Publish event
        if hasattr(self, 'event_bus'):
            self.event_bus.publish('device_selected', device_name)
    
    def _handle_entity_select(self, msg: tuple):
        """Handle entity selection message."""
        try:
            _, entity_name = msg
            from system import entity_handler, entity_registry as er
            
            entity = er.get_entity(entity_name)
            entity_type = entity.get("type", "device") if entity else "device"
            
            # Delegate to entity handler
            entity_handler.handle_entity(entity_name, entity_type, self.mode_manager.switch_mode)
            
            # Publish event
            if hasattr(self, 'event_bus'):
                self.event_bus.publish('entity_select', {'name': entity_name, 'type': entity_type})
        except Exception as e:
            showlog.error(f"[MESSAGE_MIXIN] Entity select error: {e}")
    
    def _handle_force_redraw(self, msg: tuple):
        """Handle force redraw request."""
        try:
            val = msg[1] if len(msg) > 1 else 2.0
            frames = int(float(val) * 60) if float(val) < 10 else int(val)
            self.frame_controller.request_full_frames(frames)
            showlog.debug(f"[MESSAGE_MIXIN] Forced redraw for {frames} frames")
        except Exception as e:
            showlog.warn(f"[MESSAGE_MIXIN] Force redraw failed: {e}")
    
    def _handle_remote_char(self, msg: tuple, ui_context: dict):
        """Handle remote character input."""
        _, char = msg
        ui_mode = ui_context.get("ui_mode")
        
        if ui_mode == "vibrato":
            from pages import module_base as vibrato
            if hasattr(vibrato, "is_preset_ui_active") and vibrato.is_preset_ui_active():
                vibrato.handle_remote_input(char)
        elif ui_mode == "patchbay":
            from pages import patchbay
            patchbay.handle_remote_input(char)
    
    def _handle_patch_select(self, msg: str, ui_context: dict):
        """Handle patch select message."""
        try:
            showlog.debug(f"[MESSAGE_MIXIN] Patch select: {msg}")
            dialhandlers.on_patch_select(msg)
        except Exception as e:
            showlog.error(f"[MESSAGE_MIXIN] Patch select error: {e}")
    
    def _persist_current_page_dials(self):
        """Persist current page dial values to state manager."""
        try:
            from system import state_manager
            sm = getattr(state_manager, "manager", None)
            if sm and hasattr(sm, "save"):
                sm.save()
                showlog.debug("[MESSAGE_MIXIN] Persisted dial values")
        except Exception as e:
            showlog.warn(f"[MESSAGE_MIXIN] Persist failed: {e}")
