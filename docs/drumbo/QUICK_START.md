# Drumbo Metadata Quick Start

This guide gets you from zero to selecting a metadata-driven Drumbo instrument in a couple of minutes.

---

## 1. Prepare an Instrument Folder

1. Create a new folder under `assets/samples/drums/` (for example `assets/samples/drums/snares/fatty/`).
2. Drop your `.wav` files in that folder.
  - Recommended naming: keep a shared prefix plus a numeric suffix (e.g. `fatty_01.wav`, `fatty_02.wav` or `snare-a-01.wav`). Drumbo groups round-robin samples by the prefix before the first `_` or `-`, and orders them by the digits that follow.
  - New in this build: when Drumbo detects a folder full of samples but no `meta.json`, it auto-creates a starter file based on the filename tokens (instrument, category, mic label). Skip to the next step if you see `meta.json` appear automatically.
3. If you prefer to define it manually (or tweak the auto-generated version), create/edit the `meta.json` alongside the audio. At minimum include:
   ```json
   {
     "id": "fatty",
     "display_name": "Fatty Snare",
     "category": "snare",
     "banks": [
       {
         "id": "A",
         "dials": [
    { "slot": 1, "label": "Top", "variable": "mic_1_level" },
    { "slot": 2, "label": "Bottom", "variable": "mic_2_level" }
         ]
       }
     ]
   }
   ```

## 2. Launch the UI

- Start the UI from the usual entry point (for dev builds that is typically `python ui.py`).
- Navigate to the Drumbo module page (`Main → Drumbo`).

## 3. Refresh the Instrument Browser (First Time Only)

- Open either the **Presets** page or the **Module Presets** page.
- The Drumbo Instruments panel appears on the left. Click once in the panel to trigger a refresh. New instruments detected on disk show up automatically.

## 4. Select the Instrument

1. Click the instrument entry in the Drumbo Instruments panel.
2. The selection immediately updates the Drumbo module:
   - Mini-dial banks re-label and adopt the defaults from `meta.json`.
   - The Drumbo widget shows the new display name.
   - Drumbo switches to the matching category (`snare` or `kick`) and applies the dial values.

## 5. Play and Tweak

- Hit pads or send MIDI notes mapped to Drumbo; samples now come from the instrument folder you selected.
- Adjust any dial—changes stay scoped to the active instrument until you save or switch away.

## Need Help?

- For the full schema, read `docs/drumbo/instrument_metadata_schema.md`.
- For a deeper dive into how Drumbo works under the hood, see `docs/manuals/drumbo_backend_manual.md`.
