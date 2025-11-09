# Plugins & Widgets Universe – The Bible (Logging Patch Revision, Nov 2025)

## 3.11 A – Standard Logger Usage (Unified Rules)

**Purpose:** All plugins, widgets, and services must use the central `showlog` module for diagnostics so that runtime logs remain structured, searchable, and correctly filtered by the UI.

---

### 1. Import Pattern
Always import the module, **never individual functions**:

```python
import showlog
```

Example usage:

```python
showlog.debug("*entered on_init() with value {val}")
showlog.info("spectra_switch", "mounted widget successfully")
showlog.warn("spectra_switch", "fallback to default theme")
showlog.error("spectra_switch", "preset load failed")
```

---

### 2. Severity Levels & Behaviour

| Level | Method | Intended Use | UI Visibility | Notes |
|:------|:--------|:-------------|:--------------|:------|
| **DEBUG** | `showlog.debug("*message {var}")` | Temporary, high‑volume developer tracing. Prefix `*` to mark as **Loupemode** (immediate on‑screen debug). | Hidden from normal UI; visible in console/log. | Use liberally while writing or testing new scripts. |
| **INFO** | `showlog.info(id, msg)` | **Essential lifecycle or status events** that the user should see in the on‑screen UI. | ✅ Visible on UI overlay. | Reserve for module/page transitions, device connects, or key user actions. |
| **WARN** | `showlog.warn(id, msg)` | Non‑fatal recoverable issues or configuration anomalies. | Logged only; not fatal. | E.g. missing optional theme key, retrying service. |
| **ERROR** | `showlog.error(id, msg)` | Fatal or unrecoverable failure. | Logged + may trigger UI error indicator. | Used when the module cannot continue normally. |

---

### 3. Exceptions
Use `showlog.exception(id, exc)` when catching Python exceptions. It automatically prints the traceback and class name.

---

### 4. Best Practices
- Keep `debug` logs concise; remove or downgrade them before merging stable code.  
- Do **not** raise additional exceptions inside logging statements.  
- Always tag messages with the plugin or service identifier (e.g., `"drumbo"`, `"spectra_switch"`).  
- Ensure fatal paths end with `showlog.error` or `showlog.exception` before raising or returning.

---
