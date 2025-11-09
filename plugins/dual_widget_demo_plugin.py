# plugins/dual_widget_demo_plugin.py
import showlog
from core.plugin import Plugin as BasePlugin
from pages.module_base import ModuleBase


# -----------------------------------------------------------------------------
#  PLUGIN REGISTRATION  (auto-discovery entry point)
# -----------------------------------------------------------------------------
class DualWidgetDemoPlugin(BasePlugin):
    name = "Dual Widget Demo"
    version = "1.0"
    page_id = "dual_widget_demo"

    def on_load(self, app):
        # Register the host page (module_base orchestrates the UI)
        from pages import module_base

        app.page_registry.register(
            self.page_id,
            module_base,
            label="Dual Widget Demo",
            meta={"version": self.version},
        )


# -----------------------------------------------------------------------------
#  MODULE IMPLEMENTATION  (UI logic controlled by the host)
# -----------------------------------------------------------------------------
class DualWidgetDemoModule(ModuleBase):
    MODULE_ID = "dual_widget_demo"

    SLOT_TO_CTRL = {
        1: "main_dial_1",
        2: "main_dial_2",
    }

    CUSTOM_WIDGET = {
        "class": "WidgetA",
        "path": "widgets.widget_a_widget",
        "grid_size": [4, 2],
        "grid_pos": [0, 0],
    }

    _WIDGET_SPEC_MAP = {
        "widget_a": CUSTOM_WIDGET,
        "widget_b": {
            "class": "WidgetB",
            "path": "widgets.widget_b_widget",
            "grid_size": [4, 2],
            "grid_pos": [0, 0],
        },
    }

    REGISTRY = {
        MODULE_ID: {
            "01": {
                "label": "Main 1",
                "range": [0, 127],
                "type": "raw",
            },
            "02": {
                "label": "Main 2",
                "range": [0, 127],
                "type": "raw",
            },
        }
    }

    BUTTONS = [
        {
            "id": "1",
            "label": "Widget Mode",
            "behavior": "multi",
            "states": [
                {"label": "A", "value": "widget_a"},
                {"label": "B", "value": "widget_b"},
            ],
        }
    ]

    INIT_STATE = {
        "dials": [64, 96, 0, 0, 0, 0, 0, 0],
        "buttons": {"1": 0},
        "widget": {
            "active": "widget_a",
            "widget_a": {"dial1": 64, "dial2": 96},
            "widget_b": {"dial1": 32, "dial2": 112},
        },
    }

    THEME = {
        "plugin_background_color": (20, 20, 25),
        "dial_panel_color": (40, 40, 45),
        "dial_text_color": (230, 230, 230),
        "mini_dial_fill": (120, 180, 255),
        "mini_dial_outline": (60, 90, 130),
    }

    def __init__(self):
        super().__init__()

        init_state = self.INIT_STATE if isinstance(self.INIT_STATE, dict) else {}
        dial_defaults = init_state.get("dials", []) if isinstance(init_state.get("dials"), list) else []
        self._main_dials = [
            self._clamp_value(dial_defaults[0]) if len(dial_defaults) > 0 else 64,
            self._clamp_value(dial_defaults[1]) if len(dial_defaults) > 1 else 96,
        ]

        widget_defaults = init_state.get("widget", {}) if isinstance(init_state.get("widget"), dict) else {}
        self._widget_state_cache = self._build_widget_state_cache(widget_defaults)
        self._active_widget_id = widget_defaults.get("active", "widget_a")

        self.button_states = dict(init_state.get("buttons", {"1": 0}))
        self.widget = None

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------
    def on_init(self):
        self._sync_main_dials_to_host()
        self._load_widget(self._active_widget_id or "widget_a")

    def on_button(self, btn_id, state_index, state_data):
        if btn_id != "1":
            return

        target = (state_data or {}).get("value")
        if not target:
            showlog.debug(f"[{self.MODULE_ID}] Button 1 pressed without target widget")
            return

        self.button_states["1"] = int(state_index)
        self._load_widget(target)
        showlog.info(f"[{self.MODULE_ID}] Widget toggled to '{target}'")

    def on_dial_change(self, label, value):
        idx = {"Main 1": 0, "Main 2": 1}.get((label or "").strip())
        if idx is None:
            return

        clamped = self._clamp_value(value)
        self._main_dials[idx] = clamped

        active_id = self._active_widget_id
        if active_id in self._widget_state_cache:
            self._widget_state_cache[active_id][f"dial{idx + 1}"] = clamped

        if self.widget and hasattr(self.widget, "update_value"):
            self.widget.update_value(idx, clamped)

    # ------------------------------------------------------------------
    # Widget orchestration
    # ------------------------------------------------------------------
    def _load_widget(self, widget_id: str):
        widget_id = widget_id if widget_id in self._widget_state_cache else "widget_a"

        if self.widget:
            self._persist_widget_state(self._active_widget_id)
            self.detach_widget()

        self._active_widget_id = widget_id

        state = self._widget_state_cache.get(widget_id, {})
        self._main_dials[0] = self._clamp_value(state.get("dial1", self._main_dials[0]))
        self._main_dials[1] = self._clamp_value(state.get("dial2", self._main_dials[1]))
        self._sync_main_dials_to_host()

        host = self._host()
        spec = self._WIDGET_SPEC_MAP.get(widget_id, self.CUSTOM_WIDGET)

        if widget_id == "widget_a":
            host.clear_custom_widget_override(include_overlays=True)
        else:
            host.set_custom_widget_override(dict(spec), include_overlays=True)

        host.request_custom_widget_redraw(include_overlays=True)

    def attach_widget(self, widget):
        self.widget = widget
        widget_id = self._active_widget_id

        if hasattr(widget, "apply_theme"):
            widget.apply_theme(self.THEME)

        state = self._widget_state_cache.get(widget_id, {})
        if hasattr(widget, "set_state"):
            widget.set_state(state)

        if hasattr(widget, "on_change"):
            widget.on_change = lambda payload: self._handle_widget_change(widget_id, payload)

        host = self._host()
        host.request_custom_widget_redraw(include_overlays=True)

    def detach_widget(self):
        if not self.widget:
            return

        if hasattr(self.widget, "on_change"):
            self.widget.on_change = None

        self.widget = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _build_widget_state_cache(self, widget_defaults):
        base_states = {
            "widget_a": {"dial1": self._main_dials[0], "dial2": self._main_dials[1]},
            "widget_b": {"dial1": 32, "dial2": 112},
        }

        out = {}
        for widget_id, defaults in base_states.items():
            override = widget_defaults.get(widget_id, {}) if isinstance(widget_defaults, dict) else {}
            out[widget_id] = {
                "dial1": self._clamp_value(override.get("dial1", defaults["dial1"])),
                "dial2": self._clamp_value(override.get("dial2", defaults["dial2"])),
            }
        return out

    def _handle_widget_change(self, widget_id, payload):
        if not isinstance(payload, dict):
            return

        state = self._widget_state_cache.get(widget_id)
        if not state:
            return

        updated = {}
        for idx, key in enumerate(("dial1", "dial2")):
            if key in payload:
                value = self._clamp_value(payload[key])
                state[key] = value
                if widget_id == self._active_widget_id:
                    self._main_dials[idx] = value
                updated[key] = value

        if updated:
            self._sync_main_dials_to_host()
            showlog.debug(f"[{self.MODULE_ID}] Widget '{widget_id}' pushed {updated}")

    def _sync_main_dials_to_host(self):
        try:
            import dialhandlers

            dials = getattr(dialhandlers, "dials", None)
            if not dials:
                return

            for idx, value in enumerate(self._main_dials, start=1):
                if idx > len(dials):
                    break
                dial_obj = dials[idx - 1]
                if not dial_obj:
                    continue
                try:
                    dial_obj.set_value(value)
                except Exception:
                    dial_obj.value = value
                dial_obj.display_text = f"{getattr(dial_obj, 'label', f'Dial {idx}')}: {value}"
                if getattr(dialhandlers, "msg_queue", None):
                    dialhandlers.msg_queue.put(("update_dial_value", idx, value))
        except Exception as exc:
            showlog.debug(f"[{self.MODULE_ID}] Main dial sync skipped: {exc}")

    def _persist_widget_state(self, widget_id):
        if not self.widget or widget_id not in self._widget_state_cache:
            return
        try:
            state = self.widget.get_state()
        except Exception:
            return

        if isinstance(state, dict):
            self._widget_state_cache[widget_id].update({
                "dial1": self._clamp_value(state.get("dial1", self._main_dials[0])),
                "dial2": self._clamp_value(state.get("dial2", self._main_dials[1])),
            })

    @staticmethod
    def _host():
        from pages import module_base as host

        return host

    @staticmethod
    def _clamp_value(value):
        try:
            return max(0, min(127, int(value)))
        except Exception:
            return 0


# -----------------------------------------------------------------------------
#  EXPORT ALIAS FOR AUTO-DISCOVERY
# -----------------------------------------------------------------------------
Plugin = DualWidgetDemoPlugin
