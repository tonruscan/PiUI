"""
Event bus for publish/subscribe messaging.

Provides a decoupled communication layer on top of the existing queue system.
"""

from collections import defaultdict
from typing import Callable, Any, List, Dict
import showlog


class EventBus:
    """Simple event bus for publish/subscribe pattern."""
    
    def __init__(self):
        """Initialize event bus."""
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
    
    def subscribe(self, event_type: str, callback: Callable[[Any], None]) -> None:
        """
        Subscribe to an event type.
        
        Args:
            event_type: Event identifier (e.g., "mode_change", "dial_update")
            callback: Function to call when event is published
        """
        self._subscribers[event_type].append(callback)
        showlog.debug(f"[EVENT_BUS] Subscribed to '{event_type}'")
    
    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        """
        Unsubscribe from an event type.
        
        Args:
            event_type: Event identifier
            callback: Callback function to remove
        """
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(callback)
                showlog.debug(f"[EVENT_BUS] Unsubscribed from '{event_type}'")
            except ValueError:
                pass
    
    def publish(self, event_type: str, data: Any = None) -> None:
        """
        Publish an event to all subscribers.
        
        Args:
            event_type: Event identifier
            data: Optional event data
        """
        if event_type in self._subscribers:
            showlog.debug(f"[EVENT_BUS] Publishing '{event_type}' to {len(self._subscribers[event_type])} subscribers")
            for callback in self._subscribers[event_type]:
                try:
                    callback(data)
                except Exception as e:
                    showlog.error(f"[EVENT_BUS] Error in subscriber for '{event_type}': {e}")
    
    def clear(self, event_type: str = None) -> None:
        """
        Clear subscribers.
        
        Args:
            event_type: If provided, clear only this event type. Otherwise clear all.
        """
        if event_type:
            self._subscribers.pop(event_type, None)
        else:
            self._subscribers.clear()
    
    def subscriber_count(self, event_type: str) -> int:
        """
        Get number of subscribers for an event type.
        
        Args:
            event_type: Event identifier
            
        Returns:
            Number of subscribers
        """
        return len(self._subscribers.get(event_type, []))
    
    def list_events(self) -> List[str]:
        """Get list of all event types with subscribers."""
        return list(self._subscribers.keys())
