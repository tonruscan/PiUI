# logit.py
"""
Minimal standalone logger.
- Safe to call at import time
- Writes to file and optional network target
"""

import socket
import threading
import queue
import time
import os
import config as cfg

# ------------------------------------------------------------------
# Basic configuration (edit as needed)
# ------------------------------------------------------------------
LOG_FILE = "/home/pi/ui_logit.txt"       # absolute path for simplicity
NET_HOST = "192.168.137.1"               # your Windows receiver IP
NET_PORT = 5051                          # match log_receiver.py
ENABLE_NET = True
RECONNECT_DELAY = 5                      # seconds between retries
_last_msg = None

# ------------------------------------------------------------------

_q = queue.Queue()
_sender_started = False
_sender_thread = None


# ------------------------------------------------------------------
# Public log function
# ------------------------------------------------------------------
def log(msg: str):
    """Append message to file and enqueue for network send (no repeats)."""
    global _sender_started, _last_msg
    try:
        if not _sender_started:
            _start_sender()

        line = str(msg).rstrip("\r\n")

        # --- prevent duplicate consecutive messages ---
        if line == _last_msg:
            return
        _last_msg = line
        #line = f"** {line} ***"
        if cfg.LOG_IT_ACTIVE:
            _write_file(line)
            _enqueue_net(line)
    except Exception:
        pass


# ------------------------------------------------------------------
# File writing
# ------------------------------------------------------------------
def _write_file(line: str):
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ------------------------------------------------------------------
# Queue + background sender
# ------------------------------------------------------------------
def _enqueue_net(line: str):
    if not ENABLE_NET:
        return
    try:
        _q.put_nowait(line)
    except Exception:
        pass


def _start_sender():
    global _sender_started, _sender_thread
    if _sender_started:
        return
    _sender_started = True
    _sender_thread = threading.Thread(target=_net_loop, daemon=True)
    _sender_thread.start()


def _net_loop():
    sock = None
    while True:
        try:
            if not ENABLE_NET:
                time.sleep(1)
                continue

            # ensure socket
            if sock is None:
                try:
                    sock = socket.create_connection((NET_HOST, NET_PORT), timeout=3)
                except Exception:
                    sock = None
                    time.sleep(RECONNECT_DELAY)
                    continue

            try:
                line = _q.get(timeout=1.0)
            except queue.Empty:
                continue

            try:
                sock.sendall((line + "\n").encode("utf-8", errors="replace"))
            except Exception:
                try:
                    _q.put_nowait(line)
                except Exception:
                    pass
                try:
                    sock.close()
                except Exception:
                    pass
                sock = None
                time.sleep(RECONNECT_DELAY)

        except Exception:
            try:
                if sock:
                    sock.close()
            except Exception:
                pass
            sock = None
            time.sleep(1.0)
