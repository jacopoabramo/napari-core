"""Pan and zoom of the camera from mouse input."""

from napari_core.model import ButtonEvent, View, WheelEvent

from ._coordinates import surface_to_world


class CameraController:
    """Pan on a left-button drag and zoom on the wheel, as the camera allows."""

    def __init__(self, view: View) -> None:
        self._view = view
        self._drag_from: tuple[float, float] | None = None

    def handle(self, event: ButtonEvent | WheelEvent) -> None:
        """Move the camera for `event`."""
        camera = self._view.camera
        match event:
            case ButtonEvent(type="mouse_press", button=1, pos=pos):
                self._drag_from = pos
            case ButtonEvent(type="mouse_move", pos=(x, y)) if self._drag_from:
                x0, y0 = self._drag_from
                if camera.mouse_pan:
                    row, column = camera.center
                    camera.center = (
                        row - (y - y0) / camera.zoom,
                        column - (x - x0) / camera.zoom,
                    )
                self._drag_from = (x, y)
            case ButtonEvent(type="mouse_release"):
                self._drag_from = None
            case WheelEvent(pos=(x, y), delta=(_, dy)) if camera.mouse_zoom:
                before = surface_to_world(self._view, x, y)
                camera.zoom *= 1.1 ** (-dy / 100)
                after = surface_to_world(self._view, x, y)
                camera.center = (
                    camera.center[0] + before[0] - after[0],
                    camera.center[1] + before[1] - after[1],
                )
            case _:
                pass
