# remote_typing_server.py
# ----------------------------------------------------
# Simple TCP server for receiving keystrokes from PC
# and forwarding them into msg_queue for UI display.
# ----------------------------------------------------

import socket
import json
import showlog


HOST = "0.0.0.0"   # Listen on all interfaces
PORT = 8765


def run_server(msg_queue, screen=None):
    """Blocking server loop that listens for remote keystrokes."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((HOST, PORT))
            s.listen(1)
            showlog.log(screen, f"Listening on {HOST}:{PORT}")

            while True:
                conn, addr = s.accept()
                showlog.log(screen, f"[REMOTE_TYPING] Connection from {addr}")

                with conn:
                    try:
                        buffer = b""
                        while True:
                            chunk = conn.recv(1024)
                            if not chunk:
                                break
                            buffer += chunk

                            # Process complete lines
                            while b"\n" in buffer:
                                line, buffer = buffer.split(b"\n", 1)
                                try:
                                    msg = json.loads(line.decode("utf-8"))
                                    char = msg.get("text")
                                    if char:
                                        msg_queue.put(("remote_char", char))
                                except Exception as e:
                                    showlog.log(screen, f"[REMOTE_TYPING] JSON error: {e}")

                    except Exception as e:
                        showlog.log(screen, f"[REMOTE_TYPING] Connection error: {e}")
                    finally:
                        showlog.log(screen, f"[REMOTE_TYPING] Disconnected {addr}")

    except Exception as e:
        showlog.log(screen, f"[REMOTE_TYPING] Server error: {e}")
