"""
Service registry for dependency injection.

Provides a central registry for loosely coupling application components.
"""

from typing import Any, Optional, Dict


class ServiceRegistry:
    """Central dependency injection container."""
    
    def __init__(self):
        """Initialize empty service registry."""
        self._services: Dict[str, Any] = {}
    
    def register(self, key: str, instance: Any) -> None:
        """
        Register a service instance.
        
        Args:
            key: Service identifier
            instance: Service instance to register
        """
        self._services[key] = instance
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get a service by key.
        
        Args:
            key: Service identifier
            
        Returns:
            Service instance or None if not found
        """
        return self._services.get(key)
    
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
