# showlog.py — robust log bar with timestamps, levels, auto-tag, short INFO tag, cached CPU meter
import pygame, os, sys, time, datetime
from helper import hex_to_rgb
import config as cfg

# ---------- Paths & state ----------
BASE_DIR = os.path.dirname(__file__)
LOG_FILE = os.path.join(BASE_DIR, "ui_log.txt")

font = None
screen_ref = None
log_text = ""     # last text actually shown on screen (short-tagged when INFO)
lastmsg  = ""     # last full canonical log line written to file (with [LEVEL module])
_module_cache = {}
_last_file_tail = None  # last tail content written to file (dedupe overlay repeats)

# CPU cache to avoid flicker / blocking
_last_cpu = 0.0
_last_cpu_t = 0.0

_last_write_time = 0.0
_idle_sent = False
_IDLE_TIMEOUT = 0.5   # seconds of inactivity before separator

# Short tags (INFO lines only)
SHORT_TAGS = {
    "device_states": "STATE",
    "midiserver": "MIDI",
    "network": "NET",
    "ui": "UI",
    "navigator": "NAV",
    "devices": "DEV",
    "dialhandlers": "DIAL",
    "presets": "PRES",
    "patchbay": "PATCH",
    "text_input_page": "TEXT",
    "__main__": "UI",
    "device_select": "DEV_SELECT",
    "mixer_control": "MIXER_CTRL"
}



# --------- BEGIN add to showlog.py near top (after imports) ----------
import socket
import threading
import queue
import time
# forwarding queue & thread
_forward_q = queue.Queue()   # lines to send
_forward_thread = None
_forward_thread_started = False

# Read defaults from config (attempt import)
try:
    import config as cfg
except Exception:
    cfg = None



# --- Numeric verbosity: 0=ERROR, 1=WARN, 2=INFO (default) ---
try:
    _LOG_LEVEL = int(getattr(cfg, "LOG_LEVEL", 2))
except Exception:
    _LOG_LEVEL = 2

def _allow_level_for_bar(level_name: str) -> bool:
    """Filter on-screen log bar by numeric LOG_LEVEL (0=error,1=warn,2=info)."""
    lvl = (level_name or "INFO").upper()
    if lvl == "ERROR":
        return _LOG_LEVEL >= 0
    elif lvl == "WARN":
        return _LOG_LEVEL >= 1
    elif lvl == "INFO":
        return _LOG_LEVEL >= 2
    elif lvl == "DEBUG":
        return bool(getattr(cfg, "DEBUG_LOG", False))
    elif lvl == "VERBOSE" or lvl == "MAIN":
        return bool(getattr(cfg, "VERBOSE_LOG", False))
    else:
        # treat unknown/custom tags as INFO
        return _LOG_LEVEL >= 2



# ---------------------------------------------------------------------
# Background file writer for non-blocking logging
# ---------------------------------------------------------------------
import threading, queue

_log_queue = queue.Queue(maxsize=512)
_log_writer_started = False

def _log_writer_loop():
    """Drain the log queue and write to file / forwarder."""
    global _last_write_time
    while True:
        try:
            msg = _log_queue.get()
        except Exception:
            continue
        if msg is None:
            break
        try:
            # actual write + forward handled by existing helper
            _direct_write_file(msg)
        except Exception as e:
            try:
                print(f"[showlog] writer failed: {e}")
            except Exception:
                pass
        finally:
            _log_queue.task_done()

def _start_log_writer():
    global _log_writer_started
    if _log_writer_started:
        return
    t = threading.Thread(target=_log_writer_loop, name="showlog-writer", daemon=True)
    t.start()
    _log_writer_started = True




def _start_forwarder_once():
    """Start background thread once (daemon)."""
    global _forward_thread_started, _forward_thread
    if _forward_thread_started:
        return
    _forward_thread_started = True
    _forward_thread = threading.Thread(target=_forwarder_loop, daemon=True)
    _forward_thread.start()

