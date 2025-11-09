"""Sampler plugin package providing a modular instrument architecture."""

from importlib import import_module
from typing import Any

__all__ = ["Plugin", "SamplerPlugin"]


def __getattr__(name: str) -> Any:
	"""Lazily expose plugin exports without creating circular imports."""
	if name in __all__:
		module = import_module(".plugin", __name__)
		return getattr(module, name)
	raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
