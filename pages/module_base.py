# /build/pages/module_base.py  (rename of your vibrato.py)
import copy
import json

import pygame
import config as cfg
import custom_controls
import showlog
from typing import Optional, Dict, Any
import helper
import dialhandlers
from system import state_manager, cc_registry
from assets import ui_button
from system.module_core import ModuleBase
# Module reference set dynamically by plugin registration
_ACTIVE_MODULE = None
from widgets.dial_widget import DialWidget
from preset_manager import get_preset_manager
from preset_ui import PresetSaveUI
from utils.debug_overlay_grid import draw_debug_grid
from utils.grid_layout import get_grid_cell_rect, get_zone_rect_tight, get_grid_geometry

# Plugin metadata for rendering system
PLUGIN_METADATA = {
    "rendering": {
        "fps_mode": "high",              # Needs 100 FPS for smooth animation
        "supports_dirty_rect": True,     # Uses dirty rect optimization
        "burst_multiplier": 1.0,         # Standard burst behavior
    }
}

# ----------------------------------------------------------------------------
# Shared UI state
# ----------------------------------------------------------------------------
button_rects = []
button_rects_map = {}
pressed_button = None
selected_buttons = set()

_SLOT_META: Dict[int, Dict[str, Any]] = {}
_MAPPED_SRC: Optional[str] = None
_LOGTAG = "MODULE"  # Updated when set_active_module() is called

_MOD_INSTANCE = None
_PRESET_UI = None  # Preset save overlay UI
_BUTTON_STATES: Dict[str, int] = {}  # Track multi-state button indices
_ACTIVE_WIDGETS = []  # Dial widgets for current module
_CUSTOM_WIDGET_INSTANCE = None  # Custom widget (ADSR, etc.) for current module
_WIDGET_SLOT_DIALS: Dict[int, Any] = {}  # Widget-owned dial objects by slot
_ORIGINAL_SLOT_DIALS: Dict[int, Any] = {}  # Original dial objects for restoration
_DIAL_BANK_MANAGER = None  # Optional multi-bank dial controller
_PENDING_WIDGET_REDRAW = False
_PENDING_WIDGET_REDRAW_INCLUDE_OVERLAY = False
_CUSTOM_WIDGET_OVERRIDE_SPEC = None
_CUSTOM_WIDGET_SPEC_KEY = None


class DialBankManager:
    """Manage one or more banks of overlay dial widgets."""

    def __init__(self, bank_config: Dict[str, Dict[str, Any]], default_bank: Optional[str] = None):
        self._config = bank_config or {}
        self._ordered_keys = [k for k in self._config.keys()]
        self.default_bank = default_bank or (self._ordered_keys[0] if self._ordered_keys else None)
        self.active_bank = self.default_bank
        self.bank_widgets: Dict[str, list] = {}
        self.bank_values: Dict[str, list] = {}
        self.bank_visible_flags: Dict[str, bool] = {}
        self.show_all_banks = False

    def is_ready(self) -> bool:
        return bool(self.bank_widgets)

    def build_widgets(self):
        if self.bank_widgets or not self._config:
            return

        module_id = _get_module_attr("MODULE_ID", "MODULE")
        grid_layout = getattr(_ACTIVE_MODULE, "GRID_LAYOUT", {"rows": 2, "cols": 4})
        total_rows = grid_layout.get("rows", 2)
        total_cols = grid_layout.get("cols", 4)

        for bank_key in self._ordered_keys:
            entry = self._config.get(bank_key) or {}
            ctrl_ids = list(entry.get("ctrl_ids", []))
            if not ctrl_ids:
                showlog.warn(f"[{module_id}] DialBank '{bank_key}' missing ctrl_ids")
                continue

            layout = entry.get("layout", {}) or {}
            dial_size = entry.get("dial_size")
            if dial_size is None:
                dial_size = layout.get("dial_size")

            positions = self._compute_positions(layout, len(ctrl_ids), total_rows, total_cols)
            widgets = []

            for idx, ctrl_id in enumerate(ctrl_ids):
                meta = custom_controls.get(ctrl_id) or {}
                label = meta.get("label", f"Slot {idx + 1}")
                rng = meta.get("range", [0, 127])
                opts = meta.get("options")
                typ = meta.get("type", "raw")

                cfg_dict = {
                    "id": idx + 1,
                    "label": label,
                    "range": rng,
                    "options": opts,
                    "type": typ,
                }

                if dial_size is not None:
                    cfg_dict["dial_size"] = dial_size

                uid = f"{module_id}.{bank_key}.{label}.{idx + 1}"
                rect = pygame.Rect(0, 0, 1, 1)
                widget = DialWidget(uid, rect, cfg_dict)

                cx, cy = positions[idx] if idx < len(positions) else (rect.centerx, rect.centery)
                panel_size = widget.dial.radius * 2 + 20
                widget.rect = pygame.Rect(0, 0, int(round(panel_size)), int(round(panel_size)))
                widget.rect.center = (int(round(cx)), int(round(cy)))
                widget.dial.cx = int(round(cx))
                widget.dial.cy = int(round(cy))
                setattr(widget.dial, "bank_key", bank_key)
                widgets.append(widget)

            self.bank_widgets[bank_key] = widgets
            self.bank_values[bank_key] = [int(getattr(w.dial, "value", 0)) for w in widgets]
            self.bank_visible_flags[bank_key] = True

        if self.active_bank not in self.bank_widgets:
            self.active_bank = next(iter(self.bank_widgets.keys()), None)

        self._update_visual_modes()

    def _compute_positions(self, layout: Dict[str, Any], count: int, total_rows: int, total_cols: int):
        if count <= 0:
            return []

        geom = get_grid_geometry()
        if not geom:
            get_grid_cell_rect(0, 0, total_rows, total_cols)
            geom = get_grid_geometry()
        if not geom:
            return [(0.0, 0.0)] * count

        row = int(layout.get("row", 0))
        col = int(layout.get("col", 0))
        width = int(layout.get("width", total_cols))
        height = int(layout.get("height", 1))
        zone = get_zone_rect_tight(row, col, width, height, geom)
        y_offset = float(layout.get("y_offset", 0.0))

        if zone.width <= 0 or zone.height <= 0:
            return [(zone.left, zone.top + y_offset)] * count

        slot_width = zone.width / max(count, 1)
        cy = zone.top + (zone.height / 2.0) + y_offset

        positions = []
        for idx in range(count):
            cx = zone.left + slot_width * (idx + 0.5)
            positions.append((cx, cy))
        return positions

    def get_active_widgets(self) -> list:
        return list(self.bank_widgets.get(self.active_bank, []))

    def get_all_widgets(self) -> list:
        widgets = []
        for key in self._ordered_keys:
            widgets.extend(self.bank_widgets.get(key, []))
        return widgets

    def set_bank_visible(self, bank_key: str, visible: bool):
        current = self.bank_visible_flags.get(bank_key, True)
        self.bank_visible_flags[bank_key] = bool(visible)
        if bank_key == self.active_bank and not visible:
            # Ensure active bank stays in sync with visibility state
            self.capture_active_values()
        self._update_visual_modes()
        if current != bool(visible):
            for widget in self.bank_widgets.get(bank_key, []):
                self._mark_widget_dirty(widget)

    def set_bank_values(self, bank_key: str, values: Optional[list]):
        widgets = self.bank_widgets.get(bank_key)
        if not widgets:
            return

        vals = list(values or [])
        if len(vals) < len(widgets):
            vals.extend([0] * (len(widgets) - len(vals)))
        vals = vals[:len(widgets)]
        self.bank_values[bank_key] = [int(max(0, min(127, v))) for v in vals]

        for widget, val in zip(widgets, self.bank_values[bank_key]):
            try:
                widget.dial.set_value(int(val))
            except Exception:
                widget.dial.value = int(val)
            self._mark_widget_dirty(widget)

    def set_bank_value(self, bank_key: str, slot_index: int, value: int):
        widgets = self.bank_widgets.get(bank_key)
        if not widgets or slot_index < 1 or slot_index > len(widgets):
            return

        idx = slot_index - 1
        val = int(max(0, min(127, value)))
        self.bank_values.setdefault(bank_key, [0] * len(widgets))
        self.bank_values[bank_key][idx] = val

        widget = widgets[idx]
        try:
            widget.dial.set_value(val)
        except Exception:
            widget.dial.value = val
        self._mark_widget_dirty(widget)

    def get_bank_values(self, bank_key: str) -> list:
        widgets = self.bank_widgets.get(bank_key, [])
        if not widgets:
            return []
        values = []
        for widget in widgets:
            dial = getattr(widget, "dial", None)
            if not dial:
                values.append(0)
                continue
            try:
                values.append(int(dial.value))
            except Exception:
                values.append(int(getattr(dial, "value", 0)))
        self.bank_values[bank_key] = list(values)
        return list(values)

    def capture_active_values(self):
        if not self.active_bank:
            return
        self.bank_values[self.active_bank] = self.get_bank_values(self.active_bank)

    def set_active_bank(self, bank_key: str) -> bool:
        if bank_key not in self.bank_widgets:
            return False
        if not self.bank_visible_flags.get(bank_key, True):
            # Prevent activating an invisible bank; fall back to the first visible bank
            for candidate in self._ordered_keys:
                if self.bank_visible_flags.get(candidate, True):
                    bank_key = candidate
                    break
            else:
                return False
        self.active_bank = bank_key
        self._update_visual_modes()
        return True

    def apply_bank_values(self, bank_key: str):
        if bank_key not in self.bank_widgets:
            return
        self.set_bank_values(bank_key, self.bank_values.get(bank_key, []))
        self.bank_visible_flags.setdefault(bank_key, True)

    def draw(self, screen, device_name=None, offset_y=0):
        for key in self._ordered_keys:
            widgets = self.bank_widgets.get(key, [])
            for widget in widgets:
                try:
                    widget.draw(screen, device_name=device_name, offset_y=offset_y)
                except Exception as exc:
                    showlog.warn(f"[{_LOGTAG}] Bank '{key}' widget draw failed: {exc}")

    def _update_visual_modes(self):
        for key, widgets in self.bank_widgets.items():
            is_active = key == self.active_bank
            visible_flag = self.bank_visible_flags.get(key, True)
            should_show = visible_flag and (self.show_all_banks or is_active)
            for widget in widgets:
                dial = getattr(widget, "dial", None)
                if not dial:
                    continue
                target_mode = "default" if should_show else "hidden"
                current_mode = getattr(dial, "visual_mode", "default")
                if current_mode != target_mode:
                    try:
                        dial.set_visual_mode(target_mode)
                    except ValueError:
                        dial.visual_mode = target_mode
                    self._mark_widget_dirty(widget)
                setattr(widget.dial, "bank_active", is_active)

    def set_show_all_banks(self, show: bool):
        self.show_all_banks = bool(show)
        self._update_visual_modes()

    @staticmethod
    def _mark_widget_dirty(widget):
        if hasattr(widget, "mark_dirty"):
            widget.mark_dirty()
        elif hasattr(widget, "dirty"):
            widget.dirty = True


def _mark_widgets_dirty(widgets):
    for widget in widgets or []:
        if hasattr(widget, "mark_dirty"):
            widget.mark_dirty()
        elif hasattr(widget, "dirty"):
            widget.dirty = True


def request_custom_widget_redraw(include_overlays: bool = False) -> bool:
    """Ensure the active custom widget repaints on the next frame."""
    global _PENDING_WIDGET_REDRAW, _PENDING_WIDGET_REDRAW_INCLUDE_OVERLAY

    widget = _CUSTOM_WIDGET_INSTANCE
    if widget and hasattr(widget, "mark_dirty"):
        try:
            widget.mark_dirty()
        except Exception as exc:
            showlog.warn(f"[{_LOGTAG}] mark_dirty on custom widget failed: {exc}")
        if include_overlays:
            _mark_widgets_dirty(_ACTIVE_WIDGETS)
        return True

    # Defer until the widget is instantiated again
    _PENDING_WIDGET_REDRAW = True
    _PENDING_WIDGET_REDRAW_INCLUDE_OVERLAY = include_overlays
    showlog.debug(f"[{_LOGTAG}] Custom widget not ready; deferred redraw (include_overlays={include_overlays})")
    return False


def _clone_widget_spec(spec):
    if spec is None:
        return None
    try:
        return copy.deepcopy(spec)
    except Exception:
        try:
            return dict(spec)
        except Exception:
            return spec


def _widget_spec_key(spec) -> Optional[str]:
    if spec is None:
        return None
    try:
        return json.dumps(spec, sort_keys=True)
    except (TypeError, ValueError):
        return repr(spec)


def set_custom_widget_override(spec: Optional[dict], *, include_overlays: bool = True) -> None:
    """Replace the active module's widget spec until cleared."""
    global _CUSTOM_WIDGET_OVERRIDE_SPEC, _CUSTOM_WIDGET_INSTANCE, _CUSTOM_WIDGET_SPEC_KEY

    _CUSTOM_WIDGET_OVERRIDE_SPEC = _clone_widget_spec(spec)
    _CUSTOM_WIDGET_INSTANCE = None
    _CUSTOM_WIDGET_SPEC_KEY = None
    request_custom_widget_redraw(include_overlays=include_overlays)