def _enqueue_remote(line: str, force: bool = False):
    """Queue a file_line for remote send (non-blocking)."""
    try:
        if not getattr(cfg, "LOG_REMOTE_ENABLED", False):
            return
    except Exception:
        return
    
        # --- optional network debug filter ---
    try:
        if not bool(getattr(cfg, "NET_DEBUG", True)):
            up = (line or "").upper()
            # skip if line is DEBUG or VERBOSE (unless forced)
            if not force and ("[DEBUG" in up or "[VERBOSE" in up):
                return
    except Exception:
        pass

    # In LOUPE_MODE, only forward messages whose content begins with '*' or loupe emoji '🔍'
    try:
        if getattr(cfg, "LOUPE_MODE", False) and not force:
            s = (line or "").strip()
            allow = False
            if s.startswith("*"):
                allow = True
            elif s.startswith("[") and "]" in s:
                try:
                    tail = s.split("]", 1)[1].lstrip()
                    if tail.startswith("*") or tail.startswith("🔍"):
                        allow = True
                except Exception:
                    allow = False
            if not allow:
                return
    except Exception:
        # If config lookup/parsing fails, fall back to forwarding
        pass
    # lazily start forwarder thread when first queued
    _start_forwarder_once()
    try:
        _forward_q.put_nowait(line)
    except Exception:
        pass

def _forwarder_loop():
    """Background loop: keep a TCP connection to remote and send queued lines."""
    host = getattr(cfg, "LOG_REMOTE_HOST", None)
    port = getattr(cfg, "LOG_REMOTE_PORT", None)
    proto = getattr(cfg, "LOG_REMOTE_PROTO", "tcp")
    reconnect_delay = getattr(cfg, "LOG_REMOTE_RECONNECT_SEC", 5)

    sock = None
    while True:
        try:
            # if disabled or missing config, sleep and retry
            if not host or not port or not getattr(cfg, "LOG_REMOTE_ENABLED", False):
                time.sleep(1.0)
                continue

            # ensure sock connected
            if sock is None:
                try:
                    # log connect attempt
                    try:
                        log(None, f"[INFO showlog] [LOG NET] Connecting to {host}:{int(port)} …")
                    except Exception:
                        pass
                    sock = socket.create_connection((host, int(port)), timeout=3)
                    sock.settimeout(None)  # blocking mode after connect
                    try:
                        log(None, f"[INFO showlog] [LOG NET] Connected to {host}:{int(port)}")
                    except Exception:
                        pass
                except Exception:
                    try:
                        log(None, f"[WARN showlog] [LOG NET] Connect failed to {host}:{int(port)}; retrying in {reconnect_delay}s")
                    except Exception:
                        pass
                    sock = None
                    time.sleep(reconnect_delay)
                    continue

            # send while queue has items (block short time if empty)
            try:
                line = _forward_q.get(timeout=1.0)
            except queue.Empty:
                # nothing to send — loop to check config/connection
                continue

            # guarantee newline termination
            tosend = (line.rstrip("\r\n") + "\n").encode("utf-8", errors="replace")

            # send with simple retry on failure
            try:
                sock.sendall(tosend)
            except Exception:
                # drop the socket and requeue the line for next attempt
                try:
                    _forward_q.put_nowait(line)
                except Exception:
                    pass
                try:
                    sock.close()
                except Exception:
                    pass
                sock = None
                try:
                    log(None, f"[WARN showlog] [LOG NET] Send failed; reconnecting in {reconnect_delay}s")
                except Exception:
                    pass
                time.sleep(reconnect_delay)

        except Exception:
            # catch-all to keep thread alive
            try:
                if sock:
                    sock.close()
            except Exception:
                pass
            sock = None
            time.sleep(1.0)
# --------- END add to showlog.py block ----------




# ---------- helpers ----------
def _timestamp() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")


import time

