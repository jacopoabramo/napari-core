"""Turn surface events into input events and move the camera."""

from ._coordinates import surface_to_world
from ._dispatch import attach

__all__ = ["attach", "surface_to_world"]
