"""
Rendering modules.

Contains rendering coordination, dirty rect management, and frame control.
"""

from .renderer import Renderer
from .dirty_rect import DirtyRectManager
from .frame_control import FrameController

__all__ = ["Renderer", "DirtyRectManager", "FrameController"]
