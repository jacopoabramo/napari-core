"""Events a surface emits, with the names, keys and units of rendercanvas."""

from typing import Literal, TypedDict

SurfaceEventType = Literal[
    "pointer_down",
    "pointer_up",
    "pointer_move",
    "double_click",
    "pointer_enter",
    "pointer_leave",
    "wheel",
    "resize",
]


class SurfacePointerEvent(TypedDict):
    """A button press, release, move or double click at a surface position.

    `x` and `y` are in logical surface pixels.
    """

    event_type: Literal["pointer_down", "pointer_up", "pointer_move", "double_click"]
    x: float
    y: float
    button: int
    buttons: tuple[int, ...]
    modifiers: tuple[str, ...]


class SurfaceWheelEvent(TypedDict):
    """A turn of the mouse wheel at a surface position."""

    event_type: Literal["wheel"]
    x: float
    y: float
    dx: float
    dy: float
    buttons: tuple[int, ...]
    modifiers: tuple[str, ...]


class SurfaceEnterLeaveEvent(TypedDict):
    """The pointer entering or leaving the surface."""

    event_type: Literal["pointer_enter", "pointer_leave"]


class SurfaceResizeEvent(TypedDict):
    """A new surface size in logical pixels."""

    event_type: Literal["resize"]
    width: float
    height: float
    pixel_ratio: float


SurfaceEvent = (
    SurfacePointerEvent
    | SurfaceWheelEvent
    | SurfaceEnterLeaveEvent
    | SurfaceResizeEvent
)
