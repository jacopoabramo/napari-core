"""Input events that layer and canvas callbacks receive."""

from collections.abc import Callable, Generator
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Literal, TypeVar

if TYPE_CHECKING:
    from ._layer import Layer
    from ._view import View


class Modifier(StrEnum):
    """A keyboard modifier that can be held during an input event."""

    SHIFT = "Shift"
    CONTROL = "Control"
    ALT = "Alt"
    META = "Meta"


@dataclass(kw_only=True, slots=True)
class InputEvent:
    """Base of all input events; a callback sets `handled` to stop propagation."""

    modifiers: frozenset[Modifier]
    handled: bool = False


@dataclass(kw_only=True, slots=True)
class CanvasEvent(InputEvent):
    """An event with a position on the canvas.

    Attributes
    ----------
    pos
        Position on the canvas in pixels, `(x, y)`.
    viewbox
        The cell of the grid of views under the pointer. There is one view
        and no grid, so it is always `(0, 0)`.
    """

    view: "View"
    pos: tuple[float, float]
    viewbox: tuple[int, int]


@dataclass(kw_only=True, slots=True)
class PointerEvent(CanvasEvent):
    """A canvas event with its position and the view geometry in world terms."""

    position: tuple[float, ...]
    view_direction: tuple[float, ...] | None
    up_direction: tuple[float, ...] | None
    dims_displayed: tuple[int, ...]
    dims_point: tuple[float, ...]
    camera_zoom: float


@dataclass(kw_only=True, slots=True)
class ButtonEvent(PointerEvent):
    """A mouse press, move, release or double click."""

    type: Literal["mouse_press", "mouse_move", "mouse_release", "mouse_double_click"]
    button: int | None


@dataclass(kw_only=True, slots=True)
class WheelEvent(PointerEvent):
    """A turn of the mouse wheel."""

    type: Literal["mouse_wheel"]
    delta: tuple[float, float]
    inverted: bool


@dataclass(kw_only=True, slots=True)
class EnterLeaveEvent(CanvasEvent):
    """The pointer entering or leaving the canvas."""

    type: Literal["enter", "leave"]


LayerT = TypeVar("LayerT", bound="Layer")
MouseCallback = Callable[[LayerT, ButtonEvent], Generator[None, None, None] | None]
WheelCallback = Callable[[LayerT, WheelEvent], None]
