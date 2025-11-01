"""
CV Client Service
Manages CV (Control Voltage) communication with DAC hardware over TCP.
Replaces global state in cv_client.py.
"""

import socket
import threading
import time
import queue
import showlog
import config as cfg
from core.services.base import ServiceBase


class GlideChannel:
    """Per-channel smoothing for CV output."""
    
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
        """Internal thread: fast glide to avoid clicks."""
        try:
            while self.running:
                with self.lock:
                    target = self.target
                    diff = target - self.current
                
                if diff == 0:
                    break
                
                # Fast convergence (5-10ms total)
                dist = abs(diff)
                step = max(8, min(512, int(dist / 2)))
                step *= 1 if diff > 0 else -1
                
                self.current += step
                val = int(round(self.current))
                
                self._send_func(self.ch, val)
                time.sleep(0.0002)  # 5 kHz update rate
        
        except Exception as e:
            showlog.warn(f"[CV_GLIDE {self.ch}] {e}")
        finally:
            self.running = False
    
    def set_target(self, value):
        """Set target value and start glide if needed."""
        now = time.time()
        self.last_time = now
        self.last_target = int(value)
        
        with self.lock:
            self.target = int(value)
        
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._worker, daemon=True)
            self.thread.start()


class CVClient(ServiceBase):
    """
    CV client service for DAC hardware communication.
    Manages TCP connection, glide channels, and message queue.
    """
    
    log_prefix = "[CV]"
    
    def __init__(self):
        """Initialize CV client (not yet connected)."""
        self.host = "192.168.7.2"
        self.port = 5050
        self.retry_delay = 3.0
        self.ping_interval = 15.0
        
        self.socket = None
        self.connected = False
        self.send_queue = queue.Queue()
        self.stop_flag = False
        
        # Glide management
        self.glides = {}         # ch → GlideChannel
        self.last_values = {}    # ch → last int sent
        self.last_values_lock = threading.Lock()
        
        # Background threads
        self.sender_thread = None
        self.pinger_thread = None
    
    def connect(self, host=None, port=None):
        """
        Connect to CV DAC hardware.
        
        Args:
            host: DAC server host (default: 192.168.7.2)
            port: DAC server port (default: 5050)
        
        Returns:
            True if connected, False otherwise
        """
        if host:
            self.host = host
        if port:
            self.port = port
        
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(2.0)
            self.socket.connect((self.host, self.port))
            self.connected = True
            showlog.info(f"{self.log_prefix} Connected to {self.host}:{self.port}")
            
            # Start background threads
            self._start_threads()
            return True
        
        except Exception as e:
            showlog.error(f"{self.log_prefix} Connection failed: {e}")
            self.connected = False
            return False
    
    def connect_async(self, delay=5):
        """
        Deferred connection with auto-retry (non-blocking startup).
        
        Args:
            delay: Seconds between retry attempts
        """
        threading.Thread(target=self._try_connect, args=(delay,), daemon=True).start()
        showlog.info(f"{self.log_prefix} Async connection scheduled (delay={delay}s)")
    
    def _try_connect(self, delay):
        """Background connection retry loop."""
        time.sleep(delay)
        
        while not self.connected and not self.stop_flag:
            if self.connect():
                break
            showlog.warn(f"{self.log_prefix} Retry in {delay}s...")
            time.sleep(delay)
    
    def _start_threads(self):
        """Start sender and pinger background threads."""
        if self.sender_thread is None or not self.sender_thread.is_alive():
            self.sender_thread = threading.Thread(target=self._sender_loop, daemon=True)
            self.sender_thread.start()
        
        if self.pinger_thread is None or not self.pinger_thread.is_alive():
            self.pinger_thread = threading.Thread(target=self._pinger_loop, daemon=True)
            self.pinger_thread.start()
    
    def _sender_loop(self):
        """Background thread for sending queued messages."""
        while not self.stop_flag:
            try:
                ch, val = self.send_queue.get(timeout=0.1)
                if self.connected and self.socket:
                    self._send_raw(ch, val)
            except queue.Empty:
                continue
            except Exception as e:
                showlog.error(f"{self.log_prefix} Sender error: {e}")
                self.connected = False
    
    def _pinger_loop(self):
        """Background thread for keep-alive pings."""
        while not self.stop_flag:
            time.sleep(self.ping_interval)
            if self.connected:
                try:
                    self._send_raw(99, 0)  # Ping channel
                except Exception as e:
                    showlog.warn(f"{self.log_prefix} Ping failed: {e}")
                    self.connected = False
    
    def _send_raw(self, channel, value):
        """
        Send raw CV value to DAC hardware.
        
        Args:
            channel: CV channel (0-9)
            value: 12-bit DAC value (0-4095)
        """
        if not self.connected or not self.socket:
            return False
        
        try:
            # Protocol: "CH<channel>:<value>\n"
            message = f"CH{channel}:{value}\n"
            self.socket.sendall(message.encode())
            return True
        except Exception as e:
            showlog.error(f"{self.log_prefix} Send error: {e}")
            self.connected = False
            return False
    
    def send_cv(self, channel, value):
        """
        Send CV value (queued for background sending).
        
        Args:
            channel: CV channel (0-9)
            value: 12-bit DAC value (0-4095)
        """
        if not self.connected:
            return
        
        # Update last value cache
        with self.last_values_lock:
            self.last_values[channel] = value
        
        # Queue for sending
        self.send_queue.put((channel, value))
    
    def send_cv_glide(self, channel, value):
        """
        Send CV value with glide smoothing.
        
        Args:
            channel: CV channel (0-9)
            value: 12-bit DAC value (0-4095)
        """
        if channel not in self.glides:
            self.glides[channel] = GlideChannel(channel, self.send_cv)
        
        self.glides[channel].set_target(value)
    
    def send_cal(self, channel, cal_lo, cal_hi):
        """
        Send calibration values to DAC hardware.
        
        Args:
            channel: CV channel (0-9)
            cal_lo: Low calibration value (0-4095)
            cal_hi: High calibration value (0-4095)
        """
        if not self.connected:
            return
        
        # Queue calibration command
        # Protocol: "CAL<channel>:<lo>,<hi>\n"
        try:
            message = f"CAL{channel}:{cal_lo},{cal_hi}\n"
            if self.socket:
                self.socket.sendall(message.encode())
                showlog.debug(f"{self.log_prefix} Sent calibration: ch{channel} lo={cal_lo} hi={cal_hi}")
        except Exception as e:
            showlog.error(f"{self.log_prefix} Calibration send error: {e}")
            self.connected = False
    
    def send_raw(self, command):
        """
        Send raw command string to DAC hardware.
        
        Args:
            command: Raw command string (will be sent with newline)
        """
        if not self.connected or not self.socket:
            return
        
        try:
            # Ensure command ends with newline
            if not command.endswith('\n'):
                command += '\n'
            self.socket.sendall(command.encode())
            showlog.debug(f"{self.log_prefix} Sent raw: {command.strip()}")
        except Exception as e:
            showlog.error(f"{self.log_prefix} Raw send error: {e}")
            self.connected = False
    
    def disconnect(self):
        """Disconnect from CV hardware."""
        self.connected = False
        
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
        
        showlog.info(f"{self.log_prefix} Disconnected")
    
    def is_connected(self):
        """Check if connected to CV hardware."""
        return self.connected
    
    def cleanup(self):
        """Cleanup CV client resources."""
        self.stop_flag = True
        self.disconnect()
        
        # Wait for threads to finish
        if self.sender_thread and self.sender_thread.is_alive():
            self.sender_thread.join(timeout=1.0)
        
        if self.pinger_thread and self.pinger_thread.is_alive():
            self.pinger_thread.join(timeout=1.0)
        
        showlog.info(f"{self.log_prefix} Cleanup complete")
