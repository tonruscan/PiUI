"""
Mode (page) management.

Handles UI mode switching and page transitions.
"""

from typing import Optional, Callable
import navigator
import dialhandlers
import showlog
from managers.preset_manager import UnifiedPresetManager


class ModeManager:
    """Manages UI mode/page switching."""
    
    def __init__(self, dial_manager, button_manager, screen=None):
        """
        Initialize mode manager.
        
        Args:
            dial_manager: DialManager instance
            button_manager: ButtonManager instance
            screen: Pygame screen surface (optional, can be set later)
        """
        self.dial_manager = dial_manager
        self.button_manager = button_manager
        self.screen = screen
        
        # Unified preset manager
        self.preset_manager = UnifiedPresetManager(screen) if screen else None
        
        self.ui_mode = "device_select"
        self.prev_mode = None
        self.header_text = ""
        self.block_preset_autoswitch_until = 0
        
        # Frame control for transitions
        self._full_frames_left = 0
        self._transitioning_mode = None  # Block rendering for specific mode during transitions
        self._transitioning_from_mode = None  # Also block the mode we're transitioning FROM
    
    def get_current_mode(self) -> str:
        """Get the current UI mode."""
        return self.ui_mode
    
    def get_previous_mode(self) -> Optional[str]:
        """Get the previous UI mode."""
        return self.prev_mode
    
    def is_transitioning(self) -> bool:
        """Check if mode is currently transitioning."""
        return self._transitioning_mode is not None
    
    def is_mode_blocked(self, mode: str) -> bool:
        """
        Check if a specific mode should be blocked from rendering during transition.
        
        Args:
            mode: The mode to check
            
        Returns:
            True if mode is currently transitioning and should not render
        """
        return self._transitioning_mode == mode or self._transitioning_from_mode == mode
    
    def get_header_text(self) -> str:
        """Get the current header text."""
        return self.header_text
    
    def set_header_text(self, text: str):
        """Set the header text."""
        self.header_text = text
    
    def request_full_frames(self, count: int):
        """
        Request a number of full redraw frames.
        
        Args:
            count: Number of frames to force full redraw
        """
        self._full_frames_left = max(self._full_frames_left, count)
        showlog.debug(f"[MODE_MGR] Requested {count} full frames, total={self._full_frames_left}")
    
    def needs_full_frame(self) -> bool:
        """Check if a full frame redraw is needed."""
        if self._full_frames_left > 0:
            self._full_frames_left -= 1
            showlog.debug(f"[MODE_MGR] needs_full_frame=True, remaining={self._full_frames_left}")
            return True
        return False
    
    def switch_mode(self, 
                   new_mode: str,
                   persist_callback: Optional[Callable] = None,
                   device_behavior_map: Optional[dict] = None):
        """
        Switch to a new UI mode/page.
        
        Args:
            new_mode: The new mode to switch to
            persist_callback: Optional callback to persist current page dials
            device_behavior_map: Optional device behavior map reference
        """
        # Save current page state before switching
        if persist_callback:
            persist_callback()
        
        # Block rendering for BOTH old and new modes during transition
        self._transitioning_from_mode = self.ui_mode
        
        # Handle navigation recording
        self._handle_navigation(new_mode)
        
        # Update mode
        self.prev_mode, self.ui_mode = self.ui_mode, new_mode
        showlog.debug(f"[MODE_MGR] Mode switched {self.prev_mode} → {self.ui_mode}")
        
        # Handle mode-specific setup
        if new_mode == "device_select":
            self._setup_device_select()
        elif new_mode == "dials":
            self._setup_dials(device_behavior_map)
            # NOTE: Don't request full frames here - state needs to load first
            # Full frames will be requested after state is restored in _setup_dials
        elif new_mode == "presets":
            self._setup_presets()
        elif new_mode == "patchbay":
            self._setup_patchbay()
        elif new_mode == "mixer":
            self._setup_mixer()
        elif new_mode == "vibrato":
            self._setup_vibrato()
        elif new_mode == "vk8m_main":
            self._setup_vk8m()
        elif new_mode == "ascii_animator":
            self._setup_ascii_animator()
        elif new_mode == "drumbo":
            self._setup_drumbo()
        elif new_mode == "drumbo_main":
            self._setup_drumbo()
        elif new_mode == "test_minimal_main":
            self._setup_test_minimal()
        elif new_mode == "module_presets":
            self._setup_module_presets()
        elif new_mode == "dual_widget_demo":
            self._setup_dual_widget_demo()
        elif new_mode == "spectra_switch":
            self._setup_spectra_switch()

        
        # Clear the from-mode block after setup completes
        self._transitioning_from_mode = None
        
        # Request full frames for transition (except dials - handled internally)
        if new_mode != "dials":
            self.request_full_frames(3)

        if self.prev_mode == "module_presets":
            try:
                from pages import module_base
                module_base.request_custom_widget_redraw(include_overlays=True)
            except Exception as redraw_err:
                showlog.debug(f"[MODE_MGR] Deferred widget redraw failed: {redraw_err}")
    
    def _handle_navigation(self, new_mode: str):
        """
        Handle navigation history recording.
        
        Args:
            new_mode: The new mode being switched to
        """
        try:
            record = False
            
            if new_mode == "device_select":
                record = True
            elif new_mode == "dials" and self.prev_mode != "presets":
                record = True
            elif new_mode == "presets":
                record = True
            elif new_mode in ("patchbay", "text_input", "mixer", "vibrato", "vk8m_main", "ascii_animator", "drumbo", "drumbo_main", "test_minimal_main", "module_presets"):
                record = True
            
            navigator.set_page(new_mode, record=record)
            showlog.debug(f"[NAVIGATOR] {navigator._history}")
            showlog.debug(f"[NAVIGATOR] current={navigator.current()}")
            
        except Exception as e:
            showlog.debug(f"[NAVIGATOR ERROR] {e}")
    
    def _setup_device_select(self):
        """Setup for device_select mode."""
        self.dial_manager.clear_dials()
        self.button_manager.select_button(None)
        self.header_text = "Select Device"
        showlog.debug("[MODE_MGR] Device select page ready")
    
    def _setup_dials(self, device_behavior_map: Optional[dict]):
        """
        Setup for dials mode.
        
        Args:
            device_behavior_map: Device behavior map reference
        """
        import time
        
        # Block rendering for dials mode during transition to prevent flicker
        self._transitioning_mode = "dials"
        start_time = time.perf_counter()
        
        try:
            self._setup_dials_internal(device_behavior_map)
        finally:
            # Always unblock rendering, even if setup fails
            self._transitioning_mode = None
            
            # Log transition duration for performance monitoring
            duration_ms = (time.perf_counter() - start_time) * 1000
            if duration_ms > 40:  # One frame at 25 FPS
                showlog.warn(f"[MODE_MGR] Dials transition took {duration_ms:.1f}ms (perceptible delay)")
            else:
                showlog.debug(f"[MODE_MGR] Dials transition took {duration_ms:.1f}ms")
    
    def _setup_dials_internal(self, device_behavior_map: Optional[dict]):
        """
        Internal dials setup logic.
        
        Args:
            device_behavior_map: Device behavior map reference
        """
        showlog.verbose(f"[MODE_MGR] Entering Dials (prev_mode={self.prev_mode})")
        
        device_name = getattr(dialhandlers, "current_device_name", None)
        
        # Reload device mapping when arriving from device_select or presets
        if self.prev_mode in ("device_select", "presets") and device_name:
            try:
                dialhandlers.load_device(device_name)
            except Exception as e:
                showlog.error(f"[MODE_MGR] Failed to load device: {e}")
        
        # Restore HW routing
        if device_name:
            try:
                import unit_router
                unit_router.load_device(device_name, dialhandlers.on_midi_cc)
            except Exception as e:
                showlog.error(f"[MODE_MGR] Failed to restore device dial route: {e}")
        
        # Restore button behavior map
        if device_name and device_behavior_map is not None:
            new_map = device_behavior_map.get(device_name.upper())
            if new_map:
                self.button_manager.set_button_behavior_map(new_map)
                showlog.verbose(f"[MODE_MGR] Reloaded behavior map for {device_name}")
            else:
                # Lazy load from device module
                try:
                    from initialization import DeviceLoader
                    loader = DeviceLoader()
                    loaded_map = loader.get_button_behavior(device_name)
                    if loaded_map:
                        if device_behavior_map is not None:
                            device_behavior_map[device_name.upper()] = loaded_map
                        self.button_manager.set_button_behavior_map(loaded_map)
                except Exception as e:
                    showlog.verbose(f"[MODE_MGR] Failed to load behavior: {e}")
        
        # Rebuild dials (creates dial objects with generic labels)
        # DO NOT pass device_name - we don't want REGISTRY to set page 1 labels
        # on_button_press() will set the correct page-specific labels via update_from_device()
        if device_name is None:
            showlog.warn("[MODE_MGR] Rebuild bypassed REGISTRY mapping; ensure update_from_device() called immediately.")
        self.dial_manager.rebuild_dials(device_name=None)
        
        # Handle different entry contexts - loads the correct page with suppress_render=True
        # This configures the dials WITHOUT triggering premature redraws
        if self.prev_mode == "device_select":
            self._handle_dials_from_device_select()
        elif self.prev_mode == "presets":
            self._handle_dials_from_presets()
        else:
            self._handle_dials_restore_last_button()
        
        # NOW request full frames AFTER page state is fully loaded
        # This ensures dials are properly configured before any frames are drawn
        self.request_full_frames(3)
    
    def _handle_dials_from_device_select(self):
        """Handle entering dials mode from device_select."""
        device_name = getattr(dialhandlers, "current_device_name", None)
        if not device_name:
            return
        
        # Try to restore preset
        try:
            from control import global_control as gc
            preset_info = gc.get_current_preset(device_name)
        except Exception:
            preset_info = None
        
        if preset_info:
            self._restore_preset(device_name, preset_info)
        else:
            # Default to previously selected left button or page 1
            which = self.button_manager.restore_left_page("1")
            try:
                # Use suppress_render to load state without triggering frames
                dialhandlers.on_button_press(int(which), suppress_render=True)
                # Remember this button for the device
                self.button_manager.remember_device_button(device_name, which)
            except Exception as e:
                showlog.error(f"[MODE_MGR] Failed to load page {which}: {e}")
            showlog.debug(f"[MODE_MGR] Restored/defaulted page {which}")
    
    def _handle_dials_from_presets(self):
        """Handle entering dials mode from presets page."""
        device_name = getattr(dialhandlers, "current_device_name", None)
        if not device_name:
            return
        
        try:
            from control import global_control as gc
            preset_info = gc.get_current_preset(device_name)
        except Exception:
            preset_info = None
        
        if preset_info:
            self._restore_preset(device_name, preset_info)
        else:
            try:
                # Use suppress_render to load state without triggering frames
                dialhandlers.on_button_press(1, suppress_render=True)
                # Remember button 1 for the device
                self.button_manager.remember_device_button(device_name, "1")
            except Exception as e:
                showlog.error(f"[MODE_MGR] Failed to load page 1: {e}")
            self.button_manager.select_button("1")
            showlog.debug("[MODE_MGR] Default page 1 loaded (no current preset)")
    
    def _handle_dials_restore_last_button(self):
        """Handle restoring last active button when returning to dials."""
        try:
            device_name = getattr(dialhandlers, "current_device_name", None)
            if not device_name:
                showlog.warn("[MODE_MGR] No device_name in restore_last_button, skipping")
                return
            
            last_button = self.button_manager.get_device_button(device_name)
            if not last_button:
                # Should not happen - all entry paths now remember buttons
                showlog.error(f"[MODE_MGR] No last button for {device_name} - this is a bug!")
                return
            
            behavior = self.button_manager.get_button_behavior(last_button)
            
            if behavior == "state":
                idx = int(last_button)
                # Use suppress_render to load state without triggering frames
                dialhandlers.on_button_press(idx, suppress_render=True)
                showlog.log(f"[MODE_MGR] Restored state button {last_button}")
            else:
                showlog.debug(f"[MODE_MGR] Skipped restore for non-state button {last_button}")
                
        except Exception as e:
            showlog.error(f"[MODE_MGR] Failed to restore last button: {e}")
    
    def _restore_preset(self, device_name: str, preset_info: dict):
        """
        Restore a preset.
        
        Args:
            device_name: Device name
            preset_info: Preset information dictionary
        """
        try:
            import devices
            
            page_id = preset_info.get("page_id")
            page_name = preset_info.get("page_name") or str(page_id)
            idx = devices.get_button_index_by_page_name(device_name, page_name)
            
            values = preset_info.get("values")
            program = preset_info.get("program")
            
            if values:
                if device_name not in dialhandlers.live_states:
                    dialhandlers.live_states[device_name] = {}
                dialhandlers.live_states[device_name][page_id] = values
                showlog.debug(f"[MODE_MGR] Seeded LIVE for {device_name}:{page_id}")
            elif program is not None:
                import midiserver
                midiserver.send_program_change(int(program))
                showlog.debug(f"[MODE_MGR] Recalled program {program}")
            
            button_index = idx if idx else int(page_id) if str(page_id).isdigit() else 1
            dialhandlers.on_button_press(button_index)
            showlog.debug(f"[MODE_MGR] Restored preset '{preset_info['preset']}'")
            
        except Exception as e:
            showlog.debug(f"[MODE_MGR] Failed to restore preset: {e}")
    
    def _setup_presets(self):
        """Setup for presets mode."""
        device_name = getattr(dialhandlers, "current_device_name", None) or "Unknown"
        try:
            if device_name and isinstance(device_name, str):
                self.header_text = f"{device_name} Presets"
            else:
                self.header_text = "Presets"
        except Exception:
            self.header_text = "Presets"
        
        page_id = getattr(dialhandlers, "current_page_id", "01")
        showlog.debug(f"[MODE_MGR] Loading Presets page for {device_name}")
        
        # Use unified preset manager for device presets
        if self.preset_manager:
            self.preset_manager.init_for_device(device_name, page_id)
    

