# plugins/spectra_switch_plugin.py
import importlib
from typing import Any, Dict, Optional
import showlog
from pages import module_base as host
import dialhandlers
import custom_controls
from core.plugin import Plugin as BasePlugin
from system.module_core import ModuleBase


class SpectraSwitchModule(ModuleBase):
    MODULE_ID = "spectra_switch"

    SLOT_TO_CTRL = {1: "spectra_main_1", 2: "spectra_main_2"}

    REGISTRY = {
        MODULE_ID: {
            "type": "module",
            "01": {
                "label": "Spectra Main 1",
                "range": [0, 127],
                "type": "raw",
            },
            "02": {
                "label": "Spectra Main 2",
                "range": [0, 127],
                "type": "raw",
            },
        }
    }

    BUTTONS = [
        {
            "id": "1",
            "behavior": "multi",
            "states": [
                {"label": "Luma", "value": "widget_luma"},
                {"label": "Chroma", "value": "widget_chroma"},
            ],
        }
    ]

    THEME = {
        "plugin_background_color": (18, 18, 22),
        "dial_panel_color": (28, 28, 34),
        "dial_text_color": (230, 230, 230),
        "mini_dial_outline": (90, 90, 100),
        "mini_dial_fill": (160, 160, 210),
        "button_active_fill": (60, 120, 255),
    }

    _WIDGET_SPEC_MAP = {
        "widget_luma": {
            "class": "LumaWidget",
            "path": "widgets.luma_widget",
            "grid_size": [4, 2],
            "grid_pos": [0, 0],
        },
        "widget_chroma": {
            "class": "ChromaWidget",
            "path": "widgets.chroma_widget",
            "grid_size": [4, 2],
            "grid_pos": [0, 0],
        },
    }

    # Correct INIT_STATE: numeric floats, never control IDs as values
    INIT_STATE = {
        # Slot-indexed dial list (ModuleBase hydrates by slot order)
        "dials": [32, 95, 0, 0, 0, 0, 0, 0],
        "button_states": {"1": 0},
        "widget": {
            "active_id": "widget_luma",
            "snapshots": {
                "widget_luma": {"mini_a": 0.3, "mini_b": 0.7},
                "widget_chroma": {"mini_a": 0.5, "mini_b": 0.5},
            },
        },
    }

    def __init__(self):
        super().__init__()
        showlog.debug("*[DEF __init__ STEP 1] create module instance")
        self.button_states: Dict[str, int] = {}
        self._widget_state_cache: Dict[str, Dict[str, Any]] = {}
        self._active_widget_id: Optional[str] = None
        self._widget_instance = None
        self.theme = dict(self.THEME)

    # -------------------------
    # Lifecycle
    # -------------------------
    def on_init(self):
        showlog.debug("*[DEF on_init STEP 1] validating dial values")

        # Dial hydration handled by module_base.init_page; no manual overrides here.

        self.button_states = dict(self.INIT_STATE.get("button_states", {}))
        widget_block = self.INIT_STATE.get("widget", {})
        self._active_widget_id = widget_block.get("active_id", "widget_luma")
        self._widget_state_cache = dict(widget_block.get("snapshots", {}))
        self._load_active_widget()

    def on_button(self, btn_id: str, state_index: int, state_data: Dict[str, Any]):
        showlog.debug(f"*[DEF on_button STEP 1] btn_id={btn_id} idx={state_index}")
        if btn_id == "1":
            new_widget_id = state_data.get("value")
            showlog.debug(f"*[DEF on_button STEP 2] switch-> {new_widget_id}")
            self.button_states["1"] = state_index
            self._switch_widget(new_widget_id)
            return True
        return False

    def on_dial_change(self, ctrl_id: str, value: float):
        showlog.debug(f"*[DEF on_dial_change STEP 1] ctrl_id={ctrl_id} val={value}")
        if self._widget_instance and hasattr(self._widget_instance, "update_value"):
            self._widget_instance.update_value(ctrl_id, value)
        else:
            showlog.debug("*[DEF on_dial_change STEP 2] no widget instance active")
        return True

    def attach_widget(self, widget_obj):
        showlog.debug("*[DEF attach_widget STEP 1] attach widget instance")
        self._widget_instance = widget_obj
        if not widget_obj:
            showlog.warn(self.MODULE_ID, "attach_widget called with None")
            return

        def _on_change(payload: Dict[str, Any]):
            showlog.debug(f"*[DEF _on_change STEP 1] payload={payload}")
            if isinstance(payload, dict):
                self._widget_state_cache[self._active_widget_id] = payload

        widget_obj.on_change = _on_change
        snap = self._widget_state_cache.get(self._active_widget_id, None)
        if snap:
            showlog.debug(f"*[DEF attach_widget STEP 2] restore snap={snap}")
            widget_obj.set_state(snap)
        host.request_custom_widget_redraw(include_overlays=True)

    def detach_widget(self):
        showlog.debug("*[DEF detach_widget STEP 1] clearing widget instance")
        self._widget_instance = None

    def on_preset_loaded(self, data: Dict[str, Any]):
        showlog.debug("*[DEF on_preset_loaded STEP 1] restore preset data")
        self.button_states = dict(data.get("button_states", self.button_states))
        widget = data.get("widget", {})
        self._widget_state_cache = dict(widget.get("snapshots", self._widget_state_cache))
        self._active_widget_id = widget.get("active_id", self._active_widget_id)
        self._load_active_widget()

    def prepare_preset_save(self, data: Dict[str, Any]):
        showlog.debug("*[DEF prepare_preset_save STEP 1] capture current state")
        data["dials"] = self._capture_live_dials()
        data["button_states"] = dict(self.button_states)
        data["widget"] = {
            "active_id": self._active_widget_id,
            "snapshots": dict(self._widget_state_cache),
        }
        return data

    def _capture_live_dials(self) -> list:
        """Return the current dial snapshot as a slot-indexed list."""
        live_main = dialhandlers.live_states.get(self.MODULE_ID, {}).get("main")
        if isinstance(live_main, dict):
            dial_vals = live_main.get("dials", [])
        elif isinstance(live_main, list):
            dial_vals = live_main
        else:
            dial_vals = self.INIT_STATE.get("dials", [])

        values = list(dial_vals if isinstance(dial_vals, list) else [])
        while len(values) < 8:
            values.append(0)
        return values[:8]

    # -------------------------
    # Internal helpers
    # -------------------------
    def _load_active_widget(self):
        showlog.debug(f"*[DEF _load_active_widget STEP 1] active={self._active_widget_id}")
        spec = self._WIDGET_SPEC_MAP.get(self._active_widget_id)
        if not spec:
            showlog.error(self.MODULE_ID, f"Unknown widget id: {self._active_widget_id}")
            return
        host.set_custom_widget_override({
            "class": spec["class"],
            "path": spec["path"],
            "grid_size": spec["grid_size"],
            "grid_pos": spec["grid_pos"],
            "init_state": self._widget_state_cache.get(self._active_widget_id, None),
        })

    def _switch_widget(self, new_widget_id: str):
        showlog.debug(f"*[DEF _switch_widget STEP 1] new={new_widget_id}")
        if new_widget_id == self._active_widget_id:
            showlog.debug("*[DEF _switch_widget STEP 2] same id; skip")
            return
        if self._widget_instance and hasattr(self._widget_instance, "get_state"):
            self._widget_state_cache[self._active_widget_id] = self._widget_instance.get_state()
        host.clear_custom_widget_override()
        self._active_widget_id = new_widget_id
        self._load_active_widget()


class SpectraSwitchPlugin(BasePlugin):
    name = "Spectra Switch"
    version = "1.2.1"
    page_id = SpectraSwitchModule.MODULE_ID

    def on_load(self, app):
        showlog.debug("*[DEF on_load STEP 1] registering page spectra_switch")
        from pages import module_base as page
        app.page_registry.register(
            self.page_id,
            page,
            label="Spectra Switch",
            meta={"plugin": "spectra_switch", "version": self.version},
        )

    def on_unload(self, app):
        showlog.debug("*[DEF on_unload STEP 1] unload plugin")


Plugin = SpectraSwitchPlugin
