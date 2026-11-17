import gc
import logging
import weakref
from typing import Final

import numpy as np
import pytest
from helpers import (
    Show,
    assign,
    middle,
    mouse_move,
    mouse_press,
    mouse_release,
    turn_wheel_away,
    undrawable,
    until,
    white_image,
)
from PyQt6.QtCore import QEvent, QPoint, Qt
from PyQt6.QtWidgets import QApplication, QWidget

from napari_core.interaction import attach
from napari_core.model import (
    COLORMAPS,
    Camera,
    Image,
    IntensityAppearance,
    Interpolation,
    Transform,
    ViewerModel,
)
from napari_core.render import RenderBackend, RenderSurface, SurfaceEvent

pytestmark = pytest.mark.gl

BACKGROUND = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
LACKS_LANCZOS: Final = frozenset({"pygfx"})


def test_image_is_drawn(shown: Show) -> None:
    """Draw a white image so the middle of the screenshot is not background."""
    viewer = ViewerModel()
    viewer.layers.append(white_image())
    viewer.camera.center = (25.0, 25.0)
    surface = shown(viewer)
    shot = surface.screenshot()
    assert shot.dtype == np.uint8 and shot.shape[2] == 4
    assert middle(shot) != BACKGROUND
    surface.close()


def test_hidden_layer_is_not_drawn(qapp: QApplication, shown: Show) -> None:
    """Draw nothing for a layer that is not visible."""
    viewer = ViewerModel()
    layer = white_image()
    viewer.layers.append(layer)
    viewer.camera.center = (25.0, 25.0)
    surface = shown(viewer)
    assert middle(surface.screenshot()) != BACKGROUND
    layer.visible = False
    qapp.processEvents()
    assert middle(surface.screenshot()) == BACKGROUND
    surface.close()


def test_camera_change_moves_the_image(qapp: QApplication, shown: Show) -> None:
    """Follow the model camera, so panning far away leaves the middle empty."""
    viewer = ViewerModel()
    viewer.layers.append(white_image())
    viewer.camera.center = (25.0, 25.0)
    surface = shown(viewer)
    assert middle(surface.screenshot()) != BACKGROUND
    viewer.camera.center = (10_000.0, 10_000.0)
    qapp.processEvents()
    assert middle(surface.screenshot()) == BACKGROUND
    surface.close()


def test_surface_follows_the_camera_after_a_refused_replacement(
    shown: Show,
) -> None:
    """Keep following the camera's fields after assigning a new camera failed."""
    viewer = ViewerModel()
    viewer.layers.append(white_image())
    viewer.camera.center = (25.0, 25.0)
    surface = shown(viewer)
    with pytest.raises(ValueError, match="frozen"):
        assign(viewer.view, "camera", Camera(center=(10_000.0, 10_000.0)))
    assert middle(surface.screenshot()) != BACKGROUND
    viewer.camera.center = (10_000.0, 10_000.0)
    assert middle(surface.screenshot()) == BACKGROUND
    surface.close()


def test_removed_layer_disappears(qapp: QApplication, shown: Show) -> None:
    """Remove a layer's visual when the layer leaves the list."""
    viewer = ViewerModel()
    layer = white_image()
    viewer.layers.append(layer)
    viewer.camera.center = (25.0, 25.0)
    surface = shown(viewer)
    assert middle(surface.screenshot()) != BACKGROUND
    viewer.layers.remove(layer)
    layer.gamma = 0.5
    qapp.processEvents()
    assert middle(surface.screenshot()) == BACKGROUND
    surface.close()


def test_layer_added_later_is_drawn(qapp: QApplication, shown: Show) -> None:
    """Draw a layer appended after the surface exists."""
    viewer = ViewerModel()
    viewer.camera.center = (25.0, 25.0)
    surface = shown(viewer)
    viewer.layers.append(white_image())
    qapp.processEvents()
    assert middle(surface.screenshot()) != BACKGROUND
    surface.close()