def _direct_write_file(msg: str):
    global _last_write_time, _idle_sent
    now = time.time()

    # --- idle separator check ---
    if (_last_write_time and not _idle_sent and 
        (now - _last_write_time) >= _IDLE_TIMEOUT):
        sep = "--------------------------------"
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(sep + "\n")        # no timestamp
            _enqueue_remote(sep)            # send raw
        except Exception:
            pass
        _idle_sent = True

    # --- normal log write ---
    try:
        # determine level from message prefix
        level = "INFO"
        upper = msg.upper()
        if upper.startswith("[ERROR"):
            level = "ERROR"
        elif upper.startswith("[WARN"):
            level = "WARN"
        elif upper.startswith("[DEBUG"):
            level = "DEBUG"
        elif upper.startswith("[VERBOSE"):
            level = "VERBOSE"
        elif upper.startswith("[MAIN"):
            level = "MAIN"
                # Skip verbose lines unless enabled
        # if level == "VERBOSE" and not bool(getattr(cfg, "VERBOSE_LOG", False)):
        #     return


        # pick emoji
        emoji_map = {"INFO": "🟢", "WARN": "🟠", "ERROR": "🔴", "DEBUG": "⚫", "VERBOSE": "⚪", "MAIN": "⚙️"}

        # Default emoji by level
        emoji = emoji_map.get(level, "🟢")

        # Detect explicit Loupe (*) messages anywhere after [LEVEL ...]
        if isinstance(msg, str):
            # find the text portion after any initial bracketed tag
            check_zone = msg
            if msg.startswith("[") and "]" in msg:
                check_zone = msg.split("]", 1)[1].lstrip()

            if check_zone.startswith("*"):
                emoji = "🔍"
                # remove only the first '*' and following space from that section
                parts = msg.split("]", 1)
                if len(parts) == 2:
                    left, right = parts
                    right = right.lstrip("* ").rstrip()
                    msg = f"{left}] {right}"
                else:
                    msg = msg.lstrip("* ").rstrip()

                # --- Loupe Mode global filter: only send/write * messages when enabled ---
        try:
            if bool(getattr(cfg, "LOUPE_MODE", False)):
                # Re-check the message portion after [LEVEL ...]
                check_zone = msg
                if msg.startswith("[") and "]" in msg:
                    check_zone = msg.split("]", 1)[1].lstrip()
                # If this line no longer contains a '*' (non-loupe message), skip it entirely

                if "*" not in check_zone and not emoji == "🔍":
                    # import logit
                    #logit.log(f"[LOGIT] Skipping non-loupe message in loupe mode: {msg}")
                    return
        except Exception:
            pass



        # optional text level toggle
        show_text = bool(getattr(cfg, "SHOW_LOG_TYPE_AS_TEXT", True))

        # derive module text if present in msg
        if show_text:
            # Keep the original "[LEVEL module] ..." from msg to avoid duplication.
            # We only prepend the emoji.
            line = f"{emoji} {msg}"
        else:
            # Compact mode: strip a single leading "[LEVEL module]" token (case-insensitive),
            # but keep any other tags like [DEVICES], [NET], [STATE], etc.
            import re
            msg_core = re.sub(
                r'^\s*\[(INFO|WARN|ERROR|DEBUG|VERBOSE|MAIN)\s+[^\]]+\]\s*',
                '',
                msg,
                count=1,
                flags=re.IGNORECASE
            )
            line = f"{emoji} {msg_core}"


        # timestamp prefix
        line = f"[{_timestamp()}] {line}"

        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")

        _enqueue_remote(line)

    except Exception:
        pass

    _last_write_time = now
    _idle_sent = False


def _write_file(msg: str):
    """Enqueue log lines for background writing."""
    _start_log_writer()
    try:
        _log_queue.put_nowait(msg)
    except queue.Full:
        # Drop oldest to keep throughput steady
        try:
            _log_queue.get_nowait()
            _log_queue.put_nowait(msg)
        except Exception:
            pass




def _detect_level(msg: str) -> int:
    # 0=ERROR, 1=WARN, 2=INFO, 3=DEBUG
    if not msg: return 2
    t = msg.strip().upper()
    if t.startswith("[ERROR"): return 0
    if t.startswith("[WARN"):  return 1
    if t.startswith("[INFO"):  return 2
    if t.startswith("[DEBUG"): return 3
    return 2

def _caller_module() -> str:
    try:
        frame = sys._getframe(1)
        while frame:
            filename = frame.f_code.co_filename
            # stop when we're outside showlog.py
            if not filename.endswith("showlog.py"):
                # derive module from filename (robust)
                import os
                short = os.path.splitext(os.path.basename(filename))[0] or "main"
                return short
            frame = frame.f_back
        return "main"
    except Exception:
        return "main"
    