def clear_custom_widget_override(*, include_overlays: bool = True) -> None:
    """Restore the module's default custom widget specification."""
    set_custom_widget_override(None, include_overlays=include_overlays)


def get_custom_widget_override() -> Optional[dict]:
    """Return a clone of the current override spec, if any."""
    return _clone_widget_spec(_CUSTOM_WIDGET_OVERRIDE_SPEC)


def _register_active_bank_with_dialhandlers():
    global _MAPPED_SRC
    if not _DIAL_BANK_MANAGER:
        return
    active_widgets = _DIAL_BANK_MANAGER.get_active_widgets()
    dial_objs = []
    for widget in active_widgets:
        dial_objs.append(getattr(widget, "dial", None))
    while len(dial_objs) < 8:
        dial_objs.append(None)
    dialhandlers.set_dials(dial_objs[:8])

    try:
        module_id = _get_module_attr("MODULE_ID", "MODULE")
        cc_registry.attach_mapping_to_dials(module_id, dial_objs[:8])
        global _MAPPED_SRC
        _MAPPED_SRC = module_id
    except Exception as exc:
        showlog.warn(f"[{_LOGTAG}] attach_mapping_to_dials failed: {exc}")


def configure_dial_banks(bank_config: Dict[str, Dict[str, Any]], default_bank: Optional[str] = None):
    """Initialize the dial bank manager with plugin-provided configuration."""
    global _DIAL_BANK_MANAGER, _ACTIVE_WIDGETS

    if not isinstance(bank_config, dict) or not bank_config:
        showlog.warn(f"[{_LOGTAG}] configure_dial_banks called with invalid config")
        return None

    _DIAL_BANK_MANAGER = DialBankManager(bank_config, default_bank)
    _DIAL_BANK_MANAGER.build_widgets()

    if not _DIAL_BANK_MANAGER.active_bank:
        showlog.warn(f"[{_LOGTAG}] DialBankManager has no active bank")
        return None

    _ACTIVE_WIDGETS = _DIAL_BANK_MANAGER.get_active_widgets()
    _register_active_bank_with_dialhandlers()
    _DIAL_BANK_MANAGER.apply_bank_values(_DIAL_BANK_MANAGER.active_bank)
    return _DIAL_BANK_MANAGER.active_bank


def set_dial_bank_values(bank_key: str, values: Optional[list]):
    if not _DIAL_BANK_MANAGER:
        return False
    _DIAL_BANK_MANAGER.set_bank_values(bank_key, values)
    if bank_key == _DIAL_BANK_MANAGER.active_bank:
        _mark_widgets_dirty(_ACTIVE_WIDGETS)
    return True


def set_dial_bank_value(bank_key: str, slot_index: int, value: int):
    if not _DIAL_BANK_MANAGER:
        return False
    _DIAL_BANK_MANAGER.set_bank_value(bank_key, slot_index, value)
    if bank_key == _DIAL_BANK_MANAGER.active_bank:
        _mark_widgets_dirty(_ACTIVE_WIDGETS)
    return True


def get_dial_bank_values(bank_key: str) -> list:
    if not _DIAL_BANK_MANAGER:
        return []
    return _DIAL_BANK_MANAGER.get_bank_values(bank_key)


def capture_active_dial_bank_values():
    if _DIAL_BANK_MANAGER:
        _DIAL_BANK_MANAGER.capture_active_values()


def get_active_dial_bank() -> Optional[str]:
    return _DIAL_BANK_MANAGER.active_bank if _DIAL_BANK_MANAGER else None


def set_active_dial_bank(bank_key: str) -> bool:
    global _ACTIVE_WIDGETS
    if not _DIAL_BANK_MANAGER:
        return False
    if bank_key == _DIAL_BANK_MANAGER.active_bank:
        return True

    _DIAL_BANK_MANAGER.capture_active_values()
    if not _DIAL_BANK_MANAGER.set_active_bank(bank_key):
        return False

    _ACTIVE_WIDGETS = _DIAL_BANK_MANAGER.get_active_widgets()
    _register_active_bank_with_dialhandlers()
    _DIAL_BANK_MANAGER.apply_bank_values(bank_key)
    _mark_widgets_dirty(_ACTIVE_WIDGETS)
    return True


def set_dial_bank_visibility(bank_key: str, visible: bool) -> bool:
    global _ACTIVE_WIDGETS
    if not _DIAL_BANK_MANAGER:
        return False
    _DIAL_BANK_MANAGER.set_bank_visible(bank_key, visible)
    if bank_key == _DIAL_BANK_MANAGER.active_bank and not visible:
        for candidate in _DIAL_BANK_MANAGER.bank_widgets.keys():
            if _DIAL_BANK_MANAGER.bank_visible_flags.get(candidate, True):
                if candidate != _DIAL_BANK_MANAGER.active_bank:
                    set_active_dial_bank(candidate)
                break
    _ACTIVE_WIDGETS = _DIAL_BANK_MANAGER.get_active_widgets()
    _mark_widgets_dirty(_ACTIVE_WIDGETS)
    return True


def clear_dial_banks():
    global _DIAL_BANK_MANAGER
    _DIAL_BANK_MANAGER = None


def get_dial_bank_manager() -> Optional[DialBankManager]:
    """Return the active DialBankManager, if configured."""
    return _DIAL_BANK_MANAGER


def set_slot_to_ctrl_mapping(mapping: Dict[int, str]):
    if not _ACTIVE_MODULE:
        showlog.warn(f"[{_LOGTAG}] set_slot_to_ctrl_mapping skipped - no active module")
        return False

    safe_mapping = {}
    for key, val in (mapping or {}).items():
        try:
            safe_mapping[int(key)] = val
        except Exception:
            continue

    setattr(_ACTIVE_MODULE, "SLOT_TO_CTRL", safe_mapping)
    rebuild_slot_meta()
    return True


def rebuild_slot_meta():
    _SLOT_META.clear()
    _ensure_meta()

def _get_module_attr(attr_name, default=None):
    """Get attribute from active module, with fallback."""
    if _ACTIVE_MODULE is None:
        return default
    return getattr(_ACTIVE_MODULE, attr_name, default)


def _normalize_visual_mode(mode) -> str:
    """Normalize visual mode strings (accepts 'visible' as 'default')."""
    if mode is None:
        return "default"
    normalized = str(mode).strip().lower()
    if normalized in ("default", "visible", ""):
        return "default"
    if normalized == "hidden":
        return "hidden"
    raise ValueError(f"Unsupported visual_mode '{mode}'")


def register_widget_dial(slot: int, dial_obj, visual_mode: str = "hidden") -> bool:
    """Replace the dial at a given slot with a widget-owned dial."""
    showlog.info(f"[{_LOGTAG}] 📝 register_widget_dial called: slot={slot}, dial_obj={dial_obj}, mode={visual_mode}")
    
    if not dial_obj:
        showlog.warn(f"[{_LOGTAG}] ❌ register_widget_dial: dial_obj is None")
        return False

    try:
        slot = int(slot)
    except (TypeError, ValueError):
        showlog.warn(f"[{_LOGTAG}] ❌ register_widget_dial: invalid slot '{slot}'")
        return False

    try:
        normalized_mode = _normalize_visual_mode(visual_mode)
    except ValueError as exc:
        showlog.warn(f"[{_LOGTAG}] ⚠️ register_widget_dial: {exc}")
        normalized_mode = "default"

    dials = getattr(dialhandlers, "dials", None)
    if not dials:
        showlog.warn(f"[{_LOGTAG}] ❌ register_widget_dial: dialhandlers not ready")
        return False

    idx = slot - 1
    if idx < 0 or idx >= len(dials):
        showlog.warn(f"[{_LOGTAG}] ❌ register_widget_dial: slot {slot} out of range")
        return False

    # Store original dial
    original_dial = dials[idx]
    _ORIGINAL_SLOT_DIALS.setdefault(slot, original_dial)
    showlog.info(f"[{_LOGTAG}] 💾 Saved original dial for slot {slot}: label='{getattr(original_dial, 'label', 'NO_LABEL')}'")
    
    # Replace with widget dial
    dials[idx] = dial_obj
    _WIDGET_SLOT_DIALS[slot] = dial_obj
    showlog.info(f"[{_LOGTAG}] ✅ Replaced slot {slot} with widget dial: label='{getattr(dial_obj, 'label', 'NO_LABEL')}'")

    try:
        dial_obj.set_visual_mode(normalized_mode)
    except AttributeError:
        setattr(dial_obj, "visual_mode", normalized_mode)
        if hasattr(dial_obj, "dirty"):
            dial_obj.dirty = True
    except ValueError:
        dial_obj.visual_mode = normalized_mode
        if hasattr(dial_obj, "dirty"):
            dial_obj.dirty = True

    set_dial_visual_mode(slot, normalized_mode)
    showlog.verbose(f"[{_LOGTAG}] Registered widget dial in slot {slot}")
    return True


def unregister_widget_dial(slot: int) -> bool:
    """Restore the original dial for a slot that was overridden by a widget."""
    showlog.info(f"[{_LOGTAG}] 🔄 unregister_widget_dial called for slot {slot}")
    
    try:
        slot = int(slot)
    except (TypeError, ValueError):
        showlog.warn(f"[{_LOGTAG}] ❌ unregister_widget_dial: invalid slot type")
        return False

    original = _ORIGINAL_SLOT_DIALS.get(slot)
    if original is None:
        showlog.warn(f"[{_LOGTAG}] ⚠️ unregister_widget_dial: no original dial for slot {slot}")
        return False

    dials = getattr(dialhandlers, "dials", None)
    if not dials:
        showlog.warn(f"[{_LOGTAG}] ❌ unregister_widget_dial: dialhandlers not ready")
        return False

    idx = slot - 1
    if idx < 0 or idx >= len(dials):
        showlog.warn(f"[{_LOGTAG}] ❌ unregister_widget_dial: slot {slot} out of range")
        return False

    showlog.info(f"[{_LOGTAG}] 🔄 Restoring slot {slot}: widget_dial='{getattr(dials[idx], 'label', 'NO_LABEL')}' -> original='{getattr(original, 'label', 'NO_LABEL')}'")
    
    dials[idx] = original
    _WIDGET_SLOT_DIALS.pop(slot, None)
    _ORIGINAL_SLOT_DIALS.pop(slot, None)
    set_dial_visual_mode(slot, "default")
    
    showlog.info(f"[{_LOGTAG}] ✅ Slot {slot} restored successfully")
    return True


def set_dial_visual_mode(slot: int, mode: str) -> bool:
    """Update the visual_mode for all dial representations associated with a slot."""
    try:
        slot = int(slot)
    except (TypeError, ValueError):
        return False

    try:
        normalized = _normalize_visual_mode(mode)
    except ValueError as exc:
        showlog.warn(f"[{_LOGTAG}] set_dial_visual_mode failed: {exc}")
        return False

    updated = False

    # Update grid dial widgets
    for widget in _ACTIVE_WIDGETS:
        dial = getattr(widget, "dial", None)
        if getattr(dial, "id", None) == slot:
            try:
                dial.set_visual_mode(normalized)
            except ValueError:
                pass
            if hasattr(widget, "mark_dirty"):
                widget.mark_dirty()
            else:
                widget.dirty = True
            updated = True

    # Update dialhandlers entry (widget-owned dial or original)
    dials = getattr(dialhandlers, "dials", None)
    idx = slot - 1
    if dials and 0 <= idx < len(dials):
        dial_obj = dials[idx]
        if hasattr(dial_obj, "set_visual_mode"):
            try:
                dial_obj.set_visual_mode(normalized)
            except ValueError:
                pass
        else:
            setattr(dial_obj, "visual_mode", normalized)
        if hasattr(dial_obj, "dirty"):
            dial_obj.dirty = True
        updated = True

    # Update cached widget dial reference if stored separately
    widget_dial = _WIDGET_SLOT_DIALS.get(slot)
    if widget_dial and widget_dial is not (dials[idx] if dials and 0 <= idx < len(dials) else None):
        if hasattr(widget_dial, "set_visual_mode"):
            try:
                widget_dial.set_visual_mode(normalized)
            except ValueError:
                pass
        else:
            setattr(widget_dial, "visual_mode", normalized)
        if hasattr(widget_dial, "dirty"):
            widget_dial.dirty = True
        updated = True

    return updated


def set_dial_visibility(slot: int, visible: bool) -> bool:
    """Convenience wrapper for toggling between hidden and default rendering."""
    mode = "visible" if visible else "hidden"
    return set_dial_visual_mode(slot, mode)

