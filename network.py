# /build/network.py — Pi3 version with showlog, fatal catch + throttling + local/remote toggle + de-garbler
import socket
import threading
import time
import traceback
import showlog
import string

# --- config import (safe) ---
try:
    import config as cfg
except Exception:
    class _Cfg: pass
    cfg = _Cfg()

# --- throttle config & state (define BEFORE logging) ---
THROTTLE_S = float(getattr(cfg, "LED_THROTTLE_DELAY", 0.0))

# Per-device throttle state
_th_lock = threading.Lock()
_th_last = {"DEV1": 0.0, "DEV2": 0.0}
_th_pending = {"DEV1": None, "DEV2": None}
_th_timer = {"DEV1": None, "DEV2": None}

# --- mode banner (safe now) ---
if getattr(cfg, "LED_IS_NETWORK", True):
    showlog.log(None, "[LED MODE] Network → Pico")
else:
    showlog.log(None, f"[LED MODE] Local (I2C), throttle={THROTTLE_S:.3f}s")

# -------------------------------------------------------
# Network config
# -------------------------------------------------------
HOST = "0.0.0.0"
PORT = 5050

# Pico destination
PICO_HOST = "192.168.4.1"
PICO_PORT = 5050

_last_device_sent = None  # remembers the last synth name sent to DEV1


# -------------------------------------------------------
# Message sanitizer / de-garbler
# -------------------------------------------------------
def _sanitize_text(txt: str) -> str:
    """Remove non-printable / glitch characters before display."""
    if not txt:
        return ""
    # Keep only printable ASCII + minimal punctuation
    allowed = string.ascii_letters + string.digits + string.punctuation + " "
    clean = "".join(ch for ch in txt if ch in allowed)
    # Replace double dots or odd spacing artifacts
    clean = clean.replace("..", ".").replace("  ", " ").strip()
    return clean

_send_lock = threading.Lock()
# -------------------------------------------------------
# Throttled LED/LCD routing
# -------------------------------------------------------
def _send_now(msg: str):
    """Actually route the message (local I²C or Pico)."""
    if not msg:
        return
    with _send_lock:
        clean = _sanitize_text(msg.strip())

        # Local (I²C) path
        if not getattr(cfg, "LED_IS_NETWORK", True):
            try:
                from get_patch_and_send_local import output_msg as local_output_msg
            except Exception as ie:
                showlog.error(f"[FATAL] Local display module not available: {ie}")
                return
            try:
                local_output_msg(clean)  # expects "DEVx TXT:..."
                showlog.verbose(f"[LED] (local) {clean}")
            except Exception as le:
                showlog.error(f"[FATAL] Local display error: {type(le).__name__}: {le}")
            return

        # Network (Pico) path
        try:
            showlog.log(None, f"[DEBUG] Connecting to Pico {PICO_HOST}:{PICO_PORT} ...")
            with socket.create_connection((PICO_HOST, PICO_PORT), timeout=1.0) as s:
                s.sendall((_sanitize_text(clean) + "\n").encode("utf-8"))
            showlog.verbose(f"[LED] → Pico {clean}")
        except Exception as e:
            showlog.error(f"[FATAL] {type(e).__name__}: {e}")


def _flush_dev(dev_key: str):
    """Timer callback: send newest pending message for this device."""
    with _th_lock:
        msg = _th_pending.get(dev_key)
        _th_pending[dev_key] = None
        _th_timer[dev_key] = None
    if msg:
        _send_now(msg)
        with _th_lock:
            _th_last[dev_key] = time.monotonic()


def send_led_line(msg: str):
    """
    Route a 'DEVx TXT:...' line with optional throttle.
    DEV1 and DEV2 are throttled independently by cfg.LED_THROTTLE_DELAY.
    """
    if not msg:
        return

    # Decide which device bucket to throttle on

    try:
        dev_key = msg.split(None, 1)[0].upper()
    except Exception:
        dev_key = "DEV1"
    if dev_key not in ("DEV1", "DEV2"):
        dev_key = "DEV1"

    if THROTTLE_S <= 0:
        _send_now(msg)
        return

    now = time.monotonic()
    with _th_lock:
        gap = now - _th_last.get(dev_key, 0.0)
        if gap >= THROTTLE_S and _th_timer.get(dev_key) is None:
            _th_last[dev_key] = now
            immediate = True
        else:
            _th_pending[dev_key] = msg
            if _th_timer.get(dev_key) is None:
                t = threading.Timer(THROTTLE_S, _flush_dev, args=(dev_key,))
                t.daemon = True
                _th_timer[dev_key] = t
                t.start()
            immediate = False

    if immediate:
        _send_now(msg)


