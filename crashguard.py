# /build/crashguard.py
# ------------------------------------------------------------
#  Robust crash logger — import this FIRST in any entry script
# ------------------------------------------------------------
import os, sys, faulthandler, traceback, signal, threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(BASE_DIR, "crash.txt")

try:
    _fh = open(LOG_PATH, "a", encoding="utf-8")
except Exception:
    _fh = None


def _write_crash(msg: str):
    try:
        if _fh:
            _fh.write(msg + "\n")
            _fh.flush()
            os.fsync(_fh.fileno())
        else:
            sys.stderr.write(msg + "\n")
            sys.stderr.flush()
    except Exception:
        pass


# --- low-level / segfaults ---
try:
    faulthandler.enable(_fh or sys.stderr, all_threads=True)
except Exception:
    pass


# --- global exception hook ---
def _global_excepthook(exc_type, exc_value, exc_tb):
    trace = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    _write_crash(f"\n=== Unhandled Exception ===\n{trace}")
    try:
        import showlog
        showlog.error(f"{exc_type.__name__}: {exc_value}")
    except Exception:
        pass

sys.excepthook = _global_excepthook


# --- thread hook ---
def _thread_excepthook(args):
    tb = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
    _write_crash(f"\n=== THREAD CRASH in {args.thread.name} ===\n{tb}")
    try:
        import showlog
        showlog.error(f"[THREAD CRASH] {args.thread.name}: {args.exc_value}")
    except Exception:
        pass

threading.excepthook = _thread_excepthook


# --- optional manual dump ---
try:
    faulthandler.register(signal.SIGUSR1, file=_fh or sys.stderr, all_threads=True)
except Exception:
    pass


# --- announce path once ---
try:
    import showlog
    showlog.warn(f"[CRASHLOG] writing to: {LOG_PATH}")
except Exception:
    _write_crash(f"[CRASHLOG] writing to: {LOG_PATH}")