def set_active_module(module_ref):
    """Called by plugins to register themselves with this page renderer."""
    global _ACTIVE_MODULE, _LOGTAG, _MOD_INSTANCE
    global _CUSTOM_WIDGET_INSTANCE, _ACTIVE_WIDGETS, _BUTTON_STATES, _SLOT_META
    global _CUSTOM_WIDGET_OVERRIDE_SPEC, _CUSTOM_WIDGET_SPEC_KEY
    
    showlog.info(f"[MODULE_BASE] set_active_module called with: {module_ref}")
    showlog.info(f"[MODULE_BASE] Current _ACTIVE_MODULE: {_ACTIVE_MODULE}")
    showlog.info(f"[MODULE_BASE] Current _MOD_INSTANCE: {_MOD_INSTANCE}")
    
    # Only clear if we're actually switching to a different module
    new_module_id = getattr(module_ref, "MODULE_ID", None)
    current_module_id = getattr(_ACTIVE_MODULE, "MODULE_ID", None) if _ACTIVE_MODULE else None
    
    if new_module_id != current_module_id:
        showlog.info(f"[MODULE_BASE] ⚡ SWITCHING MODULES: {current_module_id} -> {new_module_id}")
        
        # Debug: Show current dial state
        dials = getattr(dialhandlers, "dials", None)
        if dials:
            showlog.info(f"[MODULE_BASE] 🔍 Current dials count: {len(dials)}")
            for i, d in enumerate(dials[:8], 1):
                if d:
                    showlog.info(f"[MODULE_BASE] 🔍 Dial slot {i}: label='{getattr(d, 'label', 'NO_LABEL')}', id={getattr(d, 'id', 'NO_ID')}, value={getattr(d, 'value', 'NO_VAL')}")
        
        # Debug: Show widget dial replacements
        showlog.info(f"[MODULE_BASE] 🔍 _WIDGET_SLOT_DIALS: {list(_WIDGET_SLOT_DIALS.keys())}")
        showlog.info(f"[MODULE_BASE] 🔍 _ORIGINAL_SLOT_DIALS: {list(_ORIGINAL_SLOT_DIALS.keys())}")
        
        # Ensure any module-specific widget overrides are cleared before switching
        try:
            clear_custom_widget_override(include_overlays=True)
        except Exception as exc:
            showlog.debug(f"[MODULE_BASE] clear_custom_widget_override during switch failed: {exc}")
        global _CUSTOM_WIDGET_OVERRIDE_SPEC, _CUSTOM_WIDGET_SPEC_KEY
        _CUSTOM_WIDGET_OVERRIDE_SPEC = None
        _CUSTOM_WIDGET_SPEC_KEY = None

        # Restore original dials that were replaced by widgets
        if _WIDGET_SLOT_DIALS:
            showlog.info(f"[MODULE_BASE] ♻️ Restoring {len(_WIDGET_SLOT_DIALS)} widget-replaced dials")
            for slot in list(_WIDGET_SLOT_DIALS.keys()):
                result = unregister_widget_dial(slot)
                showlog.info(f"[MODULE_BASE] ♻️ Restored slot {slot}: {result}")
        else:
            showlog.info(f"[MODULE_BASE] ℹ️ No widget dials to restore")
        
        # Debug: Show dial state after restoration
        if dials:
            showlog.info(f"[MODULE_BASE] 🔍 AFTER RESTORE - dials count: {len(dials)}")
            for i, d in enumerate(dials[:8], 1):
                if d:
                    showlog.info(f"[MODULE_BASE] 🔍 Dial slot {i}: label='{getattr(d, 'label', 'NO_LABEL')}', id={getattr(d, 'id', 'NO_ID')}, value={getattr(d, 'value', 'NO_VAL')}")
        
        # Clear cached module instance and widgets when switching modules
        _MOD_INSTANCE = None
        _CUSTOM_WIDGET_INSTANCE = None
        _ACTIVE_WIDGETS = []  # Reset to empty list
        _BUTTON_STATES.clear()  # Clear button states
        _SLOT_META.clear()  # Force metadata reload for new module
        clear_dial_banks()
        
        # Update dialhandlers.current_device_name ONLY for standalone modules
        # (modules with STANDALONE=True don't inherit parent device theme)
        is_standalone = getattr(module_ref, "STANDALONE", False)
        if new_module_id and is_standalone:
            dialhandlers.current_device_name = new_module_id
            showlog.info(f"[MODULE_BASE] Standalone module - updated dialhandlers.current_device_name to '{new_module_id}'")
            
            # Clear showheader theme cache to force reload
            try:
                import showheader
                showheader.clear_theme_cache()
                showlog.info(f"[MODULE_BASE] Cleared showheader theme cache")
            except Exception as e:
                showlog.warn(f"[MODULE_BASE] Failed to clear showheader cache: {e}")
        else:
            showlog.info(f"[MODULE_BASE] Non-standalone module '{new_module_id}' - preserving parent device theme")
    else:
        showlog.info(f"[MODULE_BASE] Same module ({new_module_id}), preserving instance and state")
    
    _ACTIVE_MODULE = module_ref
    module_id = getattr(module_ref, "MODULE_ID", "MODULE")
    _LOGTAG = module_id.upper()
    showlog.info(f"[MODULE_BASE] Active module set to: {_LOGTAG}")

def _get_mod_instance():
    """Create/cache the active module instance (class discovered dynamically)."""
    global _MOD_INSTANCE
    if _MOD_INSTANCE is not None:
        return _MOD_INSTANCE
    try:
        # 0) If _ACTIVE_MODULE is already a ModuleBase subclass, instantiate it directly
        if isinstance(_ACTIVE_MODULE, type) and issubclass(_ACTIVE_MODULE, ModuleBase) and _ACTIVE_MODULE is not ModuleBase:
            _MOD_INSTANCE = _ACTIVE_MODULE()
            return _MOD_INSTANCE
        
        # 1) explicit factory wins
        factory = getattr(_ACTIVE_MODULE, "get_instance", None)
        if callable(factory):
            _MOD_INSTANCE = factory()
            return _MOD_INSTANCE

        target_id = getattr(_ACTIVE_MODULE, "MODULE_ID", None)

        # 2) find a real subclass (not the base) with matching MODULE_ID
        candidates = []
        for name in (dir(_ACTIVE_MODULE) if _ACTIVE_MODULE else []):
            obj = getattr(_ACTIVE_MODULE, name)
            if not (isinstance(obj, type) and issubclass(obj, ModuleBase)):
                continue
            if obj is ModuleBase:
                continue  # skip the base class re-exported by the module
            mid = getattr(obj, "MODULE_ID", None)
            score = 0
            if mid and target_id and mid == target_id:
                score += 10
            if name.lower() == "vibrato":  # friendly hint
                score += 1
            candidates.append((score, obj))

        if candidates:
            candidates.sort(reverse=True)
            cls = candidates[0][1]
            _MOD_INSTANCE = cls()
            return _MOD_INSTANCE

        showlog.warn(f"[{_LOGTAG}] No ModuleBase subclass found in module.")
    except Exception as e:
        showlog.warn(f"[{_LOGTAG}] _get_mod_instance failed: {e}")
    return None

def _dispatch_hook(name: str, *args):
    """Call a hook on the active module instance if it exists."""
    try:
        inst = _get_mod_instance()
        if inst and hasattr(inst, name):
            method = getattr(inst, name)
            if callable(method):
                method(*args)
    except Exception as e:
        _mod_id = _get_module_attr("MODULE_ID", "MODULE")
        showlog.warn(f"[{_mod_id}] _dispatch_hook({name}) failed: {e}")
        inst = _get_mod_instance()
        if not inst:
            return
        method = getattr(inst, name, None)
        if callable(method):
            return method(*args)
    except Exception as e:
        showlog.warn(f"[{_LOGTAG}] hook '{name}' failed: {e}")

def handle_midi_note(note: int, velocity: int, channel: int = None) -> bool:
    """Forward MIDI note data to the active module and/or its widget."""
    handled = False

    inst = _get_mod_instance()
    if inst and hasattr(inst, "on_midi_note"):
        try:
            result = inst.on_midi_note(note, velocity, channel)
            if result is None:
                handled = handled or False
            else:
                handled = bool(result)
        except Exception as exc:
            showlog.warn(f"[{_LOGTAG}] on_midi_note hook failed: {exc}")

    if not handled and _CUSTOM_WIDGET_INSTANCE and hasattr(_CUSTOM_WIDGET_INSTANCE, "on_midi_note"):
        try:
            _CUSTOM_WIDGET_INSTANCE.on_midi_note(note, velocity)
            handled = True
        except Exception as exc:
            showlog.warn(f"[{_LOGTAG}] Widget on_midi_note failed: {exc}")

    return handled


def _check_dial_latch(slot: int, hardware_value: int, target_value: int) -> bool:
    """
    Check if hardware dial should be latched (pickup mode).
    Returns True if the value should be dispatched, False if it should be discarded.
    
    Implements crossover detection: hardware must pass through target value to unlock.
    """
    inst = _get_mod_instance()
    if not inst:
        return True  # No module instance, allow through
    
    # Check if plugin opted out of latch system
    metadata = getattr(_ACTIVE_MODULE, "PLUGIN_METADATA", {})
    if metadata.get("no_latch", False):
        return True  # Plugin disabled latch system
    
    # Get latch state for this hardware dial slot
    latch_state = inst.dial_latch_states.get(slot)
    if not latch_state:
        return True  # No state tracking, allow through
    
    # Store current hardware position
    previous_hw = latch_state["previous_hw_value"]
    inst.hardware_dial_positions[slot] = hardware_value
    latch_state["previous_hw_value"] = hardware_value
    
    # Check if we need to latch (hardware and target differ significantly)
    distance = abs(hardware_value - target_value)
    
    if not latch_state["latched"]:
        # Not currently latched - check if we should latch
        if distance > inst.dial_pickup_threshold:
            # Hardware is too far from target - engage latch
            latch_state["latched"] = True
            latch_state["target_value"] = target_value
            showlog.info(f"[{_LOGTAG}] Dial {slot} LATCHED (HW={hardware_value}, Target={target_value}, dist={distance})")
            return False  # Discard this update
        else:
            # Close enough, allow through
            return True
    else:
        # Currently latched - check for crossover
        target = latch_state["target_value"]
        
        # Detect crossover: did we pass through the target value?
        crossed = False
        if previous_hw < target <= hardware_value:
            # Crossed upward
            crossed = True
        elif previous_hw > target >= hardware_value:
            # Crossed downward  
            crossed = True
        
        if crossed:
            # Crossover detected - unlatch and allow through
            latch_state["latched"] = False
            showlog.info(f"[{_LOGTAG}] Dial {slot} UNLATCHED (crossover at {target}, HW now {hardware_value})")
            return True
        else:
            # Still waiting for crossover - discard
            showlog.debug(f"[{_LOGTAG}] Dial {slot} still latched (HW={hardware_value}, target={target}, prev={previous_hw})")
            return False


