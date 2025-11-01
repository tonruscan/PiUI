"""
Network Server Service
Manages remote typing server and network communication.
Replaces global state in network.py.
"""

import socket
import threading
import time
import showlog
import config as cfg
from core.services.base import ServiceBase


class NetworkServer(ServiceBase):
    """
    Network server service for remote typing and LED/LCD routing.
    Manages TCP server and message forwarding.
    """
    
    log_prefix = "[NETWORK]"
    
    def __init__(self):
        """Initialize network server (not yet started)."""
        self.host = "0.0.0.0"
        self.port = 5050
        self.pico_host = "192.168.4.1"
        self.pico_port = 5050
        
        self.server_socket = None
        self.server_thread = None
        self.running = False
        self.clients = []
        
        # LED routing state
        self.send_lock = threading.Lock()
        self.last_device_sent = None
    
    def start(self, port=None):
        """
        Start network server.
        
        Args:
            port: Server port (default 5050)
        
        Returns:
            True if server started, False otherwise
        """
        if port:
            self.port = port
        
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            
            self.running = True
            self.server_thread = threading.Thread(
                target=self._server_loop,
                daemon=True,
                name="NetworkServer"
            )
            self.server_thread.start()
            
            showlog.info(f"{self.log_prefix} Server started on {self.host}:{self.port}")
            return True
        
        except Exception as e:
            showlog.error(f"{self.log_prefix} Failed to start server: {e}")
            return False
    
    def _server_loop(self):
        """Background thread for accepting connections."""
        while self.running and self.server_socket:
            try:
                self.server_socket.settimeout(1.0)  # Allow periodic checks of running flag
                try:
                    client_socket, addr = self.server_socket.accept()
                    showlog.info(f"{self.log_prefix} Client connected: {addr}")
                    
                    # Handle client in separate thread
                    client_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, addr),
                        daemon=True
                    )
                    client_thread.start()
                except socket.timeout:
                    continue
                
            except Exception as e:
                if self.running:
                    showlog.error(f"{self.log_prefix} Server error: {e}")
    
    def _handle_client(self, client_socket, addr):
        """
        Handle individual client connection.
        
        Args:
            client_socket: Client socket
            addr: Client address tuple
        """
        try:
            buffer = ""
            while self.running:
                data = client_socket.recv(1024)
                if not data:
                    break
                
                buffer += data.decode('utf-8', errors='ignore')
                
                # Process complete lines
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line = line.strip()
                    
                    if line:
                        self._process_message(line)
        
        except Exception as e:
            showlog.error(f"{self.log_prefix} Client {addr} error: {e}")
        finally:
            try:
                client_socket.close()
                showlog.info(f"{self.log_prefix} Client {addr} disconnected")
            except:
                pass
    
    def _process_message(self, message):
        """
        Process received network message.
        
        Args:
            message: Message string to process
        """
        # Implement your message protocol here
        showlog.debug(f"{self.log_prefix} Received: {message}")
        
        # Example: forward to LED/LCD display
        if message.startswith("DEV"):
            self.send_led_line(message)
    
    def send_led_line(self, text, row=1):
        """
        Send message to LED/LCD display (local or network).
        
        Args:
            text: Message text or full message string (e.g., "DEV1 TXT:Quadraverb")
            row: Row number (default 1, may be ignored by some displays)
        """
        # Normalize to message format if needed
        message = text if text.startswith("DEV") else f"DEV{row} TXT:{text}"
        
        with self.send_lock:
            if cfg.LED_IS_NETWORK:
                self._forward_to_pico(message)
            else:
                self._send_local(message)
    
    def _forward_to_pico(self, message):
        """
        Forward message to Pico over TCP.
        
        Args:
            message: Message string to forward
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(2.0)
                sock.connect((self.pico_host, self.pico_port))
                sock.sendall((message + "\n").encode())
                showlog.verbose(f"{self.log_prefix} Forwarded to Pico: {message}")
        except Exception as e:
            showlog.error(f"{self.log_prefix} Pico forward error: {e}")
    
    def _send_local(self, message):
        """
        Send message to local I2C display.
        
        Args:
            message: Message string to send locally
        """
        try:
            from get_patch_and_send_local import output_msg as local_output_msg
            local_output_msg(message.strip())
            showlog.verbose(f"{self.log_prefix} (local) {message}")
        except Exception as e:
            showlog.error(f"{self.log_prefix} Local display error: {e}")
    
    def stop(self):
        """Stop network server."""
        self.running = False
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            self.server_socket = None
        
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=2.0)
        
        showlog.info(f"{self.log_prefix} Server stopped")
    
    def is_running(self):
        """Check if server is running."""
        return self.running
    
    def cleanup(self):
        """Cleanup network server resources."""
        self.stop()
        showlog.info(f"{self.log_prefix} Cleanup complete")
