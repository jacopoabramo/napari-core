import gc
import logging
import weakref
from collections.abc import Callable

import numpy as np
import numpy.typing as npt
import pytest
from helpers import assign, mouse_move, mouse_press, mouse_release, wait
from PyQt6 import sip
from PyQt6.QtCore import QCoreApplication, QEvent, QPoint, QPointF, Qt
from PyQt6.QtGui import QImage, QWheelEvent
from PyQt6.QtWidgets import QApplication, QWidget

from napari_core.interaction import attach
from napari_core.model import (
    COLORMAPS,
    Camera,
    Image,
    IntensityAppearance,
    Layer,
    Transform,
    ViewerModel,
)
from napari_core.render import (
    LayerAdapter,
    RenderSurface,
    SurfaceEvent,
    create_layer_adapter,
)
from napari_core.render.vispy import VispyBackend

pytestmark = pytest.mark.gl

BACKGROUND = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
BLUE = (0, 0, 255)


class Undrawable(Layer):
    """A layer type that the vispy backend has no adapter for."""

    data: int = 0

    @property
    def ndim(self) -> int:
        return 2

    @property
    def extent_steps(self) -> tuple[int, ...]:
        return (2, 2)

    def slice(self, dims: object) -> npt.NDArray[np.uint8]:
        return np.zeros((2, 2), dtype=np.uint8)


def undrawable() -> Undrawable:
    """Return a layer of a type the vispy backend cannot draw."""
    return Undrawable(
        name="p", transform=Transform(scale=(1.0, 1.0), translate=(0.0, 0.0))
    )


def white_image() -> Image:
    """Return a 50 by 50 image whose pixels all map to white."""
    return Image(
        name="a",
        data=np.full((50, 50), 255, dtype=np.uint8),
        appearance=IntensityAppearance(contrast_limits=(0.0, 255.0)),
    )


def shown(viewer: ViewerModel, qapp: QApplication) -> RenderSurface[QWidget]:
    """Return a surface of the viewer's view, shown at 200 by 100 pixels."""
    surface = VispyBackend[QWidget]().create_surface(viewer.view, None)
    viewer.view.canvas_size = (200, 100)
    surface.native.resize(200, 100)
    surface.native.show()
    qapp.processEvents()
    return surface


