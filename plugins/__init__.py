"""
plugins/
--------
Plugin ecosystem for modular audio/MIDI features.

All plugins are automatically discovered and loaded by PluginManager.
Each plugin must define a Plugin subclass with metadata and lifecycle hooks.

Example plugin structure:
    from core.plugin import Plugin
    
    class Plugin(VibratoPlugin):
        name = "My Plugin"
        version = "1.0.0"
        category = "modulation"
        
        def on_load(self, app):
            # Register with PageRegistry, subscribe to events, etc.
            pass
"""
