# midiserver.py
import mido
import showlog
import config as cfg
# --- Device Drivers ---
import quadraverb_driver as qv
import traceback

outport = None
inport = None

# --- Dynamic CC map for 8 dials, based on config ---
# If DIAL_CC_START = 30 -> [30..37]; if 70 -> [70..77]
cc_map = list(range(cfg.DIAL_CC_START, cfg.DIAL_CC_START + 8))

# Callbacks set by UIif msg.type == "control_change"
dial_handler = None   # function(dial_id, value)
sysex_handler = None  # function(device, layer, dial, value, cc_num)


# -------------------------------------------------------
# MIDI Initialization
# -------------------------------------------------------

def init(dial_cb=None, sysex_cb=None):
    """Initialize MIDI I/O: open USB MS1x1 for out, plus a default input."""
    global outport, inport, dial_handler, sysex_handler

    dial_handler = dial_cb
    sysex_handler = sysex_cb

    try:
        ports_out = mido.get_output_names()
        ports_in = mido.get_input_names()
        showlog.debug(f"Found MIDI OUT ports: {ports_out}")
        showlog.debug(f"Found MIDI IN ports: {ports_in}")

        # --- Open output ---
        for name in ports_out:
            if "USB MS1x1 MIDI Interface" in name:
                outport = mido.open_output(name)
                showlog.debug(f"MIDI out → {name}")
                break
        if outport is None:
            showlog.warn("⚠️ USB MS1x1 output not found")

        # --- Open input ---
        for name in ports_in:
            if "USB MS1x1 MIDI Interface" in name:
                inport = mido.open_input(name, callback=_on_midi_in)
                showlog.debug(f"MIDI in ← {name}")
                break

    except Exception as e:
        showlog.error(f"[MIDI INIT error] {e}")

    start_send_worker()


# -------------------------------------------------------
# MIDI Message Sending
# -------------------------------------------------------

def send_cc(target_type, index, value):
    """
    Send a MIDI CC message.

    target_type: "dial" or "button"
    index: 0-based index (0..7 for dials, 0..4 for buttons)
    value: 0–127
    """
    try:
        if outport is None:
            showlog.error("No outport")
            return

        if target_type == "dial":
            cc_num = cfg.DIAL_CC_START + index
        elif target_type == "button":
            cc_num = cfg.BUTTON_CC_START + index
        else:
            showlog.warn(f"Unknown target_type '{target_type}'")
            return

        msg = mido.Message(
            "control_change",
            control=cc_num,
            value=value,
            channel=cfg.CC_CHANNEL
        )
        outport.send(msg)

    except Exception as e:
        showlog.error(f"send_cc error: {e}")


def send_cc_raw(cc_num, value):
    """Send a specific CC number directly (for buttons)."""
    try:
        if outport is None:
            return
        msg = mido.Message(
            "control_change",
            control=cc_num,
            value=value,
            channel=cfg.CC_CHANNEL
        )
        outport.send(msg)
    except Exception as e:
        showlog.error(f"send_cc_raw error: {e}")


def send_bytes(data):
    """Send a raw 3-byte MIDI message (e.g. for announce)."""
    try:
        if outport is None:
            showlog.error("No active outport for send_bytes")
            return

        # Force conversion to bytes for safety
        if isinstance(data, list):
            data = bytes(data)

        showlog.debug(f"Raw bytes about to send: {[hex(b) for b in data]}")

        msg = mido.Message.from_bytes(data)
        showlog.debug(f"Mido interpreted message: {msg}")

        outport.send(msg)
        status = data[0]
        ch = (status & 0x0F) + 1
        msg_type = status & 0xF0
        kind = "NoteOn" if msg_type == 0x90 else f"Status {status:02X}"
        showlog.debug(f"Send_bytes → {kind} ch{ch} {data[1]:02X} {data[2]:02X}")

    except Exception as e:
        showlog.error(f"send_bytes error: {e}")