def _load_custom_widget():
    """Load and position a module's custom widget (if declared)."""
    global _CUSTOM_WIDGET_INSTANCE, _PENDING_WIDGET_REDRAW, _PENDING_WIDGET_REDRAW_INCLUDE_OVERLAY
    global _CUSTOM_WIDGET_OVERRIDE_SPEC, _CUSTOM_WIDGET_SPEC_KEY

    # Return cached instance if already created
    if _CUSTOM_WIDGET_INSTANCE:
        return _CUSTOM_WIDGET_INSTANCE

    raw_spec = _CUSTOM_WIDGET_OVERRIDE_SPEC
    if raw_spec is None:
        raw_spec = getattr(_ACTIVE_MODULE, "CUSTOM_WIDGET", None)

    if not raw_spec:
        _CUSTOM_WIDGET_SPEC_KEY = None
        return None

    spec = _clone_widget_spec(raw_spec)
    spec_key = _widget_spec_key(spec)
    if _CUSTOM_WIDGET_SPEC_KEY != spec_key:
        _CUSTOM_WIDGET_SPEC_KEY = spec_key
        _CUSTOM_WIDGET_INSTANCE = None

    try:
        import importlib

        # ─────────────────────────────────────────────
        # Ensure grid geometry exists (for grid-space sizing)
        # ─────────────────────────────────────────────
        geom = get_grid_geometry()
        if not geom:
            get_grid_cell_rect(0, 0)  # trigger geometry calc
            geom = get_grid_geometry()

        # ─────────────────────────────────────────────
        # Resolve widget rect
        # ─────────────────────────────────────────────
        rect = None

        # 1️⃣ Prefer explicit grid_size
        if "grid_size" in spec:
            w_cells, h_cells = spec["grid_size"]
            # Anchor default: row 0, col 1 (same area as old zone C)
            row, col = spec.get("grid_pos", [0, 1])
            rect = get_zone_rect_tight(row, col, w_cells, h_cells, geom)
            
            # Debug: Show detailed grid calculations
            showlog.verbose(
                f"[VIBRATO] Widget grid calculation: "
                f"pos=({col},{row}) size={w_cells}×{h_cells} → rect={rect}"
            )
            
            # Debug: Compare with individual dial positions for alignment verification
            dial_rect_tl = get_grid_cell_rect(0, 1)  # Top-left dial of widget area
            dial_rect_tr = get_grid_cell_rect(0, 3)  # Top-right dial of widget area  
            dial_rect_bl = get_grid_cell_rect(1, 1)  # Bottom-left dial of widget area
            dial_rect_br = get_grid_cell_rect(1, 3)  # Bottom-right dial of widget area
            
            # Get module ID once for logging (avoid f-string quote issues)
            _mod_id = _get_module_attr("MODULE_ID", "MODULE")
            
            showlog.verbose(
                f"[{_mod_id}] Individual dials in widget area:"
            )
            showlog.verbose(f"[{_mod_id}]   TL(0,1): {dial_rect_tl}")
            showlog.verbose(f"[{_mod_id}]   TR(0,3): {dial_rect_tr}")
            showlog.verbose(f"[{_mod_id}]   BL(1,1): {dial_rect_bl}")
            showlog.verbose(f"[{_mod_id}]   BR(1,3): {dial_rect_br}")

            # Calculate what the perfect widget rect should be
            perfect_left = dial_rect_tl.left
            perfect_top = dial_rect_tl.top
            perfect_right = dial_rect_tr.right
            perfect_bottom = dial_rect_br.bottom
            perfect_rect = pygame.Rect(perfect_left, perfect_top, 
                                     perfect_right - perfect_left, 
                                     perfect_bottom - perfect_top)

            showlog.verbose(f"[{_mod_id}] Perfect widget rect: {perfect_rect}")
            showlog.verbose(f"[{_mod_id}] Actual widget rect:  {rect}")
            showlog.verbose(
                f"[{_mod_id}] Differences: "
                f"left={rect.left - perfect_left}, top={rect.top - perfect_top}, "
                f"right={rect.right - perfect_right}, bottom={rect.bottom - perfect_bottom}"
            )

        # 2️⃣ Fallback to manual rect
        elif "rect" in spec:
            rect = pygame.Rect(spec["rect"])
            showlog.verbose(f"[VIBRATO] Custom widget manual rect {rect}")

        # 3️⃣ Default rectangle
        else:
            rect = pygame.Rect(120, 80, 660, 300)
            showlog.verbose(f"[VIBRATO] Custom widget default rect {rect}")

        # ─────────────────────────────────────────────
        # Import class and instantiate
        # ─────────────────────────────────────────────
        mod_widget = importlib.import_module(spec["path"])
        cls = getattr(mod_widget, spec["class"])

        # Instantiate widget without wiring it directly to module logic.
        # The module may provide an `attach_widget(widget)` hook to wire callbacks.

        from helper import theme_rgb
        device_name = getattr(dialhandlers, "current_device_name", None)

        # Strictly pass through your device theme colors from cfg/helper. No alpha, no transforms.
        theme = {
            "bg":       theme_rgb(device_name, "DIAL_PANEL_COLOR"),    # background panel (brown rect behind dial)
            "fill":     theme_rgb(device_name, "DIAL_FILL_COLOR"),     # middle selection band
            "outline":  theme_rgb(device_name, "DIAL_OUTLINE_COLOR"),  # frame + dots
            "guides":   (255, 255, 255),                               # white lines
            "solid_mode": True,                                        # hard disable any alpha logic
        }

        # Also pass the full module THEME dict so widgets can access custom keys
        # (e.g., plugin_background_color, dial_label_color)
        module_theme = getattr(_ACTIVE_MODULE, "THEME", {})
        if module_theme:
            theme.update(module_theme)

        # Get widget init state from plugin's INIT_STATE (if defined)
        widget_init = _get_module_attr("INIT_STATE", {}).get("widget", None)

        # Check if widget constructor accepts init_state parameter
        import inspect
        sig = inspect.signature(cls.__init__)
        if 'init_state' in sig.parameters:
            _CUSTOM_WIDGET_INSTANCE = cls(rect, on_change=None, theme=theme, init_state=widget_init)
        else:
            _CUSTOM_WIDGET_INSTANCE = cls(rect, on_change=None, theme=theme)

        # Get module ID once for logging
        _mod_id = _get_module_attr("MODULE_ID", "MODULE")
        showlog.info(
            f"[{_mod_id}] Custom widget loaded → "
            f"{spec['class']} from {spec['path']} (rect={rect})"
        )
        # If the active module exposes an attach_widget hook, call it to let the
        # module wire the widget's on_change handler (e.g. Vibrato.attach_widget).
        try:
            _dispatch_hook("attach_widget", _CUSTOM_WIDGET_INSTANCE)
            showlog.debug(f"[{_mod_id}] attach_widget() dispatched to module instance")
        except Exception:
            # ignore: not all modules implement attach_widget
            pass

        # NOTE: Widget dial registration is deferred to draw_ui() because
        # dialhandlers.dials doesn't exist yet during first _load_custom_widget() call.
        # See widget dial registration in draw_ui() after widget is loaded.

        if _PENDING_WIDGET_REDRAW:
            include_overlay = _PENDING_WIDGET_REDRAW_INCLUDE_OVERLAY
            _PENDING_WIDGET_REDRAW = False
            _PENDING_WIDGET_REDRAW_INCLUDE_OVERLAY = False
            request_custom_widget_redraw(include_overlay)

        return _CUSTOM_WIDGET_INSTANCE

    except Exception as e:
        _mod_id = _get_module_attr("MODULE_ID", "MODULE")
        showlog.error(f"[{_mod_id}] custom widget load failed: {e}")
        return None


# ----------------------------------------------------------------------------
# Initialization
# ----------------------------------------------------------------------------
def init_page():
    """Called once when page becomes active."""
    global _PRESET_UI, _BUTTON_STATES
    
    showlog.debug(f"[{_LOGTAG}] === INIT_PAGE CALLED ===")
    showlog.debug(f"[{_LOGTAG}] _PRESET_UI currently exists: {_PRESET_UI is not None}")
    showlog.debug(f"[{_LOGTAG}] _PRESET_UI type: {type(_PRESET_UI) if _PRESET_UI else 'None'}")
    showlog.debug(f"[{_LOGTAG}] Module ID: {_get_module_attr('MODULE_ID', 'UNKNOWN')}")
    
    dials = getattr(dialhandlers, "dials", None)
    if not dials:
        showlog.warn(f"[{_LOGTAG}] init_page: No dials available yet")
        return

    sm = getattr(state_manager, "manager", None)
    if not sm:
        showlog.warn(f"[{_LOGTAG}] StateManager not ready during init")
        return

    module_instance = _get_mod_instance()
    if module_instance and hasattr(module_instance, "on_init"):
        try:
            module_instance.on_init()
        except Exception as exc:
            showlog.error(f"[{_LOGTAG}] on_init failed: {exc}")
    
    # ============================================================================
    # STATE PERSISTENCE (matching device/BMLPF pattern)
    # ============================================================================
    # Build page key for tracking visits and state persistence
    plugin_id = _get_module_attr("PLUGIN_ID", _get_module_attr("MODULE_ID", "UNKNOWN"))
    page_key = f"{plugin_id}:main"
    
    showlog.debug(f"[{_LOGTAG}] State persistence for page_key: {page_key}")
    
    # Check if this page has been visited before
    visited = page_key in dialhandlers.visited_pages
    
    # Priority system for state loading:
    # 1. LIVE state (user has modified values)
    # 2. INIT state (first visit)
    # 3. Defaults (zeros)
    
    dial_vals = None
    button_vals = {}
    widget_vals = {}
    
    # Priority 1: Check for LIVE state (user modifications)
    if plugin_id in dialhandlers.live_states and "main" in dialhandlers.live_states[plugin_id]:
        live_state = dialhandlers.live_states[plugin_id]["main"]
        showlog.info(f"[{_LOGTAG}] LIVE state found for {page_key}")
        
        # Handle both old format (list) and new format (dict)
        if isinstance(live_state, dict):
            dial_vals = live_state.get("dials", [])
            button_vals = live_state.get("buttons", {})
            widget_vals = live_state.get("widget", {})
        elif isinstance(live_state, list):
            dial_vals = live_state  # Legacy format
            button_vals = {}
            widget_vals = {}
    
    # Priority 2: Use INIT state on first visit
    elif not visited:
        init_state = _get_module_attr("INIT_STATE", {})
        if init_state:
            dial_vals = init_state.get("dials", [])
            button_vals = init_state.get("buttons", {})
            widget_vals = init_state.get("widget", {})
            showlog.info(f"[{_LOGTAG}] First visit - loading INIT state for {page_key}")
            showlog.debug(f"[{_LOGTAG}] INIT dials: {dial_vals}")
            showlog.debug(f"[{_LOGTAG}] INIT buttons: {button_vals}")
            dialhandlers.visited_pages.add(page_key)
        else:
            showlog.warn(f"[{_LOGTAG}] No INIT_STATE defined for plugin")
    
    # Priority 3: Defaults (zeros) - will be used if nothing else available
    else:
        showlog.debug(f"[{_LOGTAG}] No state found for {page_key}, using defaults")
    
    # Apply dial values (BMLPF pattern: lines 708-720)
    if dial_vals and dials:
        showlog.info(f"[{_LOGTAG}] Applying {len(dial_vals)} dial values to {len(dials)} dials")
        for dial_id, val in enumerate(dial_vals, start=1):
            if dial_id <= len(dials):
                try:
                    dial_obj = dials[dial_id - 1]
                    dial_obj.set_value(val)
                    dial_obj.display_text = f"{dial_obj.label}: {val}"
                    showlog.verbose(f"[{_LOGTAG}] Dial {dial_id} set to {val}")
                except Exception as e:
                    showlog.error(f"[{_LOGTAG}] Error setting dial {dial_id}: {e}")
    
    # ============================================================================
    # END STATE PERSISTENCE
    # ============================================================================
    
    # Initialize multi-state button tracking (only if empty - preserve loaded state)
    if not _BUTTON_STATES:
        module_buttons = _get_module_attr("BUTTONS", [])
        for btn in module_buttons:
            if isinstance(btn, dict):
                btn_id = str(btn.get("id", ""))
                states = btn.get("states") or btn.get("options")
                if states and isinstance(states, list) and len(states) > 1:
                    # Initialize to first state (index 0)
                    _BUTTON_STATES[btn_id] = 0
                    showlog.debug(f"[{_LOGTAG}] Initialized multi-state button {btn_id} with {len(states)} states")
        
        # Apply button values from state (INIT or LIVE)
        if button_vals:
            for btn_id, state_idx in button_vals.items():
                _BUTTON_STATES[btn_id] = state_idx
                showlog.debug(f"[{_LOGTAG}] Applied button {btn_id} state: {state_idx}")
    else:
        showlog.debug(f"[{_LOGTAG}] _BUTTON_STATES already populated, preserving state")
    
    # Initialize preset UI overlay if not already created
    if _PRESET_UI is None:
        try:
            showlog.debug(f"[{_LOGTAG}] _PRESET_UI is None, creating new instance...")
            screen_w = getattr(cfg, "SCREEN_WIDTH", 800)
            screen_h = getattr(cfg, "SCREEN_HEIGHT", 480)
            showlog.debug(f"[{_LOGTAG}] Screen dimensions: {screen_w}x{screen_h}")
            
            # Get msg_queue from service registry
            msg_queue = None
            try:
                from core.service_registry import ServiceRegistry
                services = ServiceRegistry()
                msg_queue = services.get('msg_queue')
                showlog.debug(f"[{_LOGTAG}] Got msg_queue from services: {msg_queue is not None}")
            except Exception as e:
                showlog.debug(f"[{_LOGTAG}] Could not get msg_queue from services: {e}")
            
            showlog.debug(f"[{_LOGTAG}] Creating PresetSaveUI instance...")
            _PRESET_UI = PresetSaveUI((screen_w, screen_h), msg_queue=msg_queue)
            showlog.debug(f"[{_LOGTAG}] PresetSaveUI successfully initialized!")
            showlog.debug(f"[{_LOGTAG}] _PRESET_UI type after creation: {type(_PRESET_UI)}")
            showlog.debug(f"[{_LOGTAG}] _PRESET_UI has 'show' method: {hasattr(_PRESET_UI, 'show')}")
            showlog.debug(f"[{_LOGTAG}] _PRESET_UI has 'active' attr: {hasattr(_PRESET_UI, 'active')}")
        except Exception as e:
            showlog.error(f"[{_LOGTAG}] Failed to initialize PresetSaveUI: {e}")
            import traceback
            showlog.error(f"[{_LOGTAG}] Traceback: {traceback.format_exc()}")
    else:
        showlog.debug(f"[{_LOGTAG}] PresetSaveUI already exists, skipping creation")

    # Keep module state independent of device page state
    # (If you later need device names in the module key, add it here.)
    global _MAPPED_SRC
    if _MAPPED_SRC != _get_module_attr("MODULE_ID"):
        # Ensure knobs exist for this module; attach happens after labels in draw_ui()
        try:
            cc_registry.load_from_module(_get_module_attr("MODULE_ID"), _get_module_attr("REGISTRY"), None)
        except Exception as e:
            showlog.warn(f"[{_LOGTAG}] cc_registry.load_from_module failed: {e}")
        _MAPPED_SRC = None  # force (re)attach in draw_ui

    # Clear first-load flags so new module state is recalled
    try:
        for d in dials:
            if d and hasattr(d, "_mod_init"):
                delattr(d, "_mod_init")
    except Exception:
        pass

    owned_slots = set(_get_owned_slots())
    attached = sum(1 for d in dials if d and d.id in owned_slots and getattr(d, "sm_param_id", None))
    _mod_id = _get_module_attr("MODULE_ID", "MODULE")
    showlog.debug(f"[{_LOGTAG}] init_page linked {attached} dials to StateManager (src={_mod_id})")


# ----------------------------------------------------------------------------
# Utilities
# ----------------------------------------------------------------------------
def _dial_hit(d, pos):
    if not d:
        return False
    dx = pos[0] - d.cx
    dy = pos[1] - d.cy
    return (dx * dx + dy * dy) <= (d.radius * d.radius)

def _ensure_meta():
    _SLOT_META.clear()
    for slot, ctrl_id in _get_module_attr("SLOT_TO_CTRL", {}).items():
        meta = custom_controls.get(ctrl_id)
        if not meta:
            showlog.warn(f"[{_LOGTAG}] Missing controller '{ctrl_id}' in custom_dials.json")
        _SLOT_META[slot] = meta or {}