def test_image_orientation_and_pixel_centres(shown: Show) -> None:
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
    surface = shown(viewer)
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


def test_wheel_away_from_the_user_zooms_in(shown: Show) -> None:
    """Report a wheel notch away from the user as dy of -120, which zooms in."""
    viewer = ViewerModel()
    surface = shown(viewer)
    seen: list[SurfaceEvent] = []
    surface.add_event_handler(seen.append, "wheel")
    attach(viewer.view, surface)
    turn_wheel_away(surface.native, 2)
    (event,) = seen
    assert event["event_type"] == "wheel"
    assert (event["dx"], event["dy"]) == (0.0, -240.0)
    assert viewer.camera.zoom == pytest.approx(1.1**2.4)
    surface.close()


def test_resize_of_the_widget_writes_the_canvas_size(
    qapp: QApplication,
    shown: Show,
) -> None:
    """Write the widget's new logical size into the view of an attached surface."""
    viewer = ViewerModel()
    surface = shown(viewer)
    attach(viewer.view, surface)
    surface.native.resize(300, 150)
    qapp.processEvents()
    assert viewer.view.canvas_size == (300, 150)
    surface.close()


def test_unattached_surface_keeps_the_default_canvas_size(
    qapp: QApplication,
    backend: RenderBackend[QWidget],
) -> None:
    """Leave the view's canvas size alone when no dispatcher is attached."""
    viewer = ViewerModel()
    default = viewer.view.canvas_size
    surface = backend.create_surface(viewer.view, None)
    surface.native.resize(300, 150)
    surface.native.show()
    qapp.processEvents()
    assert surface.get_logical_size() == (300.0, 150.0)
    assert viewer.view.canvas_size == default
    surface.close()


def test_mouse_press_reaches_handlers_in_rendercanvas_vocabulary(
    shown: Show,
) -> None:
    """Translate a real Qt mouse press into a pointer_down surface event."""
    viewer = ViewerModel()
    surface = shown(viewer)
    seen: list[SurfaceEvent] = []
    surface.add_event_handler(seen.append, "pointer_down")
    # Presses are not coalesced, so the handler has run when mousePress returns.
    mouse_press(surface.native, Qt.MouseButton.LeftButton, QPoint(30, 40))
    (event,) = seen
    assert event["event_type"] == "pointer_down"
    assert (event["x"], event["y"], event["button"]) == (30.0, 40.0, 1)
    assert event["buttons"] == (1,)
    surface.close()


def test_pointer_move_has_no_button_and_lists_the_held_ones(shown: Show) -> None:
    """Emit pointer_move with button 0 and the pressed buttons during a drag."""
    surface = shown(ViewerModel())
    seen: list[SurfaceEvent] = []
    surface.add_event_handler(seen.append, "pointer_move")
    mouse_press(surface.native, Qt.MouseButton.LeftButton, QPoint(30, 40))
    mouse_move(surface.native, QPoint(40, 40), Qt.MouseButton.LeftButton)
    until(lambda: bool(seen), surface, message="a pointer_move event")
    move = seen[-1]
    assert move["event_type"] == "pointer_move"
    assert (move["button"], move["buttons"]) == (0, (1,))
    surface.close()


def test_replaced_appearance_is_drawn_and_the_old_one_is_not_followed(
    shown: Show,
) -> None:
    """Show a replacement appearance, follow its fields and ignore the old one's."""
    viewer = ViewerModel()
    layer = white_image()
    viewer.layers.append(layer)
    viewer.camera.center = (25.0, 25.0)
    surface = shown(viewer)
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
    shown: Show,
) -> None:
    """Place by a replacement transform, follow its fields and ignore the old one's."""
    viewer = ViewerModel()
    layer = white_image()
    viewer.layers.append(layer)
    viewer.camera.center = (25.0, 25.0)
    surface = shown(viewer)
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
    shown: Show,
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
    surface = shown(viewer)
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


