# preset_manager.py
"""
Modular preset saver/loader system.
Reads config/save_state_vars.json to determine what variables to save per page/module.
Stores presets in config/presets/<page_id>/<preset_name>.json
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
import showlog


class PresetManager:
    """
    Handles saving and loading presets for any page/module based on configuration.
    """
    
    def __init__(self, config_path: str = "config/save_state_vars.json"):
        """
        Initialize the preset manager.
        
        Args:
            config_path: Path to the save state variables configuration file
        """
        self.config_path = config_path
        self.presets_dir = Path("config/presets")
        self.config = self._load_config()
        
        # Ensure presets directory exists
        self.presets_dir.mkdir(parents=True, exist_ok=True)
        
        showlog.debug(f"[PresetManager] Initialized with config: {config_path}")
    
    def _load_config(self) -> Dict:
        """Load the save state variables configuration."""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            # Filter out comment keys
            return {k: v for k, v in config.items() if not k.startswith("_")}
        except FileNotFoundError:
            showlog.error(f"[PresetManager] Config file not found: {self.config_path}")
            return {}
        except json.JSONDecodeError as e:
            showlog.error(f"[PresetManager] Invalid JSON in config: {e}")
            return {}
    
    def get_page_config(self, page_id: str, module_instance=None) -> Optional[Dict]:
        """
        Get the configuration for a specific page/module.
        Priority order:
        1. Module's PRESET_STATE attribute (explicit declaration)
        2. Auto-discovered from module's REGISTRY (all slots automatically included)
        3. save_state_vars.json fallback
        
        Args:
            page_id: The page or module identifier (e.g., "vibrato", "mixer")
            module_instance: Optional module instance to check for PRESET_STATE
            
        Returns:
            Configuration dict or None if not found
        """
        # Priority 1: Check if module defines PRESET_STATE (explicit, self-contained)
        if module_instance and hasattr(module_instance, 'PRESET_STATE'):
            config = getattr(module_instance, 'PRESET_STATE')
            if config:
                showlog.debug(f"[PresetManager] Using PRESET_STATE from module for {page_id}")
                return config
        
        # Check module class for PRESET_STATE
        if module_instance:
            module_class = type(module_instance)
            if hasattr(module_class, 'PRESET_STATE'):
                config = getattr(module_class, 'PRESET_STATE')
                if config:
                    showlog.debug(f"[PresetManager] Using PRESET_STATE from module class for {page_id}")
                    return config
        
        # Priority 2: Auto-discover from REGISTRY (automatic, no config needed!)
        if module_instance and hasattr(module_instance, 'REGISTRY'):
            registry = getattr(module_instance, 'REGISTRY')
            if registry:
                # Extract all slot IDs from registry
                auto_config = self._auto_discover_from_registry(module_instance, registry)
                if auto_config:
                    showlog.debug(f"[PresetManager] Auto-discovered config from REGISTRY for {page_id}")
                    return auto_config
        
        # Priority 3: Fall back to save_state_vars.json
        config = self.config.get(page_id)
        if config:
            showlog.debug(f"[PresetManager] Using save_state_vars.json for {page_id}")
        return config
    
    def _auto_discover_from_registry(self, module_instance, registry: Dict) -> Optional[Dict]:
        """
        Auto-discover preset configuration from a module's REGISTRY.
        Extracts variables from registry entries (via "variable" field).
        Also checks for WIDGET_STATE, PRESET_VARS, and BUTTONS on the module.
        
        For buttons: looks for common state variable patterns like is_on, is_active, etc.
        
        Args:
            module_instance: The module instance
            registry: The module's REGISTRY dict
            
        Returns:
            Auto-generated config dict
        """
        try:
            variables = []
            registry_slots = []
            button_state_vars = []
            
            # Scan registry for slot IDs and linked variables
            for key, value in registry.items():
                if not isinstance(value, dict):
                    continue
                if value.get("type") == "module":
                    # This is the module-level entry, scan its slots
                    for slot_key, slot_data in value.items():
                        if slot_key in ["type", "label", "description"]:
                            continue
                        if isinstance(slot_data, dict):
                            registry_slots.append(slot_key)
                            # Check if this slot has a linked variable
                            var_name = slot_data.get("variable")
                            if var_name and var_name not in variables:
                                variables.append(var_name)
            
            # Auto-discover button state variables by checking common patterns
            # Check for is_on, is_active, enabled, etc. that are likely button states
            common_button_state_vars = ['is_on', 'is_active', 'enabled', 'bypass']
            for var_name in common_button_state_vars:
                if hasattr(module_instance, var_name):
                    val = getattr(module_instance, var_name)
                    # Only add boolean state variables
                    if isinstance(val, bool) and var_name not in variables:
                        button_state_vars.append(var_name)
                        variables.append(var_name)
            
            # Add module-level preset variables (PRESET_VARS) - for extra vars not in registry
            if hasattr(module_instance, 'PRESET_VARS'):
                preset_vars = getattr(module_instance, 'PRESET_VARS')
                if isinstance(preset_vars, list):
                    for var in preset_vars:
                        if var not in variables:
                            variables.append(var)
            
            module_class = type(module_instance)
            if hasattr(module_class, 'PRESET_VARS'):
                preset_vars = getattr(module_class, 'PRESET_VARS')
                if isinstance(preset_vars, list):
                    for var in preset_vars:
                        if var not in variables:
                            variables.append(var)
            
            # Get widget state if defined
            widget_state = []
            if hasattr(module_instance, 'WIDGET_STATE'):
                widget_state = getattr(module_instance, 'WIDGET_STATE') or []
            elif hasattr(module_class, 'WIDGET_STATE'):
                widget_state = getattr(module_class, 'WIDGET_STATE') or []
            
            config = {
                "variables": variables,
                "widget_state": widget_state,
                "registry_slots": registry_slots,
                "auto_discovered": True
            }
            
            showlog.debug(
                f"[PresetManager] Auto-discovered from REGISTRY: "
                f"{len(variables)} vars (including {len(button_state_vars)} button states), "
                f"{len(registry_slots)} slots"
            )
            return config
            
        except Exception as e:
            showlog.error(f"[PresetManager] Auto-discovery failed: {e}")
            return None
    
    def save_preset(self, page_id: str, preset_name: str, module_instance, widget=None) -> bool:
        """
        Save a preset for the given page/module.
        Saves module variables, widget state, registry values, and button states (1-5 only).
        
        Args:
            page_id: The page or module identifier
            preset_name: Name for this preset
            module_instance: The module instance to save state from
            widget: Optional widget instance to save widget state
            
        Returns:
            True if save successful, False otherwise
        """
        try:
            page_config = self.get_page_config(page_id, module_instance)
            if not page_config:
                showlog.warn(f"[PresetManager] No config found for page: {page_id}")
                return False
            
            preset_data = {
                "page_id": page_id,
                "preset_name": preset_name,
                "variables": {},
                "widget_state": {},
                "button_states": {}
            }
            
            # Save module variables (includes button state vars like is_on)
            for var_name in page_config.get("variables", []):
                if hasattr(module_instance, var_name):
                    value = getattr(module_instance, var_name)
                    preset_data["variables"][var_name] = value
                    showlog.debug(f"[PresetManager] Saved {var_name} = {value}")
            
            # Save widget state
            if widget:
                # First try the widget's get_state() method if available
                if hasattr(widget, 'get_state') and callable(widget.get_state):
                    try:
                        widget_state_data = widget.get_state()
                        if isinstance(widget_state_data, dict):
                            preset_data["widget_state"] = widget_state_data
                            showlog.debug(f"[PresetManager] Saved widget state from get_state(): {widget_state_data}")
                    except Exception as e:
                        showlog.warn(f"[PresetManager] widget.get_state() failed: {e}")
                
                # Fallback to individual attributes from WIDGET_STATE config
                if not preset_data["widget_state"]:
                    for state_name in page_config.get("widget_state", []):
                        if hasattr(widget, state_name):
                            value = getattr(widget, state_name)
                            preset_data["widget_state"][state_name] = value
                            showlog.debug(f"[PresetManager] Saved widget.{state_name} = {value}")
            
            # Save button states from module instance
            try:
                if hasattr(module_instance, 'button_states'):
                    preset_data["button_states"] = module_instance.button_states.copy() if isinstance(module_instance.button_states, dict) else {}
                    showlog.debug(f"[PresetManager] Saved button_states = {preset_data['button_states']}")
                else:
                    preset_data["button_states"] = {}
            except Exception as e:
                showlog.warn(f"[PresetManager] Could not retrieve button states: {e}")
                preset_data["button_states"] = {}
            
            # Save to file
            page_preset_dir = self.presets_dir / page_id
            page_preset_dir.mkdir(parents=True, exist_ok=True)
            
            preset_file = page_preset_dir / f"{preset_name}.json"
            with open(preset_file, 'w') as f:
                json.dump(preset_data, f, indent=2)
            
            showlog.info(f"[PresetManager] Saved preset '{preset_name}' for {page_id} to {preset_file}")
            return True
            
        except Exception as e:
            showlog.error(f"[PresetManager] Failed to save preset: {e}")
            return False
    
    def load_preset(self, page_id: str, preset_name: str, module_instance, widget=None) -> bool:
        """
        Load a preset for the given page/module.
        Restores module variables, widget state, registry values, and button states.
        
        Args:
            page_id: The page or module identifier
            preset_name: Name of the preset to load
            module_instance: The module instance to restore state to
            widget: Optional widget instance to restore widget state
            
        Returns:
            True if load successful, False otherwise
        """
        try:
            preset_file = self.presets_dir / page_id / f"{preset_name}.json"
            
            if not preset_file.exists():
                showlog.warn(f"[PresetManager] Preset file not found: {preset_file}")
                return False
            
            with open(preset_file, 'r') as f:
                preset_data = json.load(f)
            
            # FIRST: Restore button states so that dial methods can check vibrato on/off correctly
            raw_button_states = preset_data.get("button_states", {})
            button_states = {}

            if isinstance(raw_button_states, dict):
                # Normalize keys to strings and values to ints when possible
                for key, value in raw_button_states.items():
                    if value is None:
                        continue
                    try:
                        button_states[str(key)] = int(value)
                    except (TypeError, ValueError):
                        # Fall back to keeping the original value
                        button_states[str(key)] = value
            elif isinstance(raw_button_states, list):
                # Legacy presets stored button states as [bool, ...]
                for idx, value in enumerate(raw_button_states, start=1):
                    if value is None:
                        continue
                    try:
                        button_states[str(idx)] = int(value)
                    except (TypeError, ValueError):
                        button_states[str(idx)] = value

            if button_states:
                try:
                    # Restore to module instance if it has the attribute
                    if hasattr(module_instance, 'button_states'):
                        module_instance.button_states = button_states.copy() if isinstance(button_states, dict) else {}

                        # Sync rotating state (button 2) if module has stereo_mode
                        if hasattr(module_instance, 'stereo_mode') and "2" in button_states:
                            try:
                                raw_index = button_states["2"]
                                safe_index = None

                                if isinstance(raw_index, bool):
                                    safe_index = int(raw_index)
                                elif isinstance(raw_index, int):
                                    safe_index = raw_index
                                elif isinstance(raw_index, str):
                                    safe_index = int(raw_index) if raw_index.isdigit() else None

                                if safe_index is not None:
                                    safe_index = max(0, min(safe_index, module_instance.stereo_mode.count() - 1))
                                    module_instance.stereo_mode.set_index(safe_index)
                                else:
                                    # Fall back to label restore if index missing or invalid
                                    if isinstance(raw_index, str):
                                        module_instance.stereo_mode.set_label(raw_index)
                                    else:
                                        showlog.warn(
                                            f"[PresetManager] stereo_mode restore encountered unsupported value: {raw_index}"
                                        )

                                label = module_instance.stereo_mode.label()
                                module_instance.button_states["2"] = module_instance.stereo_mode.index()
                                showlog.debug(
                                    f"[PresetManager] Synced stereo_mode to index "
                                    f"{module_instance.button_states['2']} ({label})"
                                )

                                if hasattr(module_instance, '_update_button_label'):
                                    try:
                                        module_instance._update_button_label("2", label)
                                        showlog.debug("[PresetManager] Updated button 2 label after stereo sync")
                                    except Exception as e:
                                        showlog.warn(f"[PresetManager] _update_button_label failed: {e}")
                            except Exception as e:
                                showlog.warn(f"[PresetManager] stereo_mode sync failed: {e}")

                        # Update any UI bindings driven off button state snapshots (other helpers may exist)

                        if hasattr(module_instance, '_push_button_states'):
                            try:
                                module_instance._push_button_states()
                                showlog.debug("[PresetManager] Pushed button state snapshot after preset load")
                            except Exception as e:
                                showlog.warn(f"[PresetManager] _push_button_states failed: {e}")

                    showlog.debug(f"[PresetManager] Restored button_states = {button_states}")
                except Exception as e:
                    showlog.warn(f"[PresetManager] Could not restore button states: {e}")
            
            # Turn off vibrato before making changes to avoid layering
            was_vibrato_on = button_states.get("1", 0) == 1 if isinstance(button_states, dict) else False
            if was_vibrato_on:
                try:
                    import cv_client
                    cv_client.send_raw("VIBEOFF 16")
                    cv_client.send_raw("VIBEOFF 17")
                    showlog.debug("[PresetManager] Stopped vibrato before preset load")
                except Exception as e:
                    showlog.warn(f"[PresetManager] Could not stop vibrato: {e}")
            
            # Restore module variables
            for var_name, value in preset_data.get("variables", {}).items():
                if hasattr(module_instance, var_name):
                    setattr(module_instance, var_name, value)
                    showlog.debug(f"[PresetManager] Restored {var_name} = {value}")
            
            # Call module's on_preset_loaded hook if it exists (for post-restore sync)
            if hasattr(module_instance, 'on_preset_loaded') and callable(module_instance.on_preset_loaded):
                try:
                    module_instance.on_preset_loaded(preset_data.get("variables", {}))
                    showlog.debug(f"[PresetManager] Called on_preset_loaded hook")
                except Exception as e:
                    showlog.warn(f"[PresetManager] on_preset_loaded hook failed: {e}")
            
            # Trigger on_dial_change for each variable to apply CV commands
            # This ensures the module actually sends CV updates, not just sets variables
            page_config = self.get_page_config(page_id, module_instance)
            if page_config and hasattr(module_instance, 'on_dial_change'):
                # Get the registry to map variables back to labels
                registry = getattr(module_instance, 'REGISTRY', {})
                var_to_label = {}
                
                # Build reverse mapping: variable_name -> dial_label
                for key, value in registry.items():
                    if isinstance(value, dict) and value.get("type") == "module":
                        for slot_key, slot_data in value.items():
                            if isinstance(slot_data, dict) and "variable" in slot_data and "label" in slot_data:
                                var_to_label[slot_data["variable"]] = slot_data["label"]
                
                # Call on_dial_change for each restored variable
                for var_name, value in preset_data.get("variables", {}).items():
                    label = var_to_label.get(var_name)
                    if label:
                        try:
                            module_instance.on_dial_change(label, value)
                            showlog.debug(f"[PresetManager] Triggered on_dial_change('{label}', {value})")
                        except Exception as e:
                            showlog.warn(f"[PresetManager] on_dial_change failed for {label}: {e}")
            
            # Restore widget state
            widget_state_data = preset_data.get("widget_state", {})
            if widget and widget_state_data:
                # First try the widget's set_from_state() method if available
                if hasattr(widget, 'set_from_state') and callable(widget.set_from_state):
                    try:
                        # VibratoField expects: set_from_state(low_norm, high_norm, fade_ms, emit=True)
                        if 'low_norm' in widget_state_data and 'high_norm' in widget_state_data and 'fade_ms' in widget_state_data:
                            widget.set_from_state(
                                widget_state_data['low_norm'],
                                widget_state_data['high_norm'],
                                widget_state_data['fade_ms'],
                                emit=False
                            )
                            showlog.debug(f"[PresetManager] Restored widget state via set_from_state()")
                    except Exception as e:
                        showlog.warn(f"[PresetManager] widget.set_from_state() failed: {e}")
                
                # Fallback to setting individual attributes
                else:
                    for state_name, value in widget_state_data.items():
                        if hasattr(widget, state_name):
                            setattr(widget, state_name, value)
                            showlog.debug(f"[PresetManager] Restored widget.{state_name} = {value}")
                
                # Trigger widget layout update if available
                if hasattr(widget, '_clamp_layout'):
                    widget._clamp_layout()
                elif hasattr(widget, '_apply_constraints'):
                    widget._apply_constraints(emit=False)
                
                # Manually trigger CV calibration update after widget state is restored
                if hasattr(widget, 'on_change') and callable(widget.on_change):
                    try:
                        current_state = widget.get_state() if hasattr(widget, 'get_state') else None
                        if current_state:
                            widget.on_change(current_state)
                            showlog.debug(f"[PresetManager] Triggered widget CV update with state: {current_state}")
                    except Exception as e:
                        showlog.warn(f"[PresetManager] Failed to trigger widget CV update: {e}")
            
            # Finally, if vibrato was supposed to be on, start it with the correct settings
            if was_vibrato_on:
                try:
                    if hasattr(module_instance, '_restart_vibrato'):
                        module_instance._restart_vibrato()
                        showlog.debug("[PresetManager] Reapplied vibrato after preset load")
                    else:
                        import cv_client
                        channels = []
                        if hasattr(module_instance, '_get_active_channels'):
                            try:
                                channels = list(module_instance._get_active_channels())
                            except Exception:
                                channels = []
                        if not channels:
                            channels = [16]
                        current_hz = getattr(module_instance, 'current_hz', 0)
                        if current_hz > 0:
                            for ch in channels:
                                cv_client.send_raw(f"VIBEON {ch} {current_hz}")
                            showlog.debug(
                                f"[PresetManager] Restarted vibrato at {current_hz} Hz on channels {channels}"
                            )
                except Exception as e:
                    showlog.warn(f"[PresetManager] Could not restart vibrato: {e}")
            
            showlog.info(f"[PresetManager] Loaded preset '{preset_name}' for {page_id}")
            return True
            
        except Exception as e:
            showlog.error(f"[PresetManager] Failed to load preset: {e}")
            return False
    
    def list_presets(self, page_id: str) -> List[str]:
        """
        List all available presets for a given page.
        
        Args:
            page_id: The page or module identifier
            
        Returns:
            List of preset names (without .json extension)
        """
        page_preset_dir = self.presets_dir / page_id
        
        if not page_preset_dir.exists():
            return []
        
        presets = []
        for preset_file in page_preset_dir.glob("*.json"):
            presets.append(preset_file.stem)
        
        return sorted(presets)
    
    def delete_preset(self, page_id: str, preset_name: str) -> bool:
        """
        Delete a preset file.
        
        Args:
            page_id: The page or module identifier
            preset_name: Name of the preset to delete
            
        Returns:
            True if deletion successful, False otherwise
        """
        try:
            preset_file = self.presets_dir / page_id / f"{preset_name}.json"
            
            if preset_file.exists():
                preset_file.unlink()
                showlog.info(f"[PresetManager] Deleted preset '{preset_name}' for {page_id}")
                return True
            else:
                showlog.warn(f"[PresetManager] Preset not found: {preset_file}")
                return False
                
        except Exception as e:
            showlog.error(f"[PresetManager] Failed to delete preset: {e}")
            return False
    
    def get_preset_data(self, page_id: str, preset_name: str) -> Optional[Dict]:
        """
        Get the raw preset data without applying it.
        
        Args:
            page_id: The page or module identifier
            preset_name: Name of the preset
            
        Returns:
            Preset data dict or None if not found
        """
        try:
            preset_file = self.presets_dir / page_id / f"{preset_name}.json"
            
            if not preset_file.exists():
                return None
            
            with open(preset_file, 'r') as f:
                return json.load(f)
                
        except Exception as e:
            showlog.error(f"[PresetManager] Failed to read preset data: {e}")
            return None


# Singleton instance for global access
_preset_manager_instance = None

def get_preset_manager() -> PresetManager:
    """Get or create the global PresetManager instance."""
    global _preset_manager_instance
    if _preset_manager_instance is None:
        _preset_manager_instance = PresetManager()
    return _preset_manager_instance
