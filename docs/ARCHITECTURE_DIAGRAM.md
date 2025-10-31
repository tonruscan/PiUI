# UI Architecture Diagram

## 🏗️ Modular Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                          ui_new.py                              │
│                      (Entry Point - 50 lines)                   │
│                                                                  │
│  • Import crashguard                                            │
│  • Create UIApplication()                                       │
│  • app.initialize()                                             │
│  • app.run()                                                    │
│  • app.cleanup()                                                │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    core/app.py                                  │
│                    UIApplication                                │
│                                                                  │
│  Responsibilities:                                              │
│  • Initialize all subsystems                                    │
│  • Coordinate managers                                          │
│  • Run main event loop                                          │
│  • Handle application lifecycle                                 │
└────────────────┬───────┬───────┬───────┬────────────────────────┘
                 │       │       │       │
        ┌────────┘       │       │       └────────┐
        │                │       │                │
        ▼                ▼       ▼                ▼
┌──────────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐
│ core/        │  │managers/ │  │rendering/│  │initialization│
│ display.py   │  │          │  │          │  │              │
│              │  │          │  │          │  │              │
│ • Setup      │  │ • Dials  │  │• Render  │  │• Hardware    │
│ • Screen     │  │ • Buttons│  │• Dirty   │  │• Devices     │
│ • Cursor     │  │ • Modes  │  │• FPS     │  │• Registries  │
└──────────────┘  │ • Queue  │  └──────────┘  └──────────────┘
                  └──────────┘
                       │
                       ▼
              ┌──────────────┐
              │  handlers/   │
              │              │
              │ • Global     │
              │ • Dials      │
              │ • DeviceSelect│
              └──────────────┘
```

## 🔄 Data Flow

```
                    User Input (Mouse/Keyboard)
                              │
                              ▼
                    ┌─────────────────┐
                    │  Event Loop     │
                    │  (core/loop.py) │
                    └────────┬────────┘
                             │
                    ┌────────┴────────┐
                    │                 │
                    ▼                 ▼
          ┌──────────────┐   ┌──────────────┐
          │ Global       │   │ Page         │
          │ Handler      │   │ Handler      │
          └──────┬───────┘   └──────┬───────┘
                 │                  │
                 └────────┬─────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │ Message Queue   │
                 │   Processor     │
                 └────────┬────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
          ▼               ▼               ▼
    ┌─────────┐    ┌──────────┐    ┌─────────┐
    │ Manager │    │ Manager  │    │ Manager │
    │ Updates │    │ Updates  │    │ Updates │
    └────┬────┘    └────┬─────┘    └────┬────┘
         │              │               │
         └──────────────┼───────────────┘
                        │
                        ▼
                 ┌──────────────┐
                 │  Renderer    │
                 │  (Renderer)  │
                 └──────┬───────┘
                        │
                        ▼
                  Screen Update
```

## 📦 Module Dependencies

```
ui_new.py
  └── core/app.py
       ├── core/display.py
       ├── core/loop.py
       ├── managers/dial_manager.py
       ├── managers/button_manager.py
       ├── managers/mode_manager.py
       ├── managers/message_queue.py
       ├── rendering/renderer.py
       ├── rendering/dirty_rect.py
       ├── rendering/frame_control.py
       ├── initialization/hardware_init.py
       ├── initialization/device_loader.py
       ├── initialization/registry_init.py
       ├── handlers/global_handler.py
       ├── handlers/dials_handler.py
       └── handlers/device_select_handler.py
