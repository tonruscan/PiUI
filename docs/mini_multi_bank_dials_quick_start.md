# Mini & Multi-Bank Dials Quick Start Guide

## 1. Define Dial Metadata
- Extend `config/custom_dials.json` with controls that include labels, ranges, and optional `dial_size` overrides.
- Example snippet:
  ```json
  "mic_1": { "label": "M1", "range": [0, 127], "dial_size": 25 },
  "mic_9": { "label": "M9", "range": [0, 127], "dial_size": 25 }
  ```
- The mini-dial support relies on the update in `widgets/dial_widget.py`, which now honors the `dial_size` field to shrink the rendered dial when present.

## 2. Module Base Dial Bank Infrastructure
- `pages/module_base.py` hosts the `DialBankManager` that renders and swaps overlay dials.
- Key helpers now exposed to plugins:
  ```python
  from pages import module_base

  module_base.configure_dial_banks(bank_config, default_bank="A")
  module_base.set_active_dial_bank("B")
  manager = module_base.get_dial_bank_manager()
  ```
- Dirty-redraw routines (`get_dirty_widgets`, `get_all_widgets`, `redraw_dirty_widgets`) were extended to pull every bank’s widgets so both rows repaint correctly.

## 3. Describe Bank Layout in Your Plugin (Drumbo example)
- Add a reusable config describing dial banks and layout hints:
  ```python
  DIAL_BANK_CONFIG = {
      "A": {
          "ctrl_ids": ["mic_1", ..., "mic_8"],
          "layout": {"row": 0, "col": 0, "width": 4, "height": 1, "y_offset": -12},
          "dial_size": 25,
      },
      "B": {
          "ctrl_ids": ["mic_9", ..., "mic_16"],
          "layout": {"row": 1, "col": 0, "width": 4, "height": 1, "y_offset": -12},
          "dial_size": 25,
      },
  }
  SLOT_TO_CTRL = {idx + 1: ctrl for idx, ctrl in enumerate(DIAL_BANK_CONFIG["A"]["ctrl_ids"])}
  ```
- Initialize in `__init__`:
  ```python
  self.current_bank = "A"
  self.button_states = {"1": 0, "2": 0}
  self._ensure_bank_setup(default_bank=self.current_bank)
  ```
- Convert Button 2 into a bank selector:
  ```python
  {
      "id": "2",
      "behavior": "multi",
      "label": "BANK",
      "states": ["A", "B"],
  }
  ```

## 4. Bank Switching Logic
- Use `_activate_bank` (or similar) instead of rebuilding the UI:
  ```python
  def _activate_bank(self, bank_key):
      target = bank_key.upper()
      self.REGISTRY = (self.BANK_A_REGISTRY if target == "A" else self.BANK_B_REGISTRY).copy()
      self.current_bank = target
      self.button_states["2"] = 0 if target == "A" else 1

      module_base.configure_dial_banks(self._get_bank_config(), default_bank=target)
      module_base.set_slot_to_ctrl_mapping(self._slot_map_for_bank(target))
      module_base.set_active_dial_bank(target)

      self._refresh_widget_bank_refs()
      if self.widget and hasattr(self.widget, "active_bank"):
          self.widget.active_bank = target
          self.widget.mark_dirty()
  ```
- `_ensure_bank_setup` uses `configure_dial_banks` once, while `_refresh_widget_bank_refs` ensures the widget keeps references to both rows of Dial objects.

## 5. Widget Integration
- `DrumboMainWidget` tracks both dial rows and the visible bank indicator:
  ```python
  self.active_bank = "A"
  self.mic_dials_row_1 = []
  self.mic_dials_row_2 = []
  ```
- When the widget attaches, refresh dial references:
  ```python
  def _refresh_widget_bank_refs(self, manager=None):
      manager = manager or module_base.get_dial_bank_manager()
      if not manager:
          return
      self.widget.mic_dials_row_1 = [w.dial for w in manager.bank_widgets.get("A", [])]
      self.widget.mic_dials_row_2 = [w.dial for w in manager.bank_widgets.get("B", [])]
  ```
- The widget’s `draw` method now renders a “BANK A/B” badge in the corner to reflect the active bank.

## 6. Responding to Dial Changes
- Map M1–M16 labels to the correct dial row regardless of bank:
  ```python
  label = dial_label.strip().upper()
  mic_number = int(label[1:])  # M1 -> 1
  row = 0 if mic_number <= 8 else 1
  idx = (mic_number - 1) % 8
  target_row = self.widget.mic_dials_row_1 if row == 0 else self.widget.mic_dials_row_2
  target_row[idx].set_value(value)
  self.widget.mark_dirty()
  ```

## 7. Putting It All Together
1. Add mini-dial metadata (`dial_size`) in `custom_dials.json`.
2. Describe your banks using `DIAL_BANK_CONFIG` within the plugin.
3. During module init, call `_ensure_bank_setup` to configure `DialBankManager` and apply the default bank.
4. Wire a multi-state button (or other trigger) to call `_activate_bank` so `module_base` handles the swap.
5. Use `_refresh_widget_bank_refs` to give your widget access to both rows of Dial objects.
6. Update `on_dial_change` to route incoming values to the correct dial widgets.

Follow this pattern for any plugin that needs compact overlay dials and banked controls: define consistent metadata, configure the bank manager, and keep your widget references in sync with the active bank.
