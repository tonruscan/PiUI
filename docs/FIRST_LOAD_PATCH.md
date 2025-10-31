# First-Load Init State Patch

## Problem
Pages should load their INIT state on first visit only, then use LIVE state on subsequent visits.

## Solution

### 1. Add tracking set to dialhandlers.py (line ~22):
```python
visited_pages = set()        # track which device:page combinations have been visited
```

### 2. Update page switching logic in dialhandlers.py (around line 531):

Replace the "# Recall LIVE or INIT states" section with:

```python
        # Create a unique key for tracking visited pages
        global visited_pages
        page_key = f"{dev['name']}:{current_page_id}"
        is_first_visit = page_key not in visited_pages

        # Recall LIVE or INIT states
        page_vals = None
        button_vals = {}
        
        if dev["name"] in live_states and current_page_id in live_states[dev["name"]]:
            # LIVE state exists (page has been visited and modified)
            page_vals = live_states[dev["name"]][current_page_id]
            msg_queue.put(f"[STATE] Recalling LIVE state for {dev['name']}:{current_page_id}")
        elif is_first_visit:
            # First visit - use INIT state
            init_data = device_states.get_init(dev["name"], current_page_id)
            showlog.verbose(f"[DEBUG STATE] init_data={init_data}")

            # Extract proper values and buttons
            if isinstance(init_data, dict) and "init" in init_data:
                init_state = init_data["init"]
                if isinstance(init_state, dict):
                    # Modern format: {"dials": [...], "buttons": {...}}
                    page_vals = init_state.get("dials", [0]*8)
                    button_vals = init_state.get("buttons", {})
                elif isinstance(init_state, list):
                    # Legacy format: [0, 0, 0, 0, 0, 0, 0, 0]
                    page_vals = init_state
            elif isinstance(init_data, list):
                # Legacy format: [0, 0, 0, 0, 0, 0, 0, 0]
                page_vals = init_data
            else:
                page_vals = None

            if page_vals:
                msg_queue.put(f"[STATE] First visit - loading INIT for {dev['name']}:{current_page_id}")
                # Mark as visited so subsequent visits use live state
                visited_pages.add(page_key)
            else:
                msg_queue.put(f"[STATE] No INIT values found for {dev['name']}:{current_page_id}")
        else:
            # Not first visit but no live state - use zeros
            msg_queue.put(f"[STATE] No state found for {dev['name']}:{current_page_id}")

        # 🔎 DIAGNOSTIC: show the source and full values we're about to apply
        try:
            src = "LIVE" if (dev["name"] in live_states and current_page_id in live_states[dev["name"]]) else ("INIT" if is_first_visit else "NONE")
            showlog.debug(f"[RECALL {src}] {dev['name']}:{current_page_id} → dials:{page_vals}, buttons:{button_vals}")
        except Exception:
            pass
```

### 3. Apply button states after dial restoration (around line 625):

After the existing dial value application loop, add button state restoration:

```python
        if page_vals:
            for dial_id, val in enumerate(page_vals, start=1):
                dials[dial_id - 1].set_value(val)
                dials[dial_id - 1].display_text = f"{dials[dial_id - 1].label}: {val}"
        
        # Restore button states if available
        if button_vals:
            # TODO: Apply button states to module instance if one is active
            # This will require detecting if we're on a module page and restoring button_states dict
            showlog.debug(f"[BUTTON RESTORE] {button_vals} for {dev['name']}:{current_page_id}")
```

## Behavior

**First visit to page:**
- Loads from INIT_STATE (from device/module file or device_states.json)
- Shows: `[STATE] First visit - loading INIT for BMLPF:01`
- Adds "BMLPF:01" to visited_pages set

**Subsequent visits:**
- If user changed values → loads LIVE state
- If no changes → shows `[STATE] No state found`
- Never reloads INIT unless system restarts

**System restart:**
- visited_pages set is cleared
- All pages treated as first visit again
- INIT states loaded fresh
