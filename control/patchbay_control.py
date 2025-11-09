# control/patchbay_control.py
import showlog

def handle_message(tag, msg, ui):
    """
    Temporary stub control module for the Patchbay page.
    Prevents reload warnings and allows UI to stay resident.
    """
    try:
        if tag is None:
            showlog.log(None, f"[PATCHBAY CONTROL] {msg}")
        elif isinstance(msg, tuple):
            payload = msg[1:] if len(msg) > 1 else ()
            showlog.log(None, f"[PATCHBAY CONTROL] {tag} {payload}")
        else:
            showlog.log(None, f"[PATCHBAY CONTROL] {tag}")

        # --- Example handlers ---
        if tag == "connect_ports" and isinstance(msg, tuple) and len(msg) >= 3:
            _, src, dst = msg
            showlog.log(None, f"[PATCHBAY CONTROL] Connect {src} → {dst}")

        elif tag == "disconnect_ports" and isinstance(msg, tuple) and len(msg) >= 2:
            _, src = msg
            showlog.log(None, f"[PATCHBAY CONTROL] Disconnect {src}")

        elif tag == "refresh":
            showlog.log(None, "[PATCHBAY CONTROL] Refresh request received")
        if tag == "remote_char" and isinstance(msg, tuple) and len(msg) == 1:
            char = msg[0]
            ui.pages.patchbay.handle_remote_input(char)

        # You can safely ignore all other tags for now
    except Exception as e:
        showlog.log(None, f"[PATCHBAY CONTROL ERROR] {e}")
