import pytest
from helpers import pointer, wheel

from napari_core.interaction import attach, surface_to_world
from napari_core.model import Camera, View


def view(size=(200, 100), zoom=2.0, center=(10.0, 20.0)):
    """Return a view with the given canvas size and camera."""
    return View(canvas_size=size, camera=Camera(zoom=zoom, center=center))


def test_surface_middle_is_the_camera_center():
    """Map the middle of the surface to the camera centre."""
    assert surface_to_world(view(), 100, 50) == (10.0, 20.0)


def test_surface_offsets_scale_with_zoom():
    """Map surface y to world rows and x to columns, divided by the zoom."""
    assert surface_to_world(view(), 110, 40) == (5.0, 25.0)


def test_drag_pans_by_the_pixel_distance_over_zoom(surface):
    """Move the centre against the drag, by pixels over zoom."""
    v = view()
    attach(v, surface)
    surface.emit(pointer("pointer_down", 100, 50, button=1))
    surface.emit(pointer("pointer_move", 120, 60, button=1))
    surface.emit(pointer("pointer_up", 120, 60, button=1))
    assert v.camera.center == (5.0, 10.0)


def test_wheel_zooms_about_the_pointer(surface):
    """Zoom in on a wheel turn away from the user, fixing the point under it."""
    v = view()
    attach(v, surface)
    before = surface_to_world(v, 150, 20)
    surface.emit(wheel(150, 20, dy=-120))
    assert v.camera.zoom == pytest.approx(2.0 * 1.1**1.2)
    assert surface_to_world(v, 150, 20) == pytest.approx(before)


def test_camera_flags_switch_pan_and_zoom_off(surface):
    """Leave the camera alone while mouse_pan and mouse_zoom are false."""
    v = view()
    v.camera.mouse_pan = v.camera.mouse_zoom = False
    attach(v, surface)
    surface.emit(pointer("pointer_down", 100, 50, button=1))
    surface.emit(pointer("pointer_move", 120, 60, button=1))
    surface.emit(wheel(150, 20, dy=-120))
    assert (v.camera.center, v.camera.zoom) == ((10.0, 20.0), 2.0)


def test_resize_updates_canvas_size(surface):
    """Write the surface's logical size into the view."""
    v = view()
    attach(v, surface)
    surface.emit(
        {"event_type": "resize", "width": 300.0, "height": 150.0, "pixel_ratio": 1.0}
    )
    assert v.canvas_size == (300, 150)


def test_zero_sized_surface_moves_nothing(surface):
    """Ignore input on a surface with no area."""
    v = view(size=(0, 0))
    attach(v, surface)
    surface.emit(wheel(0, 0, dy=-120))
    surface.emit(pointer("pointer_down", 0, 0, button=1))
    surface.emit(pointer("pointer_move", 5, 5, button=1))
    assert (v.camera.center, v.camera.zoom) == ((10.0, 20.0), 2.0)