def send_program_change(program_num, channel=None):
    """Send a MIDI Program Change message on the specified channel (or cfg.CC_CHANNEL)."""
    showlog.debug(f"[DEBUG] ProgramChange called from:\n{''.join(traceback.format_stack(limit=3))}")
    try:
        if outport is None:
            return

        ch = 0 if channel is None else channel
        msg = mido.Message("program_change", program=program_num, channel=ch)
        outport.send(msg)
        showlog.debug(f"Program Change → ch{ch+1} prog={program_num}")

    except Exception as e:
        showlog.error(f"send_program_change error: {e}")


# -------------------------------------------------------
# Incoming MIDI Handler
# -------------------------------------------------------

def _on_midi_in(msg):
    """Handle incoming MIDI (CC or SysEx)."""
    try:
        if msg.type == "control_change":
            cc_num = msg.control

            # Map CC → dial ID (1..8)
            if cc_num in cc_map:
                dial_index = cc_map.index(cc_num)   # 0..7
                dial_id = dial_index + 1            # 1..8 for dialhandlers
                if dial_handler:
                    dial_handler(dial_id, msg.value)

        elif msg.type == "sysex":
            data = list(msg.data)
            showlog.debug(f"[MIDI IN] SYSEX RAW: {data}")
            if len(data) >= 6 and data[0] == 0x7D:
                # F0 7D <device> <layer> <dial> <value> <ccnum> F7
                device, layer, dial_id, value, cc_in = data[1:6]

                # --- Normalize device name / code before dispatch ---
                if isinstance(device, str):
                    device = device.strip().upper()

                if sysex_handler:
                    sysex_handler(device, layer, dial_id, value, cc_in)

    except Exception as e:
        hname = "<unset>"
        showlog.error(f"[MIDI IN] {e}")
        showlog.debug(f"[MIDI IN ctx] msg={msg!r}, handler={hname}, cc_map={cc_map}")


# -------------------------------------------------------
# Device Routing (SysEx + CC)
# -------------------------------------------------------

def send_device_message(device_name, dial_index, value, param_range=None,
                        section_id=1, page_offset=0, dial_obj=None, cc_override=None):
    """
    Route an outgoing control message to the correct device driver.

    device_name : str   e.g. "Quadraverb"
    dial_index  : int   1–8 (dial number)
    value       : int   0–127
    param_range : any   optional range for scaling
    section_id  : int   current layer/page (e.g. 1=Reverb)
    """
    if page_offset is None:
        showlog.warn(f"Missing page_offset for dial {dial_index}, defaulting to 0")
        page_offset = 0

    try:
        # --- determine CC number (with optional override) ---
        if cc_override is not None:
            cc_num = cc_override
        else:
            cc_num = cfg.DIAL_CC_START + (dial_index - 1)

        if outport is None:
            showlog.warn("[MIDI ROUTER] No MIDI outport available")
            return

        if device_name.lower() == "quadraverb":
            # --- SysEx path ---
            qv.send_sysex(
                out_port=outport,
                section_id=section_id,
                dial_index=dial_index,
                dial_value=value,
                parameter_range=param_range,
                page_offset=page_offset,
                dial_obj=None      # placeholder; can be passed later
            )
            showlog.debug(f"[MIDI OUT] QV Sysex → Page {page_offset}, Dial {dial_index}, Val {value}")

        else:
            # --- Fallback: send plain CC (supports CC override) ---
            msg = mido.Message(
                "control_change",
                control=cc_num,
                value=value,
                channel=cfg.CC_CHANNEL
            )
            outport.send(msg)
            showlog.debug(f"[MIDI OUT] CC → {device_name} CC={cc_num} (Dial {dial_index}) = {value}")

    except Exception as e:
        showlog.error(f"[MIDI ROUTER error] {e}")





# ---------------------------------------------------------------------
# Background MIDI Send Worker (non-blocking)
# ---------------------------------------------------------------------
import threading, queue, time

_send_queue = queue.Queue(maxsize=256)
_send_thread = None
_running_send_worker = False

def _midi_send_worker():
    """Continuously send queued MIDI messages in the background."""
    showlog.verbose("Send worker thread started loop.")

    global _running_send_worker
    while _running_send_worker:
        try:
            item = _send_queue.get(timeout=0.1)
        except queue.Empty:
            continue
        try:
            showlog.debug(f"Worker sending → {item.get('device_name')} dial={item.get('dial_index')} value={item.get('value')}")
            send_device_message(**item)   # call the real blocking send
            showlog.verbose(f"Worker finished send for dial {item.get('dial_index')}")

        except Exception as e:
            showlog.error(f"send_worker failed: {e}")
        finally:
            _send_queue.task_done()
        time.sleep(0.001)  # tiny yield to avoid 100% CPU spin

