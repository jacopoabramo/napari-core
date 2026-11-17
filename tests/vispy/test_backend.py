import gc
import logging
import weakref
from collections.abc import Callable

import numpy as np
import numpy.typing as npt
import pytest
from helpers import (
    middle,
    mouse_move,
    mouse_press,
    mouse_release,
    undrawable,
    wait,
    white_image,
)
from PyQt6 import sip
from PyQt6.QtCore import QCoreApplication, QEvent, QPoint, Qt
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication, QWidget

from napari_core.interaction import attach
from napari_core.model import ViewerModel
from napari_core.render import (
    LayerAdapter,
    RenderSurface,
    SurfaceEvent,
    create_layer_adapter,
)
from napari_core.render.vispy import VispyBackend

pytestmark = pytest.mark.gl

BACKGROUND = (0, 0, 0)


def shown(viewer: ViewerModel, qapp: QApplication) -> RenderSurface[QWidget]:
    """Return a surface of the viewer's view, shown at 200 by 100 pixels."""
    surface = VispyBackend[QWidget]().create_surface(viewer.view, None)
    viewer.view.canvas_size = (200, 100)
    surface.native.resize(200, 100)
    surface.native.show()
    qapp.processEvents()
    return surface


def grab(native: QWidget) -> npt.NDArray[np.uint8]:
    """Return the RGBA rows of a screenshot of `native`."""
    image = native.grab().toImage().convertToFormat(QImage.Format.Format_RGBA8888)
    bits = image.constBits()
    assert bits is not None
    pixels = np.frombuffer(bits.asstring(image.sizeInBytes()), dtype=np.uint8)
    return pixels.reshape(image.height(), image.width(), 4).copy()


def test_closed_adapter_ignores_the_layer(
    qapp: QApplication,
    visual_state: Callable[[LayerAdapter], tuple[float, tuple[float, float]]],
) -> None:
    """Keep the visual as it was when the adapter closed, whatever changes."""
    viewer = ViewerModel()
    layer = white_image()
    viewer.layers.append(layer)
    adapter = create_layer_adapter("vispy", layer, viewer.view)
    adapter.close()
    layer.gamma = 0.5
    layer.contrast_limits = (10.0, 20.0)
    assert visual_state(adapter) == (1.0, (0.0, 255.0))


def test_failed_surface_closes_its_canvas_and_logs_no_error(
    qapp: QApplication,
    closed_canvases: list[object],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Close the canvas quietly when a layer has no adapter and the surface fails."""
    viewer = ViewerModel()
    viewer.layers.append(undrawable())
    caplog.set_level(logging.ERROR)
    caplog.set_level(logging.ERROR, logger="vispy")
    with pytest.raises(LookupError):
        VispyBackend[QWidget]().create_surface(viewer.view, None)
    assert len(closed_canvases) == 1
    assert not caplog.records


def only_native(
    viewer: ViewerModel, qapp: QApplication, seen: list[SurfaceEvent]
) -> QWidget:
    """Return the native widget of a shown, attached surface that is then dropped."""
    surface = shown(viewer, qapp)
    surface.add_event_handler(seen.append, "pointer_down")
    attach(viewer.view, surface)
    return surface.native


def test_surface_works_while_only_its_widget_is_kept(qapp: QApplication) -> None:
    """Keep following the model, reaching handlers and panning without the surface."""
    viewer = ViewerModel()
    viewer.layers.append(white_image())
    viewer.camera.center = (25.0, 25.0)
    seen: list[SurfaceEvent] = []
    native = only_native(viewer, qapp, seen)
    gc.collect()
    assert middle(grab(native)) != BACKGROUND
    viewer.camera.center = (10_000.0, 10_000.0)
    qapp.processEvents()
    assert middle(grab(native)) == BACKGROUND
    viewer.camera.center = (25.0, 25.0)
    mouse_press(native, Qt.MouseButton.LeftButton, QPoint(30, 40))
    assert [event["event_type"] for event in seen] == ["pointer_down"]
    mouse_move(native, QPoint(30, 40), Qt.MouseButton.LeftButton)
    for offset in range(1, 6):
        mouse_move(native, QPoint(30 + 4 * offset, 40), Qt.MouseButton.LeftButton)
        wait(20)
    mouse_release(native, Qt.MouseButton.LeftButton, QPoint(50, 40))
    assert viewer.camera.center[1] < 25.0
    native.close()
    native.deleteLater()


def test_close_deletes_the_native_widget(qapp: QApplication) -> None:
    """Have Qt delete the widget of a closed surface at its next deferred delete."""
    surface = shown(ViewerModel(), qapp)
    native = surface.native
    surface.close()
    assert not sip.isdeleted(native)
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
    assert sip.isdeleted(native)


def test_widget_close_keeps_the_surface_until_it_is_closed(
    qapp: QApplication,
) -> None:
    """Keep a dropped surface reacting after the widget's close, until it is closed."""
    viewer = ViewerModel()
    viewer.layers.append(white_image())
    viewer.camera.center = (25.0, 25.0)
    surface = shown(viewer, qapp)
    native = surface.native
    reference = weakref.ref(surface)
    native.close()
    del surface
    gc.collect()
    kept = reference()
    assert kept is not None
    assert middle(kept.screenshot()) != BACKGROUND
    viewer.camera.center = (10_000.0, 10_000.0)
    assert middle(kept.screenshot()) == BACKGROUND
    kept.close()
    kept.close()
    del kept, native
    gc.collect()
    assert reference() is None
