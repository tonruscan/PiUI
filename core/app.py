"""
Main application class.

Coordinates all subsystems and manages application lifecycle.
"""

import os
import pygame
import queue
import sys
from typing import Optional

from .display import DisplayManager
from .loop import EventLoop
from .service_registry import ServiceRegistry
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
from rendering import color_correction


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
        self._last_render_path = None  # track render branch for debugging
        
    def initialize(self):
        """Initialize all subsystems."""
        print("[INIT] Initializing display...")
        self._init_display()
        
        print("[INIT] Initializing logging...")
        self._init_logging()

        print("[INIT] Inspecting audio mixer...")
        self._log_audio_startup_state()
        
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
        
        print("[INIT] Starting async message processing...")
        self._start_async_processing()
        
        print("[INIT] Application initialized successfully")
    
    def _init_display(self):
        """Initialize display and screen."""
        import crashguard
        crashguard.checkpoint("_init_display: Starting (DisplayManager version)")
        
        from managers.safe_queue import SafeQueue
        crashguard.checkpoint("_init_display: SafeQueue imported")
        
        crashguard.checkpoint(f"_init_display: Creating DisplayManager (width={getattr(cfg, 'SCREEN_WIDTH', 800)}, height={getattr(cfg, 'SCREEN_HEIGHT', 480)})")
        self.display_manager = DisplayManager(
            width=getattr(cfg, "SCREEN_WIDTH", 800),
            height=getattr(cfg, "SCREEN_HEIGHT", 480),
            fullscreen=True
        )
        crashguard.checkpoint("_init_display: DisplayManager created")
        
        crashguard.checkpoint("_init_display: Initializing display...")
        self.screen = self.display_manager.initialize()
        crashguard.checkpoint(f"_init_display: Display initialized ({self.screen.get_width()}x{self.screen.get_height()})")
        
        # Message queue (thread-safe for async processing)
        self.msg_queue = SafeQueue()
        crashguard.checkpoint("_init_display: SafeQueue created")
        
        # Share queue with existing modules
        devices.msg_queue = self.msg_queue
        crashguard.checkpoint("_init_display: Complete")
    
    def _init_logging(self):
        """Initialize logging and display modules."""
        import crashguard
        crashguard.checkpoint("_init_logging: Starting")
        
        showlog.init(self.screen)
        crashguard.checkpoint("_init_logging: showlog.init() complete")
        
        showheader.init(self.screen)
        crashguard.checkpoint("_init_logging: showheader.init() complete")
        
        showheader.init_queue(self.msg_queue)
        crashguard.checkpoint("_init_logging: showheader.init_queue() complete")

    def _log_audio_startup_state(self):
        """Log current mixer configuration so loupe captures startup audio state."""
        try:
            from config import audio as audio_cfg
        except Exception as exc:
            showlog.warn(f"[AUDIO] Failed to import config.audio: {exc}")
            audio_cfg = None

        requested = {}
        preferred = {}
        force_config = None

        if audio_cfg:
            requested = {
                "freq": getattr(audio_cfg, "SAMPLE_RATE", None),
                "size": getattr(audio_cfg, "SAMPLE_SIZE", None),
                "channels": getattr(audio_cfg, "CHANNELS", None),
                "buffer": getattr(audio_cfg, "BUFFER_SIZE", None),
            }
            preferred = {
                "name": getattr(audio_cfg, "PREFERRED_AUDIO_DEVICE_NAME", None),
                "index": getattr(audio_cfg, "PREFERRED_AUDIO_DEVICE_INDEX", None),
                "keywords": getattr(audio_cfg, "PREFERRED_AUDIO_DEVICE_KEYWORDS", ()),
                "force_device": getattr(audio_cfg, "FORCE_AUDIO_DEVICE", True),
            }
            requested["allow_changes"] = getattr(audio_cfg, "ALLOW_AUDIO_CHANGES", None)
            requested["mixer_channels"] = getattr(audio_cfg, "MIXER_NUM_CHANNELS", None)
            force_config = getattr(audio_cfg, "FORCE_AUDIO_CONFIG", None)

        env_force_value = os.environ.get("DRUMBO_FORCE_AUDIO_REINIT")
        env_force_flag = self._bool_from_env(env_force_value)

        if force_config or env_force_flag:
            reason_bits = []
            if force_config:
                reason_bits.append("config")
            if env_force_flag:
                reason_bits.append("env")
            reason = "/".join(reason_bits) or "unspecified"
            self._force_audio_reinit(requested, preferred, reason)

        mixer_init = pygame.mixer.get_init()
        mixer_channels = None
        actual = None

        if mixer_init:
            actual = {
                "freq": mixer_init[0],
                "format": mixer_init[1],
                "channels": mixer_init[2],
            }
            try:
                mixer_channels = pygame.mixer.get_num_channels()
            except Exception as exc:
                showlog.debug(f"[AUDIO] Unable to query mixer channels: {exc}")
        else:
            actual = None

        keywords_display = None
        if preferred.get("keywords"):
            try:
                keywords_display = ", ".join(sorted({str(k) for k in preferred["keywords"] if k})) or None
            except Exception:
                keywords_display = str(preferred.get("keywords"))

        showlog.info("[AUDIO] ═══════════════════════════════════════")
        showlog.info("[AUDIO] Audio Mixer Startup")
        showlog.info("[AUDIO] ═══════════════════════════════════════")
        showlog.info(f"[AUDIO] Requested → freq={requested.get('freq')} size={requested.get('size')} channels={requested.get('channels')} buffer={requested.get('buffer')}")
        showlog.info(f"[AUDIO] Mixer channels (requested) → {requested.get('mixer_channels')}")
        showlog.info(f"[AUDIO] Allow changes → {requested.get('allow_changes')}")
        showlog.info(f"[AUDIO] Preferred device → name='{preferred.get('name')}' index={preferred.get('index')} keywords={keywords_display}")
        showlog.info(f"[AUDIO] Force device selection → {preferred.get('force_device')}")
        showlog.info(f"[AUDIO] FORCE_AUDIO_CONFIG (config) → {force_config}")
        showlog.info(f"[AUDIO] DRUMBO_FORCE_AUDIO_REINIT (env) → {env_force_value}")

        if actual:
            showlog.info(f"[AUDIO] Mixer active → freq={actual['freq']} format={actual['format']} channels={actual['channels']} num_channels={mixer_channels}")
        else:
            showlog.info("[AUDIO] Mixer active → False (pygame.mixer not initialized)")

        showlog.info("[AUDIO] ═══════════════════════════════════════")

        payload = {
            "requested": requested,
            "preferred": preferred,
            "force_config": force_config,
            "env_force": env_force_value,
            "mixer_active": bool(mixer_init),
            "actual": actual,
            "mixer_channels": mixer_channels,
        }

        showlog.debug(f"*[AUDIO] Startup mixer state {payload}")

    def _force_audio_reinit(self, requested: dict, preferred: dict, reason: str):
        requested = dict(requested or {})
        preferred = dict(preferred or {})

        freq = self._safe_int(requested.get("freq"), 44100)
        size = self._safe_int(requested.get("size"), -16)
        channels = self._safe_int(requested.get("channels"), 2)
        buffer_len = self._safe_int(requested.get("buffer"), 1024)
        mixer_channels = self._safe_int(requested.get("mixer_channels"), 8)

        allow_changes = requested.get("allow_changes")
        if allow_changes is not None:
            allow_changes = self._safe_int(allow_changes)

        keywords = preferred.get("keywords") or ()
        if isinstance(keywords, str):
            keywords = (keywords,)
        else:
            try:
                keywords = tuple(keywords)
            except TypeError:
                keywords = (str(keywords),)

        force_device = bool(preferred.get("force_device", True))

        devices = self._enumerate_audio_devices()
        if devices:
            showlog.info("[AUDIO] Available output devices:")
            for idx, name in enumerate(devices, 1):
                showlog.info(f"[AUDIO]   {idx}. {name}")
        else:
            showlog.info("[AUDIO] Output device list unavailable (SDL2 audio) – proceeding with defaults")

        resolved_device = None
        if force_device:
            resolved_device = self._resolve_audio_device(preferred, devices, keywords)

        showlog.info(f"[AUDIO] Forcing mixer reinitialization ({reason}) → freq={freq} size={size} channels={channels} buffer={buffer_len}")
        if resolved_device:
            showlog.info(f"[AUDIO] Target output device → {resolved_device}")
        elif not force_device:
            showlog.info("[AUDIO] Force device selection disabled; letting SDL choose output")

        try:
            pygame.mixer.quit()
        except Exception as exc:
            showlog.warn(f"[AUDIO] Mixer quit during forced reinit reported: {exc}")

        pre_kwargs = {
            "frequency": freq,
            "size": size,
            "channels": channels,
            "buffer": buffer_len,
        }

        try:
            pygame.mixer.pre_init(**pre_kwargs)
        except TypeError as exc:
            showlog.debug(f"[AUDIO] pygame.mixer.pre_init argument mismatch: {exc}")
        except Exception as exc:
            showlog.debug(f"[AUDIO] pygame.mixer.pre_init failed: {exc}")

        init_kwargs = {
            "frequency": freq,
            "size": size,
            "channels": channels,
            "buffer": buffer_len,
        }

        if allow_changes is not None:
            init_kwargs["allowedchanges"] = allow_changes
        if resolved_device:
            init_kwargs["devicename"] = resolved_device

        attempt_kwargs = dict(init_kwargs)

        while True:
            try:
                pygame.mixer.init(**attempt_kwargs)
                break
            except TypeError as exc:
                if "allowedchanges" in attempt_kwargs:
                    showlog.debug(f"[AUDIO] Removing unsupported allowedchanges during init: {exc}")
                    attempt_kwargs.pop("allowedchanges", None)
                    continue
                raise
            except Exception as exc:
                failing_device = attempt_kwargs.get("devicename")
                if failing_device:
                    showlog.warn(f"[AUDIO] Mixer init failed on '{failing_device}', retrying with default device: {exc}")
                    attempt_kwargs.pop("devicename", None)
                    resolved_device = None
                    continue
                showlog.error(f"[AUDIO] Mixer init failed: {exc}")
                return

        try:
            pygame.mixer.set_num_channels(mixer_channels)
        except Exception as exc:
            showlog.warn(f"[AUDIO] Unable to set mixer channel count to {mixer_channels}: {exc}")

        actual = pygame.mixer.get_init()
        if actual:
            showlog.info(f"[AUDIO] ✓ Mixer reinitialized → freq={actual[0]} format={actual[1]} channels={actual[2]} num_channels={pygame.mixer.get_num_channels()}")
            showlog.debug(f"*[AUDIO] Mixer reinit kwargs={attempt_kwargs} actual={actual}")
        else:
            showlog.warn("[AUDIO] Mixer reinitialization reported success but pygame.mixer.get_init() returned None")

    def _enumerate_audio_devices(self):
        devices = []
        try:
            from pygame._sdl2 import audio as sdl2_audio
            raw_devices = list(sdl2_audio.get_audio_device_names(False))
            for device in raw_devices:
                if isinstance(device, str):
                    devices.append(device)
                else:
                    try:
                        devices.append(device.decode("utf-8", "ignore"))
                    except Exception:
                        devices.append(str(device))
        except Exception as exc:
            showlog.debug(f"[AUDIO] SDL2 audio device query unavailable: {exc}")
        return devices

    def _resolve_audio_device(self, preferred: dict, devices: list, keywords: tuple):
        devices = devices or []
        name_pref = preferred.get("name") if preferred else None
        index_pref = preferred.get("index") if preferred else None

        if name_pref:
            resolved = self._match_audio_device(name_pref, devices)
            if resolved:
                return resolved
            return name_pref

        if index_pref is not None and devices:
            try:
                index_pref = int(index_pref)
                if 0 <= index_pref < len(devices):
                    return devices[index_pref]
                if 1 <= index_pref <= len(devices):
                    return devices[index_pref - 1]
            except Exception as exc:
                showlog.warn(f"[AUDIO] Invalid preferred device index '{index_pref}': {exc}")

        for keyword in keywords:
            if not keyword:
                continue
            resolved = self._match_audio_device(keyword, devices)
            if resolved:
                return resolved

        return None

    def _match_audio_device(self, needle, haystack):
        if not needle:
            return None
        target = str(needle).lower()
        for device in haystack:
            if device and str(device).lower() == target:
                return device
        for device in haystack:
            if device and target in str(device).lower():
                return device
        return None

    def _bool_from_env(self, value):
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        try:
            text = str(value).strip().lower()
        except Exception:
            return False
        return text not in ("", "0", "false", "off", "no")

    def _safe_int(self, value, default=None):
        try:
            if value is None:
                return default
            return int(value)
        except (TypeError, ValueError):
            return default
    
    def _init_state_management(self):
        """Initialize state management systems."""
        import crashguard
        crashguard.checkpoint("_init_state_management: Starting")
        
        from system import state_manager
        from initialization import RegistryInitializer
        crashguard.checkpoint("_init_state_management: Imports successful")
        
        state_manager.init()
        crashguard.checkpoint("_init_state_management: state_manager.init() complete")
        
        registry_init = RegistryInitializer()
        crashguard.checkpoint("_init_state_management: RegistryInitializer created")
        
        registry_init.initialize_cc_registry()
        crashguard.checkpoint("_init_state_management: CC registry initialized")
        
        registry_init.initialize_entity_registry()
        crashguard.checkpoint("_init_state_management: Entity registry initialized")
    
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
        
        # Create frame controller with page_registry for capability queries
        self.frame_controller = FrameController(page_registry=self.page_registry)
        
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
        """Initialize hardware connections and register services."""
        import crashguard
        crashguard.checkpoint("_init_hardware: Starting")
        
        # Create and register services FIRST (before HardwareInitializer)
        from core.services.midi_server import MIDIServer
        from core.services.cv_client import CVClient
        from core.services.network_server import NetworkServer
        crashguard.checkpoint("_init_hardware: Service imports successful")
        
        # Create service instances
        crashguard.checkpoint("_init_hardware: Creating MIDIServer...")
        midi_server = MIDIServer()
        crashguard.checkpoint("_init_hardware: MIDIServer created")
        
        crashguard.checkpoint("_init_hardware: Creating CVClient...")
        cv_client = CVClient()
        crashguard.checkpoint("_init_hardware: CVClient created")
        
        crashguard.checkpoint("_init_hardware: Creating NetworkServer...")
        network_server = NetworkServer()
        crashguard.checkpoint("_init_hardware: NetworkServer created")
        
        # Register services (deterministic order: Network → CV → MIDI)
        self.services.register('network_server', network_server)
        self.services.register('cv_client', cv_client)
        self.services.register('midi_server', midi_server)
        crashguard.checkpoint("_init_hardware: Services registered")
        
        showlog.info("[SERVICES] Registered: network_server, cv_client, midi_server")
        
        # Initialize services (check config flags with defaults)
        disable_network = getattr(cfg, 'DISABLE_NETWORK', False)
        disable_midi = getattr(cfg, 'DISABLE_MIDI', False)
        
        if not disable_network:
            crashguard.checkpoint("_init_hardware: Starting network server...")
            network_server.start()
            crashguard.checkpoint("_init_hardware: Network server started")
            
            crashguard.checkpoint("_init_hardware: Starting CV client async...")
            cv_client.connect_async()  # Deferred connection (non-blocking)
            crashguard.checkpoint("_init_hardware: CV client async started")
        else:
            crashguard.checkpoint("_init_hardware: Network/CV disabled by config")
        
        if not disable_midi:
            crashguard.checkpoint("_init_hardware: Initializing MIDI server...")
            midi_server.init(
                dial_cb=dialhandlers.on_midi_cc,
                sysex_cb=dialhandlers.on_midi_sysex,
                note_cb=dialhandlers.on_midi_note
            )
            crashguard.checkpoint("_init_hardware: MIDI server initialized")
        else:
            crashguard.checkpoint("_init_hardware: MIDI disabled by config")
        
        # Legacy: Initialize old hardware module (will use compatibility wrappers)
        from initialization import HardwareInitializer
        crashguard.checkpoint("_init_hardware: HardwareInitializer imported")
        
        self.hardware_initializer = HardwareInitializer(self.msg_queue)
        crashguard.checkpoint("_init_hardware: HardwareInitializer created")
        
        # Initialize remote typing server
        showlog.info("[INIT] Starting remote typing server...")
        self.hardware_initializer.initialize_remote_typing(self.screen)
        crashguard.checkpoint("_init_hardware: Remote typing server started")
        
        # Skip initialize_all since we already initialized services
        # self.hardware_initializer.initialize_all(...)
        
        status = {"midi": midi_server.is_connected(), 
                  "cv": cv_client.is_connected(),
                  "network": network_server.is_running()}
        showlog.debug(f"[INIT] Hardware status: {status}")
        crashguard.checkpoint(f"_init_hardware: Complete - Status: {status}")
    
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
        # Request initial full frame renders
        self.mode_manager.request_full_frames(3)
    
    def _start_async_processing(self):
        """Start background message processing thread."""
        # Start async loop with context provider
        self.msg_processor.start_async_loop(self._get_ui_context)
    
    def _get_ui_context(self):
        """
        Get snapshot of current UI state for background thread.
        
        Returns:
            Dictionary with current UI state (safe for background thread)
        """
        try:
            return {
                "ui_mode": self.mode_manager.get_current_mode(),
                "screen": self.screen,
                "msg_queue": self.msg_queue,
                "dials": self.dial_manager.get_dials(),
                "select_button": self.button_manager.select_button,
                "header_text": self.mode_manager.get_header_text(),
            }
        except Exception as e:
            showlog.error(f"[APP] Error getting UI context: {e}")
            return {}
    
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
                ui_mode = self.mode_manager.get_current_mode()
                render_start = None
                if ui_mode == "drumbo":
                    import time
                    render_start = time.time()
                
                self._render()
                
                if ui_mode == "drumbo" and render_start:
                    render_time = (time.time() - render_start) * 1000
                    showlog.debug(f"*[APP] drumbo render took {render_time:.2f}ms")
                
                # Control frame rate
                in_burst = self.dirty_rect_manager.is_in_burst()
                target_fps = self.frame_controller.get_target_fps(ui_mode, in_burst)
                
                # DEBUG: Log FPS for vibrato
                if ui_mode == "vibrato" and in_burst:
                    showlog.debug(f"[FPS DEBUG] vibrato: in_burst={in_burst}, target_fps={target_fps}")
                
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
                    
                    # Check if any widgets are dirty after event handling (vibrato, tremolo, etc.)
                    if hasattr(page.get("module"), "get_dirty_widgets"):
                        module = page["module"]
                        dirty_widgets = module.get_dirty_widgets()
                        if dirty_widgets:
                            self.dirty_rect_manager.start_burst()
                            
                except Exception as e:
                    showlog.error(f"[APP] Event handling error for {ui_mode}: {e}")
            elif page:
                showlog.warn(f"[APP] Page {ui_mode} has no handle_event method")
            else:
                showlog.warn(f"[APP] Unknown page mode: {ui_mode}")
    
    def _update(self):
        """Update application state each frame (lightweight - messages processed async)."""
        # Update header animation
        showheader.update()
        
        # Update widget animations EVERY FRAME (not just when in burst mode)
        # This ensures smooth animation playback at full framerate
        ui_mode = self.mode_manager.get_current_mode()
        page_info = self.page_registry.get(ui_mode)
        if page_info and hasattr(page_info.get("module"), "get_all_widgets"):
            module = page_info["module"]
            for widget in module.get_all_widgets():
                if hasattr(widget, "update_animation"):
                    widget.update_animation()
        
        # Optional: Monitor queue backlog for debugging with rolling average
        if cfg.DEBUG and hasattr(self.msg_queue, 'qsize'):
            backlog = self.msg_queue.qsize()
            
            # Calculate rolling average for smoother display (90% old, 10% new)
            if not hasattr(self, '_avg_backlog'):
                self._avg_backlog = backlog
            else:
                self._avg_backlog = (self._avg_backlog * 0.9) + (backlog * 0.1)
            
            # Warn if sustained high backlog
            if self._avg_backlog > 100:
                showlog.warn(f"[ASYNC] Queue backlog: {int(self._avg_backlog)} (current: {backlog})")
        
        # Note: Message processing now happens in background thread
        # The async loop in MessageQueueProcessor handles all messages at ~100Hz
    
    def _render(self):
        """Render the current frame."""
        # Skip rendering for modes currently transitioning to prevent flicker
        # Other modes can still render (e.g., overlays, background animations)
        ui_mode = self.mode_manager.get_current_mode()
        if self.mode_manager.is_mode_blocked(ui_mode):
            if self._last_render_path != "blocked":
                showlog.debug(f"*[RENDER_FLOW] ui_mode={ui_mode} path=blocked")
                self._last_render_path = "blocked"
            return
        
        offset_y = showheader.get_offset()
        
        # Check if any widgets are dirty (including custom widgets with animations)
        page_info = self.page_registry.get(ui_mode)
        if page_info and hasattr(page_info.get("module"), "get_dirty_widgets"):
            module = page_info["module"]
            dirty_widgets = module.get_dirty_widgets()
            if dirty_widgets:
                showlog.verbose(f"[APP] Found {len(dirty_widgets)} dirty widgets before render - starting burst")
                self.dirty_rect_manager.start_burst()
        
        in_burst = self.dirty_rect_manager.is_in_burst()
        
        # Check if we need a full frame
        need_full = (
            self.frame_controller.needs_full_frame() or
            self.mode_manager.needs_full_frame()
        )
        
        # DEBUG: Log why we're doing full frames
        if need_full and ui_mode == "dials":
            frame_ctrl_needs = self.frame_controller.needs_full_frame()
            mode_mgr_needs = self.mode_manager.needs_full_frame()
            showlog.verbose(f"[RENDER DEBUG] need_full=True: frame_controller={frame_ctrl_needs}, mode_manager={mode_mgr_needs}")
        
        # Check if header is animating (if method exists)
        try:
            if hasattr(showheader, 'is_animating') and showheader.is_animating():
                need_full = True
                if ui_mode == "dials":
                    showlog.debug(f"[RENDER DEBUG] need_full=True: header is animating")
        except Exception:
            pass
        
        # Check if this mode is excluded from dirty rect optimization
        exclude_dirty = getattr(cfg, "EXCLUDE_DIRTY", ())
        can_use_dirty = ui_mode not in exclude_dirty
        
        def _log_render_path(label: str):
            if self._last_render_path != label:
                showlog.debug(
                    f"*[RENDER_FLOW] ui_mode={ui_mode} path={label} in_burst={in_burst} need_full={need_full}"
                )
                self._last_render_path = label

        if can_use_dirty and not need_full and in_burst:
            _log_render_path("dirty-burst")
            # TURBO mode - only redraw changed dials + log bar (dirty rect optimization)
            self._render_dirty_dials(offset_y)
        elif can_use_dirty and not need_full and not in_burst:
            # Check if there are any dirty dials/widgets to update
            has_dirty = False
            
            # Check module-based pages
            page_info = self.page_registry.get(ui_mode)
            if page_info and hasattr(page_info.get("module"), "get_dirty_widgets"):
                try:
                    module = page_info["module"]
                    dirty_widgets = module.get_dirty_widgets()
                    has_dirty = len(dirty_widgets) > 0
                except Exception:
                    pass
            else:
                # Check legacy dials
                dials = self.dial_manager.get_dials()
                for dial in dials:
                    if hasattr(dial, 'dirty') and dial.dirty:
                        has_dirty = True
                        break
            
            if has_dirty:
                _log_render_path("dirty-once")
                # Render dirty dials even outside burst
                self._render_dirty_dials(offset_y)
            else:
                _log_render_path("idle")
                # Idle - only refresh log bar
                fps = self.frame_controller.get_fps()
                log_rect = self.renderer.draw_log_bar_only(fps)
                if log_rect:
                    self.dirty_rect_manager.mark_dirty(log_rect)
                self.dirty_rect_manager.present_dirty(force_full=False)
        else:
            _log_render_path("full")
            # Full frame draw (either excluded from dirty rects or needs full redraw)
            self._draw_full_frame(offset_y)
            
            # Optional debug overlay
            if cfg.DEBUG_OVERLAY:
                self._draw_debug_overlay()
            
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
    
    def _draw_debug_overlay(self):
        """Draw debug performance overlay (development mode)."""
        try:
            from rendering.debug_overlay import draw_overlay
            fps = self.frame_controller.get_fps()
            
            # Use rolling average for smoother queue display
            if hasattr(self, '_avg_backlog'):
                queue_size = int(self._avg_backlog)
            else:
                queue_size = self.msg_queue.qsize() if hasattr(self.msg_queue, 'qsize') else 0
            
            mode = cfg.ACTIVE_PROFILE if hasattr(cfg, 'ACTIVE_PROFILE') else "production"
            draw_overlay(self.screen, fps, queue_size, mode)
        except Exception as e:
            showlog.warn(f"[APP] Debug overlay error: {e}")
    
    def _render_dirty_dials(self, offset_y: int):
        """
        Render only the dials/widgets that changed (burst/turbo mode).
        Uses dirty rect optimization for smooth 100+ FPS dial updates.
        """
        ui_mode = self.mode_manager.get_current_mode()
        
        # Check if this is a module-based page with dirty rect support
        page_info = self.page_registry.get(ui_mode)
        if page_info and hasattr(page_info.get("module"), "redraw_dirty_widgets"):
            # New module-based approach (vibrato, tremolo, etc.)
            module = page_info["module"]
            
            # Update any animations BEFORE drawing - check ALL widgets, not just dirty ones
            # Animation updates need to happen every frame to maintain smooth playback
            if hasattr(module, "get_all_widgets"):
                for widget in module.get_all_widgets():
                    if hasattr(widget, "update_animation"):
                        widget.update_animation()
            elif hasattr(module, "get_dirty_widgets"):
                # Fallback to dirty widgets if get_all_widgets not available
                for widget in module.get_dirty_widgets():
                    if hasattr(widget, "update_animation"):
                        widget.update_animation()
            
            try:
                dirty_rects = module.redraw_dirty_widgets(self.screen, offset_y=offset_y)
                for rect in dirty_rects:
                    self.dirty_rect_manager.mark_dirty(rect)
            except Exception as e:
                showlog.warn(f"[APP] Module dirty redraw failed for {ui_mode}: {e}")
        else:
            # Legacy dials page approach
            from pages import page_dials
            import dialhandlers
            
            dials = self.dial_manager.get_dials()
            device_name = getattr(dialhandlers, "current_device_name", None)
            
            is_page_muted = False
            try:
                current_pid = getattr(dialhandlers, "current_page_id", "01")
                mute_states = dialhandlers.get_page_mute_states(device_name)
                is_page_muted = mute_states.get(current_pid, False)
            except Exception as e:
                showlog.debug(f"[APP] Mute state check failed: {e}")
            
            # Redraw each dial that changed
            for dial in dials:
                if hasattr(dial, 'dirty') and dial.dirty:
                    showlog.info(f"*[APP] Redrawing dirty dial {dial.id}, value={getattr(dial, 'value', None)}, angle={getattr(dial, 'angle', None)}")
                    try:
                        rect = page_dials.redraw_single_dial(
                            self.screen, dial, offset_y=offset_y,
                            device_name=device_name, is_page_muted=is_page_muted,
                            update_label=True, force_label=False
                        )
                        showlog.error(f"[APP] redraw_single_dial returned rect={rect}")
                        if rect:
                            self.dirty_rect_manager.mark_dirty(rect)
                        dial.dirty = False
                    except Exception as e:
                        showlog.warn(f"[APP] Dirty dial redraw failed for dial {dial.id}: {e}")
        
        # Update log bar
        fps = self.frame_controller.get_fps()
        log_rect = self.renderer.draw_log_bar_only(fps)
        if log_rect:
            self.dirty_rect_manager.mark_dirty(log_rect)
        
        # Debug overlay: Draw magenta boxes around dirty regions
        self.dirty_rect_manager.debug_overlay(self.screen)
        
        self.dirty_rect_manager.present_dirty(force_full=False)
    
    # Message callback handlers
    
    def _handle_dial_update(self, dial_id: int, value: int, ui_context: dict):
        """Handle dial value update message."""
        ui_mode = self.mode_manager.get_current_mode()
        
        showlog.debug(f"*[APP] _handle_dial_update(dial_id={dial_id}, value={value}), ui_mode={ui_mode}")
        
        # Check if this is a module-based page
        page_info = self.page_registry.get(ui_mode)
        showlog.debug(f"*[APP] page_info={page_info is not None}, has module={hasattr(page_info.get('module') if page_info else None, 'handle_hw_dial')}")
        
        if page_info and hasattr(page_info.get("module"), "handle_hw_dial"):
            # Module-based page (vibrato, tremolo, etc.)
            module = page_info["module"]
            showlog.debug(f"*[APP] Routing to module {module}")
            try:
                handled = module.handle_hw_dial(dial_id, value)
                showlog.debug(f"*[APP] Module handled={handled}")
                if handled:
                    self.dirty_rect_manager.start_burst()
                    return
            except Exception as e:
                showlog.warn(f"[APP] Module dial update failed for {ui_mode}: {e}")
        else:
            showlog.debug(f"*[APP] Not a module page, using legacy dial system")
        
        # Legacy dials page approach
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
            raw_val = msg[1] if len(msg) > 1 else 2

            def _seconds_to_frames(seconds: float) -> int:
                ui_mode = self.mode_manager.get_current_mode()
                fps = max(self.frame_controller.get_target_fps(ui_mode, False), 1)
                return int(max(round(seconds * fps), 1))

            if isinstance(raw_val, dict):
                frames = int(raw_val.get("frames", 0))
                if frames <= 0 and "seconds" in raw_val:
                    frames = _seconds_to_frames(float(raw_val["seconds"]))
            elif isinstance(raw_val, str):
                trimmed = raw_val.strip().lower()
                if trimmed.endswith("s"):
                    frames = _seconds_to_frames(float(trimmed[:-1] or 0))
                else:
                    frames = int(float(trimmed))
            elif isinstance(raw_val, int):
                frames = raw_val
            elif isinstance(raw_val, float):
                if raw_val.is_integer():
                    frames = int(raw_val)
                else:
                    frames = _seconds_to_frames(raw_val)
            else:
                frames = int(float(raw_val))

            frames = max(frames, 1)
            self.frame_controller.request_full_frames(frames)
            showlog.debug(f"[APP] Forced redraw for {frames} frame(s) (raw={raw_val!r})")
        except Exception as e:
            showlog.warn(f"[APP] Force redraw failed: {e}")
    
    def _handle_remote_char(self, msg: tuple, ui_context: dict):
        """Handle remote character input."""
        _, char = msg
        ui_mode = ui_context.get("ui_mode")
        
        showlog.debug(f"[APP._handle_remote_char] char='{char}', ui_mode='{ui_mode}'")
        
        # Check if this is a module_base page (vibrato, vk8m, ascii_animator, etc.)
        # First try to import module_base and check if preset UI is active
        try:
            from pages import module_base
            if hasattr(module_base, "is_preset_ui_active") and module_base.is_preset_ui_active():
                showlog.debug(f"[APP._handle_remote_char] Preset UI is active, routing to module_base")
                module_base.handle_remote_input(char)
                return
        except Exception as e:
            showlog.debug(f"[APP._handle_remote_char] Could not check module_base: {e}")
        
        # Legacy: specific page handlers
        if ui_mode == "patchbay":
            showlog.debug(f"[APP._handle_remote_char] Patchbay mode, routing to patchbay")
            from pages import patchbay
            patchbay.handle_remote_input(char)
        else:
            showlog.debug(f"[APP._handle_remote_char] Unhandled ui_mode '{ui_mode}'")
    
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
        showlog.info("[EXIT] Cleaning up...")
        
        # Clean up all registered services (MIDI, CV, Network, etc.)
        if hasattr(self, 'services'):
            showlog.info("[EXIT] Cleaning up services...")
            self.services.cleanup()
        
        # Stop background message processing thread gracefully
        if hasattr(self, 'msg_processor') and self.msg_processor:
            self.msg_processor.stop_async_loop()
            
            # Wait for thread to terminate
            if getattr(self.msg_processor, '_thread', None) and self.msg_processor._thread.is_alive():
                self.msg_processor._thread.join(timeout=1.0)
                if not self.msg_processor._thread.is_alive():
                    showlog.info("[ASYNC] Message processor stopped gracefully")
                else:
                    showlog.warn("[ASYNC] Message processor timeout (forced exit)")
        
        # Close display and exit
        if self.display_manager:
            self.display_manager.cleanup()
        
        showlog.info("[EXIT] All services stopped")
        sys.exit()