def _get_owned_slots():
    """Return the slot ids that this module actually owns."""
    def _normalize(values):
        out = []
        for v in values:
            try:
                out.append(int(v))
            except (TypeError, ValueError):
                continue
        return sorted(set(out))

    slots = getattr(_ACTIVE_MODULE, "OWNED_SLOTS", None)
    if slots:
        result = _normalize(slots)
        showlog.debug(f"[MODULE_BASE] _get_owned_slots from OWNED_SLOTS: {result}")
        return result

    ctrl_map = getattr(_ACTIVE_MODULE, "SLOT_TO_CTRL", {}) or {}
    if isinstance(ctrl_map, dict):
        result = _normalize(ctrl_map.keys())
        showlog.debug(f"[MODULE_BASE] _get_owned_slots from SLOT_TO_CTRL={ctrl_map}: {result}")
        return result

    showlog.warn(f"[MODULE_BASE] _get_owned_slots: no OWNED_SLOTS or SLOT_TO_CTRL found for {_ACTIVE_MODULE}")
    return []

def _snap_for_meta_default(meta) -> int:
    """Return a snapped 0..127 default based on control meta defaults (center-ish)."""
    opts = (meta or {}).get("options")
    rng = (meta or {}).get("range")

    if isinstance(opts, list) and len(opts) > 1:
        steps = len(opts)
        idx = (steps - 1) // 2
        return int(round(idx * (127.0 / (steps - 1))))

    if isinstance(rng, (list, tuple)) and len(rng) == 2 and all(isinstance(v, int) for v in rng):
        lo, hi = rng
        steps = (hi - lo) + 1
        if 1 < steps <= 16:
            idx = (steps - 1) // 2
            return int(round(idx * (127.0 / (steps - 1))))
        return int(round(127.0 * 0.5))

    return 0


def _module_value_to_raw(meta, value):
    """Translate a module variable back to a 0..127 dial position."""
    if value is None:
        return None

    meta = meta or {}
    opts = meta.get("options")
    rng = meta.get("range")

    try:
        if isinstance(opts, list) and len(opts) > 1:
            idx = int(round(value))
            idx = max(0, min(len(opts) - 1, idx))
            step = 127.0 / (len(opts) - 1)
            return int(round(idx * step))

        if isinstance(rng, (list, tuple)) and len(rng) == 2 and all(isinstance(x, (int, float)) for x in rng):
            lo = float(rng[0])
            hi = float(rng[1])
            if hi == lo:
                return 0
            val = max(lo, min(hi, float(value)))
            norm = (val - lo) / (hi - lo)
            return int(round(norm * 127.0))

        return int(value)
    except Exception:
        return None


def _apply_state_to_dials(dial_vals, state_type="INIT"):
    """
    Apply dial values to both regular widgets and widget-owned dials.
    
    Args:
        dial_vals: List of dial values (0-127)
        state_type: "INIT" or "LIVE" (for logging)
    """
    # Apply to regular grid dials (DialWidget instances)
    for widget in _ACTIVE_WIDGETS:
        dial_obj = getattr(widget, "dial", None)
        if dial_obj:
            dial_id = getattr(dial_obj, "id", 0)
            if 1 <= dial_id <= len(dial_vals):
                val = dial_vals[dial_id - 1]
                try:
                    dial_obj.set_value(val)
                    dial_obj.display_text = f"{dial_obj.label}: {val}"
                    showlog.verbose(f"[{_LOGTAG}] {state_type} - Widget dial {dial_id} set to {val}")
                except Exception as e:
                    showlog.error(f"[{_LOGTAG}] Error setting widget dial {dial_id}: {e}")
    
    # Apply to widget-owned dials (e.g., DrawBarWidget speed dial)
    # These are registered in _WIDGET_SLOT_DIALS and also in dialhandlers.dials
    for slot, dial_obj in _WIDGET_SLOT_DIALS.items():
        if 1 <= slot <= len(dial_vals):
            val = dial_vals[slot - 1]
            try:
                dial_obj.set_value(val)
                # Widget dials may not have display_text
                if hasattr(dial_obj, "label"):
                    label = getattr(dial_obj, "label", f"Slot {slot}")
                    if hasattr(dial_obj, "display_text"):
                        dial_obj.display_text = f"{label}: {val}"
                showlog.info(f"[{_LOGTAG}] {state_type} - Widget-owned dial (slot {slot}) set to {val}")
            except Exception as e:
                showlog.error(f"[{_LOGTAG}] Error setting widget-owned dial {slot}: {e}")


def _sync_module_state_to_dials(module_instance):
    """Push freshly loaded preset values into the on-screen dials."""
    registry = getattr(_ACTIVE_MODULE, "REGISTRY", {}) or {}
    slot_map = {}

    showlog.verbose(f"[{_LOGTAG}] _sync_module_state_to_dials called")
    
    for entry in registry.values():
        if not isinstance(entry, dict) or entry.get("type") != "module":
            continue
        for slot_key, slot_data in entry.items():
            if slot_key in {"type", "label", "description"}:
                continue
            if not isinstance(slot_data, dict):
                continue
            var = slot_data.get("variable")
            if not var:
                continue
            try:
                slot_idx = int(slot_key)
            except Exception:
                continue
            slot_map[var] = (slot_idx, slot_data)

    showlog.verbose(f"[{_LOGTAG}] slot_map: {slot_map}")
    
    if not slot_map:
        showlog.verbose(f"[{_LOGTAG}] No slot_map entries, cannot sync dials")
        return

    widgets = _ACTIVE_WIDGETS or []
    dial_list = getattr(dialhandlers, "dials", None)
    sm = getattr(state_manager, "manager", None)

    for var_name, payload in slot_map.items():
        slot_idx, slot_meta = payload
        if not hasattr(module_instance, var_name):
            showlog.verbose(f"[{_LOGTAG}] Module missing variable {var_name}")
            continue

        value = getattr(module_instance, var_name)
        showlog.verbose(f"[{_LOGTAG}] Syncing {var_name}={value} to slot {slot_idx}")
        
        meta = (_SLOT_META.get(slot_idx) or {}).copy()
        if not meta:
            meta = slot_meta.copy()
        raw = _module_value_to_raw(meta, value)
        if raw is None:
            showlog.verbose(f"[{_LOGTAG}] _module_value_to_raw returned None for {var_name}")
            continue
        
        showlog.verbose(f"[{_LOGTAG}] Converted {var_name}={value} to raw={raw}")

        dial_obj = None

        # First, try to find the dial in _ACTIVE_WIDGETS
        for widget in widgets:
            dial = getattr(widget, "dial", None)
            if dial and getattr(dial, "id", None) == slot_idx:
                try:
                    dial.set_value(raw)
                    showlog.verbose(f"[{_LOGTAG}] Synced widget dial {slot_idx} to {raw}")
                except Exception:
                    dial.value = raw
                dial_obj = dial
                break

        # Then update the dialhandlers.dials entry (if it exists and is not None)
        if dial_list and 1 <= slot_idx <= len(dial_list):
            dial_in_list = dial_list[slot_idx - 1]
            if dial_in_list:  # Skip None entries
                try:
                    dial_in_list.set_value(raw)
                    showlog.verbose(f"[{_LOGTAG}] Synced dialhandlers.dials[{slot_idx-1}] to {raw}")
                except Exception:
                    dial_in_list.value = raw
                if dial_obj is None:
                    dial_obj = dial_in_list

        if sm and dial_obj and getattr(dial_obj, "sm_param_id", None):
            src = getattr(dial_obj, "sm_source_name", None) or _get_module_attr("MODULE_ID")
            try:
                sm.set_value(src, dial_obj.sm_param_id, int(dial_obj.value))
            except Exception:
                pass

# ----------------------------------------------------------------------------
# Preset Save/Load Functions
# ----------------------------------------------------------------------------
def save_current_preset(preset_name: str):
    """
    Save the current module state as a preset.
    
    Args:
        preset_name: Name for the preset
    """
    showlog.info(f"*[{_LOGTAG}] save_current_preset called with name: '{preset_name}'")
    try:
        preset_mgr = get_preset_manager()
        module_instance = _get_mod_instance()
        widget = _CUSTOM_WIDGET_INSTANCE
        
        showlog.debug(f"*[{_LOGTAG}] module_instance: {module_instance}")
        showlog.debug(f"*[{_LOGTAG}] widget: {widget}")
        
        if not module_instance:
            showlog.error(f"*[{_LOGTAG}] Cannot save preset - no module instance")
            return False

        preset_name = (preset_name or "").strip()
        if hasattr(module_instance, "prepare_preset_save"):
            try:
                module_instance.prepare_preset_save()
            except Exception as exc:
                showlog.warn(f"*[{_LOGTAG}] prepare_preset_save failed: {exc}")

        if hasattr(module_instance, "normalize_preset_name"):
            try:
                preset_name = module_instance.normalize_preset_name(preset_name)
            except Exception as exc:
                showlog.warn(f"*[{_LOGTAG}] normalize_preset_name failed: {exc}")

        if not preset_name:
            showlog.error(f"*[{_LOGTAG}] Preset name empty after normalization; aborting save")
            return False
        
        page_id = _get_module_attr("MODULE_ID")
        showlog.info(f"*[{_LOGTAG}] Saving preset for page_id: '{page_id}', button_states: {getattr(module_instance, 'button_states', 'N/A')}")
        
        success = preset_mgr.save_preset(page_id, preset_name, module_instance, widget)
        
        if success:
            showlog.info(f"*[{_LOGTAG}] Successfully saved preset '{preset_name}'")
        else:
            showlog.error(f"*[{_LOGTAG}] Failed to save preset '{preset_name}'")
        
        return success
        
    except Exception as e:
        showlog.error(f"*[{_LOGTAG}] Exception saving preset: {e}")
        import traceback
        showlog.error(f"*[{_LOGTAG}] Traceback: {traceback.format_exc()}")
        return False

def load_preset(preset_name: str, msg_queue=None):
    """
    Load a saved preset and apply it to the current module.
    
    Args:
        preset_name: Name of the preset to load
        msg_queue: Optional message queue for UI updates
    """
    try:
        preset_mgr = get_preset_manager()
        module_instance = _get_mod_instance()
        widget = _CUSTOM_WIDGET_INSTANCE
        
        if not module_instance:
            showlog.error(f"[{_LOGTAG}] Cannot load preset - no module instance")
            return False
        
        page_id = _get_module_attr("MODULE_ID")
        success = preset_mgr.load_preset(page_id, preset_name, module_instance, widget)
        
        if success:
            showlog.info(f"[{_LOGTAG}] Loaded preset '{preset_name}'")
            try:
                _ensure_meta()
                _sync_module_state_to_dials(module_instance)
            except Exception as e:
                showlog.warn(f"[{_LOGTAG}] Failed to sync dials after preset load: {e}")
            if msg_queue:
                msg_queue.put(("invalidate", None))
        else:
            showlog.error(f"[{_LOGTAG}] Failed to load preset '{preset_name}'")
        
        return success
        
    except Exception as e:
        showlog.error(f"[{_LOGTAG}] Exception loading preset: {e}")
        return False

def show_preset_save_ui():
    """Show the preset save UI overlay."""
    global _PRESET_UI
    showlog.debug(f"[{_LOGTAG}] === SHOW_PRESET_SAVE_UI CALLED ===")
    showlog.debug(f"[{_LOGTAG}] _PRESET_UI exists: {_PRESET_UI is not None}")
    showlog.debug(f"[{_LOGTAG}] _PRESET_UI type: {type(_PRESET_UI)}")
    
    # Fallback: Initialize _PRESET_UI if it doesn't exist
    if _PRESET_UI is None:
        showlog.debug(f"[{_LOGTAG}] _PRESET_UI is None! Attempting to create it now...")
        try:
            screen_w = getattr(cfg, "SCREEN_WIDTH", 800)
            screen_h = getattr(cfg, "SCREEN_HEIGHT", 480)
            showlog.debug(f"[{_LOGTAG}] Screen dimensions: {screen_w}x{screen_h}")
            
            # Get msg_queue from service registry
            msg_queue = None
            try:
                from core.service_registry import ServiceRegistry
                services = ServiceRegistry()
                msg_queue = services.get('msg_queue')
                showlog.debug(f"[{_LOGTAG}] Got msg_queue from services: {msg_queue is not None}")
            except Exception as e:
                showlog.debug(f"[{_LOGTAG}] Could not get msg_queue from services: {e}")
            
            showlog.debug(f"[{_LOGTAG}] Creating PresetSaveUI instance...")
            _PRESET_UI = PresetSaveUI((screen_w, screen_h), msg_queue=msg_queue)
            showlog.debug(f"[{_LOGTAG}] PresetSaveUI created on-demand successfully!")
            showlog.debug(f"[{_LOGTAG}] New _PRESET_UI type: {type(_PRESET_UI)}")
        except Exception as e:
            showlog.error(f"[{_LOGTAG}] Failed to create PresetSaveUI on-demand: {e}")
            import traceback
            showlog.error(f"[{_LOGTAG}] Traceback: {traceback.format_exc()}")
            return
    
    if _PRESET_UI:
        showlog.debug(f"[{_LOGTAG}] About to call _PRESET_UI.show()")
        showlog.debug(f"[{_LOGTAG}] Callback function: {save_current_preset}")
        _PRESET_UI.show(on_save_callback=save_current_preset)
        showlog.debug(f"[{_LOGTAG}] _PRESET_UI.show() called successfully")
    else:
        showlog.error(f"[{_LOGTAG}] PresetSaveUI could not be initialized - dialog cannot be shown!")

