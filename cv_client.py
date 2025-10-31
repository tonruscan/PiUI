# /build/cv_client.py
# Persistent TCP client for the 10 V DAC server (port 5050)

import socket
import threading
import time
import queue
import showlog
import math

# -----------------------------------------------------------
# Glide manager (per-channel smoothing)
# -----------------------------------------------------------

class GlideChannel:
    def __init__(self, ch, send_func):
        self.ch = ch
        self._send_func = send_func
        self.current = 0
        self.target = 0
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        self.last_target = 0
        self.last_time = time.time()

    def _worker(self):
        """Internal thread: VERY fast glide - just a few steps to avoid clicks."""
        try:
            while self.running:
                with self.lock:
                    target = self.target
                    diff = target - self.current
                if diff == 0:
                    break

                # Much faster steps - we want to reach target quickly (in ~5-10ms total)
                dist = abs(diff)
                step = max(8, min(512, int(dist / 2)))  # Larger steps, faster convergence
                step *= 1 if diff > 0 else -1

                self.current += step
                val = int(round(self.current))

                self._send_func(self.ch, val)
                time.sleep(0.0002)  # 5 kHz update rate - much faster
        except Exception as e:
            showlog.warn(f"[CV_GLIDE {self.ch}] {e}")
        finally:
            self.running = False

    def set_target(self, value):
        now = time.time()
        self.last_time = now
        self.last_target = int(value)
        with self.lock:
            self.target = int(value)
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._worker, daemon=True)
            self.thread.start()


# -----------------------------------------------------------
# Globals
# -----------------------------------------------------------

_glides = {}                   # ch → GlideChannel instance
_last_values = {}  # ch → last int sent
_last_values_lock = threading.Lock()

_DAC_HOST = "192.168.7.2"
_DAC_PORT = 5050
_RETRY_DELAY = 3.0
_PING_INTERVAL = 15.0

_sock = None
_connected = False
_send_q = queue.Queue()
_stop_flag = False

# keep small ring of recent sent lines for RX correlation
_last_sent = ["<none>"] * 5
_last_lock = threading.Lock()


def _remember_sent(line: str):
    """Store a few recently sent lines for pairing with RX replies."""
    with _last_lock:
        _last_sent.pop(0)
        _last_sent.append(line.strip())


def _get_last_sent():
    with _last_lock:
        return list(_last_sent)


# -----------------------------------------------------------
# Receiver
# -----------------------------------------------------------

def _recv_thread(sock):
    """Read responses from the DAC server and log them with last TX."""
    sock.settimeout(1.0)
    buf = b""
    try:
        while True:
            try:
                data = sock.recv(1024)
                if not data:
                    break
                buf += data
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    msg = line.decode("ascii", errors="ignore").strip()
                    if not msg:
                        continue
                    last_tx = _get_last_sent()[-1]
                    showlog.verbose(f"[CV_CLIENT TX/RX] {last_tx}  →  {msg}")
            except socket.timeout:
                continue
    except Exception as e:
        showlog.warn(f"[CV_CLIENT RX] stopped: {e}")


# -----------------------------------------------------------
# Connection manager
# -----------------------------------------------------------

def _conn_thread():
    """Persistent connection manager."""
    global _sock, _connected
    last_ping = 0.0

    while not _stop_flag:
        # --- try to connect if needed ---
        if not _connected:
            try:
                showlog.debug(f"[CV_CLIENT] Connecting to {_DAC_HOST}:{_DAC_PORT} …")
                _sock = socket.create_connection((_DAC_HOST, _DAC_PORT), timeout=2.0)
                _sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

                _connected = True
                showlog.info(f"[CV_CLIENT] Connected to DAC server at {_DAC_HOST}:{_DAC_PORT}")
                threading.Thread(target=_recv_thread, args=(_sock,), daemon=True).start()
            except Exception as e:
                showlog.warn(f"[CV_CLIENT] Connect failed: {e}")
                time.sleep(_RETRY_DELAY)
                continue

        # --- main send / keepalive loop ---
        try:
            try:
                line = _send_q.get(timeout=0.05)
            except queue.Empty:
                line = None

            if line:
                # dedup check just before transmission
                with _last_values_lock:
                    try:
                        parts = line.strip().split()
                        if len(parts) == 3 and parts[0].upper() == "SET":
                            ch = int(parts[1])
                            val = int(parts[2])
                            last = _last_values.get(ch)
                            if last == val:
                                showlog.debug(f"[CV_CLIENT] suppressed duplicate TX {line}")
                                continue  # don't resend identical value
                            _last_values[ch] = val
                    except Exception as parse_err:
                        showlog.warn(f"[CV_CLIENT dedup] parse error: {parse_err}")

                # actually send it now
                try:
                    raw = (line + "\n").encode("ascii")
                    showlog.debug(f"[CV_CLIENT TX_RAW] {repr(raw)}")  # full bytes as seen by socket
                    _sock.sendall(raw)
                    _remember_sent(line)
                    time.sleep(0.0005)  # small guard for DAC line parser
                except Exception as send_err:
                    showlog.warn(f"[CV_CLIENT] send error: {send_err}")


            # --- periodic keep-alive ping ---
            now = time.time()
            if now - last_ping > _PING_INTERVAL:
                _sock.sendall(b"PING\n")
                _remember_sent("PING")
                last_ping = now

        except Exception as e:
            showlog.warn(f"[CV_CLIENT] Lost connection: {e}")
            _connected = False
            try:
                _sock.close()
            except Exception:
                pass
            _sock = None
            time.sleep(_RETRY_DELAY)


