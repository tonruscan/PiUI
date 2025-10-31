"""
Main application class.

Coordinates all subsystems and manages application lifecycle.
"""

import pygame
import queue
import sys
from typing import Optional

from .display import DisplayManager
from .loop import EventLoop
from .services import ServiceRegistry
from .event_bus import EventBus
from .ui_context import UIContext
from .page_registry import PageRegistry
from .plugin import PluginManager
from .mixins import HardwareMixin, RenderMixin, MessageMixin
from managers.module_registry import ModuleRegistry
import config as cfg
import showlog
import showheader
import dialhandlers
import navigator
import devices


class UIApplication(HardwareMixin, RenderMixin, MessageMixin):
    """Main UI application coordinator."""
    
    def __init__(self):
        """Initialize the application."""
        print("[INIT] Starting UI module")
        
        # Modern architecture components
        self.services = ServiceRegistry()
        self.event_bus = EventBus()
        self.page_registry = PageRegistry()
        self.plugin_manager = PluginManager(self)
        self.module_registry = ModuleRegistry()
        
        # Core components
        self.display_manager: Optional[DisplayManager] = None
        self.event_loop: Optional[EventLoop] = None
        self.screen: Optional[pygame.Surface] = None
        self.msg_queue: Optional[queue.Queue] = None
        
        # Managers
        self.dial_manager = None
        self.button_manager = None
        self.mode_manager = None
        self.msg_processor = None
        self.renderer = None
        self.dirty_rect_manager = None
        self.frame_controller = None
        self.global_handler = None
        self.dials_handler = None
        self.device_select_handler = None
        self.hardware_initializer = None
        self.device_loader = None
        
        # Shared state (for compatibility with existing code)
        self.device_behavior_map = {}
        self.exit_rect = pygame.Rect(755, 5, 40, 40)
        
        # State
        self.running = False
        
    def initialize(self):
        """Initialize all subsystems."""
        print("[INIT] Initializing display...")
        self._init_display()
        
        print("[INIT] Initializing logging...")
        self._init_logging()
        
        print("[INIT] Initializing state management...")
        self._init_state_management()
        
        print("[INIT] Loading devices...")
        self._init_devices()
        
        print("[INIT] Initializing managers...")
        self._init_managers()
        
        print("[INIT] Registering pages...")
        self._init_pages()
        
        print("[INIT] Initializing hardware...")
        self._init_hardware()
        
        print("[INIT] Initializing event handling...")
        self._init_event_handling()
        
        print("[INIT] Setting initial page...")
        self._init_initial_page()
        
        print("[INIT] Application initialized successfully")
    
    def _init_display(self):
        """Initialize display and screen."""
        self.display_manager = DisplayManager(
            width=getattr(cfg, "SCREEN_WIDTH", 800),
            height=getattr(cfg, "SCREEN_HEIGHT", 480),
            fullscreen=True
        )
        self.screen = self.display_manager.initialize()
        
        # Message queue
        self.msg_queue = queue.Queue()
        
        # Share queue with existing modules
        devices.msg_queue = self.msg_queue
    
    def _init_logging(self):
        """Initialize logging and display modules."""
        showlog.init(self.screen)
        showheader.init(self.screen)
        showheader.init_queue(self.msg_queue)
    
    def _init_state_management(self):
        """Initialize state management systems."""
        from system import state_manager
        from initialization import RegistryInitializer
        
        state_manager.init()
        
        registry_init = RegistryInitializer()
        registry_init.initialize_cc_registry()
        registry_init.initialize_entity_registry()
    
    def _init_devices(self):
        """Initialize device loader and load devices."""
        from initialization import DeviceLoader
        
        self.device_loader = DeviceLoader()
        self.device_loader.load_all_devices()
    
    def _init_managers(self):
        """Initialize all manager classes."""
        from managers import DialManager, ButtonManager, ModeManager
        from managers.message_queue import MessageQueueProcessor
        from rendering import Renderer, DirtyRectManager, FrameController
        
        # Create managers
        self.dial_manager = DialManager(screen_width=800)
        self.button_manager = ButtonManager()
        self.mode_manager = ModeManager(self.dial_manager, self.button_manager, self.screen)
        self.msg_processor = MessageQueueProcessor(self.msg_queue)
        
        # Create frame controller first
        self.frame_controller = FrameController()
        
        # Rendering components (pass preset_manager, page_registry, and frame_controller to renderer)
        self.renderer = Renderer(self.screen, self.mode_manager.preset_manager, self.page_registry, self.frame_controller)
        self.dirty_rect_manager = DirtyRectManager()
        
        # Register services for dependency injection
        self.services.register('dial_manager', self.dial_manager)
        self.services.register('button_manager', self.button_manager)
        self.services.register('mode_manager', self.mode_manager)
        self.services.register('msg_processor', self.msg_processor)
        self.services.register('renderer', self.renderer)
        self.services.register('dirty_rect_manager', self.dirty_rect_manager)
        self.services.register('frame_controller', self.frame_controller)
        self.services.register('preset_manager', self.mode_manager.preset_manager)
        self.services.register('msg_queue', self.msg_queue)
        self.services.register('screen', self.screen)
        self.services.register('plugin_manager', self.plugin_manager)
        self.services.register('module_registry', self.module_registry)
        
        showlog.debug(f"[APP] Registered {len(self.services.list_services())} services")
        
        # Connect message processor callbacks
        self._connect_message_callbacks()
        
        # Initialize dialhandlers with queue
        dialhandlers.init(self.msg_queue)
    
    def _connect_message_callbacks(self):
        """Connect message processor callbacks to managers."""
        self.msg_processor.on_header_text_change = self.mode_manager.set_header_text
        self.msg_processor.on_button_select = self.button_manager.select_button
        self.msg_processor.on_dial_update = self._handle_dial_update
        self.msg_processor.on_mode_change = self._handle_mode_change
        self.msg_processor.on_device_selected = self._handle_device_selected
        self.msg_processor.on_entity_select = self._handle_entity_select
        self.msg_processor.on_force_redraw = self._handle_force_redraw
        self.msg_processor.on_remote_char = self._handle_remote_char
        self.msg_processor.on_patch_select = self._handle_patch_select
    
    def _init_pages(self):
        """Register all UI pages in the page registry."""
        from pages import page_dials, device_select, patchbay, mixer
        
        # Register static pages
        self.page_registry.register("dials", page_dials, "Device Dials", 
                                    meta={"themed": True, "requires_device": True})
        self.page_registry.register("device_select", device_select, "Select Device",
                                    meta={"themed": False})
        self.page_registry.register("patchbay", patchbay, "Patchbay",
                                    meta={"themed": True})
        self.page_registry.register("mixer", mixer, "Mixer",
                                    meta={"themed": True})
        
        # Discover and load plugins (auto-registers their pages)
        showlog.info("[APP] Discovering plugins...")
        plugin_count = self.plugin_manager.discover("plugins")
        showlog.info(f"[APP] Loaded {plugin_count} plugin(s)")
        
        # Initialize all plugins
        self.plugin_manager.init_all()
        
        # Preset pages handled by unified preset manager
        # But still register for completeness
        self.page_registry.register("presets", None, "Presets",
                                    meta={"themed": True, "managed": True})
        self.page_registry.register("module_presets", None, "Module Presets",
                                    meta={"themed": True, "managed": True})
        
        # Register in services
        self.services.register('page_registry', self.page_registry)
        
        showlog.debug(f"[APP] Registered {len(self.page_registry.list_ids())} pages")
    
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
        showlog.debug(f"[INIT] Hardware status: {status}")
    
    def _init_event_handling(self):
        """Initialize event handlers."""
        from handlers import GlobalEventHandler, DialsEventHandler, DeviceSelectEventHandler
        
        self.global_handler = GlobalEventHandler(self.exit_rect, self.msg_queue)
        self.dials_handler = DialsEventHandler(self.msg_queue)
        self.device_select_handler = DeviceSelectEventHandler(self.msg_queue)
        
        # Create event loop
        self.event_loop = EventLoop()
        self.event_loop.add_handler(self._handle_event)
    
    def _init_initial_page(self):
        """Set initial page."""
        navigator.set_page("device_select", record=False)
        self.mode_manager.ui_mode = "device_select"
        self.mode_manager.header_text = "Select Device"
    
    def run(self):
        """Run the main application loop."""
        if not self.event_loop:
            raise RuntimeError("Application not initialized. Call initialize() first.")
        
        self.running = True
        
        # Run event loop with proper callbacks
        try:
            while self.running and self.global_handler.is_running():
                # Process pygame events
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                        break
                    
                    if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                        self.running = False
                        break
                    
                    # Handle events
                    self._handle_event(event)
                
                # Update
                self._update()
                
                # Render
                self._render()
                
                # Control frame rate
                ui_mode = self.mode_manager.get_current_mode()
                in_burst = self.dirty_rect_manager.is_in_burst()
                target_fps = self.frame_controller.get_target_fps(ui_mode, in_burst)
                self.frame_controller.tick(target_fps)
                
        except Exception as e:
            showlog.error(f"[APP] Error in main loop: {e}")
            import traceback
            traceback.print_exc()
    
    def _handle_event(self, event: pygame.event.Event):
        """Handle a pygame event."""
        # Mouse button down - special handling for burst mode
        if event.type == pygame.MOUSEBUTTONDOWN and hasattr(event, "pos"):
            # End burst mode and force full redraw before processing click
            if self.dirty_rect_manager.is_in_burst():
                self.dirty_rect_manager.end_burst()
                offset_y = showheader.get_offset()
                self._draw_full_frame(offset_y)
                pygame.display.flip()
            
            # Global events first
            if self.global_handler.handle_event(event):
                return
            
            # Let header handle its events
            header_action = showheader.handle_event(event)
            if header_action == "go_back":
                back_page = navigator.go_back()
                if back_page:
                    self.msg_queue.put(("ui_mode", back_page))
                return
            elif header_action == "toggle_menu":
                return
            elif header_action in ("set_mode_patches", "set_mode_presets"):
                from control import presets_control
                presets_control.handle_header_action(
                    header_action,
                    {"ui_mode": self.mode_manager.get_current_mode(), "screen": self.screen}
                )
                return
        
        # Page-specific event handling using page registry
        ui_mode = self.mode_manager.get_current_mode()
        
        # Special cases that need custom handlers
        if ui_mode == "dials":
            # Dials page uses custom handler
            from pages import page_dials
            button_rects = getattr(page_dials, "button_rects", [])
            
            self.dials_handler.handle_event(
                event,
                self.dial_manager.get_dials(),
                button_rects,
                self.button_manager.get_selected_buttons(),
                self.button_manager.active_button_behavior,
                self.button_manager.device_button_memory,
                self.button_manager.select_button
            )
        elif ui_mode == "device_select":
            # Device select uses custom handler
            self.device_select_handler.handle_event(event)
        elif ui_mode in ("presets", "module_presets"):
            # Preset pages use unified preset manager
            self.mode_manager.preset_manager.handle_event(event, self.msg_queue)
        else:
            # All other pages use page registry dynamic dispatch
            page = self.page_registry.get(ui_mode)
            if page and page["handle_event"]:
                try:
                    page["handle_event"](event, self.msg_queue)
                except Exception as e:
                    showlog.error(f"[APP] Event handling error for {ui_mode}: {e}")
            elif page:
                showlog.warn(f"[APP] Page {ui_mode} has no handle_event method")
            else:
                showlog.warn(f"[APP] Unknown page mode: {ui_mode}")
    
    def _update(self):
        """Update application state each frame."""
        # Update header animation
        showheader.update()
        
        # Create typed UI context
        ui_context = UIContext(
            ui_mode=self.mode_manager.get_current_mode(),
            screen=self.screen,
            msg_queue=self.msg_queue,
            dials=self.dial_manager.get_dials(),
            select_button=self.button_manager.select_button,
            header_text=self.mode_manager.get_header_text(),
            prev_mode=self.mode_manager.get_previous_mode(),
            selected_buttons=self.button_manager.get_selected_buttons()
        )
        
        # Process message queue with typed context
        # Convert to dict for backward compatibility with existing msg_processor
        self.msg_processor.process_all({
            "ui_mode": ui_context.ui_mode,
            "screen": ui_context.screen,
            "msg_queue": ui_context.msg_queue,
            "dials": ui_context.dials,
            "select_button": ui_context.select_button,
            "header_text": ui_context.header_text,
        })
    
    def _render(self):
        """Render the current frame."""
        offset_y = showheader.get_offset()
        ui_mode = self.mode_manager.get_current_mode()
        in_burst = self.dirty_rect_manager.is_in_burst()
        
        # Check if we need a full frame
        need_full = (
            self.frame_controller.needs_full_frame() or
            self.mode_manager.needs_full_frame()
        )
        
        # Check if header is animating (if method exists)
        try:
            if hasattr(showheader, 'is_animating') and showheader.is_animating():
                need_full = True
        except Exception:
            pass
        
        if ui_mode == "dials" and not need_full and in_burst:
            # TURBO mode - only redraw changed dials + log bar (dirty rect optimization)
            self._render_dirty_dials(offset_y)
        elif ui_mode == "dials" and not need_full and not in_burst:
            # Idle dials - only refresh log bar
            fps = self.frame_controller.get_fps()
            log_rect = self.renderer.draw_log_bar_only(fps)
            if log_rect:
                self.dirty_rect_manager.mark_dirty(log_rect)
            self.dirty_rect_manager.present_dirty(force_full=False)
        else:
            # Full frame draw
            self._draw_full_frame(offset_y)
            pygame.display.flip()
            
            # End burst mode after full frame
            if in_burst:
                self.dirty_rect_manager.end_burst()
    
    def _draw_full_frame(self, offset_y: int):
        """Draw a complete frame."""
        self.renderer.draw_current_page(
            self.mode_manager.get_current_mode(),
            self.mode_manager.get_header_text(),
            self.dial_manager.get_dials(),
            60,  # radius
            self.button_manager.get_pressed_button(),
            offset_y=offset_y
        )
    
    def _render_dirty_dials(self, offset_y: int):
        """
        Render only the dials that changed (burst/turbo mode).
        Uses dirty rect optimization for smooth 100+ FPS dial updates.
        """
        from pages import page_dials
        import dialhandlers
        
        # Get changed dials
        dials = self.dial_manager.get_dials()
        device_name = getattr(dialhandlers, "current_device_name", None)
        
        # Check if page is muted
        is_page_muted = False
        try:
            if hasattr(dialhandlers, "mute_page_on"):
                is_page_muted = dialhandlers.mute_page_on
        except Exception:
            pass
        
        # Redraw each dial that changed
        for dial in dials:
            # Check if dial was recently updated
            if hasattr(dial, 'dirty') and dial.dirty:
                try:
                    # Redraw just this dial
                    rect = page_dials.redraw_single_dial(
                        self.screen, 
                        dial, 
                        offset_y=offset_y,
                        device_name=device_name,
                        is_page_muted=is_page_muted,
                        update_label=True,
                        force_label=False
                    )
                    
                    # Mark the dial rect as dirty
                    if rect:
                        self.dirty_rect_manager.mark_dirty(rect)
                    
                    # Clear dirty flag
                    dial.dirty = False
                except Exception as e:
                    showlog.warn(f"[APP] Dirty dial redraw failed for dial {dial.id}: {e}")
        
        # Also update log bar
        fps = self.frame_controller.get_fps()
        log_rect = self.renderer.draw_log_bar_only(fps)
        if log_rect:
            self.dirty_rect_manager.mark_dirty(log_rect)
        
        # Present all dirty regions at once
        self.dirty_rect_manager.present_dirty(force_full=False)
        
        # Update burst timing
        self.dirty_rect_manager.update_burst()
    
    # Message callback handlers
    
    def _handle_dial_update(self, dial_id: int, value: int, ui_context: dict):
        """Handle dial value update message."""
        self.dial_manager.update_dial_value(dial_id, value)
        
        # Mark dial as dirty for selective redraw
        dial = self.dial_manager.get_dial_by_id(dial_id)
        if dial:
            dial.dirty = True  # Flag for dirty rect optimization
            
            # Persist to state manager if configured
            try:
                from system import state_manager, cc_registry
                sm = getattr(state_manager, "manager", None)
                if sm:
                    src = getattr(dial, "sm_source_name", None)
                    pid = getattr(dial, "sm_param_id", None)
                    if src and pid:
                        sm.set_value(src, pid, int(value))
            except Exception as e:
                showlog.warn(f"[APP] Dial persist failed: {e}")
        
        # Trigger burst mode (turbo dirty rect updates)
        self.dirty_rect_manager.start_burst()
    
    def _handle_mode_change(self, new_mode: str):
        """Handle mode change request."""
        self.mode_manager.switch_mode(
            new_mode,
            persist_callback=self._persist_current_page_dials,
            device_behavior_map=self.device_behavior_map
        )
    
    def _handle_device_selected(self, msg: tuple):
        """Handle device selection message."""
        _, device_name = msg
        showlog.debug(f"[APP] Device selected: {device_name}")
        
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
    
    def _handle_entity_select(self, msg: tuple):
        """Handle entity selection message."""
        try:
            _, entity_name = msg
            from system import entity_handler, entity_registry as er
            
            entity = er.get_entity(entity_name)
            entity_type = entity.get("type", "device") if entity else "device"
            
            # Delegate to entity handler
            entity_handler.handle_entity(entity_name, entity_type, self.mode_manager.switch_mode)
        except Exception as e:
            showlog.error(f"[APP] Entity select error: {e}")
    
    def _handle_force_redraw(self, msg: tuple):
        """Handle force redraw request."""
        try:
            val = msg[1] if len(msg) > 1 else 2.0
            frames = int(float(val) * 60) if float(val) < 10 else int(val)
            self.frame_controller.request_full_frames(frames)
            showlog.debug(f"[APP] Forced redraw for {frames} frames")
        except Exception as e:
            showlog.warn(f"[APP] Force redraw failed: {e}")
    
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
            from pages import presets
            import midiserver
            
            # Parse message
            core = msg.split("]", 1)[1].strip()
            if "|" in core and "." in core:
                dev, rest = core.split("|", 1)
                num_str, name = rest.split(".", 1)
                preset_num = int(num_str)
                
                # Update display
                presets.selected_preset = preset_num
                presets.ensure_visible(preset_num, self.screen)
                presets.draw(self.screen)
                
                # Send MIDI if external message and on presets page
                if not msg.startswith("[PATCH_SELECT_UI]") and ui_context.get("ui_mode") == "presets":
                    midiserver.send_program_change(preset_num)
                    
        except Exception as e:
            showlog.error(f"[APP] Patch select error: {e}")
    
    def _persist_current_page_dials(self):
        """Persist current page dial values to state manager."""
        try:
            from system import state_manager
            sm = getattr(state_manager, "manager", None)
            if not sm:
                return
            
            for dial in self.dial_manager.get_dials():
                src = getattr(dial, "sm_source_name", None)
                pid = getattr(dial, "sm_param_id", None)
                if src and pid:
                    val = int(getattr(dial, "value", 0))
                    sm.set_value(src, pid, val)
        except Exception as e:
            showlog.error(f"[APP] Persist failed: {e}")
    
    def cleanup(self):
        """Clean up resources and exit."""
        print("[EXIT] Cleaning up...")
        if self.display_manager:
            self.display_manager.cleanup()
        sys.exit()