def is_preset_ui_active():
    """Check if the preset save UI is currently active."""
    global _PRESET_UI
    result = _PRESET_UI and _PRESET_UI.active
    showlog.debug(f"[{_LOGTAG}] is_preset_ui_active: _PRESET_UI exists={_PRESET_UI is not None}, active={_PRESET_UI.active if _PRESET_UI else 'N/A'}, result={result}")
    return result

def handle_remote_input(data):
    """
    Handle remote keyboard input for preset UI.
    
    Args:
        data: Character or special key from remote keyboard
    """
    global _PRESET_UI
    showlog.debug(f"*[{_LOGTAG}] === HANDLE_REMOTE_INPUT CALLED ===")
    showlog.debug(f"*[{_LOGTAG}] Data: '{data}' (repr: {repr(data)})")
    showlog.debug(f"*[{_LOGTAG}] _PRESET_UI exists: {_PRESET_UI is not None}")
    showlog.debug(f"*[{_LOGTAG}] _PRESET_UI active: {_PRESET_UI.active if _PRESET_UI else 'N/A'}")
    if _PRESET_UI and _PRESET_UI.active:
        showlog.debug(f"*[{_LOGTAG}] Forwarding to _PRESET_UI.handle_remote_input()")
        _PRESET_UI.handle_remote_input(data)
    else:
        showlog.debug(f"*[{_LOGTAG}] NOT forwarding - preset UI not active")


def apply_drumbo_instrument(instrument_id: str) -> bool:
    """Apply a Drumbo instrument selection to the active module (if any)."""
    showlog.debug(f"*[MODULE_BASE] apply_drumbo_instrument called with id={instrument_id}")

    if not instrument_id:
        showlog.warn("*[MODULE_BASE] apply_drumbo_instrument skipped - empty id")
        return False

    try:
        from plugins import drumbo_instrument_service as service
    except Exception as exc:
        showlog.warn(f"*[MODULE_BASE] Drumbo service unavailable: {exc}")
        return False

    spec = service.get_instrument(str(instrument_id))
    if spec is None:
        showlog.debug("*[MODULE_BASE] Instrument not cached - refreshing via service.select")
        spec = service.select(str(instrument_id), auto_refresh=True)

    if spec is None:
        showlog.warn(f"*[MODULE_BASE] Instrument '{instrument_id}' not found after refresh")
        return False

    module_id = str(_get_module_attr("MODULE_ID", "")).lower()
    if module_id != "drumbo":
        showlog.debug(f"*[MODULE_BASE] Active module {module_id} is not Drumbo - selection stored only")
        return True

    inst = _get_mod_instance()
    if inst is None:
        showlog.warn("*[MODULE_BASE] No module instance available to apply Drumbo instrument")
        return True

    handler = getattr(inst, "load_instrument_from_spec", None)
    if not callable(handler):
        showlog.warn("*[MODULE_BASE] Drumbo module missing load_instrument_from_spec handler")
        return False

    try:
        result = handler(spec)
        showlog.debug(f"*[MODULE_BASE] Drumbo handler returned {result}")
    except Exception as exc:
        showlog.warn(f"*[MODULE_BASE] Drumbo instrument apply failed: {exc}")
        return False

    widget = getattr(inst, "widget", None)
    if widget and hasattr(widget, "mark_dirty"):
        try:
            widget.mark_dirty()
        except Exception:
            pass

    request_custom_widget_redraw(include_overlays=False)
    return bool(result is None or result is True)


# ----------------------------------------------------------------------------
# Draw UI
# ----------------------------------------------------------------------------
# Dirty rect support
# ----------------------------------------------------------------------------
def get_dirty_widgets():
    """
    Get list of widgets that need redrawing.
    Returns: List of widgets with dirty flag set
    """
    global _ACTIVE_WIDGETS, _CUSTOM_WIDGET_INSTANCE
    dirty_list = []

    widgets = _DIAL_BANK_MANAGER.get_all_widgets() if _DIAL_BANK_MANAGER else _ACTIVE_WIDGETS
    showlog.verbose(
        f"[MODULE_BASE] get_dirty_widgets() called, checking {len(widgets)} dials and custom widget={_CUSTOM_WIDGET_INSTANCE is not None}"
    )

    for w in widgets:
        if hasattr(w, "is_dirty"):
            if w.is_dirty():
                dirty_list.append(w)
        elif getattr(w, 'dirty', False):
            dirty_list.append(w)
    
    # Check custom widget (ADSR, etc.)
    if _CUSTOM_WIDGET_INSTANCE:
        widget = _CUSTOM_WIDGET_INSTANCE
        has_is_dirty = hasattr(widget, "is_dirty")
        is_dirty_result = widget.is_dirty() if has_is_dirty else False
        dirty_attr = getattr(widget, 'dirty', False)
        is_dirty_check = is_dirty_result or dirty_attr
        showlog.verbose(f"[MODULE_BASE] Custom widget dirty check: has_is_dirty={has_is_dirty}, is_dirty()={is_dirty_result}, dirty attr={dirty_attr}, final={is_dirty_check}")
        if is_dirty_check:
            showlog.verbose(f"[MODULE_BASE] Custom widget is DIRTY: {widget.__class__.__name__} - adding to dirty_list")
            dirty_list.append(widget)
        else:
            showlog.verbose(f"[MODULE_BASE] Custom widget is CLEAN: {widget.__class__.__name__}")
    
    showlog.verbose(f"[MODULE_BASE] get_dirty_widgets() returning {len(dirty_list)} dirty widgets")
    return dirty_list


def get_all_widgets():
    """
    Get list of ALL widgets (dirty or not) for animation updates.
    Returns: List of all active widgets
    """
    global _ACTIVE_WIDGETS, _CUSTOM_WIDGET_INSTANCE
    base_widgets = _DIAL_BANK_MANAGER.get_all_widgets() if _DIAL_BANK_MANAGER else _ACTIVE_WIDGETS
    all_widgets = list(base_widgets)
    
    # Add custom widget if it exists
    if _CUSTOM_WIDGET_INSTANCE:
        all_widgets.append(_CUSTOM_WIDGET_INSTANCE)
    
    return all_widgets


def redraw_dirty_widgets(screen, offset_y=0):
    """
    Redraw only the widgets that have changed.
    Returns: List of dirty rects that were redrawn
    """
    import dialhandlers
    device_name = getattr(dialhandlers, "current_device_name", None)
    
    dirty_rects = []
    dirty_widgets = get_dirty_widgets()
    
    showlog.verbose(f"[MODULE_BASE] redraw_dirty_widgets() - found {len(dirty_widgets)} dirty widgets")
    
    for widget in dirty_widgets:
        try:
            showlog.verbose(f"[MODULE_BASE] Drawing dirty widget: {widget.__class__.__name__}")
            rect = widget.draw(screen, device_name=device_name, offset_y=offset_y)
            if not rect and hasattr(widget, "get_dirty_rect"):
                rect = widget.get_dirty_rect(offset_y=offset_y)
            if rect:
                dirty_rects.append(rect)
            
            # If this is the custom widget, redraw grid dials on top of it
            if widget == _CUSTOM_WIDGET_INSTANCE:
                showlog.verbose(f"[MODULE_BASE] Redrawing grid dials on top of custom widget")
                try:
                    # Check if widget has a specific dirty dial - if so, only redraw that one
                    has_specific_dirty = hasattr(widget, '_dirty_dial') and widget._dirty_dial is not None
                    
                    if has_specific_dirty:
                        # Only redraw the specific dial that changed
                        showlog.verbose(f"[MODULE_BASE] Widget has specific dirty dial - only redrawing that one")
                        dirty_dial = widget._dirty_dial
                        overlay_widgets = _DIAL_BANK_MANAGER.get_all_widgets() if _DIAL_BANK_MANAGER else _ACTIVE_WIDGETS
                        for w in overlay_widgets:
                            if hasattr(w, 'dial') and w.dial == dirty_dial:
                                dial_rect = w.draw(screen, device_name=device_name, offset_y=offset_y)
                                if dial_rect:
                                    dirty_rects.append(dial_rect)
                                break
                    else:
                        # Full redraw - redraw all overlay dials
                        showlog.verbose(f"[MODULE_BASE] Full widget redraw - redrawing all overlay dials")
                        overlay_widgets = _DIAL_BANK_MANAGER.get_all_widgets() if _DIAL_BANK_MANAGER else _ACTIVE_WIDGETS
                        for w in overlay_widgets:
                            # Skip dial 2 if we have a DrawBarWidget
                            if _CUSTOM_WIDGET_INSTANCE and hasattr(_CUSTOM_WIDGET_INSTANCE, 'background_rect'):
                                if hasattr(w, 'dial') and getattr(w.dial, 'id', None) == 2:
                                    continue
                            w.draw(screen, device_name=device_name, offset_y=offset_y)
                except Exception as e:
                    showlog.warn(f"[MODULE_BASE] Failed to redraw dials on top: {e}")
            
            # Clear dirty flag
            if hasattr(widget, "clear_dirty"):
                showlog.verbose(f"[MODULE_BASE] Calling clear_dirty() on {widget.__class__.__name__}")
                widget.clear_dirty()
            elif hasattr(widget, 'dirty'):
                showlog.verbose(f"[MODULE_BASE] Setting dirty=False on {widget.__class__.__name__}")
                widget.dirty = False
        except Exception as e:
            widget_name = getattr(widget, 'uid', widget.__class__.__name__)
            showlog.error(f"[MODULE_BASE] Failed to redraw widget {widget_name}: {e}")
    
    return dirty_rects


