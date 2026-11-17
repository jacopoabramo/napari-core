"""Pan and zoom of the camera from mouse input."""

import math

from napari_core.model import (
    ButtonEvent,
    Camera,
    View,
    WheelEvent,
    surface_to_world,
)


class CameraController:
    """Pan on a left-button drag and zoom on the wheel, as the camera allows.

    The controller follows every press, move and release, so that its drag
    stays in step with the mouse. A handled event only stops the camera from
    moving.
    """

    def __init__(self, view: View) -> None:
        self._view = view
        self._drag_from: tuple[float, float] | None = None

    def handle(self, event: ButtonEvent | WheelEvent) -> None:
        """Follow `event` and move the camera unless it is handled."""
        camera = self._view.camera
        match event:
            case ButtonEvent(type="mouse_press", button=1, pos=pos) if (
                not event.handled
            ):
                self._drag_from = pos
            case ButtonEvent(type="mouse_move", pos=(x, y)) if (
                self._drag_from is not None
            ):
                x0, y0 = self._drag_from
                if camera.mouse_pan and not event.handled:
                    row, column = camera.center
                    camera.center = (
                        row - (y - y0) / camera.zoom,
                        column - (x - x0) / camera.zoom,
                    )
                self._drag_from = (x, y)
            case ButtonEvent(type="mouse_release", button=1):
                self._drag_from = None
            case WheelEvent(pos=(x, y), delta=(_, dy)) if (
                camera.mouse_zoom and not event.handled
            ):
                self._zoom(x, y, dy)
            case _:
                pass

    def _zoom(self, x: float, y: float, dy: float) -> None:
        """Zoom by the wheel step `dy`, keeping the world point under `(x, y)`.

        A step that would leave the zoom or the centre not finite, or the zoom
        not above 0, is skipped.
        """
        camera = self._view.camera
        try:
            zoom = camera.zoom * 1.1 ** (-dy / 100)
        except OverflowError:
            return
        if not (math.isfinite(zoom) and zoom > 0):
            return
        before = surface_to_world(self._view, x, y)
        zoomed = View(
            canvas_size=self._view.canvas_size,
            camera=Camera(center=camera.center, zoom=zoom),
        )
        after = surface_to_world(zoomed, x, y)
        row, column = camera.center
        center = (row + before[0] - after[0], column + before[1] - after[1])
        if not all(map(math.isfinite, center)):
            return
        camera.zoom = zoom
        camera.center = center
