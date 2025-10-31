# watch_and_run.py — robust watcher/runner for ui.py
import subprocess
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path
import threading
import signal
import os
import sys

WATCH_FILE = Path("/home/jaine/share/UI/build/ui.py")
WATCH_DIR = WATCH_FILE.parent
PYTHON = sys.executable or "python3"  # preserves venv if any

# Debounce window for filesystem events (seconds)
DEBOUNCE_S = 0.25

class Runner(FileSystemEventHandler):
    def __init__(self):
        self.proc = None
        self._lock = threading.Lock()
        self._debounce_timer = None
        self._want_stop = False

    # ---------- process control ----------
    def _spawn(self):
        env = os.environ.copy()
        # Leave DISPLAY / XAUTHORITY / PYTHONPATH to systemd unit
        print("Starting UI script...")
        self.proc = subprocess.Popen([PYTHON, "-u", str(WATCH_FILE)], cwd=str(WATCH_DIR), env=env)

    def _stop_if_running(self):
        if self.proc and self.proc.poll() is None:
            print("Stopping old UI...")
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None

    def start_or_restart(self, reason: str):
        with self._lock:
            print(f"[watch] restart due to: {reason}")
            self._stop_if_running()
            # Small pause so editors finish replace/rename dance
            time.sleep(0.05)
            self._spawn()

    # ---------- debounce for FS events ----------
    def _debounced_restart(self, reason: str):
        with self._lock:
            if self._debounce_timer:
                self._debounce_timer.cancel()
            self._debounce_timer = threading.Timer(DEBOUNCE_S, self.start_or_restart, args=(reason,))
            self._debounce_timer.daemon = True
            self._debounce_timer.start()

    # ---------- watchdog event handlers ----------
    def _is_target(self, path: str) -> bool:
        try:
            return Path(path).resolve() == WATCH_FILE.resolve()
        except Exception:
            return False

    def on_modified(self, event):
        if not event.is_directory and self._is_target(event.src_path):
            self._debounced_restart("ui.py modified")

    def on_created(self, event):
        if not event.is_directory and self._is_target(event.src_path):
            self._debounced_restart("ui.py created")

    def on_moved(self, event):
        # editors often write temp -> move to ui.py
        if not event.is_directory and self._is_target(getattr(event, "dest_path", "")):
            self._debounced_restart("ui.py moved into place")

    # ---------- lifecycle ----------
    def run(self):
        # launch once
        self._spawn()

        # background thread: auto-restart if process exits unexpectedly
        def reap_loop():
            while not self._want_stop:
                time.sleep(0.2)
                with self._lock:
                    if self.proc and self.proc.poll() is not None:
                        code = self.proc.returncode
                        print(f"[watch] ui.py exited with code {code}; restarting…")
                        self._spawn()
        t = threading.Thread(target=reap_loop, daemon=True)
        t.start()

        # setup watchdog
        obs = Observer()
        obs.schedule(self, str(WATCH_DIR), recursive=False)
        obs.start()

        # clean SIGTERM/SIGINT handling
        def _shutdown(signum, frame):
            print(f"[watch] received signal {signum}, shutting down…")
            self._want_stop = True
            try:
                obs.stop()
            except Exception:
                pass
            with self._lock:
                self._stop_if_running()
        signal.signal(signal.SIGTERM, _shutdown)
        signal.signal(signal.SIGINT, _shutdown)

        try:
            while obs.is_alive():
                time.sleep(0.5)
        finally:
            try:
                obs.stop()
                obs.join(timeout=2)
            except Exception:
                pass
            with self._lock:
                self._stop_if_running()


if __name__ == "__main__":
    # Ensure the file exists; if not, we still start and will catch created/moved events
    print(f"[watch] monitoring {WATCH_FILE}")
    Runner().run()
