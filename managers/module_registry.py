"""
managers/module_registry.py
----------------------------
Centralized registry for module/plugin metadata.

Provides runtime awareness of all loaded modules with easy metadata access.
Used by UI for displaying module lists, filtering by category, etc.
"""

import showlog


class ModuleRegistry:
    """
    Central registry for plugin/module metadata.
    
    Maintains a dictionary of loaded modules with structured metadata
    for use by UI components, navigation systems, and introspection tools.
    
    Features:
    - Register plugins with metadata
    - Query by name or category
    - List all modules
    - Filter by category
    """
    
    def __init__(self):
        """Initialize empty registry."""
        self.modules = {}  # name → metadata dict
        self._by_category = {}  # category → list of names
    
    def register(self, plugin):
        """
        Register a plugin's metadata.
        
        Args:
            plugin: Plugin instance with get_metadata() method
        """
        try:
            meta = plugin.get_metadata()
            name = meta.get("name", "Unknown")
            category = meta.get("category", "general")
            
            # Store metadata
            self.modules[name] = meta
            
            # Index by category
            if category not in self._by_category:
                self._by_category[category] = []
            if name not in self._by_category[category]:
                self._by_category[category].append(name)
            
            showlog.debug(f"[ModuleRegistry] Registered: {name} ({category})")
        
        except Exception as e:
            showlog.error(f"[ModuleRegistry] Failed to register plugin: {e}")
    
    def unregister(self, name: str):
        """
        Remove a plugin from the registry.
        
        Args:
            name: Plugin name to remove
        
        Returns:
            bool: True if removed, False if not found
        """
        if name in self.modules:
            meta = self.modules[name]
            category = meta.get("category", "general")
            
            # Remove from main registry
            del self.modules[name]
            
            # Remove from category index
            if category in self._by_category and name in self._by_category[category]:
                self._by_category[category].remove(name)
            
            showlog.debug(f"[ModuleRegistry] Unregistered: {name}")
            return True
        
        return False
    
    def get(self, name: str):
        """
        Get metadata for a specific module.
        
        Args:
            name: Plugin name
        
        Returns:
            dict: Metadata dictionary or None
        """
        return self.modules.get(name)
    
    def has(self, name: str) -> bool:
        """
        Check if module is registered.
        
        Args:
            name: Plugin name
        
        Returns:
            bool: True if registered
        """
        return name in self.modules
    
    def list_modules(self):
        """
        Get list of all registered module metadata.
        
        Returns:
            list: List of metadata dictionaries
        """
        return list(self.modules.values())
    
    def list_names(self):
        """
        Get list of all registered module names.
        
        Returns:
            list: List of module names (strings)
        """
        return list(self.modules.keys())
    
    def list_categories(self):
        """
        Get list of all categories.
        
        Returns:
            list: List of category names (strings)
        """
        return list(self._by_category.keys())
    
    def get_by_category(self, category: str):
        """
        Get all modules in a specific category.
        
        Args:
            category: Category name (e.g., "modulation", "filter")
        
        Returns:
            list: List of metadata dictionaries
        """
        names = self._by_category.get(category, [])
        return [self.modules[name] for name in names if name in self.modules]
    
    def filter_by_author(self, author: str):
        """
        Get all modules by a specific author.
        
        Args:
            author: Author name
        
        Returns:
            list: List of metadata dictionaries
        """
        return [meta for meta in self.modules.values() 
                if meta.get("author") == author]
    
    def count(self) -> int:
        """
        Get total number of registered modules.
        
        Returns:
            int: Module count
        """
        return len(self.modules)
    
    def clear(self):
        """Remove all registered modules."""
        self.modules.clear()
        self._by_category.clear()
        showlog.debug("[ModuleRegistry] Cleared all registrations")