def test_undrawable_layer_appended_later_is_logged_and_skipped(
    qapp: QApplication,
    caplog: pytest.LogCaptureFixture,
    shown: Show,
) -> None:
    """Log a later undrawable layer once and keep drawing the others."""
    viewer = ViewerModel()
    viewer.camera.center = (25.0, 25.0)
    surface = shown(viewer)
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
    shown: Show,
) -> None:
    """Follow a replacement appearance that equals the old one."""
    viewer = ViewerModel()
    layer = white_image()
    viewer.layers.append(layer)
    viewer.camera.center = (25.0, 25.0)
    surface = shown(viewer)
    old = layer.appearance
    layer.appearance = old.model_copy()
    assert layer.appearance == old and layer.appearance is not old
    old.colormap = COLORMAPS["green"]
    assert middle(surface.screenshot()) == WHITE
    layer.appearance.colormap = COLORMAPS["blue"]
    assert middle(surface.screenshot()) == BLUE
    surface.close()


def test_equal_replacement_transform_is_followed_and_the_old_one_is_not(
    shown: Show,
) -> None:
    """Follow a replacement transform that equals the old one."""
    viewer = ViewerModel()
    layer = white_image()
    viewer.layers.append(layer)
    viewer.camera.center = (25.0, 25.0)
    surface = shown(viewer)
    old = layer.transform
    layer.transform = old.model_copy()
    assert layer.transform == old and layer.transform is not old
    old.translate = (10_000.0, 10_000.0)
    assert middle(surface.screenshot()) == WHITE
    layer.transform.translate = (10_000.0, 10_000.0)
    assert middle(surface.screenshot()) == BACKGROUND
    surface.close()


def test_closed_surface_is_freed_and_ignores_the_model(
    shown: Show,
) -> None:
    """Free a closed surface once nothing refers to it and ignore later changes."""
    viewer = ViewerModel()
    viewer.layers.append(white_image())
    surface = shown(viewer)
    reference = weakref.ref(surface)
    surface.close()
    del surface
    gc.collect()
    assert reference() is None
    viewer.camera.center = (10_000.0, 10_000.0)
    viewer.layers[0].gamma = 0.5
    viewer.layers.clear()


def test_closed_surface_is_freed_while_its_widget_is_held(shown: Show) -> None:
    """Free a closed surface even when the caller still holds its widget."""
    surface = shown(ViewerModel())
    native = surface.native
    reference = weakref.ref(surface)
    surface.close()
    del surface
    gc.collect()
    assert reference() is None
    assert native is not None


def test_undrawable_layer_in_the_view_makes_create_surface_raise(
    backend: RenderBackend[QWidget],
) -> None:
    """Raise LookupError when a layer already in the view has no adapter."""
    viewer = ViewerModel()
    viewer.layers.append(undrawable())
    with pytest.raises(LookupError):
        backend.create_surface(viewer.view, None)


def test_closing_twice_does_nothing(shown: Show) -> None:
    """Accept a second close of a surface."""
    surface = shown(ViewerModel())
    surface.close()
    surface.close()


def press_and_release(surface: RenderSurface[QWidget]) -> None:
    """Press and release the left button on the surface."""
    position = QPoint(30, 40)
    mouse_press(surface.native, Qt.MouseButton.LeftButton, position)
    mouse_release(surface.native, Qt.MouseButton.LeftButton, position)


def kinds(events: list[SurfaceEvent]) -> list[str]:
    """Return the event types of `events`."""
    return [event["event_type"] for event in events]


def test_removed_handler_is_not_called(shown: Show) -> None:
    """Stop calling a handler once it is removed from the surface."""
    surface = shown(ViewerModel())
    removed: list[SurfaceEvent] = []
    kept: list[SurfaceEvent] = []
    surface.add_event_handler(removed.append, "pointer_down", "pointer_up")
    surface.add_event_handler(kept.append, "pointer_down", "pointer_up")
    surface.remove_event_handler(removed.append, "pointer_down", "pointer_up")
    press_and_release(surface)
    assert kinds(kept) == ["pointer_down", "pointer_up"]
    assert removed == []


