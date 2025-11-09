"""
Service Base Class
Provides unified interface for all registered services.
"""

from abc import ABC, abstractmethod


class ServiceBase(ABC):
    """
    Base class for all registered services.
    
    All services must implement cleanup() for proper resource management.
    Optional: on_register() hook called when service is registered.
    """
    
    # Service-specific log prefix for consistent logging
    log_prefix = "[SERVICE]"
    
    @abstractmethod
    def cleanup(self):
        """
        Cleanup service resources (connections, threads, files, etc.).
        Called automatically by ServiceRegistry during application shutdown.
        Must be implemented by all services.
        """
        pass
    
    def on_register(self, registry):
        """
        Optional lifecycle hook called when service is registered.
        
        Args:
            registry: ServiceRegistry instance for accessing other services
        """
        pass