# -------------------------------------------------------
# (Legacy) direct network send — kept for completeness
# -------------------------------------------------------
def forward_to_pico(msg: str):
    """Direct network send to Pico (unused when throttling is enabled)."""
    try:
        clean = _sanitize_text((msg or "").strip())
        showlog.log(None, f"[DEBUG] forward_to_pico called with → {clean!r}")
        if not clean:
            return
        showlog.log(None, f"[DEBUG] Connecting to Pico {PICO_HOST}:{PICO_PORT} ...")
        with socket.create_connection((PICO_HOST, PICO_PORT), timeout=1.0) as s:
            s.sendall((clean + "\n").encode("utf-8"))
        showlog.log(None, f"[LED] → Pico {clean}")
    except Exception as e:
        showlog.log(None, f"[FATAL] {type(e).__name__}: {e}")


# -------------------------------------------------------
# TCP Server (PC → Pi3)
# -------------------------------------------------------
def tcp_server(msg_queue):
    """Receives lines from the PC and forwards display text to Pico or local I²C."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    for attempt in range(10):
        try:
            sock.bind((HOST, PORT))
            showlog.log(None, f"[Network] Bound to {HOST}:{PORT}")
            break
        except OSError as e:
            if getattr(e, "errno", None) == 98:
                showlog.log(None, f"[Network] Port {PORT} busy, retrying... ({attempt+1}/10)")
                time.sleep(2)
            else:
                raise
    else:
        raise SystemExit(f"[Network] Could not bind port {PORT}")

    sock.listen(5)
    showlog.log(None, "[Network] Listening for connections...")

    try:
        while True:
            conn, addr = sock.accept()
            showlog.log(None, f"[Network] Connection from {addr}")

            def handle_client(c):
                try:
                    with c:
                        data = c.recv(1024)
                        if not data:
                            return
                        # Tiny indicator that something arrived on 5050
                        try:
                            showlog.debug(f"[Network] RX {len(data)}B")
                        except Exception:
                            pass
                        text = data.decode("utf-8", "ignore").strip()
                        for line in text.splitlines():
                            line = _sanitize_text(line.strip())
                            if not line:
                                continue
                            showlog.debug(f"raw line repr → {repr(line)}")

                            if line.startswith("[PRESET_SELECT]") or line.startswith("[PATCH_SELECT]"):
                                core = line.split("]", 1)[1].strip()
                                if "|" in core:
                                    patch = core.split("|", 1)[1].strip()
                                    if patch:
                                        pico_msg = f"DEV2 TXT:{_sanitize_text(patch)}"
                                        showlog.debug(f"Sending → {pico_msg}")
                                        send_led_line(pico_msg)
                                        showlog.verbose(f"DEV2 → {patch}")
                                continue

                            if line.upper().startswith("DEV") and "TXT:" in line:
                                send_led_line(line)
                                continue

                            if "|" in line and "." in line:
                                global _last_device_sent
                                try:
                                    device, patch = line.split("|", 1)
                                    device = _sanitize_text(device.strip())
                                    patch = _sanitize_text(patch.strip())

                                    if device and device != _last_device_sent:
                                        dev1_msg = f"DEV1 TXT:{device}"
                                        send_led_line(dev1_msg)
                                        _last_device_sent = device

                                    if patch:
                                        dev2_msg = f"DEV2 TXT:{patch}"
                                        send_led_line(dev2_msg)

                                    msg = f"[PATCH_SELECT] {device}|{patch}"
                                    msg_queue.put(msg)
                                except Exception as e:
                                    showlog.error(f"[FATAL] {type(e).__name__}: {e}")
                                continue

                            msg_queue.put(line)
                            showlog.debug(f"[Network] Queued TXT → {line}")

                except Exception as exc:
                    showlog.error(f"[FATAL] {type(exc).__name__}: {exc}")
                    print(traceback.format_exc(limit=2))

            threading.Thread(target=handle_client, args=(conn,), daemon=True).start()

    except Exception as e:
        showlog.error(f"[FATAL] {type(e).__name__}: {e}")
    finally:
        sock.close()
        showlog.info("[Network] Socket closed.")
