"""Conversion between surface and world coordinates."""

from napari_core.model import View


def surface_to_world(view: View, x: float, y: float) -> tuple[float, float]:
    """Return the world point `(row, column)` under surface pixel `(x, y)`."""
    width, height = view.canvas_size
    row, column = view.camera.center
    zoom = view.camera.zoom
    return (row + (y - height / 2) / zoom, column + (x - width / 2) / zoom)
