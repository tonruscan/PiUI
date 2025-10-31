# /build/pages/mixer.py
import pygame
import showlog
import devices, dialhandlers
import config as cfg
from helper import hex_to_rgb
from assets.fader import Fader
import quadraverb_driver as qv

# -------------------------------------------------------------------
# Globals
# -------------------------------------------------------------------
_faders = []
_initialized = False


# -------------------------------------------------------------------
# Draw + Lazy Init
# -------------------------------------------------------------------
def draw_ui(screen, offset_y=0):
    """Draw the Quadraverb mixer page (4 faders, dynamically from devices.json)."""
    global _initialized, _faders

    # --- One-time init -------------------------------------------------------
    if not _initialized:
        _initialized = True
        _faders.clear()

        dev = devices.get(dialhandlers.current_device_id)
        if not dev:
            showlog.warn("No active device loaded")
            return

        page_info = dev["pages"].get("05", {})
        faders_def = page_info.get("faders", {})
        width = screen.get_width()
        count = len(faders_def)

        # Spacing & geometry from config (with safe fallbacks)
        spacing   = int(getattr(cfg, "MIXER_SPACING", max(1, width // (count + 1))))
        y         = int(getattr(cfg, "MIXER_TOP_MARGIN", 150)) + int(offset_y)
        height    = int(getattr(cfg, "MIXER_HEIGHT", 220))
        fader_w   = int(getattr(cfg, "MIXER_WIDTH", 28))

        for i, fdef in enumerate(faders_def.values()):
            label    = fdef.get("label", f"Fader {i+1}")
            init_val = fdef.get("init", 64)

            # Center each fader on its spacing column; x is LEFT edge for Fader()
            fx = (i + 1) * spacing - (fader_w // 2)

            f = Fader(
                x=fx,
                y=y,
                height=height,
                width=fader_w,
                label=label,
                initial=init_val,
                on_change=None
            )
            f.section_id = int(fdef.get("sysex_section", i + 1))
            _faders.append(f)
            showlog.verbose(f"Created fader {label} section={f.section_id}")

        showlog.debug(f"Initialized with {len(_faders)} faders")

    # --- Draw faders ---------------------------------------------------------
    for f in _faders:
        f.draw(screen)

    # --- NEW: partial display update for smoother performance ----------------
    try:
        rect = pygame.Rect(
            0,
            int(getattr(cfg, "MIXER_TOP_MARGIN", 150)),
            screen.get_width(),
            int(getattr(cfg, "MIXER_HEIGHT", 220)) + 60
        )
        pygame.display.update(rect)
    except Exception:
        pass



# -------------------------------------------------------------------
# Event handler (same as before)
# -------------------------------------------------------------------
def handle_event(event, msg_queue):
    """Handle touchscreen/mouse events for the mixer page with throttled MIDI sends."""
    global _faders
    import time

    # Create per-fader caches on first run
    if not hasattr(handle_event, "_last_send_time"):
        handle_event._last_send_time = {}
        handle_event._last_sent_value = {}

    THROTTLE = float(getattr(cfg, "MIXER_MIDI_THROTTLE", 0.05))
    now = time.time()

    if event.type == pygame.MOUSEBUTTONDOWN and hasattr(event, "pos"):
        for f in _faders:
            if f.rect.collidepoint(event.pos):
                f.dragging = True
                msg_queue.put(f"[MIXER] Fader {f.label} touched")

    elif event.type == pygame.MOUSEBUTTONUP and hasattr(event, "pos"):
        for f in _faders:
            if getattr(f, "dragging", False):
                f.dragging = False
                msg_queue.put(f"[MIXER] Fader {f.label} released")

    elif event.type == pygame.MOUSEMOTION and hasattr(event, "pos"):
        for f in _faders:
            if getattr(f, "dragging", False):
                f.update_from_mouse(event.pos)

                # --- throttle & dedupe logic ---
                last_t = handle_event._last_send_time.get(f.label, 0)
                last_v = handle_event._last_sent_value.get(f.label)

                if (now - last_t) >= THROTTLE and f.value != last_v:
                    msg_queue.put(("mixer_value",
                                   {"section": f.section_id, "value": f.value}))
                    handle_event._last_send_time[f.label] = now
                    handle_event._last_sent_value[f.label] = f.value
