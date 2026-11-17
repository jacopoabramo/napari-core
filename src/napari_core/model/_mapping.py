"""Mapping between a view's surface pixels and world coordinates."""

from typing import NamedTuple

from ._view import View


class WorldRect(NamedTuple):
    """A rectangle in world coordinates, rows downwards.

    `left` and `width` are along columns, `top` and `height` along rows.
    """

    left: float
    top: float
    width: float
    height: float

    @property
    def right(self) -> float:
        """Column of the right edge."""
        return self.left + self.width

    @property
    def bottom(self) -> float:
        """Row of the bottom edge."""
        return self.top + self.height


def visible_rect(view: View) -> WorldRect:
    """Return the world rectangle the view's canvas shows.

    A canvas of zero width or height gives a rectangle of no size at the
    camera's centre.
    """
    width, height = view.canvas_size
    row, column = view.camera.center
    zoom = view.camera.zoom
    visible_width, visible_height = width / zoom, height / zoom
    return WorldRect(
        column - visible_width / 2,
        row - visible_height / 2,
        visible_width,
        visible_height,
    )


def surface_to_world(view: View, x: float, y: float) -> tuple[float, float]:
    """Return the world point `(row, column)` under surface pixel `(x, y)`."""
    width, height = view.canvas_size
    row, column = view.camera.center
    zoom = view.camera.zoom
    return (row + (y - height / 2) / zoom, column + (x - width / 2) / zoom)