def middle(shot: npt.NDArray[np.uint8]) -> tuple[int, ...]:
    """Return the RGB value of the middle pixel of `shot`."""
    return tuple(shot[shot.shape[0] // 2, shot.shape[1] // 2, :3])


def grab(native: QWidget) -> npt.NDArray[np.uint8]:
    """Return the RGBA rows of a screenshot of `native`."""
    image = native.grab().toImage().convertToFormat(QImage.Format.Format_RGBA8888)
    bits = image.constBits()
    assert bits is not None
    pixels = np.frombuffer(bits.asstring(image.sizeInBytes()), dtype=np.uint8)
    return pixels.reshape(image.height(), image.width(), 4).copy()


def test_image_is_drawn(qapp: QApplication) -> None:
    """Draw a white image so the middle of the screenshot is not background."""
    viewer = ViewerModel()
    viewer.layers.append(white_image())
    viewer.camera.center = (25.0, 25.0)
    surface = shown(viewer, qapp)
    shot = surface.screenshot()
    assert shot.dtype == np.uint8 and shot.shape[2] == 4
    assert middle(shot) != BACKGROUND
    surface.close()


def test_hidden_layer_is_not_drawn(qapp: QApplication) -> None:
    """Draw nothing for a layer that is not visible."""
    viewer = ViewerModel()
    layer = white_image()
    viewer.layers.append(layer)
    viewer.camera.center = (25.0, 25.0)
    surface = shown(viewer, qapp)
    assert middle(surface.screenshot()) != BACKGROUND
    layer.visible = False
    qapp.processEvents()
    assert middle(surface.screenshot()) == BACKGROUND
    surface.close()


def test_camera_change_moves_the_image(qapp: QApplication) -> None:
    """Follow the model camera, so panning far away leaves the middle empty."""
    viewer = ViewerModel()
    viewer.layers.append(white_image())
    viewer.camera.center = (25.0, 25.0)
    surface = shown(viewer, qapp)
    assert middle(surface.screenshot()) != BACKGROUND
    viewer.camera.center = (10_000.0, 10_000.0)
    qapp.processEvents()
    assert middle(surface.screenshot()) == BACKGROUND
    surface.close()


def test_surface_follows_the_camera_after_a_refused_replacement(
    qapp: QApplication,
) -> None:
    """Keep following the camera's fields after assigning a new camera failed."""
    viewer = ViewerModel()
    viewer.layers.append(white_image())
    viewer.camera.center = (25.0, 25.0)
    surface = shown(viewer, qapp)
    with pytest.raises(ValueError, match="frozen"):
        assign(viewer.view, "camera", Camera(center=(10_000.0, 10_000.0)))
    assert middle(surface.screenshot()) != BACKGROUND
    viewer.camera.center = (10_000.0, 10_000.0)
    assert middle(surface.screenshot()) == BACKGROUND
    surface.close()


def test_removed_layer_disappears(qapp: QApplication) -> None:
    """Remove a layer's visual when the layer leaves the list."""
    viewer = ViewerModel()
    layer = white_image()
    viewer.layers.append(layer)
    viewer.camera.center = (25.0, 25.0)
    surface = shown(viewer, qapp)
    assert middle(surface.screenshot()) != BACKGROUND
    viewer.layers.remove(layer)
    layer.gamma = 0.5
    qapp.processEvents()
    assert middle(surface.screenshot()) == BACKGROUND
    surface.close()


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


def test_layer_added_later_is_drawn(qapp: QApplication) -> None:
    """Draw a layer appended after the surface exists."""
    viewer = ViewerModel()
    viewer.camera.center = (25.0, 25.0)
    surface = shown(viewer, qapp)
    viewer.layers.append(white_image())
    qapp.processEvents()
    assert middle(surface.screenshot()) != BACKGROUND
    surface.close()


def test_image_orientation_and_pixel_centres(qapp: QApplication) -> None:
    """Put row 0 at the top, column 0 at the left and pixel (0, 0) on world (0, 0)."""
    data = np.zeros((3, 3), dtype=np.uint8)
    data[0, 0] = 255
    viewer = ViewerModel()
    viewer.layers.append(
        Image(
            name="a",
            data=data,
            appearance=IntensityAppearance(contrast_limits=(0.0, 255.0)),
        )
    )
    viewer.camera.center = (1.0, 1.0)
    viewer.camera.zoom = 20.0
    surface = shown(viewer, qapp)
    shot = surface.screenshot()
    ratio = shot.shape[1] / 200

    def bright(x: float, y: float) -> bool:
        return bool(shot[int(y * ratio), int(x * ratio), 0] > 128)

    # World (0, 0) is at screen (80, 30); the pixel spans x 70..90, y 20..40.
    assert bright(80, 30)
    assert bright(71, 30) and bright(89, 30) and bright(80, 21) and bright(80, 39)
    assert not bright(69, 30) and not bright(91, 30)
    assert not bright(80, 19) and not bright(80, 41)
    assert not bright(120, 30) and not bright(80, 70) and not bright(120, 70)
    surface.close()


def turn_wheel_away(native: QWidget, notches: int) -> None:
    """Send `native` a wheel event of `notches` turned away from the user."""
    centre = QPointF(100.0, 50.0)
    event = QWheelEvent(
        centre,
        QPointF(native.mapToGlobal(centre)),
        QPoint(0, 0),
        QPoint(0, 120 * notches),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(native, event)


def test_wheel_away_from_the_user_zooms_in(qapp: QApplication) -> None:
    """Report a wheel notch away from the user as dy of -120, which zooms in."""
    viewer = ViewerModel()
    surface = shown(viewer, qapp)
    seen: list[SurfaceEvent] = []
    surface.add_event_handler(seen.append, "wheel")
    attach(viewer.view, surface)
    turn_wheel_away(surface.native, 2)
    (event,) = seen
    assert event["event_type"] == "wheel"
    assert (event["dx"], event["dy"]) == (0.0, -240.0)
    assert viewer.camera.zoom == pytest.approx(1.1**2.4)
    surface.close()


def test_resize_of_the_widget_writes_the_canvas_size(qapp: QApplication) -> None:
    """Write the widget's new logical size into the view of an attached surface."""
    viewer = ViewerModel()
    surface = shown(viewer, qapp)
    attach(viewer.view, surface)
    surface.native.resize(300, 150)
    qapp.processEvents()
    assert viewer.view.canvas_size == (300, 150)
    surface.close()


def test_unattached_surface_keeps_the_default_canvas_size(qapp: QApplication) -> None:
    """Leave the view's canvas size alone when no dispatcher is attached."""
    viewer = ViewerModel()
    default = viewer.view.canvas_size
    surface = VispyBackend[QWidget]().create_surface(viewer.view, None)
    surface.native.resize(300, 150)
    surface.native.show()
    qapp.processEvents()
    assert surface.get_logical_size() == (300.0, 150.0)
    assert viewer.view.canvas_size == default
    surface.close()


def test_mouse_press_reaches_handlers_in_rendercanvas_vocabulary(
    qapp: QApplication,
) -> None:
    """Translate a real Qt mouse press into a pointer_down surface event."""
    viewer = ViewerModel()
    surface = shown(viewer, qapp)
    seen: list[SurfaceEvent] = []
    surface.add_event_handler(seen.append, "pointer_down")
    # Presses are not coalesced, so the handler has run when mousePress returns.
    mouse_press(surface.native, Qt.MouseButton.LeftButton, QPoint(30, 40))
    (event,) = seen
    assert event["event_type"] == "pointer_down"
    assert (event["x"], event["y"], event["button"]) == (30.0, 40.0, 1)
    surface.close()


def test_replaced_appearance_is_drawn_and_the_old_one_is_not_followed(
    qapp: QApplication,
) -> None:
    """Show a replacement appearance, follow its fields and ignore the old one's."""
    viewer = ViewerModel()
    layer = white_image()
    viewer.layers.append(layer)
    viewer.camera.center = (25.0, 25.0)
    surface = shown(viewer, qapp)
    old = layer.appearance
    assert middle(surface.screenshot()) == WHITE
    layer.appearance = IntensityAppearance(
        colormap=COLORMAPS["red"], contrast_limits=(0.0, 255.0)
    )
    assert middle(surface.screenshot()) == RED
    old.colormap = COLORMAPS["green"]
    assert middle(surface.screenshot()) == RED
    layer.appearance.colormap = COLORMAPS["blue"]
    assert middle(surface.screenshot()) == BLUE
    surface.close()


def test_replaced_transform_is_drawn_and_the_old_one_is_not_followed(
    qapp: QApplication,
) -> None:
    """Place by a replacement transform, follow its fields and ignore the old one's."""
    viewer = ViewerModel()
    layer = white_image()
    viewer.layers.append(layer)
    viewer.camera.center = (25.0, 25.0)
    surface = shown(viewer, qapp)
    old = layer.transform
    assert middle(surface.screenshot()) == WHITE
    layer.transform = Transform(scale=(1.0, 1.0), translate=(10_000.0, 10_000.0))
    assert middle(surface.screenshot()) == BACKGROUND
    old.translate = (0.0, 0.0)
    old.scale = (2.0, 2.0)
    assert middle(surface.screenshot()) == BACKGROUND
    layer.transform.translate = (0.0, 0.0)
    assert middle(surface.screenshot()) == WHITE
    surface.close()


def test_transform_places_the_centre_of_pixel_zero_at_translate(
    qapp: QApplication,
) -> None:
    """Centre pixel (0, 0) on the translation when the scale is not 1."""
    data = np.zeros((3, 3), dtype=np.uint8)
    data[0, 0] = 255
    viewer = ViewerModel()
    viewer.layers.append(
        Image(
            name="a",
            data=data,
            transform=Transform(scale=(2.0, 3.0), translate=(5.0, 7.0)),
            appearance=IntensityAppearance(contrast_limits=(0.0, 255.0)),
        )
    )
    viewer.camera.center = (5.0, 7.0)
    viewer.camera.zoom = 10.0
    surface = shown(viewer, qapp)
    shot = surface.screenshot()
    ratio = shot.shape[1] / 200

    def bright(x: float, y: float) -> bool:
        return bool(shot[int(y * ratio), int(x * ratio), 0] > 128)

    # The pixel is 3 world units wide and 2 high: x 85..115 and y 40..60.
    assert bright(100, 50)
    assert bright(86, 50) and bright(114, 50) and bright(100, 41) and bright(100, 59)
    assert not bright(84, 50) and not bright(116, 50)
    assert not bright(100, 39) and not bright(100, 61)
    surface.close()


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


def test_undrawable_layer_appended_later_is_logged_and_skipped(
    qapp: QApplication, caplog: pytest.LogCaptureFixture
) -> None:
    """Log a later undrawable layer once and keep drawing the others."""
    viewer = ViewerModel()
    viewer.camera.center = (25.0, 25.0)
    surface = shown(viewer, qapp)
    caplog.set_level(logging.ERROR, logger="napari_core")
    layer = undrawable()
    viewer.layers.append(layer)
    viewer.layers.append(white_image())
    qapp.processEvents()
    assert middle(surface.screenshot()) == WHITE
    (record,) = caplog.records
    assert "'p'" in record.getMessage() and "Undrawable" in record.getMessage()
    assert record.exc_info is not None
    viewer.layers.remove(layer)
    assert len(caplog.records) == 1
    surface.close()


def test_equal_replacement_appearance_is_followed_and_the_old_one_is_not(
    qapp: QApplication,
) -> None:
    """Follow a replacement appearance that equals the old one."""
    viewer = ViewerModel()
    layer = white_image()
    viewer.layers.append(layer)
    viewer.camera.center = (25.0, 25.0)
    surface = shown(viewer, qapp)
    old = layer.appearance
    layer.appearance = old.model_copy()
    assert layer.appearance == old and layer.appearance is not old
    old.colormap = COLORMAPS["green"]
    assert middle(surface.screenshot()) == WHITE
    layer.appearance.colormap = COLORMAPS["blue"]
    assert middle(surface.screenshot()) == BLUE
    surface.close()


def test_equal_replacement_transform_is_followed_and_the_old_one_is_not(
    qapp: QApplication,
) -> None:
    """Follow a replacement transform that equals the old one."""
    viewer = ViewerModel()
    layer = white_image()
    viewer.layers.append(layer)
    viewer.camera.center = (25.0, 25.0)
    surface = shown(viewer, qapp)
    old = layer.transform
    layer.transform = old.model_copy()
    assert layer.transform == old and layer.transform is not old
    old.translate = (10_000.0, 10_000.0)
    assert middle(surface.screenshot()) == WHITE
    layer.transform.translate = (10_000.0, 10_000.0)
    assert middle(surface.screenshot()) == BACKGROUND
    surface.close()


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


def test_closed_surface_is_freed_and_ignores_the_model(qapp: QApplication) -> None:
    """Free a closed surface once nothing refers to it and ignore later changes."""
    viewer = ViewerModel()
    viewer.layers.append(white_image())
    surface = shown(viewer, qapp)
    reference = weakref.ref(surface)
    surface.close()
    del surface
    gc.collect()
    assert reference() is None
    viewer.camera.center = (10_000.0, 10_000.0)
    viewer.layers[0].gamma = 0.5
    viewer.layers.clear()


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
