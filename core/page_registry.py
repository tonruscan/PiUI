"""
Page registry system.

Dynamic page registration and lookup - eliminates hardcoded page branching.
Supports plugin rendering metadata for automatic FPS and dirty rect optimization.
"""

from typing import Dict, Callable, Optional, Any
import showlog


# Default rendering capabilities for pages without explicit metadata
DEFAULT_RENDERING = {
    "fps_mode": "high",           # Assume MIDI/CV interaction (100 FPS)
    "supports_dirty_rect": True,  # Assume modern plugin with dirty rect support
    "requires_full_frame": False, # Most plugins can use dirty rects
    "burst_multiplier": 1.0,      # No FPS boost in burst mode by default
    "render_layer": "plugin",     # Standard plugin layer
    "hardware_accel": False,      # No GPU acceleration yet
    "schema_version": 1           # Metadata schema version
}


class PageRegistry:
    """Central registry for all UI pages with rendering metadata."""
    
    def __init__(self):
        """Initialize empty page registry."""
        self._pages: Dict[str, Dict[str, Any]] = {}
        self._fps_cache: Dict[tuple, int] = {}  # Cache (page_id, in_burst) -> fps
    
    def register(self, 
                 page_id: str, 
                 module: Any,
                 label: Optional[str] = None,
                 meta: Optional[dict] = None) -> None:
        """
        Register a page with its handlers and rendering metadata.
        
        Args:
            page_id: Unique page identifier (e.g., "dials", "presets")
            module: Page module containing handlers
            label: Display label for the page (optional)
            meta: Additional metadata dict including optional "rendering" field
        """
        meta = meta or {}
        
        # Extract and normalize rendering metadata
        rendering_meta = meta.get("rendering", {})
        normalized_rendering = {**DEFAULT_RENDERING, **rendering_meta}
        
        self._pages[page_id] = {
            "id": page_id,
            "label": label or page_id.capitalize(),
            "module": module,
            "handle_event": getattr(module, "handle_event", None),
            "draw": getattr(module, "draw", None),
            "draw_ui": getattr(module, "draw_ui", None),
            "update": getattr(module, "update", None),
            "init": getattr(module, "init", None),
            "meta": meta,
            # Flatten rendering capabilities to top level for easy access
            **normalized_rendering
        }
        
        showlog.debug(
            f"[PAGE_REGISTRY] Registered page: {page_id} ({label or page_id}) "
            f"fps_mode={normalized_rendering['fps_mode']}, "
            f"dirty_rect={normalized_rendering['supports_dirty_rect']}"
        )
    
    def get(self, page_id: str) -> Optional[Dict[str, Any]]:
        """
        Get page by ID.
        
        Args:
            page_id: Page identifier
            
        Returns:
            Page dict with rendering metadata or None if not found
        """
        return self._pages.get(page_id)
    
    def get_capabilities(self, page_id: str) -> Dict[str, Any]:
        """
        Get normalized rendering capabilities for a page.
        
        Args:
            page_id: Page identifier
            
        Returns:
            Dict with rendering capabilities (falls back to defaults if page not found)
        """
        page = self.get(page_id)
        if not page:
            return DEFAULT_RENDERING.copy()
        
        # Extract rendering fields from page dict
        return {
            "fps_mode": page.get("fps_mode", DEFAULT_RENDERING["fps_mode"]),
            "supports_dirty_rect": page.get("supports_dirty_rect", DEFAULT_RENDERING["supports_dirty_rect"]),
            "requires_full_frame": page.get("requires_full_frame", DEFAULT_RENDERING["requires_full_frame"]),
            "burst_multiplier": page.get("burst_multiplier", DEFAULT_RENDERING["burst_multiplier"]),
            "render_layer": page.get("render_layer", DEFAULT_RENDERING["render_layer"]),
            "hardware_accel": page.get("hardware_accel", DEFAULT_RENDERING["hardware_accel"]),
            "schema_version": page.get("schema_version", DEFAULT_RENDERING["schema_version"])
        }
    
    def invalidate_fps_cache(self, page_id: Optional[str] = None) -> None:
        """
        Invalidate FPS cache when metadata changes.
        
        Args:
            page_id: Specific page to invalidate, or None to clear entire cache
        """
        if page_id:
            # Remove all cache entries for this page
            self._fps_cache = {k: v for k, v in self._fps_cache.items() if k[0] != page_id}
        else:
            self._fps_cache.clear()
    
    def has(self, page_id: str) -> bool:
        """
        Check if page exists.
        
        Args:
            page_id: Page identifier
            
        Returns:
            True if page is registered
        """
        return page_id in self._pages
    
    def all(self) -> list:
        """
        Get all registered pages.
        
        Returns:
            List of page dicts
        """
        return list(self._pages.values())
    
    def list_ids(self) -> list:
        """
        Get list of all page IDs.
        
        Returns:
            List of page ID strings
        """
        return list(self._pages.keys())
    
    def unregister(self, page_id: str) -> None:
        """
        Remove a page from registry.
        
        Args:
            page_id: Page identifier
        """
        if page_id in self._pages:
            self._pages.pop(page_id)
            showlog.debug(f"[PAGE_REGISTRY] Unregistered page: {page_id}")
    
    def get_handler(self, page_id: str, handler_name: str) -> Optional[Callable]:
        """
        Get specific handler for a page.
        
        Args:
            page_id: Page identifier
            handler_name: Handler name (e.g., "draw", "handle_event")
            
        Returns:
            Handler function or None
        """
        page = self.get(page_id)
        if page:
            return page.get(handler_name)
        return None
    
    def call_handler(self, page_id: str, handler_name: str, *args, **kwargs) -> Any:
        """
        Call a page handler if it exists.
        
        Args:
            page_id: Page identifier
            handler_name: Handler name
            *args: Positional arguments for handler
            **kwargs: Keyword arguments for handler
            
        Returns:
            Handler return value or None
        """
        handler = self.get_handler(page_id, handler_name)
        if handler:
            try:
                return handler(*args, **kwargs)
            except Exception as e:
                showlog.error(f"[PAGE_REGISTRY] Error calling {handler_name} on {page_id}: {e}")
        return None