# ----------------------------------------------------------------------------
def draw_ui(screen, offset_y=0):
    if not _SLOT_META:
        _ensure_meta()

    global _ACTIVE_WIDGETS, _MAPPED_SRC
    bank_manager = _DIAL_BANK_MANAGER
    if bank_manager:
        bank_manager.build_widgets()
        if not _ACTIVE_WIDGETS:
            _ACTIVE_WIDGETS = bank_manager.get_active_widgets()
            _register_active_bank_with_dialhandlers()

    # --------------------------------------------------------------
    # Build DialWidgets using grid layout from module
    # --------------------------------------------------------------
    owned_slots = set(_get_owned_slots())

    if not bank_manager and not _ACTIVE_WIDGETS:
        try:
            _ACTIVE_WIDGETS = []
            layout_hints = getattr(_ACTIVE_MODULE, "DIAL_LAYOUT_HINTS", {}) or {}
            overlay_positions = None
            
            # Get grid layout from module (default to 2x4 if not specified)
            grid_layout = getattr(_ACTIVE_MODULE, "GRID_LAYOUT", {"rows": 2, "cols": 4})
            total_rows = grid_layout.get("rows", 2)
            total_cols = grid_layout.get("cols", 4)
            custom_dial_size = grid_layout.get("dial_size", None)  # Per-plugin dial size override

            if layout_hints.get("type") == "overlay_top_row":
                geom = get_grid_geometry()
                if not geom:
                    # Prime geometry cache using base grid with current layout
                    get_grid_cell_rect(0, 0, total_rows, total_cols)
                    geom = get_grid_geometry()
                if geom:
                    row_hint = int(layout_hints.get("row", 0))
                    col_hint = int(layout_hints.get("col", 0))
                    span_w = int(layout_hints.get("width", total_cols))
                    span_h = int(layout_hints.get("height", 1))
                    overlay_zone = get_zone_rect_tight(row_hint, col_hint, span_w, span_h, geom)
                    dial_radius = custom_dial_size if custom_dial_size is not None else getattr(cfg, "DIAL_SIZE", 50)
                    panel_half = (dial_radius * 2 + 20) / 2.0
                    y_offset = float(layout_hints.get("y_offset", 0))
                    positions = []
                    if overlay_zone.width > 0:
                        for idx in range(8):
                            slot_width = overlay_zone.width / 8.0
                            cx = overlay_zone.left + slot_width * (idx + 0.5)
                            cy = overlay_zone.top + panel_half + y_offset
                            positions.append((cx, cy))
                        overlay_positions = positions
            
            sm = getattr(state_manager, "manager", None)
            _mod_id = _get_module_attr("MODULE_ID", "MODULE")  # Get once for all iterations

            for i in range(8):
                row = i // total_cols
                col = i % total_cols
                rect = get_grid_cell_rect(row, col, total_rows, total_cols)
                dial_id = i + 1

                ctrl_id = _get_module_attr("SLOT_TO_CTRL", {}).get(dial_id)
                meta = _SLOT_META.get(dial_id) or custom_controls.get(ctrl_id) or {}

                owned = dial_id in owned_slots
                if owned:
                    label = meta.get("label", f"Slot {dial_id}")
                    rng = meta.get("range", [0, 127])
                    opts = meta.get("options")
                    typ = meta.get("type", "raw")
                    greyed_out = False
                else:
                    label = "EMPTY"
                    rng = [0, 127]
                    opts = None
                    typ = "raw"
                    greyed_out = True

                uid = f"{_mod_id}.{label}.{dial_id}"
                cfg_dict = {
                    "id": dial_id,
                    "label": label,
                    "range": rng,
                    "options": opts,
                    "type": typ,
                    "greyed_out": greyed_out,
                    "visual_mode": meta.get("visual_mode", "default"),
                }
                
                # Apply custom dial size if specified
                if custom_dial_size is not None:
                    cfg_dict["dial_size"] = custom_dial_size

                # Only create visible dials that belong to the module
                if not greyed_out:
                    w = DialWidget(uid, rect, cfg_dict)
                    if overlay_positions and dial_id <= len(overlay_positions):
                        cx, cy = overlay_positions[dial_id - 1]
                        panel_size = w.dial.radius * 2 + 20
                        w.dial.cx = int(round(cx))
                        w.dial.cy = int(round(cy))
                        w.rect = pygame.Rect(0, 0, int(round(panel_size)), int(round(panel_size)))
                        w.rect.center = (int(round(cx)), int(round(cy)))
                    _ACTIVE_WIDGETS.append(w)
                else:
                    showlog.debug(f"[{_mod_id}] Skipping empty dial slot {dial_id}")

            showlog.debug(f"[MODULE_BASE] Created {_LOGTAG} DialWidgets with real metadata")
            
            # Populate dialhandlers.dials for compatibility (8 slots, some may be None for empty slots)
            dial_objs = [None] * 8
            for widget in _ACTIVE_WIDGETS:
                dial = getattr(widget, "dial", None)
                if dial:
                    dial_id = getattr(dial, "id", 0)
                    if 1 <= dial_id <= 8:
                        dial_objs[dial_id - 1] = dial
            
            showlog.info(f"*[{_LOGTAG}] 📋 About to set {len([d for d in dial_objs if d])} dials via dialhandlers.set_dials()")
            dialhandlers.set_dials(dial_objs)
            showlog.verbose(f"[{_LOGTAG}] Populated dialhandlers.dials with {len([d for d in dial_objs if d])} dial objects")

            try:
                module_id = _get_module_attr("MODULE_ID", "MODULE")
                cc_registry.attach_mapping_to_dials(module_id, dial_objs)
                global _MAPPED_SRC
                _MAPPED_SRC = module_id
                showlog.debug(f"[{_LOGTAG}] Attached StateManager mapping for module '{module_id}'")
            except Exception as exc:
                showlog.warn(f"[{_LOGTAG}] Failed to attach StateManager mapping: {exc}")

        except Exception as e:
            showlog.error(f"[MODULE_BASE] Failed to create DialWidgets: {e}")

        # ====================================================================
        # Apply INIT_STATE to newly created dials (first draw only)
        # ====================================================================
        if _ACTIVE_WIDGETS:
            plugin_id = _get_module_attr("PLUGIN_ID", _get_module_attr("MODULE_ID", "UNKNOWN"))
            page_key = f"{plugin_id}:main"
            
            # Priority 1: Check for LIVE state (user has modified values before)
            if plugin_id in dialhandlers.live_states and "main" in dialhandlers.live_states[plugin_id]:
                live_state = dialhandlers.live_states[plugin_id]["main"]
                
                # Handle both old format (list) and new format (dict)
                if isinstance(live_state, dict):
                    dial_vals = live_state.get("dials", [])
                elif isinstance(live_state, list):
                    dial_vals = live_state  # Legacy format
                else:
                    dial_vals = []
                
                if dial_vals:
                    showlog.info(f"[{_LOGTAG}] Restoring LIVE state to {len(_ACTIVE_WIDGETS)} widgets")
                    _apply_state_to_dials(dial_vals, "LIVE")
            
            # Priority 2: Apply INIT_STATE on first visit
            elif page_key not in dialhandlers.visited_pages:
                init_state = _get_module_attr("INIT_STATE", {})
                dial_vals = init_state.get("dials", [])
                
                if dial_vals:
                    showlog.info(f"[{_LOGTAG}] Applying INIT_STATE to {len(_ACTIVE_WIDGETS)} widgets (first visit)")
                    _apply_state_to_dials(dial_vals, "INIT")
                    
                    # DON'T mark as visited yet - we still need to initialize widget dials
                    # This happens after _load_custom_widget() below
        # ====================================================================
        # END INIT_STATE APPLICATION
        # ====================================================================



    device_name = getattr(dialhandlers, "current_device_name", None)

    # ---------- draw side buttons (match page_dials style) ----------
    btn_fill          = helper.theme_rgb(device_name, "BUTTON_FILL",           "#071C3C")
    btn_outline       = helper.theme_rgb(device_name, "BUTTON_OUTLINE",        "#0D3A7A")
    btn_text          = helper.theme_rgb(device_name, "BUTTON_TEXT",           "#FFFFFF")
    btn_disabled_fill = helper.theme_rgb(device_name, "BUTTON_DISABLED_FILL",  "#1E1E1E")
    btn_disabled_text = helper.theme_rgb(device_name, "BUTTON_DISABLED_TEXT",  "#646464")
    btn_active_fill   = helper.theme_rgb(device_name, "BUTTON_ACTIVE_FILL",    "#0050A0")
    btn_active_text   = helper.theme_rgb(device_name, "BUTTON_ACTIVE_TEXT",    "#FFFFFF")

    font_label = pygame.font.SysFont("arial", 20)
    btn_w, btn_h = 50, 50

    global button_rects
    button_rects.clear()
    _local_map = {}

    # ------------------------------------------------------------------
    # Resolve button labels from the module's own BUTTONS config
    # ------------------------------------------------------------------
    # Define sy function to apply offset_y (match page_dials pattern)
    def sy(y):
        return y + offset_y

    # Build simple id→label map from plugins.<plugin>.BUTTONS
    module_buttons = getattr(_ACTIVE_MODULE, "BUTTONS", [])
    button_label_map = {}
    button_meta_map = {}  # Store full button metadata
    
    for entry in module_buttons:
        if not isinstance(entry, dict):
            continue
        btn_id = str(entry.get("id", "")).strip()
        button_meta_map[btn_id] = entry
        
        # Check if this is a multi-state button
        states = entry.get("states") or entry.get("options")
        if states and isinstance(states, list) and len(states) > 1:
            # Multi-state button: use current state as label
            current_idx = _BUTTON_STATES.get(btn_id, 0)
            current_idx = max(0, min(current_idx, len(states) - 1))
            state = states[current_idx]
            # Extract label from state (handle both dict and string formats)
            if isinstance(state, dict):
                label = str(state.get("label", str(current_idx)))
            else:
                label = str(state)
            showlog.debug(f"[{_LOGTAG}] Button {btn_id} multi-state: idx={current_idx}, label='{label}', states={states}")
        else:
            # Regular button: use label field
            label = str(entry.get("label", "")).strip()
            # fallback to short form of action if no label
            if not label:
                act = str(entry.get("action", "")).strip()
                label = act[:2].upper() if act else btn_id
        
        button_label_map[btn_id] = label

    # Provide empty defaults if missing
    left_label_map = {k: v for k, v in button_label_map.items() if k in {"1","2","3","4","5"}}
    right_label_map = {k: v for k, v in button_label_map.items() if k in {"6","7","8","9","10"}}


    # LEFT column (1–5)
    for i, name in enumerate(["1", "2", "3", "4", "5"]):
        x = cfg.BUTTON_OFFSET_X
        y = sy(cfg.BUTTON_OFFSET_Y + i * (btn_h + cfg.BUTTON_SPACING_Y))
        rect = pygame.Rect(x, y, btn_w, btn_h)
        button_rects.append((rect, name))
        _local_map[name] = rect

        display_label = left_label_map.get(name, name)
        is_disabled = name not in left_label_map

        ui_button.draw_button(
            screen, rect, display_label, font_label,
            pressed_button, selected_buttons,
            button_id=name, disabled=is_disabled,
            fill_color=btn_fill, outline_color=btn_outline, text_color=btn_text,
            disabled_fill=btn_disabled_fill, disabled_text=btn_disabled_text,
            active_fill=btn_active_fill, active_text=btn_active_text
        )

    # RIGHT column (6–10)
    for i, name in enumerate(["6", "7", "8", "9", "10"]):
        x = screen.get_width() - cfg.BUTTON_OFFSET_X - btn_w
        y = sy(cfg.BUTTON_OFFSET_Y + i * (btn_h + cfg.BUTTON_SPACING_Y))
        rect = pygame.Rect(x, y, btn_w, btn_h)
        button_rects.append((rect, name))
        _local_map[name] = rect

        display_label = right_label_map.get(name, name)
        is_disabled = name not in right_label_map

        ui_button.draw_button(
            screen, rect, display_label, font_label,
            pressed_button, selected_buttons,
            button_id=name, disabled=is_disabled,
            fill_color=btn_fill, outline_color=btn_outline, text_color=btn_text,
            disabled_fill=btn_disabled_fill, disabled_text=btn_disabled_text,
            active_fill=btn_active_fill, active_text=btn_active_text
        )


    # check for modular widget first - draw BEFORE dials so dials appear on top
    widget = _load_custom_widget()
    if widget:
        # ====================================================================
        # Register widget's internal dials (e.g., DrawBarWidget speed dial)
        # ====================================================================
        # Only register once - _WIDGET_SLOT_DIALS persists across draws
        if hasattr(widget, 'get_speed_dial') and not _WIDGET_SLOT_DIALS:
            speed_dial = widget.get_speed_dial()
            slot = getattr(speed_dial, "id", None)
            if slot and register_widget_dial(slot, speed_dial, visual_mode="hidden"):
                showlog.verbose(f"[{_LOGTAG}] Registered widget speed dial in slot {slot}")
                
                # Apply INIT_STATE to widget dial immediately after registration (first draw only)
                plugin_id = _get_module_attr("PLUGIN_ID", _get_module_attr("MODULE_ID", "UNKNOWN"))
                page_key = f"{plugin_id}:main"
                
                # Priority 1: LIVE state
                dial_vals = []
                state_type = "DEFAULT"
                
                if plugin_id in dialhandlers.live_states and "main" in dialhandlers.live_states[plugin_id]:
                    live_state = dialhandlers.live_states[plugin_id]["main"]
                    if isinstance(live_state, dict):
                        dial_vals = live_state.get("dials", [])
                    elif isinstance(live_state, list):
                        dial_vals = live_state
                    if dial_vals:
                        state_type = "LIVE"
                
                # Priority 2: INIT state (only if not visited yet)
                elif page_key not in dialhandlers.visited_pages:
                    init_state = _get_module_attr("INIT_STATE", {})
                    dial_vals = init_state.get("dials", [])
                    if dial_vals:
                        state_type = "INIT"
                        dialhandlers.visited_pages.add(page_key)
                        showlog.verbose(f"[{_LOGTAG}] Marked {page_key} as visited (after widget dial init)")

                # Apply to widget dial
                if dial_vals and state_type != "DEFAULT" and 1 <= slot <= len(dial_vals):
                    val = dial_vals[slot - 1]
                    try:
                        speed_dial.set_value(val)
                        if hasattr(speed_dial, "label"):
                            label = getattr(speed_dial, "label", f"Slot {slot}")
                            if hasattr(speed_dial, "display_text"):
                                speed_dial.display_text = f"{label}: {val}"
                        showlog.verbose(f"[{_LOGTAG}] {state_type} - Widget dial (slot {slot}) initialized to {val}")
                    except Exception as e:
                        showlog.error(f"[{_LOGTAG}] Error initializing widget dial {slot}: {e}")
        # ====================================================================
        
        widget.draw(screen, device_name=device_name, offset_y=offset_y)
    else:
        showlog.verbose(f"[{_LOGTAG}] No custom widget for this plugin")

    globals()["button_rects_map"] = _local_map
    
    # Draw grid dials AFTER widget so they appear on top
    if bank_manager:
        try:
            bank_manager.draw(screen, device_name=device_name, offset_y=offset_y)
        except Exception as e:
            showlog.warn(f"[MODULE_BASE] DialBankManager draw failed: {e}")
    else:
        try:
            for w in _ACTIVE_WIDGETS:
                # Skip dial 2 if we have a DrawBarWidget (it renders the dial itself)
                if _CUSTOM_WIDGET_INSTANCE and hasattr(_CUSTOM_WIDGET_INSTANCE, 'background_rect'):
                    if hasattr(w, 'dial') and getattr(w.dial, 'id', None) == 2:
                        continue  # Skip drawing dial 2, widget will render it
                w.draw(screen, device_name=device_name, offset_y=offset_y)
        except Exception as e:
            showlog.warn(f"[MODULE_BASE] draw grid DialWidgets failed: {e}")
    
    # Debug grid overlay (uncomment to enable)
    # Get GRID_ZONES from module if available
    # geom = get_grid_geometry()
    # if geom:
    #     grid_zones = getattr(_ACTIVE_MODULE, "GRID_ZONES", [])
    #     draw_debug_grid(screen, geom, grid_zones)

    # Draw preset save UI overlay (always drawn last, on top of everything)
    global _PRESET_UI
    if _PRESET_UI:
        if _PRESET_UI.active:
            showlog.debug(f"[{_LOGTAG}] _PRESET_UI is active, calling update() and draw()")
        _PRESET_UI.update()
        _PRESET_UI.draw(screen)
    else:
        # Only log once per draw cycle when it should be visible
        if hasattr(draw_ui, '_logged_missing_preset_ui'):
            pass
        else:
            showlog.debug(f"[{_LOGTAG}] _PRESET_UI is None in draw_ui")
            draw_ui._logged_missing_preset_ui = True




