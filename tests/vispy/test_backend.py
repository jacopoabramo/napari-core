import numpy as np
import numpy.typing as npt
import pytest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QWidget
from vispy.app import Application

from napari_core.model import Image, IntensityAppearance, ViewerModel
from napari_core.render import RenderSurface, create_layer_adapter
from napari_core.render.vispy import VispyBackend

pytestmark = pytest.mark.gl

BACKGROUND = (0, 0, 0)


def white_image() -> Image:
    """Return a 50 by 50 image whose pixels all map to white."""
    return Image(
        name="a",
        data=np.full((50, 50), 255, dtype=np.uint8),
        appearance=IntensityAppearance(contrast_limits=(0.0, 255.0)),
    )


def shown(viewer: ViewerModel, qapp: Application) -> RenderSurface[QWidget]:
    """Return a surface of the viewer's view, shown at 200 by 100 pixels."""
    surface = VispyBackend[QWidget]().create_surface(viewer.view, None)
    viewer.view.canvas_size = (200, 100)
    surface.native.resize(200, 100)
    surface.native.show()
    qapp.process_events()
    return surface


def middle(shot: npt.NDArray[np.uint8]) -> tuple[int, ...]:
    """Return the RGB value of the middle pixel of `shot`."""
    return tuple(shot[shot.shape[0] // 2, shot.shape[1] // 2, :3])


def test_image_is_drawn(qapp: Application) -> None:
    """Draw a white image so the middle of the screenshot is not background."""
    viewer = ViewerModel()
    viewer.layers.append(white_image())
    viewer.camera.center = (25.0, 25.0)
    surface = shown(viewer, qapp)
    shot = surface.screenshot()
    assert shot.dtype == np.uint8 and shot.shape[2] == 4
    assert middle(shot) != BACKGROUND
    surface.close()


def test_hidden_layer_is_not_drawn(qapp: Application) -> None:
    """Draw nothing for a layer that is not visible."""
    viewer = ViewerModel()
    layer = white_image()
    viewer.layers.append(layer)
    viewer.camera.center = (25.0, 25.0)
    surface = shown(viewer, qapp)
    layer.visible = False
    qapp.process_events()
    assert middle(surface.screenshot()) == BACKGROUND
    surface.close()


def test_camera_change_moves_the_image(qapp: Application) -> None:
    """Follow the model camera, so panning far away leaves the middle empty."""
    viewer = ViewerModel()
    viewer.layers.append(white_image())
    surface = shown(viewer, qapp)
    viewer.camera.center = (10_000.0, 10_000.0)
    qapp.process_events()
    assert middle(surface.screenshot()) == BACKGROUND
    surface.close()


def test_removed_layer_disappears_and_its_adapter_stops_listening(
    qapp: Application,
) -> None:
    """Remove a layer's visual and ignore its later signals."""
    viewer = ViewerModel()
    layer = white_image()
    viewer.layers.append(layer)
    viewer.camera.center = (25.0, 25.0)
    surface = shown(viewer, qapp)
    viewer.layers.remove(layer)
    layer.gamma = 0.5
    qapp.process_events()
    assert middle(surface.screenshot()) == BACKGROUND
    surface.close()


def test_closed_adapter_ignores_the_layer(qapp: Application) -> None:
    """Keep the visual as it was when the adapter closed, whatever changes."""
    viewer = ViewerModel()
    layer = white_image()
    viewer.layers.append(layer)
    adapter = create_layer_adapter("vispy", layer, viewer.view)
    adapter.close()
    layer.gamma = 0.5
    layer.contrast_limits = (10.0, 20.0)
    assert adapter.visual.gamma == 1.0
    assert tuple(adapter.visual.clim) == (0.0, 255.0)


def test_layer_added_later_is_drawn(qapp: Application) -> None:
    """Draw a layer appended after the surface exists."""
    viewer = ViewerModel()
    viewer.camera.center = (25.0, 25.0)
    surface = shown(viewer, qapp)
    viewer.layers.append(white_image())
    qapp.process_events()
    assert middle(surface.screenshot()) != BACKGROUND
    surface.close()


def test_image_orientation_and_pixel_centres(qapp: Application) -> None:
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
    ratio = shot.shape[1] // 200

    def bright(x: float, y: float) -> bool:
        return bool(shot[int(y * ratio), int(x * ratio), 0] > 128)

    # World (0, 0) is at screen (80, 30); the pixel spans x 70..90, y 20..40.
    assert bright(80, 30)
    assert bright(71, 30) and bright(89, 30) and bright(80, 21) and bright(80, 39)
    assert not bright(69, 30) and not bright(91, 30)
    assert not bright(80, 19) and not bright(80, 41)
    assert not bright(120, 30) and not bright(80, 70) and not bright(120, 70)
    surface.close()


def test_mouse_press_reaches_handlers_in_rendercanvas_vocabulary(
    qapp: Application,
) -> None:
    """Translate a real Qt mouse press into a pointer_down surface event."""
    viewer = ViewerModel()
    surface = shown(viewer, qapp)
    seen = []
    surface.add_event_handler(seen.append, "pointer_down")
    # Presses are not coalesced, so the handler has run when mousePress returns.
    QTest.mousePress(surface.native, Qt.MouseButton.LeftButton, pos=QPoint(30, 40))
    (event,) = seen
    assert event["event_type"] == "pointer_down"
    assert (event["x"], event["y"], event["button"]) == (30.0, 40.0, 1)
    surface.close()