def _caller_info():
    """Return (module, filename, line_no) of the caller (safe fallback)."""
    import sys, os
    try:
        # Get the module name the old reliable way
        module_name = _caller_module()

        # Then walk frames to find the first one outside showlog.py for line number
        frame = sys._getframe(1)
        while frame:
            filename = frame.f_code.co_filename
            if not filename.endswith("showlog.py"):
                line_no = frame.f_lineno
                try:
                    filename = os.path.abspath(filename)
                except Exception:
                    pass
                return module_name, filename, line_no
            frame = frame.f_back

        # Fallback if everything above fails
        return module_name, "", 0


    except Exception:
        return "main", "", 0


def _short_tag(name: str) -> str:
    if not name: return "GEN"
    key = name.lower()
    return SHORT_TAGS.get(key, key[:5].upper())

# map short -> long so we can expand for the file
SHORT_TO_LONG = {short.lower(): long for long, short in SHORT_TAGS.items()}

def _expand_for_file(name: str) -> str:
    if not name:
        return name
    key = name.strip().lower()
    return SHORT_TO_LONG.get(key, name.strip())


def init(screen, font_name="Courier", font_size=14):
    global font, screen_ref
    font = pygame.font.SysFont(font_name, font_size)
    screen_ref = screen
    # Proactively start forwarder so connection attempts are visible early
    if cfg.DEBUG:
        try:
            _start_forwarder_once()
            _enqueue_remote("[INFO showlog] Forwarder started")
        except Exception:
            pass



