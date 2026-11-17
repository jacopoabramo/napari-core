import gc
import weakref

import numpy as np
import pytest
from helpers import mouse_press, turn_wheel_away, until, white_image
from PyQt6.QtCore import QCoreApplication, QEvent, QPoint, Qt
from PyQt6.QtWidgets import QApplication, QWidget

from napari_core.interaction import attach
from napari_core.model import ViewerModel
from napari_core.render import (
    RenderSurface,
    SurfaceEvent,
    SurfacePointerEvent,
    SurfaceWheelEvent,
)
from napari_core.render.pygfx import PygfxBackend

pytestmark = pytest.mark.gl


def shown(
    backend: PygfxBackend[QWidget], viewer: ViewerModel, qapp: QApplication
) -> RenderSurface[QWidget]:
    """Return a surface of the viewer's view, shown at 200 by 100 pixels."""
    surface = backend.create_surface(viewer.view, None)
    viewer.view.canvas_size = (200, 100)
    surface.native.resize(200, 100)
    surface.native.show()
    qapp.processEvents()
    return surface


def test_screenshot_has_the_physical_size(
    qapp: QApplication, backend: PygfxBackend[QWidget]
) -> None:
    """Return a screenshot of the surface's physical size, as RGBA bytes."""
    surface = backend.create_surface(ViewerModel().view, None)
    surface.native.resize(200, 100)
    surface.native.show()
    qapp.processEvents()
    width, height = surface.get_physical_size()
    shot = surface.screenshot()
    assert shot.dtype == np.uint8
    assert shot.shape == (height, width, 4)
    surface.close()


def test_window_close_closes_the_surface(
    qapp: QApplication, backend: PygfxBackend[QWidget]
) -> None:
    """Release a surface whose window Qt closed and deleted, and accept its close."""
    viewer = ViewerModel()
    viewer.layers.append(white_image())
    surface = shown(backend, viewer, qapp)
    attach(viewer.view, surface)
    reference = weakref.ref(surface)
    surface.native.close()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
    viewer.camera.center = (10_000.0, 10_000.0)
    viewer.layers[0].gamma = 0.5
    attach(viewer.view, surface)
    surface.close()
    del surface
    gc.collect()
    assert reference() is None
    viewer.layers.clear()


def test_background_is_opaque_black(
    qapp: QApplication, backend: PygfxBackend[QWidget]
) -> None:
    """Draw the empty background as opaque black, not as transparent pixels."""
    surface = shown(backend, ViewerModel(), qapp)
    assert tuple(surface.screenshot()[0, 0]) == (0, 0, 0, 255)
    surface.close()


def test_events_have_float_positions_and_only_the_surface_keys(
    qapp: QApplication, backend: PygfxBackend[QWidget]
) -> None:
    """Emit pointer and wheel events with float numbers and no other keys."""
    surface = shown(backend, ViewerModel(), qapp)
    seen: list[SurfaceEvent] = []
    surface.add_event_handler(seen.append, "pointer_down", "wheel")
    mouse_press(surface.native, Qt.MouseButton.LeftButton, QPoint(30, 40))
    turn_wheel_away(surface.native, 1)
    until(lambda: len(seen) == 2, surface, message="a press and a wheel turn")
    press, turn = seen
    assert press["event_type"] == "pointer_down" and turn["event_type"] == "wheel"
    assert set(press) == SurfacePointerEvent.__required_keys__
    assert set(turn) == SurfaceWheelEvent.__required_keys__
    numbers = [press["x"], press["y"], turn["x"], turn["y"], turn["dx"], turn["dy"]]
    assert all(type(number) is float for number in numbers)
    surface.close()


def test_canvas_class_that_is_not_a_rendercanvas_is_refused(
    qapp: QApplication,
) -> None:
    """Raise TypeError when the canvas class makes a widget that is not a canvas."""
    with pytest.raises(TypeError, match="rendercanvas"):
        PygfxBackend[QWidget](canvas_class=lambda _parent: QWidget()).create_surface(
            ViewerModel().view, None
        )