# -----------------------------------------------------------
# Public API
# -----------------------------------------------------------

def init():
    """Start the persistent connection thread (call once at UI startup)."""
    t = threading.Thread(target=_conn_thread, daemon=True)
    t.start()
    showlog.info("[CV_CLIENT] Background connection manager started")


def _queue_send(ch, val):
    line = f"SET {ch} {val}"
    _send_q.put(line)
    _remember_sent(line)



def send_cal(channel: int, cal_lo: int, cal_hi: int):
    """Send calibration limits for a given DAC channel to the server."""
    try:
        cmd = f"CAL {channel} {cal_lo} {cal_hi}"
        _send_q.put_nowait(cmd.strip() + "\n")
        showlog.info(f"[CV_CLIENT] Sent calibration → {cmd}")
    except Exception as e:
        showlog.warn(f"[CV_CLIENT] send_cal failed: {e}")


# def send(channel: int, value: int):
#     """Queue a SET command, optionally with glide smoothing and asymmetric soft-limit protection."""
#     v = int(max(0, min(4095, value)))  # clamp to DAC range

#     # --- glide smoothing logic (unchanged) ---
#     if channel not in _glides:
#         _glides[channel] = GlideChannel(channel, _queue_send)
#     _glides[channel].set_target(v)


def send(channel: int, value: int):
    """Queue an immediate SET command to the DAC (no glide)."""
    v = max(0, min(4095, int(value)))
    _send_q.put(f"SET {channel} {v}")


def send_with_glide(channel: int, value: int):
    """Queue a SET command with light glide smoothing (use for click prevention)."""
    v = int(max(0, min(4095, value)))

    if channel not in _glides:
        _glides[channel] = GlideChannel(channel, _queue_send)

    _glides[channel].set_target(v)



# def send(channel: int, value: int):
#     """Queue a SET command, optionally with glide smoothing and asymmetric soft-limit protection."""
#     v = int(max(0, min(4095, value)))  # clamp to DAC range

#     # --- independent soft-limits ---
#     range_lo = -100     # how much to raise the bottom limit
#     range_hi = -1000    # how much to lower the top limit

#     # --- apply asymmetric soft-limit --- 
#     if v < range_lo:
#         v = range_lo
#     elif v > 4095 - range_hi:
#         v = 4095 - range_hi

#     # --- rescale so full control range still maps to 0–4095 internally ---
#     usable_span = 4095 - range_lo - range_hi
#     scale = 4095 / usable_span
#     v = int((v - range_lo) * scale)

#     # --- glide smoothing logic (unchanged) ---
#     if channel not in _glides:
#         _glides[channel] = GlideChannel(channel, _queue_send)
#     _glides[channel].set_target(v)


def send_raw(cmd: str):
    """Send a raw text command directly to the CV server."""
    try:
        _send_q.put_nowait(cmd.strip() + "\n")
    except Exception as e:
        showlog.warn(f"[CV_CLIENT] send_raw failed: {e}")


def all_zero():
    """Set all DAC outputs to 0 V."""
    line = "ALLZERO"
    _send_q.put(line)
    _remember_sent(line)


def stop():
    """Stop the background thread cleanly (optional on exit)."""
    global _stop_flag
    _stop_flag = True
    _send_q.put("")  # unblock queue


import importlib
import dialhandlers  # knows which device is active

def _apply_calibration(param_name: str, raw_val: int) -> int:
    """
    Apply per-device, per-parameter calibration.
    param_name = dial label (e.g. 'Cutoff')
    """
    try:
        dev_name = getattr(dialhandlers, "current_device_name", None)
        if not dev_name:
            return raw_val

        module = importlib.import_module(f"device.{dev_name.lower()}")
        cv_map = getattr(module, "CV_MAP", {})
        cv_calib = getattr(module, "CV_CALIB", {})

        # Lookup calibration by parameter name
        cal = cv_calib.get(param_name)
        if cal:
            lo = int(cal.get("cal_lo", 0))
            hi = int(cal.get("cal_hi", 4095))
            norm = max(0.0, min(1.0, raw_val / 4095.0))
            mapped = int(round(lo + (hi - lo) * norm))
            return max(0, min(4095, mapped))
    except Exception as e:
        import showlog
        showlog.debug(f"[CV_CLIENT] Calibration lookup failed: {e}")

    return raw_val