```

## 🎯 Responsibility Matrix

```
┌─────────────────────┬──────────────────────────────────────┐
│ Module              │ Responsibilities                     │
├─────────────────────┼──────────────────────────────────────┤
│ core/app.py         │ • Coordinate all subsystems          │
│                     │ • Application lifecycle              │
│                     │ • Main event loop                    │
├─────────────────────┼──────────────────────────────────────┤
│ core/display.py     │ • Pygame display setup               │
│                     │ • Screen management                  │
├─────────────────────┼──────────────────────────────────────┤
│ core/loop.py        │ • Event polling                      │
│                     │ • Frame timing                       │
├─────────────────────┼──────────────────────────────────────┤
│ managers/           │ • State management                   │
│   dial_manager.py   │ • Dial lifecycle                     │
│                     │ • CC mapping                         │
├─────────────────────┼──────────────────────────────────────┤
│ managers/           │ • Button selection                   │
│   button_manager.py │ • Behavior interpretation            │
│                     │ • Per-device memory                  │
├─────────────────────┼──────────────────────────────────────┤
│ managers/           │ • Page/mode switching                │
│   mode_manager.py   │ • Navigation history                 │
│                     │ • State persistence                  │
├─────────────────────┼──────────────────────────────────────┤
│ managers/           │ • Message processing                 │
│   message_queue.py  │ • Control routing                    │
│                     │ • Module loading                     │
├─────────────────────┼──────────────────────────────────────┤
│ rendering/          │ • Page drawing                       │
│   renderer.py       │ • Header/footer                      │
│                     │ • Frame presentation                 │
├─────────────────────┼──────────────────────────────────────┤
│ rendering/          │ • Dirty region tracking              │
│   dirty_rect.py     │ • Burst mode                         │
│                     │ • Optimized updates                  │
├─────────────────────┼──────────────────────────────────────┤
│ rendering/          │ • FPS targeting                      │
│   frame_control.py  │ • Frame timing                       │
│                     │ • Full frame requests                │
├─────────────────────┼──────────────────────────────────────┤
│ initialization/     │ • MIDI setup                         │
│   hardware_init.py  │ • CV setup                           │
│                     │ • Network setup                      │
├─────────────────────┼──────────────────────────────────────┤
│ initialization/     │ • Device loading                     │
│   device_loader.py  │ • Button behaviors                   │
│                     │ • CV calibration                     │
├─────────────────────┼──────────────────────────────────────┤
│ initialization/     │ • CC registry setup                  │
│   registry_init.py  │ • Entity registry setup              │
├─────────────────────┼──────────────────────────────────────┤
│ handlers/           │ • Back navigation                    │
│   global_handler.py │ • Exit button                        │
│                     │ • Header events                      │
├─────────────────────┼──────────────────────────────────────┤
│ handlers/           │ • Dial dragging                      │
│   dials_handler.py  │ • Button clicks                      │
│                     │ • Behavior handling                  │
├─────────────────────┼──────────────────────────────────────┤
│ handlers/           │ • Device selection                   │
│   device_select_    │ • Click handling                     │
│   handler.py        │                                      │
└─────────────────────┴──────────────────────────────────────┘
```

## 🔗 Integration Points

```
UIApplication
    │
    ├─► DisplayManager ──────► pygame.display
    │
    ├─► HardwareInitializer ─┬─► midiserver
    │                        ├─► cv_client
    │                        ├─► network
    │                        └─► remote_typing
    │
    ├─► DialManager ─────────► dialhandlers (existing)
    │
    ├─► ButtonManager
    │
    ├─► ModeManager ─────────┬─► navigator (existing)
    │                        └─► pages/* (existing)
    │
    ├─► MessageQueueProcessor ──► control/* (existing)
    │
    ├─► Renderer ────────────► pages/* (existing)
    │
    ├─► DirtyRectManager
    │
    ├─► FrameController
    │
    └─► GlobalEventHandler
```

## 🎨 State Management Flow

```
User Action
    │
    ▼
Event Handler
    │
    ▼
Message Queue ◄───────┐
    │                 │
    ▼                 │
MessageQueueProcessor │
    │                 │
    ▼                 │
Manager Update        │
    │                 │
    ▼                 │
State Change          │
    │                 │
    ▼                 │
Renderer ─────────────┘
    │      (feedback)
    ▼
Screen Update
```

## 🧪 Testing Strategy

```
Unit Tests
    │
    ├─► DialManager
    │   └─► test_rebuild_dials()
    │   └─► test_update_value()
    │
    ├─► ButtonManager
    │   └─► test_select_button()
    │   └─► test_device_memory()
    │
    ├─► ModeManager
    │   └─► test_switch_mode()
    │   └─► test_navigation()
    │
    └─► ... (all managers)

Integration Tests
    │
    ├─► UIApplication.initialize()
    ├─► Event routing
    ├─► Message processing
    └─► Full render cycle

End-to-End Tests
    │
    ├─► Device selection flow
    ├─► Dial interaction
    ├─► Page navigation
    └─► State persistence
```

---

**Legend:**
- `│ ▼ ─ ├ └` - Flow/connection
- `┌ ┐ └ ┘ │ ─` - Boxes/containers
- `►` - Direct dependency
- `◄` - Feedback/callback

