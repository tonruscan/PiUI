"""
Core application module.

This module contains the main application class and event loop.
"""

from .app import UIApplication
from .display import DisplayManager
from .loop import EventLoop

__all__ = ["UIApplication", "DisplayManager", "EventLoop"]
