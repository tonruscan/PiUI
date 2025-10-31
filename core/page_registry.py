"""
Page registry system.

Dynamic page registration and lookup - eliminates hardcoded page branching.
"""

from typing import Dict, Callable, Optional, Any
import showlog


class PageRegistry:
    """Central registry for all UI pages."""
    
    def __init__(self):
        """Initialize empty page registry."""
        self._pages: Dict[str, Dict[str, Any]] = {}
    
    def register(self, 
                 page_id: str, 
                 module: Any,
                 label: Optional[str] = None,
                 meta: Optional[dict] = None) -> None:
        """
        Register a page with its handlers.
        
        Args:
            page_id: Unique page identifier (e.g., "dials", "presets")
            module: Page module containing handlers
            label: Display label for the page (optional)
            meta: Additional metadata dict (optional)
        """
        self._pages[page_id] = {
            "id": page_id,
            "label": label or page_id.capitalize(),
            "module": module,
            "handle_event": getattr(module, "handle_event", None),
            "draw": getattr(module, "draw", None),
            "draw_ui": getattr(module, "draw_ui", None),  # Some pages use draw_ui
            "update": getattr(module, "update", None),
            "init": getattr(module, "init", None),
            "meta": meta or {}
        }
        showlog.debug(f"[PAGE_REGISTRY] Registered page: {page_id} ({label or page_id})")
    
    def get(self, page_id: str) -> Optional[Dict[str, Any]]:
        """
        Get page by ID.
        
        Args:
            page_id: Page identifier
            
        Returns:
            Page dict or None if not found
        """
        return self._pages.get(page_id)
    
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
