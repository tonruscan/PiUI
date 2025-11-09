"""
Service registry for dependency injection.

Provides a central registry for loosely coupling application components.
Enhanced with lifecycle management, cleanup, and safety features.
"""

from typing import Any, Optional, Dict
import showlog


class ServiceRegistry:
    """Central dependency injection container with lifecycle management (singleton)."""
    
    _instance = None
    _services: Dict[str, Any] = {}
    
    def __new__(cls):
        """Enforce singleton pattern."""
        if cls._instance is None:
            cls._instance = super(ServiceRegistry, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize empty service registry (only on first instantiation)."""
        # No-op after first init since we share _services at class level
        pass
    
    def register(self, key: str, instance: Any) -> None:
        """
        Register a service instance.
        
        Args:
            key: Service identifier
            instance: Service instance to register
        """
        # Warn if overwriting existing service
        if key in self._services:
            showlog.warn(f"[SERVICES] Overwriting existing service: '{key}'")
        
        self._services[key] = instance
        
        # Call optional lifecycle hook if service implements it
        if hasattr(instance, 'on_register'):
            try:
                instance.on_register(self)
            except Exception as e:
                showlog.error(f"[SERVICES] on_register() failed for '{key}': {e}")
        
        showlog.debug(f"[SERVICES] Registered '{key}'")
    
    def get(self, key: str, default: Any = None) -> Optional[Any]:
        """
        Get a service by key with optional default.
        
        Args:
            key: Service identifier
            default: Default value if service not found
            
        Returns:
            Service instance or default if not found
        """
        return self._services.get(key, default)
    
    def require(self, key: str) -> Any:
        """
        Get a required service, raising exception if missing.
        
        Args:
            key: Service identifier
            
        Returns:
            Service instance
            
        Raises:
            KeyError: If service not found
        """
        service = self.get(key)
        if service is None:
            raise KeyError(f"Missing required service: {key}")
        return service
    
    def has(self, key: str) -> bool:
        """
        Check if service is registered.
        
        Args:
            key: Service identifier
            
        Returns:
            True if service exists
        """
        return key in self._services
    
    def unregister(self, key: str) -> None:
        """
        Remove a service from registry.
        
        Args:
            key: Service identifier
        """
        self._services.pop(key, None)
    
    def clear(self) -> None:
        """Clear all registered services."""
        self._services.clear()
    
    def list_services(self) -> list:
        """Get list of all registered service keys."""
        return list(self._services.keys())
    
    def cleanup(self) -> None:
        """
        Cleanup all registered services.
        Calls cleanup() method on each service that implements it.
        Called automatically during application shutdown.
        """
        for key, instance in list(self._services.items()):
            if hasattr(instance, 'cleanup'):
                showlog.debug(f"[SERVICES] Cleaning up '{key}'")
                try:
                    instance.cleanup()
                except Exception as e:
                    showlog.error(f"[SERVICES] Cleanup failed for '{key}': {e}")