def start_send_worker():
    """Launch the background thread once at init()."""
    showlog.verbose("start_send_worker() invoked.")

    global _send_thread, _running_send_worker
    if _send_thread and _send_thread.is_alive():
        return
    _running_send_worker = True
    _send_thread = threading.Thread(target=_midi_send_worker,
                                    name="MIDI-SendWorker",
                                    daemon=True)
    _send_thread.start()
    showlog.debug("Background send worker started.")

def stop_send_worker():
    """Graceful stop (optional on exit)."""
    global _running_send_worker
    _running_send_worker = False

def enqueue_device_message(**kwargs):
    """Non-blocking enqueue version of send_device_message()."""
    try:
        _send_queue.put_nowait(kwargs)
    except queue.Full:
        showlog.warn("send queue full — dropping message")











# -------------------------------------------------------
# Send full preset values to a device
# -------------------------------------------------------

def send_preset_values(device_name, section_name, values):
    """
    Send an entire preset (8 dial values) to the target device.
    Looks up device + section in devices.DEVICE_DB and sends each dial value
    using midiserver.send_device_message().
    """
    import devices, showlog, time

    try:
        # --- Find device by name ---
        device = devices.get_by_name(device_name)
        if not device:
            showlog.warn(f"[PRESET SEND] Device '{device_name}' not found.")
            return

        # --- Find matching page by its "name" (e.g. "Reverb") ---
        page_id = None
        for pid, page in device.get("pages", {}).items():
            if page.get("name", "").lower() == section_name.lower():
                page_id = pid
                break

        # Fallback: if module info lacks this section, try JSON device definition
        if not page_id:
            try:
                dev_uc = str(device_name).strip().upper()
                for dev in devices.DEVICE_DB.values():
                    if dev.get("name", "").strip().upper() == dev_uc:
                        for pid, page in dev.get("pages", {}).items():
                            if page.get("name", "").lower() == section_name.lower():
                                device = dev
                                page_id = pid
                                break
                        break
            except Exception:
                pass

        if not page_id:
            showlog.warn(f"[PRESET SEND] Section '{section_name}' not found in {device_name}.")
            return

        page = device["pages"][page_id]
        dials = page.get("dials", {})

        # --- Send each dial’s value ---
        for i, (dial_key, dial_def) in enumerate(dials.items()):
            if i >= len(values):
                break

            val = int(values[i])
            param_range = dial_def.get("range", [0, 127])
            page_offset = dial_def.get("page", 0)
            section_id = int(page_id)  # Quadraverb section/page index

            # ✅ Use the same routing as live dials
            send_device_message(
                device_name=device_name,
                dial_index=i + 1,
                value=val,
                param_range=param_range,
                section_id=section_id,
                page_offset=page_offset,
                dial_obj=None
            )

            showlog.debug(f"[PRESET SEND] {dial_def['label']} = {val}")
            time.sleep(0.05)  # optional delay for hardware safety

        showlog.debug(f"[PRESET SEND] Sent preset '{section_name}' with {len(values)} values.")

    except Exception as e:
        showlog.error(f"[PRESET SEND] Failed to send preset: {e}")


# -------------------------------------------------------
# CV SERVER LINK (Pi Zero)
# -------------------------------------------------------
import socket

CV_HOST = "192.168.7.2"   # Pi Zero CV Server IP
CV_PORT = 5050            # same port — safe, different host

def send_cv(channel: int, value: float):
    """
    Send a voltage or normalized float (0.0–1.0) to the CV Server.
    Example: send_cv(1, 0.75)
    """
    try:
        msg = f"CH{channel} {value:.4f}\n"
        with socket.create_connection((CV_HOST, CV_PORT), timeout=0.3) as s:
            s.sendall(msg.encode("utf-8"))
        showlog.debug(f"[CV] Sent → {msg.strip()}")
    except Exception as e:
        showlog.warn(f"[CV] send_cv failed: {e}")