def log_process(screen=None, msg: str = "", color=None):
    """
    Process and record a log message (write to file, update display text).
    Does NOT draw or update the screen — rendering is handled by draw_bar().
    """

        # --- Check debug_overrides.json for updated debug flags ---
    import os, json, time

    try:
        debug_path = os.path.join(os.path.dirname(__file__), "config", "debug_overrides.json")

        # Static cache for last modified time
        global _last_debug_mtime
        if "_last_debug_mtime" not in globals():
            _last_debug_mtime = 0

        # Check modification time once every ~0.5s
        now = time.time()
        if now - _last_debug_mtime > 0.5:
            mtime = os.path.getmtime(debug_path)
            if mtime != _last_debug_mtime:
                _last_debug_mtime = mtime

                # Try reading JSON overrides
                with open(debug_path, "r", encoding="utf-8") as f:
                    overrides = json.load(f)

                # Apply any flags found in JSON
                for key, value in overrides.items():
                    if hasattr(cfg, key):
                        setattr(cfg, key, bool(value))


    except FileNotFoundError:
        # No overrides file yet — ignore silently
        pass
    except Exception as e:
        # Avoid breaking log output on error
        try:
            print(f"[DEBUG_OVERRIDES] Failed to load debug_overrides.json: {e}")
        except Exception:
            pass

        
    if getattr(cfg, "LOG_OFF", False):
        return  # totally disable logging

    global log_text, screen_ref, lastmsg, _last_cpu, _last_cpu_t

    # --- Flexible calling syntax ---
    if isinstance(screen, str) and (msg is None or msg == ""):
        msg, screen = screen, None

    # If the message has no [TAG] yet, prepend one automatically
    if isinstance(msg, str) and not msg.strip().startswith("["):
        mod, _, line = _caller_info()
        msg = f"[INFO {mod}:{line}] {msg}"

    if msg is None:
        return
    raw = str(msg).strip()
    if not raw:
        return
    
    # --- LOUPE MODE: only allow lines starting with '*' (raw or after [TAG]) ---
    try:
        if bool(getattr(cfg, "LOUPE_MODE", False)):
            s = raw
            allow = False
            if s.startswith("*"):
                allow = True
            elif s.startswith("[") and "]" in s:
                try:
                    tail_after_tag = s.split("]", 1)[1].lstrip()
                    if tail_after_tag.startswith("*"):
                        allow = True
                except Exception:
                    allow = False
            if not allow:
                return  # drop non-loupe messages entirely (no file, no screen)
    except Exception:
        # if config lookup fails, do not enforce loupe mode
        pass

    # Preserve screen reference for later draws
    if screen is not None:
        screen_ref = screen
    else:
        screen = screen_ref

    # --- Parse prefix tags and format for file + bar ---
    def _split_prefix(s: str):
        if s.startswith("[") and "]" in s:
            head, tail = s.split("]", 1)
            return head[1:].strip(), tail.strip()
        return None, s

    tag, tail = _split_prefix(raw)
    LEVELS = ("INFO", "WARN", "ERROR", "DEBUG", "VERBOSE", "MAIN")
    module_name = _caller_module()
    
    module_name_full, module_file, module_line = _caller_info()

    is_level = tag and any(tag.upper().startswith(L) for L in LEVELS)

    # --- If the message has a short tag (like [NAV], [NET]) use full module name from SHORT_TO_LONG ---
    if tag:
        tag_key = tag.lower()
        if tag_key in SHORT_TO_LONG:
            module_name = SHORT_TO_LONG[tag_key]


    is_custom = not is_level if tag else False

    if is_level:
        parts = tag.split(" ", 1)
        level_name = parts[0].upper()
        if len(parts) == 2:
            module_name = parts[1].strip() or module_name

            #     # --- Filter: only affect on-screen bar ---
            # if not _allow_level_for_bar(level_name):
            #     # still write to file, skip updating log_text later
            #     _write_file(file_line)
            #     lastmsg = file_line
            #     return

        # --- add :line number ---
                # --- add :line number (with optional VSCode link) ---
        if module_line:
            module_tag = f"{module_name}:{module_line}"
        else:
            module_tag = module_name

        # VSCode clickable link toggle
        try:
            if bool(getattr(cfg, "VSCODE_LINKS", False)):
                file_path = module_file
                # normalize for Windows PowerShell view
                file_path = file_path.replace("/home/jaine/share/UI/build", "T:/UI/build").replace("\\", "/")
                # VSCode understands "file:" or plain path; prefer plain for terminal click
                clickable = f"{file_path}:{module_line}"
                file_line = f"[{level_name} {clickable}] {tail}"
            else:
                file_line = f"[{level_name} {module_tag}] {tail}"
        except Exception:
            file_line = f"[{level_name} {module_tag}] {tail}"



    elif tag:
        file_line = f"[{tag}] {tail}"
    else:
        file_line = f"[INFO {module_name}] {tail}"

    # --- File write (avoid duplicates) ---
    if file_line != lastmsg:
        _write_file(file_line)
        lastmsg = file_line

    # --- Filter: only affect the log bar ---
    if not _allow_level_for_bar(file_line):
        return  # skip updating on-screen text, but still wrote to file

    # --- Update on-screen text ---
    if is_level:
        log_text = f"[{_short_tag(module_name)}] {tail}"
    elif tag:
        log_text = f"[{tag}] {tail}"
    else:
        log_text = tail




def last():
    return log_text






def draw_bar(screen=None, fps_value=None):
    """
    Draw the bottom log bar with current log_text, clock, CPU meter, and optional FPS.
    Called once per frame by the main UI render pipeline.
    """
    import time
    global screen_ref, font, log_text, _last_cpu, _last_cpu_t

    if screen is not None:
        screen_ref = screen
    else:
        screen = screen_ref
    if not screen or not font:
        return
    
    global CURRENT_FPS
    if fps_value is not None:
        CURRENT_FPS = float(fps_value)

    log_bar_h = getattr(cfg, "LOG_BAR_HEIGHT", 20)
    rect = pygame.Rect(0, screen.get_height() - log_bar_h, screen.get_width(), log_bar_h)
    pygame.draw.rect(screen, (10, 10, 10), rect)

    # --- Left: log text ---
    text_color = hex_to_rgb(getattr(cfg, "LOG_TEXT_COLOR", "#FFFFFF"))
    text_surface = font.render(log_text, True, text_color)
    base_y = screen.get_height() - log_bar_h + 2
    screen.blit(text_surface, (10, base_y))

    # --- Right: clock + CPU (+ FPS) ---
    clock_str = time.strftime("%H:%M")
    now = time.time()
    if now - _last_cpu_t > 0.5:
        try:
            import psutil
            _last_cpu = psutil.cpu_percent(interval=None)
        except Exception:
            _last_cpu = 0.0
        _last_cpu_t = now

    cpu = int(round(_last_cpu))
    cpu_text = f"CPU: {cpu:03d}%"

    # ✅ FPS addition (integer, zero-padded)
    if fps_value is not None:
        fps_int = int(round(fps_value))
        # pad with zeros to always show 3 digits (e.g. 007, 012, 102)
        fps_text = f"FPS: {fps_int:03d}"
        overlay_text = f"{clock_str} | {cpu_text} | {fps_text}"
    else:
        overlay_text = f"{clock_str} | {cpu_text}"



    # --- Color based on CPU load ---
    if cpu < 50:
        cpu_col = (180, 180, 180)
    elif cpu < 85:
        cpu_col = (255, 180, 0)
    else:
        cpu_col = (255, 60, 60)

    overlay_surf = font.render(overlay_text, True, cpu_col)
    overlay_rect = overlay_surf.get_rect()
    overlay_rect.bottom = rect.bottom - 2
    overlay_rect.right = rect.right - 10
    screen.blit(overlay_surf, overlay_rect)







