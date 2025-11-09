import showlog

def handle_message(tag, msg, ui):
    try:
        if tag is None:
            showlog.log(None, f"[DIALS CONTROL] {msg}")
        elif isinstance(msg, tuple):
            payload = msg[1:] if len(msg) > 1 else ()
            showlog.warn(f"[DIALS CONTROL] {tag} {payload}")
        else:
            showlog.log(None, f"[DIALS CONTROL] {tag}")

        # Safe handling examples
        if tag == "update_dial_value" and isinstance(msg, tuple) and len(msg) >= 3:
            _, dial_id, val = msg
            # …do things…
        elif tag == "ui_mode" and isinstance(msg, tuple) and len(msg) >= 2:
            _, new_mode = msg
            # …do things…
    except Exception as e:
        showlog.error(e)
