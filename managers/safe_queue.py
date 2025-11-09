"""
Thread-Safe Queue Wrapper
Provides safe concurrent access for message passing between UI and background threads.
"""

import queue
from threading import Lock


class SafeQueue(queue.Queue):
    """
    Thread-safe queue wrapper for message passing.
    Prevents race conditions when multiple threads access the queue.
    """
    
    def __init__(self):
        super().__init__()
        self.lock = Lock()
    
    def safe_put(self, item):
        """Put item in queue with thread safety."""
        with self.lock:
            self.put(item)
    
    def safe_get_all(self):
        """Get all items from queue safely."""
        items = []
        with self.lock:
            while not self.empty():
                try:
                    items.append(self.get_nowait())
                except queue.Empty:
                    break
        return items
    
    def safe_peek(self):
        """Peek at queue size without blocking."""
        with self.lock:
            return self.qsize()
