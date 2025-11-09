"""
core/plugin.py
--------------
Plugin system infrastructure with metadata-driven discovery and lifecycle management.

Key Features:
- Metadata (name, version, category, author, description, icon)
- Lifecycle hooks (on_load, on_init, on_update, on_unload)
- Auto-discovery via pkgutil
- Safe error handling (bad plugins don't crash app)
- PageRegistry integration
"""

import importlib
import pkgutil
import showlog


class Plugin:
    """
    Base class for all plugins (modules, effects, utilities).
    
    Plugins define metadata and implement lifecycle hooks to integrate
    with the application's ServiceRegistry, PageRegistry, and EventBus.
    
    Metadata:
        name: Human-readable plugin name (shown in UI)
        version: Semantic version string (e.g., "1.0.0")
        category: Plugin category for grouping (e.g., "modulation", "filter")
        author: Plugin author/maintainer
        description: Brief description of functionality
        icon: Icon filename (optional, for UI)
        page_id: Unique page identifier for PageRegistry (optional)
    
    Lifecycle Hooks:
        on_load(app): Called when plugin is discovered and loaded
        on_init(app): Called after all plugins loaded, for cross-plugin setup
        on_update(app): Called each frame for dynamic behavior
        on_unload(app): Called when plugin is being unloaded/disabled
    """
    
    # Metadata (override in subclasses)
    name: str = "Unnamed Plugin"
    version: str = "1.0.0"
    category: str = "general"
    author: str = "System"
    description: str = "Generic plugin"
    icon: str = "default.png"
    page_id: str = None  # Optional: if plugin provides a page
    
    def get_metadata(self):
        """Return structured metadata dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "category": self.category,
            "author": self.author,
            "description": self.description,
            "icon": self.icon,
            "page_id": self.page_id,
        }
    
    # Lifecycle hooks (override as needed)
    def on_load(self, app):
        """
        Called when plugin is first loaded.
        Use this to register pages, subscribe to events, etc.
        
        Args:
            app: UIApplication instance with access to services
        """
        pass
    
    def on_init(self, app):
        """
        Called after all plugins have been loaded.
        Use this for cross-plugin initialization or dependencies.
        
        Args:
            app: UIApplication instance
        """
        pass
    
    def on_update(self, app):
        """
        Called each frame for dynamic plugin behavior.
        Keep this lightweight to avoid frame drops.
        
        Args:
            app: UIApplication instance
        """
        pass
    
    def on_unload(self, app):
        """
        Called when plugin is being unloaded/disabled.
        Use this to cleanup resources, unsubscribe events, etc.
        
        Args:
            app: UIApplication instance
        """
        pass


class PluginManager:
    """
    Manages plugin discovery, loading, lifecycle, and lookup.
    
    Features:
    - Auto-discovery via pkgutil.iter_modules()
    - Safe error handling (bad plugins don't crash app)
    - Metadata registration with ModuleRegistry
    - Page ID lookup for dynamic routing
    - Lifecycle orchestration (load → init → update → unload)
    """
    
    def __init__(self, app):
        """
        Initialize plugin manager.
        
        Args:
            app: UIApplication instance (provides access to services)
        """
        self.app = app
        self.plugins = []  # List of loaded Plugin instances
        self._page_map = {}  # page_id → Plugin instance
    
    def discover(self, path="plugins"):
        """
        Automatically discover and load all plugins in a directory.
        
        Scans the specified directory for Python modules, imports them,
        and loads any classes that inherit from Plugin.
        
        Args:
            path: Directory path to scan (default: "plugins")
        
        Returns:
            int: Number of plugins successfully loaded
        """
        loaded_count = 0
        
        try:
            # Scan directory for Python modules
            for finder, name, ispkg in pkgutil.iter_modules([path]):
                try:
                    # Import the module
                    mod = importlib.import_module(f"{path}.{name}")

                    # Look for Plugin subclass (conventionally named "Plugin")
                    if hasattr(mod, "Plugin"):
                        plugin_class = getattr(mod, "Plugin")

                        # Verify it's actually a Plugin subclass
                        if isinstance(plugin_class, type) and issubclass(plugin_class, Plugin):
                            plugin = plugin_class()
                            self.load(plugin)
                            loaded_count += 1
                        else:
                            showlog.warn(f"[PluginManager] {path}.{name}.Plugin is not a valid Plugin subclass")
                    else:
                        showlog.debug(f"[PluginManager] {path}.{name} has no Plugin class (skipping)")
				
                except Exception as e:
                    message = str(e)
                    if isinstance(e, ImportError) and "has been removed" in message:
                        showlog.info(
                            f"[PluginManager] Skipping legacy plugin '{name}': {message}"
                        )
                    else:
                        showlog.error(f"[PluginManager] Failed to load plugin '{name}': {e}")
                    # Continue loading other plugins
                    continue
        
        except Exception as e:
            showlog.error(f"[PluginManager] Failed to discover plugins in '{path}': {e}")
        
        showlog.info(f"[PluginManager] Discovered {loaded_count} plugin(s)")
        return loaded_count
    
    def load(self, plugin: Plugin):
        """
        Load a single plugin instance.
        
        Calls plugin.on_load(), registers with ModuleRegistry,
        and adds to internal tracking.
        
        Args:
            plugin: Plugin instance to load
        
        Raises:
            Exception: If plugin.on_load() fails (logged, not propagated)
        """
        try:
            meta = plugin.get_metadata()
            showlog.info(f"[PluginManager] Loading: {meta['name']} v{meta['version']} ({meta['category']})")
            
            # Call plugin's load hook
            plugin.on_load(self.app)
            
            # Register with ModuleRegistry (if available)
            if hasattr(self.app, 'module_registry'):
                self.app.module_registry.register(plugin)
            
            # Track plugin
            self.plugins.append(plugin)
            
            # Map page_id for quick lookup
            if meta.get('page_id'):
                self._page_map[meta['page_id']] = plugin
            
            showlog.debug(f"[PluginManager] Loaded: {meta['name']}")
        
        except Exception as e:
            showlog.error(f"[PluginManager] Failed to load {plugin.name}: {e}")
            # Don't propagate - isolate plugin failures
    
    def init_all(self):
        """
        Call on_init() for all loaded plugins.
        
        This is called after all plugins have been loaded,
        allowing cross-plugin initialization.
        """
        for plugin in self.plugins:
            try:
                plugin.on_init(self.app)
            except Exception as e:
                showlog.error(f"[PluginManager] Init failed for {plugin.name}: {e}")
    
    def update_all(self):
        """
        Call on_update() for all loaded plugins each frame.
        
        Keep plugin update logic lightweight to avoid frame drops.
        """
        for plugin in self.plugins:
            try:
                plugin.on_update(self.app)
            except Exception as e:
                showlog.error(f"[PluginManager] Update failed for {plugin.name}: {e}")
    
    def unload(self, plugin_name: str):
        """
        Unload a plugin by name.
        
        Args:
            plugin_name: Name of plugin to unload (from metadata)
        
        Returns:
            bool: True if plugin was found and unloaded
        """
        for plugin in self.plugins:
            if plugin.name == plugin_name:
                try:
                    plugin.on_unload(self.app)
                    self.plugins.remove(plugin)
                    
                    # Remove from page map
                    if plugin.page_id and plugin.page_id in self._page_map:
                        del self._page_map[plugin.page_id]
                    
                    showlog.info(f"[PluginManager] Unloaded: {plugin_name}")
                    return True
                except Exception as e:
                    showlog.error(f"[PluginManager] Unload failed for {plugin_name}: {e}")
                    return False
        
        showlog.warn(f"[PluginManager] Plugin not found: {plugin_name}")
        return False
    
    def get_by_page_id(self, page_id: str):
        """
        Lookup plugin by its registered page_id.
        
        Args:
            page_id: Page identifier (e.g., "vibrato", "mixer")
        
        Returns:
            Plugin: Plugin instance or None
        """
        return self._page_map.get(page_id)
    
    def get_by_name(self, name: str):
        """
        Lookup plugin by name.
        
        Args:
            name: Plugin name from metadata
        
        Returns:
            Plugin: Plugin instance or None
        """
        for plugin in self.plugins:
            if plugin.name == name:
                return plugin
        return None
    
    def list_plugins(self):
        """
        Get list of all loaded plugins.
        
        Returns:
            list: List of Plugin instances
        """
        return self.plugins.copy()
    
    def list_metadata(self):
        """
        Get metadata for all loaded plugins.
        
        Returns:
            list: List of metadata dictionaries
        """
        return [p.get_metadata() for p in self.plugins]
