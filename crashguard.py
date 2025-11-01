# /build/crashguard.py
# ------------------------------------------------------------
#  Robust crash logger — import this FIRST in any entry script
# ------------------------------------------------------------
import os, sys, faulthandler, traceback, signal, threading, atexit, datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CRASH_LOG_PATH = os.path.join(BASE_DIR, "crash.txt")
UI_LOG_PATH = os.path.join(BASE_DIR, "ui_log.txt")

try:
    _crash_fh = open(CRASH_LOG_PATH, "a", encoding="utf-8")
    _ui_fh = open(UI_LOG_PATH, "a", encoding="utf-8")
except Exception:
    _crash_fh = None
    _ui_fh = None


def _write_crash(msg: str, to_both=True):
    """Write to crash log and optionally ui_log."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"[{timestamp}] {msg}\n"
    
    try:
        # Always write to crash log
        if _crash_fh:
            _crash_fh.write(full_msg)
            _crash_fh.flush()
            os.fsync(_crash_fh.fileno())
        
        # Also write to ui_log if requested
        if to_both and _ui_fh:
            _ui_fh.write(full_msg)
            _ui_fh.flush()
            os.fsync(_ui_fh.fileno())
        
        # Always write to stderr as backup
        sys.stderr.write(full_msg)
        sys.stderr.flush()
    except Exception:
        pass


def _close_logs():
    """Close log files on exit."""
    try:
        if _crash_fh:
            _crash_fh.close()
        if _ui_fh:
            _ui_fh.close()
    except:
        pass

atexit.register(_close_logs)


# --- low-level / segfaults ---
_write_crash("[CRASHGUARD] Enabling faulthandler for segfaults/hard crashes")
try:
    faulthandler.enable(_crash_fh or sys.stderr, all_threads=True)
    _write_crash("[CRASHGUARD] Faulthandler enabled successfully")
except Exception as e:
    _write_crash(f"[CRASHGUARD] Failed to enable faulthandler: {e}")


# --- global exception hook ---
def _global_excepthook(exc_type, exc_value, exc_tb):
    trace = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    _write_crash(f"\n=== Unhandled Exception ===\n{trace}")
    _write_crash(f"Exception Type: {exc_type.__name__}")
    _write_crash(f"Exception Value: {exc_value}")
    _write_crash(f"Traceback written to crash.txt and ui_log.txt")
    
    try:
        import showlog
        showlog.error(f"[CRASH] {exc_type.__name__}: {exc_value}")
    except Exception:
        pass

sys.excepthook = _global_excepthook
_write_crash("[CRASHGUARD] Global exception hook installed")


# --- thread hook ---
def _thread_excepthook(args):
    tb = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
    _write_crash(f"\n=== THREAD CRASH in {args.thread.name} ===\n{tb}")
    _write_crash(f"Thread: {args.thread.name} (ID: {args.thread.ident})")
    _write_crash(f"Exception: {args.exc_type.__name__}: {args.exc_value}")
    
    try:
        import showlog
        showlog.error(f"[THREAD CRASH] {args.thread.name}: {args.exc_value}")
    except Exception:
        pass

threading.excepthook = _thread_excepthook
_write_crash("[CRASHGUARD] Thread exception hook installed")


# --- optional manual dump ---
try:
    faulthandler.register(signal.SIGUSR1, file=_crash_fh or sys.stderr, all_threads=True)
    _write_crash("[CRASHGUARD] SIGUSR1 registered for manual stack dumps")
except Exception as e:
    _write_crash(f"[CRASHGUARD] Could not register SIGUSR1: {e}")


# --- startup marker ---
_write_crash("=" * 80)
_write_crash(f"[CRASHGUARD] Python {sys.version}")
_write_crash(f"[CRASHGUARD] Crash logging initialized")
_write_crash(f"[CRASHGUARD] Logs: {CRASH_LOG_PATH} and {UI_LOG_PATH}")
_write_crash("=" * 80)


# --- public API for explicit checkpoints ---
def checkpoint(msg: str):
    """Manual checkpoint for tracking initialization progress."""
    _write_crash(f"[CHECKPOINT] {msg}")


def emergency_log(msg: str):
    """Emergency logging for critical failures."""
    _write_crash(f"[EMERGENCY] {msg}")


# Export public API
__all__ = ['checkpoint', 'emergency_log']
