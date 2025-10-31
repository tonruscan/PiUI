# Remote Keyboard Support for Preset Save Dialog

## Summary
Added remote keyboard input support to the preset save dialog, matching the behavior of the patchbay page.

## Changes Made

### 1. `preset_ui.py`
Added `handle_remote_input(data)` method to `PresetSaveUI` class:
- Handles backspace (`\b`) to delete characters
- Handles Enter (`\n`) to save preset
- Handles Escape (`\x1b`) to cancel
- Filters input to alphanumeric, space, underscore, and hyphen
- Updates cursor visibility on input

### 2. `pages/module_base.py`
Added two new functions:
- `is_preset_ui_active()` - Returns True if preset save UI is currently showing
- `handle_remote_input(data)` - Routes remote keyboard input to the preset UI

### 3. `ui.py`
Updated the `remote_char` message handler:
- Checks if preset UI is active on vibrato/module pages
- Routes remote keyboard input to `vibrato.handle_remote_input()` when active
- Falls back to patchbay handler when on patchbay page

## How It Works

1. Remote typing server is always running in background (started on line 111 of ui.py)
2. When user connects from PC keyboard, characters are sent as `("remote_char", char)` messages
3. Main event loop checks current UI mode and preset UI state
4. If preset UI is active on vibrato page, input goes to preset UI
5. If on patchbay page, input goes to patchbay
6. Otherwise, remote input is ignored

## Testing

1. Start the UI: `python ui.py`
2. Navigate to vibrato page (or any module using module_base)
3. Press button 9 (SV) to open preset save dialog
4. Connect from PC using remote keyboard client
5. Type preset name remotely
6. Press Enter to save or Escape to cancel

## Keyboard Controls (Local & Remote)

- **Type** - Alphanumeric, space, underscore, hyphen (max 32 chars)
- **Backspace** - Delete last character
- **Enter** - Save preset (if name is not empty)
- **Escape** - Cancel and close dialog
- **Click outside** - Cancel and close dialog (mouse only)
