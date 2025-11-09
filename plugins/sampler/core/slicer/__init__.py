"""Auto-slicer facilities shared across sampler instruments."""

from .controller import AutoSlicerController
from .models import SliceSet, SliceSummary
from .widget import AutoSlicerWidget

__all__ = [
    "AutoSlicerController",
    "AutoSlicerWidget",
    "SliceSet",
    "SliceSummary",
]
