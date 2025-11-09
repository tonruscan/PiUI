# Drumbo Instrument Metadata Schema

Defines the structure used to describe dynamically loaded Drumbo instruments. Each instrument lives in its own folder (e.g. `snares/fatty`) which contains audio samples and a metadata file.

---

## File Placement

```
assets/
  samples/
    drums/
      snares/
        fatty/
          meta.json      # metadata schema described below
          snare1_01.wav
          snare1_02.wav
      kicks/
        thumpy/
          meta.json
          kick1_01.wav
```

The application scans configured instrument roots (e.g. `snares/`, `kicks/`) and loads any folder containing a `meta.json` file. Audio files are assumed to live alongside that metadata (or within its subfolders); no explicit `sample_root` field is required.

---

## Top-Level Fields (`meta.json`)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | ✅ | Canonical instrument key. Must be unique across all instruments (e.g. `"fatty"`). |
| `display_name` | string | optional | Overrides the UI label; defaults to title-cased `id`. |
| `category` | string | optional | Category grouping (e.g. `"snare"`, `"kick"`, `"fx"`). |
| `mics` | integer | optional | Maximum dial count for this instrument; defaults to 16. |
| `round_robin` | object | optional | Overrides for sample sequencing (see below). |
| `banks` | array | ✅ | Ordered list of dial banks (minimum 1). Each bank defines dial layout/metadata. |
| `presets` | object | optional | Preset namespace details tied to this instrument (rare—defaults are inferred). |

---

## Bank Definition (`banks[]`)

Each bank object controls one row/page of dials in Drumbo.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | ✅ | Bank key (`"A"`, `"B"`, etc.). |
| `label` | string | optional | Friendly name shown in UI; defaults to the bank `id`. |
| `dials` | array | ✅ | Ordered list of dial definitions (length 1–16). |

### Dial Definition (`dials[]`)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `slot` | integer | ✅ | Dial slot index (1-based) used for hardware mapping. |
| `label` | string | ✅ | Text shown under the dial (e.g. `"OH L"`). |
| `variable` | string | ✅ | Module attribute updated when the dial moves (e.g. `"m1"`). |
| `range` | `[min, max]` | optional | Integer bounds (default `[0, 127]`). |
| `default` | integer | optional | Default dial value applied on instrument load. |
| `group` | string | optional | High-level grouping tag (e.g. `"overheads"`, `"room"`). |
| `color` | string | optional | Hex color override for the dial label/background. |

---

## Round Robin Overrides (`round_robin`)

The loader normally groups samples by the text before the first `_` or `-`, then orders them numerically by any suffix. Use `round_robin` to override this behaviour.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `mode` | string | optional | Sequencing mode: `"numeric"` (default), `"alphabetic"`, or `"manual"`. |
| `group_by` | string | optional | How to group samples into RR sets: `"prefix"` (default) or `"folder"`. |
| `manual_order` | array | optional | Explicit file order when `mode` is `"manual"`; each entry can be a filename or glob. |

If omitted, the automatic prefix+numeric sorting is used.

---

## Preset Namespace (`presets`)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `namespace` | string | optional | Overrides the inferred preset path (default: `drumbo/<id>`). |
| `default` | string | optional | Preset filename to auto-load when the instrument is selected; defaults to `init.json`. |
| `include_global` | boolean | optional | If true, show global Drumbo presets in addition to the instrument-specific ones. |

---

## Defaults (`defaults`)

## Example `meta.json`

```json
{
  "id": "fatty",
  "category": "snare",
  "mics": 16,
  "banks": [
    {
      "id": "A",
      "dials": [
        { "slot": 1, "label": "Top", "variable": "m1" },
        { "slot": 2, "label": "Bottom", "variable": "m2" },
        { "slot": 3, "label": "Side", "variable": "m3", "default": 90 },
        { "slot": 4, "label": "Snare Bus", "variable": "m4" }
      ]
    },
    {
      "id": "B",
      "dials": [
        { "slot": 1, "label": "Room L", "variable": "m9" },
        { "slot": 2, "label": "Room R", "variable": "m10" },
        { "slot": 3, "label": "FX", "variable": "m11" }
      ]
    }
  ],
}
```

---

## Next Steps

1. Instrument scanner: walk instrument roots, load/validate `meta.json`, build an in-memory registry.
2. Drumbo module integration: expose API to list instruments, load metadata, rebuild dial banks, and prime presets.
3. UI work: surface instrument browser/loader tied into the registry.