# ----------------------------------------------------------------------------
# Shared logic for handling dial changes (UI or hardware)
# ----------------------------------------------------------------------------
def _process_dial_change(dial_obj, meta, src_name, sm, msg_queue, hw_slot=None):
    """
    Process a dial value change (from either hardware or UI).
    Normalizes value to 0–127 and dispatches via _apply_snap_and_dispatch.
    
    Args:
        hw_slot: Hardware dial slot (1-8) if this is a hardware dial update, None for UI/mouse
    """
    if not dial_obj:
        return
    try:
        v = max(0, min(127, int(getattr(dial_obj, "value", 0))))
    except Exception:
        v = 0

    _apply_snap_and_dispatch(
        d=dial_obj,
        meta=meta or {},
        raw127=v,
        src_name=src_name,
        sm=sm,
        msg_queue=msg_queue,
        hw_slot=hw_slot
    )

def _apply_snap_and_dispatch(d, meta, raw127, src_name, sm, msg_queue, hw_slot=None):
    """
    Snap/scale raw127 using meta, update dial UI, dispatch module hook,
    persist state, and invalidate.
    
    Args:
        hw_slot: Hardware dial slot (1-8) if this is a hardware dial, None for UI/mouse updates
    """
    try:
        v = max(0, min(127, int(raw127)))
    except Exception:
        v = 0

    label = (meta or {}).get("label")
    opts  = (meta or {}).get("options")
    rng   = (meta or {}).get("range")

    # --- Dial Latch/Pickup Check (Hardware Dials Only) ---
    if hw_slot is not None:
        # Get target value from dial object (current visual position)
        target_value = getattr(d, "value", 0)
        
        # Check if this hardware dial should be latched
        should_dispatch = _check_dial_latch(hw_slot, v, target_value)
        
        if not should_dispatch:
            # Latched - don't update visual dial or dispatch to plugin
            return

    # --- Discrete options ---
    if isinstance(opts, list) and len(opts) > 1:
        step = 127.0 / (len(opts) - 1)
        idx = int(round(v / step))
        idx = max(0, min(len(opts) - 1, idx))
        snapped = int(round(idx * step))
        try:
            d.set_value(snapped)
        except Exception:
            d.value = snapped

        _dispatch_hook("on_dial_change", label, idx)

    # --- Ranged numeric ---
    elif isinstance(rng, (list, tuple)) and len(rng) == 2 and all(isinstance(x, int) for x in rng):
        lo, hi = rng
        steps = (hi - lo) + 1
        if 1 < steps <= 16:
            step = 127.0 / (steps - 1)
            idx = int(round(v / step))
            idx = max(0, min(steps - 1, idx))
            snapped = int(round(idx * step))
            out = lo + idx
        else:
            snapped = v
            out = int(round(lo + (hi - lo) * (v / 127.0)))

        try:
            d.set_value(snapped)
        except Exception:
            d.value = snapped

        _dispatch_hook("on_dial_change", label, out)

    # --- Default continuous ---
    else:
        try:
            d.set_value(v)
        except Exception:
            d.value = v
        _dispatch_hook("on_dial_change", label, int(d.value))

    # Persist state (if mapped)
    if sm and getattr(d, "sm_param_id", None):
        src = getattr(d, "sm_source_name", None) or src_name
        sm.set_value(src, d.sm_param_id, int(d.value))
    # Note: Some modules (VK8M) handle state in export_state() instead of state_manager

    # ============================================================================
    # LIVE STATE CAPTURE (plugin state persistence)
    # ============================================================================
    # Capture current dial values to live_states for persistence across page switches
    try:
        plugin_id = _get_module_attr("PLUGIN_ID", _get_module_attr("MODULE_ID", None))
        if plugin_id:
            dials = getattr(dialhandlers, "dials", None)
            if dials:
                # Collect current dial values
                dial_values = [int(getattr(dial, "value", 0)) for dial in dials]
                
                # Initialize plugin entry in live_states if needed
                if plugin_id not in dialhandlers.live_states:
                    dialhandlers.live_states[plugin_id] = {}
                
                # Store as dict with dials/buttons/widget structure
                if "main" not in dialhandlers.live_states[plugin_id]:
                    dialhandlers.live_states[plugin_id]["main"] = {
                        "dials": dial_values,
                        "buttons": _BUTTON_STATES.copy(),
                        "widget": {}
                    }
                else:
                    # Update existing entry
                    live_state = dialhandlers.live_states[plugin_id]["main"]
                    if isinstance(live_state, dict):
                        live_state["dials"] = dial_values
                    else:
                        # Legacy format - upgrade to dict
                        dialhandlers.live_states[plugin_id]["main"] = {
                            "dials": dial_values,
                            "buttons": _BUTTON_STATES.copy(),
                            "widget": {}
                        }
                
                showlog.verbose(f"[{_LOGTAG}] Captured LIVE state: {dial_values}")
    except Exception as e:
        showlog.warn(f"[{_LOGTAG}] Failed to capture live state: {e}")
    # ============================================================================
    # END LIVE STATE CAPTURE
    # ============================================================================

    if msg_queue is not None:
        msg_queue.put(("invalidate", None))


def handle_event(event, msg_queue):
    global pressed_button, selected_buttons, _PRESET_UI

    # Check preset UI first (it blocks other events when active)
    if _PRESET_UI and _PRESET_UI.handle_event(event):
        if msg_queue:
            msg_queue.put(("invalidate", None))
        return

    sm = getattr(state_manager, "manager", None)
    src_name = _get_module_attr("MODULE_ID")

    # Check custom widget (ADSR, etc.) - it sets itself dirty in handle_event
    widget = _CUSTOM_WIDGET_INSTANCE
    if widget and widget.handle_event(event):
        return  # App will detect dirty widget and trigger burst

    # --------------------------------------------------------------
    # TEMP TEST — route event to new DialWidgets first
    # --------------------------------------------------------------
    try:
        for w in _ACTIVE_WIDGETS:
            if w.handle_event(event):
                # Widget sets itself dirty in handle_event
                    _process_dial_change(
                        dial_obj=w.dial,
                        meta=_SLOT_META.get(w.dial.id) or {},
                        src_name=_get_module_attr("MODULE_ID"),
                        sm=sm,
                        msg_queue=msg_queue
                    )
                    return
    except Exception as e:
        showlog.warn(f"[MODULE_BASE] DialWidget event dispatch failed: {e}")

    # --------------------------------------------------------------
    # Side button press detection → dispatch to module hook
    # --------------------------------------------------------------
    if event.type == pygame.MOUSEBUTTONDOWN and hasattr(event, "pos"):
        hit_any = False
        for d in (dialhandlers.dials or []):
            if _dial_hit(d, event.pos):
                d.dragging = True
                hit_any = True
        if not hit_any:
            for rect, name in button_rects:
                if rect.collidepoint(event.pos):
                    pressed_button = name
                    showlog.info(f"[{_LOGTAG}] Button {name} clicked")
                    
                    # Special handling for preset load button (button 7) - BEFORE multi-state check
                    if name == "7":
                        showlog.info(f"[{_LOGTAG}] Button 7 (presets) - navigating to module_presets")
                        # Navigate to module presets page
                        if msg_queue:
                            msg_queue.put(("ui_mode", "module_presets"))
                            msg_queue.put(("invalidate", None))
                        break
                    
                    # Special handling for preset save button (button 9) - BEFORE multi-state check
                    if name == "9":
                        showlog.debug(f"[{_LOGTAG}] === BUTTON 9 (SAVE PRESET) CLICKED ===")
                        showlog.debug(f"[{_LOGTAG}] About to call show_preset_save_ui()")
                        show_preset_save_ui()
                        showlog.debug(f"[{_LOGTAG}] show_preset_save_ui() returned")
                        pressed_button = None
                        selected_buttons.discard(name)
                        if msg_queue:
                            showlog.debug(f"[{_LOGTAG}] Sending invalidate and force_redraw messages")
                            msg_queue.put(("invalidate", None))
                            msg_queue.put(("force_redraw", 10))  # Force immediate redraw
                        showlog.debug(f"[{_LOGTAG}] Button 9 handling complete")
                        break
                    
                    # Check if this is a multi-state button
                    module_buttons = _get_module_attr("BUTTONS", [])
                    btn_meta = None
                    for btn in module_buttons:
                        if isinstance(btn, dict) and str(btn.get("id")) == name:
                            btn_meta = btn
                            break
                    
                    # Handle multi-state button
                    if btn_meta:
                        states = btn_meta.get("states") or btn_meta.get("options")
                        if states and isinstance(states, list) and len(states) > 1:
                            # Advance to next state
                            current_idx = _BUTTON_STATES.get(name, 0)
                            next_idx = (current_idx + 1) % len(states)
                            _BUTTON_STATES[name] = next_idx
                            showlog.info(f"[{_LOGTAG}] Multi-state button {name}: {current_idx} → {next_idx}, _BUTTON_STATES={_BUTTON_STATES}")
                            
                            # Get state value (if state is dict, extract data)
                            state = states[next_idx]
                            if isinstance(state, dict):
                                state_data = state
                                state_label = state_data.get("label", str(next_idx))
                            else:
                                state_data = {"label": str(state)}
                                state_label = str(state)
                            
                            showlog.info(f"[{_LOGTAG}] Button {name} → {state_label} (index {next_idx})")
                            
                            # Try to call a method named after the state label (e.g., "v1", "off", "slow")
                            method_name = state_label.lower().replace(" ", "_").replace("-", "_")
                            inst = _get_mod_instance()
                            state_method = getattr(inst, method_name, None) if inst else None
                            
                            if state_method and callable(state_method):
                                # Call the state-specific method (e.g., def v1(self):)
                                showlog.debug(f"[{_LOGTAG}] Calling state method: {method_name}()")
                                try:
                                    state_method()
                                except Exception as e:
                                    showlog.error(f"[{_LOGTAG}] State method {method_name}() failed: {e}")
                            else:
                                # Fallback: dispatch to on_button with state index AND state data
                                _dispatch_hook("on_button", str(name), next_idx, state_data)
                            
                            if msg_queue:
                                msg_queue.put(("force_redraw", 10))
                            break
                    
                    # For non-multi-state buttons, dispatch to on_button
                    _dispatch_hook("on_button", str(name))
                    if msg_queue:
                        msg_queue.put(("invalidate", None))
                    break

    elif event.type == pygame.MOUSEBUTTONUP:
        pressed_button = None  # <— reset visual state
        for d in (dialhandlers.dials or []):
            if d and getattr(d, "dragging", False):
                d.dragging = False

    elif event.type == pygame.MOUSEMOTION and hasattr(event, "pos"):
        for d in (dialhandlers.dials or []):
            if d and getattr(d, "dragging", False):
                d.update_from_mouse(*event.pos)
                ctrl_id = _get_module_attr("SLOT_TO_CTRL", {}).get(d.id)
                if not ctrl_id:
                    continue
                meta = _SLOT_META.get(d.id) or {}
                _apply_snap_and_dispatch(
                    d=d, meta=meta, raw127=int(d.value),
                    src_name=src_name, sm=sm, msg_queue=msg_queue
                )


# ----------------------------------------------------------------------------
# Hardware dial handler
# ----------------------------------------------------------------------------
def handle_hw_dial(dial_id: int, value: int, msg_queue=None) -> bool:
    """
    Handle a hardware/touchscreen dial move on the module page.
    Routes to new DialWidgets or legacy dials as fallback.
    """
    global _ACTIVE_WIDGETS

    dial_id = int(dial_id)
    v = max(0, min(127, int(value)))
    sm = getattr(state_manager, "manager", None)
    src_name = _get_module_attr("MODULE_ID")
    meta = _SLOT_META.get(dial_id) or {}

    # 1️⃣ Try new widget system first
    try:
        for w in _ACTIVE_WIDGETS:
            if getattr(w.dial, "id", None) == dial_id:
                    w.dial.set_value(v)
                    if hasattr(w, "mark_dirty"):
                        w.mark_dirty()
                    else:
                        w.dirty = True  # Mark widget as needing redraw
                    _process_dial_change(
                        dial_obj=w.dial,
                        meta=meta,
                        src_name=src_name,
                        sm=sm,
                        msg_queue=msg_queue,
                        hw_slot=dial_id  # Pass hardware slot for latch system
                    )
                    return True
    except Exception as e:
        showlog.warn(f"[MODULE_BASE] handle_hw_dial (widget) failed: {e}")

    # 2️⃣ Fallback to legacy dials (for modules still using dialhandlers)
    try:
        dials = getattr(dialhandlers, "dials", None)
        if not dials or dial_id < 1 or dial_id > len(dials):
            return False
        d = dials[dial_id - 1]
        d.set_value(v)
        _process_dial_change(
            dial_obj=d,
            meta=meta,
            src_name=src_name,
            sm=sm,
            msg_queue=msg_queue,
            hw_slot=dial_id  # Pass hardware slot for latch system
        )
        return True
    except Exception as e:
        showlog.error(f"[MODULE_BASE] handle_hw_dial legacy failed: {e}")
        return False