# --- setup methods for additional modes ---

    def _setup_dual_widget_demo(self):
        self.header_text = "Dual Widget Demo"

        from pages import module_base as page
        from plugins.dual_widget_demo_plugin import DualWidgetDemoModule

        page.set_active_module(DualWidgetDemoModule)

        if hasattr(page, "init_page"):
            page.init_page()

    def _setup_spectra_switch(self):
        self.header_text = "Spectra Switch"
        from pages import module_base as page
        from plugins.spectra_switch_plugin import SpectraSwitchModule
        from system import cc_registry
        import unit_router

        page.set_active_module(SpectraSwitchModule)

        try:
            cc_registry.load_from_module(SpectraSwitchModule.MODULE_ID, SpectraSwitchModule.REGISTRY)
        except Exception as exc:
            showlog.warn(f"[MODE_MGR] Spectra registry load failed: {exc}")

        if hasattr(page, "init_page"):
            page.init_page()

        try:
            unit_router.load_module(SpectraSwitchModule.MODULE_ID, page.handle_hw_dial)
        except Exception as exc:
            showlog.warn(f"[MODE_MGR] Failed to bind Spectra hardware dials: {exc}")




    def _setup_patchbay(self):
        """Setup for patchbay mode."""
        self.header_text = "Patchbay"
        showlog.debug("[MODE_MGR] Switched to Patchbay")
    
    def _setup_mixer(self):
        """Setup for mixer mode."""
        self.header_text = "Mixer"
        showlog.debug("[MODE_MGR] Switched to Mixer")
    
    def _setup_vibrato(self):
        """Setup for vibrato mode."""
        self.header_text = "Vibrato Maker"
        showlog.debug("[MODE_MGR] Switched to Vibrato Maker")
        
        try:
            from system import cc_registry
            from pages import module_base as vibrato
            from plugins.vibrato_plugin import Vibrato
            import unit_router
            
            # Set the active module for module_base BEFORE init_page
            vibrato.set_active_module(Vibrato)
            
            cc_registry.load_from_device("vibrato")
            
            if hasattr(vibrato, "init_page"):
                vibrato.init_page()
                showlog.debug("[MODE_MGR] Vibrato page initialized")
            
            unit_router.load_module("vibrato", vibrato.handle_hw_dial)
            showlog.debug("[MODE_MGR] Vibrato module active")
            
        except Exception as e:
            showlog.error(f"[MODE_MGR] Failed to activate Vibrato: {e}")
    
    def _setup_vk8m(self):
        """Setup for VK8M mode."""
        self.header_text = "Roland VK-8M"
        showlog.debug("[MODE_MGR] Switched to VK-8M")
        
        try:
            from system import cc_registry
            from pages import module_base as vk8m_page
            from plugins.vk8m_plugin import VK8M
            import unit_router
            
            # Set the active module for module_base BEFORE init_page
            vk8m_page.set_active_module(VK8M)
            
            # Set device context for MIDI routing tags
            try:
                import midiserver
                midiserver.set_device_context("VK8M")
            except Exception as e:
                showlog.warn(f"[MODE_MGR] Could not set MIDI device context: {e}")
            
            cc_registry.load_from_device("vk8m")
            
            showlog.info(f"*[MODE_MGR] 🔄 VK8M: Checking if vk8m_page has init_page: {hasattr(vk8m_page, 'init_page')}")
            if hasattr(vk8m_page, "init_page"):
                showlog.info(f"*[MODE_MGR] 🔄 VK8M: Calling vk8m_page.init_page()")
                vk8m_page.init_page()
                showlog.info(f"*[MODE_MGR] ✅ VK8M: Page initialized - _PRESET_UI should now exist")
            else:
                showlog.warn(f"[MODE_MGR] VK8M page does not have init_page() method!")
            
            unit_router.load_module("vk8m", vk8m_page.handle_hw_dial)
            showlog.debug("[MODE_MGR] VK8M module active")
            
        except Exception as e:
            showlog.error(f"[MODE_MGR] Failed to activate VK8M: {e}")
    
    def _setup_ascii_animator(self):
        """Setup for ASCII Animator mode."""
        self.header_text = "ASCII Animator"
        showlog.debug("[MODE_MGR] Switched to ASCII Animator")
        
        try:
            from pages import module_base as page
            from plugins.ascii_animator_plugin import ASCIIAnimatorModule
            
            # Set the active module for module_base BEFORE init_page
            page.set_active_module(ASCIIAnimatorModule)
            
            # Initialize page
            if hasattr(page, "init_page"):
                page.init_page()
            
            showlog.debug("[MODE_MGR] ASCII Animator module active")
            
        except Exception as e:
            showlog.error(f"[MODE_MGR] Failed to activate ASCII Animator: {e}")
            import traceback
            showlog.error(traceback.format_exc())
    
    def _setup_drumbo(self):
        """Setup for Drumbo drum machine mode."""
        self.header_text = "Drumbo"
        showlog.debug("[MODE_MGR] Switched to Drumbo")
        
        try:
            from pages import module_base as page
            from plugins.sampler.instruments.drumbo.module import DrumboInstrument
            
            # Set the active module for module_base BEFORE init_page
            page.set_active_module(DrumboInstrument)
            
            # Initialize page
            if hasattr(page, "init_page"):
                page.init_page()
            
            showlog.debug("[MODE_MGR] Drumbo module active")
            
        except Exception as e:
            showlog.error(f"[MODE_MGR] Failed to activate Drumbo: {e}")
            import traceback
            showlog.error(traceback.format_exc())
    
    def _setup_test_minimal(self):
        """Setup for test minimal mode."""
        self.header_text = "Test Minimal"
        showlog.debug("[MODE_MGR] Switched to Test Minimal")
        
        try:
            from pages import module_base as page
            from plugins.test_minimal_plugin import TestMinimal
            
            page.set_active_module(TestMinimal)
            
            if hasattr(page, "init_page"):
                page.init_page()
            
            showlog.debug("[MODE_MGR] Test Minimal module active")
            
        except Exception as e:
            showlog.error(f"[MODE_MGR] Failed to activate Test Minimal: {e}")
            import traceback
            showlog.error(traceback.format_exc())

        
    
    def _setup_module_presets(self):
        """Setup for module_presets mode."""
        self.header_text = "Load Preset"
        showlog.debug("[MODE_MGR] === SETUP MODULE PRESETS ===")
        
        # Use unified preset manager for module presets
        if self.preset_manager:
            try:
                # Get module info from module_base (supports vibrato, vk8m, etc.)
                from pages import module_base
                
                showlog.debug("[MODE_MGR] Getting active module instance...")
                # Get the active module instance and widget
                module_instance = module_base._get_mod_instance()
                showlog.debug(f"[MODE_MGR] module_instance: {module_instance}")
                showlog.debug(f"[MODE_MGR] module_instance type: {type(module_instance)}")
                
                if module_instance:
                    module_id = getattr(module_instance, "MODULE_ID", None)
                    showlog.debug(f"[MODE_MGR] Got MODULE_ID from instance: {module_id}")
                else:
                    module_id = None
                    showlog.debug("[MODE_MGR] No module instance found!")
                
                # Fallback to module attribute if instance doesn't have it
                if not module_id:
                    module_id = module_base._get_module_attr("MODULE_ID", "unknown")
                    showlog.debug(f"[MODE_MGR] Fallback MODULE_ID from module attr: {module_id}")
                
                widget = getattr(module_base, "_CUSTOM_WIDGET_INSTANCE", None)
                showlog.debug(f"[MODE_MGR] widget: {widget}")
                
                showlog.debug(f"[MODE_MGR] Calling init_for_module with module_id='{module_id}'")
                self.preset_manager.init_for_module(module_id, module_instance, widget)
                showlog.debug(f"[MODE_MGR] Module presets initialized for {module_id}")
            except Exception as e:
                showlog.error(f"[MODE_MGR] Failed to init module presets: {e}")
                import traceback
                showlog.error(f"[MODE_MGR] Traceback: {traceback.format_exc()}")