# ---------- convenience wrappers ----------
# ---------- public log wrapper ----------
def log(*args):
    """
    Unified public entry point.
    Accepts:
        log("message")
        log(screen, "message")
    """
    if getattr(cfg, "LOG_OFF", False):
        return
    try:
        if len(args) == 1:
            # single argument → message only
            msg = args[0]
            screen = None
        elif len(args) >= 2:
            # two arguments → (screen, message)
            screen, msg = args[0], args[1]
        else:
            return

        # Always treat as INFO-level for consistent :line behavior
        log_process(f"[INFO] {msg}")

    except Exception as e:
        _write_file(f"🔴[ERROR showlog] log() wrapper failed: {e}")





# --- add near the top with imports ---
import sys, traceback
from typing import Optional

# --- helper: format traceback safely on 3.9 ---
def _format_exc_str(exc: Optional[BaseException] = None) -> str:
    """
    Return a full traceback string for the current exception context or a given exception.
    Safe to call even if no exception is active (returns empty string).
    """
    try:
        if exc is not None:
            return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        exc_type, exc_val, exc_tb = sys.exc_info()
        if exc_val is None:
            return ""
        return "".join(traceback.format_exception(exc_type, exc_val, exc_tb))
    except Exception:
        return ""


# --- 3.9-safe error(...) that appends a traceback when available ---
def error(msg: Optional[str] = None, exc: Optional[BaseException] = None):
    """
    Log an ERROR. If called inside an exception handler (or with exc=),
    append the full traceback to the message.
    """
    tb = _format_exc_str(exc)
    full = msg if msg else ""
    if tb:
        full = (full + ("\n" if full else "") + tb).rstrip()
    # Use your existing sink (log / log_toggle / write function)
    log_toggle(f"[ERROR] {full}")



# -------------------------------------------------------
# Global logging toggle
# -------------------------------------------------------



def log_toggle(message):
    """Central log gate. If LOG_OFF=True in config, skip all logging."""
    # if getattr(cfg, "LOG_OFF", False):
    #     return  # totally disable logging
    
    log_process(None, message)



def debug(message):
    """Extra-detailed debug messages (file/network only)."""

    log_toggle(f"[DEBUG] {message}")


def info(message):
    log_toggle(f"[INFO] {message}")


def warn(message):
    log_toggle(f"[WARN] {message}")





def verbose(message):
    """Extra-detailed debug messages (file/network only)."""
    if not getattr(cfg, "VERBOSE_LOG", False):
        return
    log_toggle(f"[VERBOSE] {message}")


def verbose2(message):


    if not getattr(cfg, "VERBOSE_LOG", False):
        return
    log_toggle(f"[VERBOSE2] {message}")


def main(message):
    log_toggle(f"[MAIN] {message}")

def eco(message):
    """Eco-level messages (file/network only)."""
    if (not getattr(cfg, "ECO_MODE", False)):
        return
    log_process(f"[ECO] {message}")