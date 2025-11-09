"""UI coordination helpers for the Drumbo sampler module."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

import config as cfg
import showlog

from plugins.sampler.core.utils import normalize_bank


class LegacyUISyncService:
    """Encapsulate Drumbo's legacy widget and bank wiring logic."""

    def activate_bank(self, module: Any, bank_key: str) -> None:
        """Switch the active dial bank, syncing registry, widget state, and CC bindings."""
        target = (bank_key or "A").strip().upper()
        if target not in {"A", "B"}:
            showlog.warn(f"[Drumbo] Ignoring request to activate unknown bank '{bank_key}'")
            return

        showlog.debug(f"*[Drumbo] _activate_bank requested target={target}")
        registry_source = module.BANK_A_REGISTRY if target == "A" else module.BANK_B_REGISTRY
        module.REGISTRY = registry_source.copy()
        module.current_bank = target
        module.button_states["2"] = 0 if target == "A" else 1
        self.push_button_states(module)

        manager = self.ensure_bank_setup(module)
        showlog.debug(f"*[Drumbo] _ensure_bank_setup returned manager={bool(manager)}")

        module_base = module._get_module_base()
        if not module_base:
            showlog.warn(f"[Drumbo] module_base unavailable during bank activation for {target}")
            return

        slot_map = module._slot_map_for_bank(target)
        if not module_base.set_slot_to_ctrl_mapping(slot_map):
            showlog.warn(f"[Drumbo] Failed to update SLOT_TO_CTRL for bank {target}")
        else:
            showlog.debug(f"*[Drumbo] SLOT_TO_CTRL mapping updated for bank {target}")

        if not module_base.set_active_dial_bank(target):
            showlog.warn(f"[Drumbo] Dial bank switch to {target} was rejected by module_base")
        else:
            showlog.debug(f"*[Drumbo] module_base accepted bank {target} as active dial bank")

        self.refresh_widget_bank_refs(module, manager)
        showlog.debug("*[Drumbo] Widget bank refs refreshed")

        if module.widget and hasattr(module.widget, "active_bank"):
            module.widget.active_bank = target
            module.widget.mark_dirty()
            showlog.debug(f"*[Drumbo] Widget active_bank set to {target}")

        try:
            from system import cc_registry

            cc_registry.load_from_module(module.MODULE_ID, module.REGISTRY, None)
        except Exception as exc:  # pragma: no cover - legacy path logging
            showlog.warn(f"[Drumbo] cc_registry refresh failed during bank switch: {exc}")

        showlog.info(f"*[Drumbo] Active bank set to {target}")

    def ensure_bank_setup(self, module: Any, default_bank: Optional[str] = None):
        """Make sure dial bank widgets exist and are visible for the requested bank."""
        module_base = module._get_module_base()
        if not module_base:
            showlog.debug("[Drumbo] module_base unavailable during bank setup")
            return None

        manager = module_base.get_dial_bank_manager()
        if manager:
            manager.build_widgets()
            if hasattr(manager, "set_show_all_banks"):
                manager.set_show_all_banks(True)
            for bank_key in ("A", "B"):
                if bank_key in manager.bank_widgets:
                    manager.set_bank_visible(bank_key, True)
            if default_bank and default_bank in manager.bank_widgets:
                module_base.set_active_dial_bank(default_bank)
            return manager

        config = module._get_bank_config()
        active = module_base.configure_dial_banks(config, default_bank=default_bank or module.current_bank)
        if active:
            module.current_bank = active
            module.button_states["2"] = 0 if active == "A" else 1
        slot_map = module._slot_map_for_bank(module.current_bank)
        module_base.set_slot_to_ctrl_mapping(slot_map)
        manager = module_base.get_dial_bank_manager()
        if manager and hasattr(manager, "set_show_all_banks"):
            manager.set_show_all_banks(True)
            for bank_key in ("A", "B"):
                if bank_key in manager.bank_widgets:
                    manager.set_bank_visible(bank_key, True)
        self.refresh_widget_bank_refs(module, manager)
        return manager

    def refresh_widget_bank_refs(self, module: Any, manager=None) -> None:
        """Update widget dial references so UI rows mirror the dial bank manager."""
        if not module.widget:
            return

        if manager is None:
            module_base = module._get_module_base()
            if module_base:
                manager = module_base.get_dial_bank_manager()
            else:
                manager = None

        if not manager or not getattr(manager, "bank_widgets", None):
            return

        self.position_mini_dials(module, manager)
        module.widget.mic_dials_row_1 = [w.dial for w in manager.bank_widgets.get("A", [])]
        module.widget.mic_dials_row_2 = [w.dial for w in manager.bank_widgets.get("B", [])]

    def push_button_states(self, module: Any) -> None:
        """Propagate button state changes to dialhandlers and cached legacy trackers."""
        try:
            import dialhandlers

            state_copy = dict(module.button_states)
            dialhandlers.update_button_state(module.MODULE_ID, "button_states", state_copy)
            module_base = module._get_module_base()
            for btn_id, btn_state in state_copy.items():
                dialhandlers.update_button_state(module.MODULE_ID, f"button_{btn_id}", btn_state)
                if module_base:
                    module_base._BUTTON_STATES[str(btn_id)] = btn_state

            if module_base:
                module_base._BUTTON_STATES.setdefault("1", state_copy.get("1", 0))
                module_base._BUTTON_STATES.setdefault("2", state_copy.get("2", 0))

            if hasattr(dialhandlers, "msg_queue") and dialhandlers.msg_queue:
                dialhandlers.msg_queue.put(("force_redraw", 5))
        except Exception as exc:  # pragma: no cover - defensive logging
            showlog.debug(f"[Drumbo] Failed to push button states: {exc}")

    def set_instrument(self, module: Any, instrument: str, *, force_apply: bool = False) -> None:
        """Switch the active instrument while preserving legacy widget hooks."""
        target = (instrument or "snare").strip().lower()
        if target not in {"snare", "kick"}:
            target = "snare"

        previous = (module.current_instrument or "snare").strip().lower()
        if previous not in module._instrument_bank_values:
            previous = "snare"

        changed = target != previous
        if changed:
            module._capture_instrument_values(previous)

        module.current_instrument = target

        if changed or force_apply:
            module._apply_instrument_values(target)
        else:
            module._update_preset_snapshot()

        if module.widget:
            try:
                if changed:
                    module.widget.set_instrument(target)
                else:
                    module.widget.mark_dirty()
            except Exception as exc:  # pragma: no cover - legacy widget protection
                showlog.debug(f"[Drumbo] Widget instrument update failed: {exc}")

        module.button_states["1"] = 0 if target == "snare" else 1
        self.push_button_states(module)
        if changed:
            showlog.info(f"[Drumbo] Instrument page set to {target.upper()}")

    def position_mini_dials(self, module: Any, manager) -> None:
        """Lay out the miniature mic dials relative to the widget's geometry."""
        if not module.widget or not manager:
            return

        pygame_mod = module._get_pygame()
        if not pygame_mod or not hasattr(pygame_mod, "Rect"):
            showlog.debug("[Drumbo] pygame unavailable for dial positioning")
            return

        widget_rect = getattr(module.widget, "rect", None)
        if not widget_rect:
            return

        row_a_widgets = list(manager.bank_widgets.get("A", []))
        row_b_widgets = list(manager.bank_widgets.get("B", []))
        if not row_a_widgets and not row_b_widgets:
            return

        sample_radius = 0.0
        for collection in (row_a_widgets, row_b_widgets):
            for widget in collection:
                sample_radius = float(getattr(widget.dial, "radius", 0) or 0)
                if sample_radius > 0:
                    break
            if sample_radius > 0:
                break

        if sample_radius <= 0:
            sample_radius = float(getattr(cfg, "MINI_DIAL_RADIUS", getattr(cfg, "DIAL_SIZE", 25)))

        overrides = getattr(module.widget, "MINI_DIAL_LAYOUT_OVERRIDES", {}) or {}

        def _resolve(key: str, cfg_key: str, fallback: float) -> float:
            if key in overrides:
                try:
                    return float(overrides[key])
                except Exception:
                    pass
            return float(getattr(cfg, cfg_key, fallback))

        dial_diameter = sample_radius * 2.0
        label_padding_y = _resolve("label_padding", "MINI_DIAL_LABEL_PADDING_Y", 2.0)
        label_height = float(getattr(cfg, "LABEL_RECT_HEIGHT", 18) or 18)
        row_spacing = _resolve("row_spacing", "MINI_DIAL_ROW_SPACING", 23.0)
        top_padding = _resolve("top_padding", "MINI_DIAL_TOP_PADDING", 0.0)
        bottom_padding = _resolve("bottom_padding", "MINI_DIAL_BOTTOM_PADDING", 32.0)

        rows: Iterable[list] = [
            row_a_widgets[:4],
            row_a_widgets[4:8],
            row_b_widgets[:4],
            row_b_widgets[4:8],
        ]

        total_rows = len(rows)
        first_center = widget_rect.top + top_padding + sample_radius
        vertical_step = dial_diameter + label_padding_y + label_height + row_spacing
        row_centers = [
            int(round(first_center + idx * vertical_step))
            for idx in range(total_rows)
        ]

        if row_centers:
            max_bottom = widget_rect.bottom - bottom_padding
            last_bottom = row_centers[-1] + sample_radius + label_padding_y + label_height
            if last_bottom > max_bottom:
                shift = last_bottom - max_bottom
                row_centers = [int(round(center - shift)) for center in row_centers]
            min_top_allowed = widget_rect.top + top_padding + sample_radius
            if row_centers and row_centers[0] < min_top_allowed:
                offset = min_top_allowed - row_centers[0]
                row_centers = [int(round(center + offset)) for center in row_centers]

        cluster_offset_x = _resolve("cluster_offset_x", "MINI_DIAL_CLUSTER_OFFSET_X", 16.0)
        right_margin = _resolve("cluster_right_margin", "MINI_DIAL_CLUSTER_RIGHT_MARGIN", 32.0)

        cluster_left = widget_rect.left + widget_rect.width * 0.5 + cluster_offset_x
        cluster_right = widget_rect.right - right_margin
        if cluster_right <= cluster_left:
            cluster_left = widget_rect.left + cluster_offset_x
            cluster_right = widget_rect.right - right_margin

        available_width = max(0.0, cluster_right - cluster_left)
        if available_width <= 0:
            return

        columns = 4
        column_gap_setting = _resolve("column_gap", "MINI_DIAL_COLUMN_GAP", 18.0)
        min_total_width = columns * dial_diameter + (columns - 1) * column_gap_setting
        if available_width < min_total_width:
            effective_gap = max((available_width - columns * dial_diameter) / max(columns - 1, 1), 0.0)
        else:
            effective_gap = column_gap_setting

        total_span = columns * dial_diameter + (columns - 1) * effective_gap
        start_x = cluster_left + (available_width - total_span) / 2.0 + sample_radius
        column_centers = [
            int(round(start_x + idx * (dial_diameter + effective_gap)))
            for idx in range(columns)
        ]

        min_cx = int(round(cluster_left + sample_radius))
        max_cx = int(round(cluster_right - sample_radius))
        if max_cx < min_cx:
            max_cx = min_cx
        column_centers = [max(min_cx, min(max_cx, center)) for center in column_centers]

        panel_size = int(round(sample_radius * 2 + 20))
        raw_label_color = overrides.get("label_text_color")
        if not raw_label_color:
            raw_label_color = getattr(cfg, "MINI_DIAL_LABEL_TEXT_COLOR", None)
        if not raw_label_color:
            raw_label_color = module.THEME.get("drumbo_label_text_color")
        label_text_color = raw_label_color or "#FFFFFF"

        for row_idx, widgets in enumerate(rows):
            if not widgets:
                continue
            cy = row_centers[min(row_idx, len(row_centers) - 1)]
            for col_idx, widget in enumerate(widgets):
                if col_idx >= len(column_centers):
                    break
                cx = column_centers[col_idx]
                widget.rect = pygame_mod.Rect(0, 0, panel_size, panel_size)
                widget.rect.center = (cx, cy)
                widget.dial.cx = cx
                widget.dial.cy = cy

                dial = widget.dial
                dial.display_mode = getattr(dial, "display_mode", None) or "drumbo_mic"
                show_value_cfg = getattr(cfg, "MINI_DIAL_SHOW_VALUE", False)
                dial.show_value_on_label = bool(overrides.get("show_value", show_value_cfg))
                dial.custom_label_text = getattr(dial, "label", "")
                dial.custom_label_upper = True
                dial.label_text_color_override = label_text_color
                dial._label_key = None
                dial.cached_surface = None
                dial._shown_val_text = ""
                dial.dirty = True

                if hasattr(widget, "mark_dirty"):
                    widget.mark_dirty()

        if hasattr(module.widget, "mark_dirty"):
            try:
                module.widget.mark_dirty()
            except Exception:  # pragma: no cover - widget fallback safety
                pass

    def apply_mic_value(
        self,
        module: Any,
        mic_number: int,
        value: int,
        label: str,
        *,
        mark_dirty: bool = True,
        update_snapshot: bool = True,
        log_debug: bool = False,
        allow_headless: bool = False,
        instrument_key_override: Optional[str] = None,
    ) -> bool:
        """Write mic levels into the widget, module state, and preset snapshot caches."""
        safe_value = int(max(0, min(127, value)))
        row_index = 0 if mic_number <= 8 else 1
        slot_index = (mic_number - 1) % 8

        target_row = None
        if module.widget and hasattr(module.widget, "mic_dials_row_1"):
            row_one = getattr(module.widget, "mic_dials_row_1", [])
            row_two = getattr(module.widget, "mic_dials_row_2", [])
            source_rows = [row_one, row_two]
            target_row = source_rows[row_index] if row_index < len(source_rows) else None
        elif not allow_headless:
            return False

        if target_row is not None and not (0 <= slot_index < len(target_row)):
            if not allow_headless:
                showlog.debug(f"[Drumbo] No dial mapped for mic index {slot_index} in row {row_index}")
                return False
            target_row = None

        if target_row is not None:
            try:
                target_row[slot_index].set_value(safe_value)
            except Exception:
                target_row[slot_index].value = safe_value

            if mark_dirty:
                try:
                    module.widget.mark_dirty(dial=target_row[slot_index])
                except Exception:
                    pass

            if log_debug:
                showlog.debug(
                    f"*[Drumbo] Updated widget row {row_index + 1} dial {slot_index + 1} (label {label}) to {safe_value}"
                )

        if instrument_key_override:
            instrument_key = instrument_key_override.strip().lower()
        else:
            instrument_key = (module.current_instrument or "snare").strip().lower()
        instrument_state = module._instrument_bank_values.setdefault(
            instrument_key, {"A": [0] * 8, "B": [0] * 8}
        )
        bank_key = "A" if mic_number <= 8 else "B"
        bank_values = normalize_bank(instrument_state.get(bank_key))
        bank_values[slot_index] = safe_value
        instrument_state[bank_key] = bank_values

        variable = module.LABEL_TO_VARIABLE.get(label)
        if variable:
            try:
                setattr(module, variable, safe_value)
            except Exception:
                pass

        if update_snapshot:
            module._update_preset_snapshot()

        return True

    def replay_loaded_dials(self, module: Any, instrument: str) -> None:
        """Restore saved dial values by rerouting through apply_mic_value for consistency."""
        instrument_key = (instrument or "snare").strip().lower()
        state = module._instrument_bank_values.get(instrument_key)
        if not state:
            return

        label_map = {
            "A": ("M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8"),
            "B": ("M9", "M10", "M11", "M12", "M13", "M14", "M15", "M16"),
        }

        for bank_key, labels in label_map.items():
            values = normalize_bank(state.get(bank_key))
            for idx, label in enumerate(labels):
                try:
                    raw_value = int(values[idx])
                except (TypeError, ValueError):
                    raw_value = 0

                mic_number = idx + 1 if bank_key == "A" else idx + 9
                self.apply_mic_value(
                    module,
                    mic_number,
                    raw_value,
                    label,
                    mark_dirty=True,
                    update_snapshot=False,
                    log_debug=False,
                    allow_headless=True,
                    instrument_key_override=instrument_key,
                )

        module._update_preset_snapshot()