def test_remove_without_types_removes_every_type(shown: Show) -> None:
    """Remove a handler from all its event types when no type is given."""
    surface = shown(ViewerModel())
    removed: list[SurfaceEvent] = []
    kept: list[SurfaceEvent] = []
    surface.add_event_handler(removed.append, "pointer_down", "pointer_up")
    surface.add_event_handler(kept.append, "pointer_down", "pointer_up")
    surface.remove_event_handler(removed.append)
    press_and_release(surface)
    assert kinds(kept) == ["pointer_down", "pointer_up"]
    assert removed == []


def test_remove_for_some_types_keeps_the_others(shown: Show) -> None:
    """Keep calling a handler for the types it was not removed from."""
    surface = shown(ViewerModel())
    seen: list[SurfaceEvent] = []
    surface.add_event_handler(seen.append, "pointer_down", "pointer_up")
    surface.remove_event_handler(seen.append, "pointer_down")
    press_and_release(surface)
    assert kinds(seen) == ["pointer_up"]


def test_remove_of_unknown_handler_does_nothing(shown: Show) -> None:
    """Accept the removal of a handler that was never added."""
    surface = shown(ViewerModel())
    seen: list[SurfaceEvent] = []
    surface.remove_event_handler(seen.append, "pointer_down")


def test_detach_after_close_does_nothing(shown: Show) -> None:
    """Accept a detach of a surface that is already closed."""
    viewer = ViewerModel()
    surface = shown(viewer)
    detach = attach(viewer.view, surface)
    surface.close()
    detach()


def test_closed_surface_can_be_attached_again(shown: Show) -> None:
    """Do not count a closed surface as attached."""
    viewer = ViewerModel()
    surface = shown(viewer)
    attach(viewer.view, surface)
    surface.close()
    attach(viewer.view, surface)


def test_pointer_enter_and_leave_are_emitted(shown: Show) -> None:
    """Emit pointer_enter and pointer_leave when Qt reports them to the widget."""
    surface = shown(ViewerModel())
    seen: list[SurfaceEvent] = []
    surface.add_event_handler(seen.append, "pointer_enter", "pointer_leave")
    QApplication.sendEvent(surface.native, QEvent(QEvent.Type.Enter))
    QApplication.sendEvent(surface.native, QEvent(QEvent.Type.Leave))
    until(lambda: len(seen) == 2, surface, message="enter and leave")
    assert [event["event_type"] for event in seen] == ["pointer_enter", "pointer_leave"]
    surface.close()


def test_lanczos_is_kept_by_the_model_and_warned_about_where_it_cannot_be_drawn(
    shown: Show, backend: RenderBackend[QWidget], caplog: pytest.LogCaptureFixture
) -> None:
    """Keep lanczos in the model and warn once on a backend that lacks it."""
    viewer = ViewerModel()
    layer = white_image()
    layer.interpolation = "lanczos"
    viewer.layers.append(layer)
    viewer.camera.center = (25.0, 25.0)
    with caplog.at_level(logging.WARNING, logger="napari_core"):
        surface = shown(viewer)
        layer.interpolation = "linear"
        layer.interpolation = "lanczos"
        layer.appearance = IntensityAppearance(
            contrast_limits=(0.0, 255.0), interpolation=Interpolation.LANCZOS
        )
    assert layer.interpolation == Interpolation.LANCZOS
    assert middle(surface.screenshot()) == WHITE
    assert len(caplog.records) == (1 if backend.name in LACKS_LANCZOS else 0)
    assert (Interpolation.LANCZOS in backend.capabilities.interpolation) == (
        backend.name not in LACKS_LANCZOS
    )
