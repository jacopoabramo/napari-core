from napari_core.model import (
    Camera,
    View,
    WorldRect,
    surface_to_world,
    visible_rect,
)


def view(
    size: tuple[int, int] = (200, 100),
    zoom: float = 2.0,
    center: tuple[float, float] = (10.0, 20.0),
) -> View:
    """Return a view with the given canvas size and camera."""
    return View(canvas_size=size, camera=Camera(zoom=zoom, center=center))


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
    v = View(canvas_size=(200, 100))
    v.camera.center = (25.0, 25.0)
    v.camera.zoom = 2.0
    rect = visible_rect(v)
    assert rect == WorldRect(left=-25.0, top=0.0, width=100.0, height=50.0)
    assert (rect.right, rect.bottom) == (75.0, 50.0)


def test_visible_rect_of_a_surface_of_zero_size_is_empty() -> None:
    """Return a rectangle of no width and height for a canvas of zero size."""
    v = View(canvas_size=(0, 0))
    assert visible_rect(v) == WorldRect(left=0.0, top=0.0, width=0.0, height=0.0)


def test_surface_to_world_is_row_then_column() -> None:
    """Map a surface pixel to the world (row, column) under it."""
    v = View(canvas_size=(200, 100))
    assert surface_to_world(v, 110, 40) == (-10.0, 10.0)
