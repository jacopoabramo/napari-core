import pytest
from helpers import view

from napari_core.model import (
    View,
    WorldRect,
    surface_to_world,
    visible_rect,
)


def test_surface_middle_is_the_camera_center() -> None:
    """Map the middle of the surface to the camera centre."""
    assert surface_to_world(view(), 100, 50) == (10.0, 20.0)


def test_surface_offsets_scale_with_zoom() -> None:
    """Map surface y to world rows and x to columns, divided by the zoom."""
    assert surface_to_world(view(), 110, 40) == (5.0, 25.0)


def test_visible_rect_is_centred_on_the_camera() -> None:
    """Show the canvas size in world units around the camera's centre."""
    v = View(canvas_size=(200, 100))
    assert visible_rect(v) == WorldRect(
        left=-100.0, top=-50.0, width=200.0, height=100.0
    )


def test_visible_rect_shrinks_with_zoom() -> None:
    """Halve the visible world when the zoom doubles."""
    rect = visible_rect(view(zoom=2.0))
    assert rect == WorldRect(left=-30.0, top=-15.0, width=100.0, height=50.0)
    assert (rect.right, rect.bottom) == (70.0, 35.0)


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        ((0, 0), WorldRect(left=20.0, top=10.0, width=0.0, height=0.0)),
        ((0, 100), WorldRect(left=20.0, top=-40.0, width=0.0, height=100.0)),
    ],
)
def test_visible_rect_of_a_canvas_with_no_width_has_no_width(
    size: tuple[int, int], expected: WorldRect
) -> None:
    """Keep the camera's centre in a rectangle of a canvas with a zero side."""
    assert visible_rect(view(size=size, zoom=1.0)) == expected


def test_surface_to_world_is_row_then_column() -> None:
    """Map a surface pixel to the world (row, column) under it."""
    v = View(canvas_size=(200, 100))
    assert surface_to_world(v, 110, 40) == (-10.0, 10.0)


def test_surface_to_world_answers_for_a_given_zoom() -> None:
    """Map with the given zoom and leave the camera unchanged."""
    v = view(zoom=1.0)
    assert surface_to_world(v, 110, 40, zoom=2.0) == (5.0, 25.0)
    assert v.camera.zoom == 1.0
    assert v.camera.center == (10.0, 20.0)
