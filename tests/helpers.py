"""Plain helpers shared between test modules."""

from collections.abc import Callable
from importlib import import_module
from typing import Literal

import numpy as np
import numpy.typing as npt

from napari_core.model import Image, View
from napari_core.render import (
    SurfaceEvent,
    SurfaceEventType,
    SurfacePointerEvent,
    SurfaceWheelEvent,
)

da = import_module("dask.array")
qtest = import_module("PyQt6.QtTest").QTest

PointerKind = Literal["pointer_down", "pointer_up", "pointer_move", "double_click"]


class FakeSurface:
    """A render surface that records handlers and emits events on request."""

    def __init__(self) -> None:
        self.handlers: list[tuple[Callable[[SurfaceEvent], None], tuple[str, ...]]] = []

    @property
    def native(self) -> None:
        return None

    def get_physical_size(self) -> tuple[int, int]:
        return (200, 100)

    def get_logical_size(self) -> tuple[float, float]:
        return (200.0, 100.0)

    def get_pixel_ratio(self) -> float:
        return 1.0

    def request_draw(self) -> None:
        pass

    def add_event_handler(
        self, handler: Callable[[SurfaceEvent], None], *types: SurfaceEventType
    ) -> None:
        self.handlers.append((handler, types))

    def screenshot(self) -> npt.NDArray[np.uint8]:
        return np.zeros((100, 200, 4), dtype=np.uint8)

    def close(self) -> None:
        pass

    def emit(self, event: SurfaceEvent) -> None:
        """Call the handlers registered for the type of `event`."""
        for handler, types in self.handlers:
            if event["event_type"] in types:
                handler(event)


class Closer:
    """A layer adapter that does nothing."""

    def close(self) -> None:
        pass


def pointer(
    kind: PointerKind,
    x: float,
    y: float,
    button: int = 0,
    buttons: tuple[int, ...] = (),
    modifiers: tuple[str, ...] = (),
) -> SurfacePointerEvent:
    """Return a surface pointer event of type `kind`."""
    return {
        "event_type": kind,
        "x": x,
        "y": y,
        "button": button,
        "buttons": buttons,
        "modifiers": modifiers,
    }


def wheel(
    x: float,
    y: float,
    dx: float = 0.0,
    dy: float = 0.0,
    buttons: tuple[int, ...] = (),
    modifiers: tuple[str, ...] = (),
) -> SurfaceWheelEvent:
    """Return a surface wheel event."""
    return {
        "event_type": "wheel",
        "x": x,
        "y": y,
        "dx": dx,
        "dy": dy,
        "buttons": buttons,
        "modifiers": modifiers,
    }


def view_with_image() -> tuple[View, Image]:
    """Return a view of one image and that image."""
    view = View(canvas_size=(200, 100))
    layer = image(name="image", data=np.zeros((3, 4)))
    view.layers.append(layer)
    return view, layer


def image(*, name: str, data: object, **fields: object) -> Image:
    """Return an image built with `model_validate`, so `transform` may be left out."""
    return Image.model_validate({"name": name, "data": data, **fields})


def assign(obj: object, name: str, value: object) -> None:
    """Assign `value` to the attribute `name` of `obj` as an untyped caller would."""
    setattr(obj, name, value)
