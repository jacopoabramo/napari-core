"""Connect a surface to a view: surface events become input events."""

import logging
from collections.abc import Callable, Generator
from dataclasses import fields
from functools import partial
from typing import Literal, TypeVar

from napari_core.model import (
    ButtonEvent,
    EnterLeaveEvent,
    Layer,
    Modifier,
    View,
    WheelEvent,
)
from napari_core.render import (
    RenderSurface,
    SurfaceEvent,
    SurfaceEventType,
    SurfacePointerEvent,
    SurfaceWheelEvent,
)

from ._camera_controller import CameraController
from ._coordinates import surface_to_world

logger = logging.getLogger(__name__)

R = TypeVar("R")

_EVENT_TYPES: tuple[SurfaceEventType, ...] = (
    "pointer_down",
    "pointer_up",
    "pointer_move",
    "double_click",
    "pointer_enter",
    "pointer_leave",
    "wheel",
    "resize",
)


class _Dispatcher:
    def __init__(self, view: View) -> None:
        self._view = view
        self._camera = CameraController(view)
        self._last_pos = (0.0, 0.0)
        self._drags: list[tuple[ButtonEvent, Generator[None, None, None], str]] = []
        self.active = True

    def handle(self, event: SurfaceEvent) -> None:
        if not self.active:
            return
        width, height = self._view.canvas_size
        if event["event_type"] != "resize" and (width == 0 or height == 0):
            return
        match event["event_type"]:
            case "resize":
                self._view.canvas_size = (round(event["width"]), round(event["height"]))
            case "pointer_enter":
                self._dispatch(self._enter_leave("enter"))
            case "pointer_leave":
                self._dispatch(self._enter_leave("leave"))
            case "pointer_down":
                self._dispatch(self._button("mouse_press", event))
            case "pointer_move":
                self._dispatch(self._button("mouse_move", event))
            case "pointer_up":
                self._dispatch(self._button("mouse_release", event))
            case "double_click":
                self._dispatch(self._button("mouse_double_click", event))
            case "wheel":
                self._dispatch(self._wheel(event))

    def _position(self, x: float, y: float) -> tuple[float, ...]:
        dims = self._view.dims
        position = [float(step) for step in dims.current_step]
        row_axis, column_axis = dims.displayed
        position[row_axis], position[column_axis] = surface_to_world(self._view, x, y)
        return tuple(position)

    def _button(
        self,
        kind: Literal[
            "mouse_press", "mouse_move", "mouse_release", "mouse_double_click"
        ],
        event: SurfacePointerEvent,
    ) -> ButtonEvent:
        x, y = self._last_pos = (event["x"], event["y"])
        dims = self._view.dims
        return ButtonEvent(
            type=kind,
            button=event["button"],
            modifiers=frozenset(Modifier(name) for name in event["modifiers"]),
            view=self._view,
            pos=(x, y),
            viewbox=(0, 0),
            position=self._position(x, y),
            view_direction=None,
            up_direction=None,
            dims_displayed=dims.displayed,
            dims_point=tuple(float(step) for step in dims.current_step),
            camera_zoom=self._view.camera.zoom,
        )

    def _wheel(self, event: SurfaceWheelEvent) -> WheelEvent:
        x, y = self._last_pos = (event["x"], event["y"])
        dims = self._view.dims
        return WheelEvent(
            type="mouse_wheel",
            delta=(event["dx"], event["dy"]),
            inverted=False,
            modifiers=frozenset(Modifier(name) for name in event["modifiers"]),
            view=self._view,
            pos=(x, y),
            viewbox=(0, 0),
            position=self._position(x, y),
            view_direction=None,
            up_direction=None,
            dims_displayed=dims.displayed,
            dims_point=tuple(float(step) for step in dims.current_step),
            camera_zoom=self._view.camera.zoom,
        )

    def _enter_leave(self, kind: Literal["enter", "leave"]) -> EnterLeaveEvent:
        return EnterLeaveEvent(
            type=kind,
            modifiers=frozenset(),
            view=self._view,
            pos=self._last_pos,
            viewbox=(0, 0),
        )

    def _top_layer(self) -> Layer | None:
        return next(
            (layer for layer in reversed(self._view.layers) if layer.visible), None
        )

    def _dispatch(self, event: ButtonEvent | WheelEvent | EnterLeaveEvent) -> None:
        layer = self._top_layer()
        match event:
            case ButtonEvent(type="mouse_press") if layer is not None:
                self._start_drags(layer, event)
            case ButtonEvent(type="mouse_move" | "mouse_release"):
                self._resume_drags(event)
            case WheelEvent() if layer is not None:
                for callback in layer.mouse_wheel_callbacks:
                    _run(partial(callback, layer, event), _label(callback, layer))
            case _:
                pass
        if isinstance(event, ButtonEvent | WheelEvent):
            self._camera.handle(event)

    def _start_drags(self, layer: Layer, event: ButtonEvent) -> None:
        for callback in layer.mouse_drag_callbacks:
            label = _label(callback, layer)
            result = _run(partial(callback, layer, event), label)
            if isinstance(result, Generator) and _advance(result, label):
                self._drags.append((event, result, label))

    def _resume_drags(self, event: ButtonEvent) -> None:
        drags = self._drags
        self._drags = []
        for held, generator, label in drags:
            for field in fields(held):
                setattr(held, field.name, getattr(event, field.name))
            alive = _advance(generator, label)
            event.handled = event.handled or held.handled
            if alive and event.type == "mouse_move":
                self._drags.append((held, generator, label))


def _label(callback: object, layer: Layer) -> str:
    return f"{callback!r} of layer {layer.name!r}"


def _run(call: Callable[[], R], label: str) -> R | None:
    try:
        return call()
    except Exception:
        logger.exception("input callback %s raised", label)
        return None


def _advance(generator: Generator[None, None, None], label: str) -> bool:
    try:
        next(generator)
    except StopIteration:
        return False
    except Exception:
        logger.exception("input callback %s raised", label)
        return False
    return True


def attach(view: View, surface: RenderSurface[object]) -> Callable[[], None]:
    """Make `surface` drive `view` and return a function that disconnects it.

    The events of the surface reach the callbacks of the top visible layer
    first, then the camera, which does not move when a callback set `handled`.
    A `resize` writes the view's `canvas_size`.

    Attaching the same surface and view twice dispatches every event twice.
    The returned function makes the handler do nothing; it does not remove it
    from the surface.

    A modifier name that the surface sends and that is not `Shift`,
    `Control`, `Alt` or `Meta` makes the handler raise `ValueError`.
    """
    dispatcher = _Dispatcher(view)
    surface.add_event_handler(dispatcher.handle, *_EVENT_TYPES)

    def detach() -> None:
        dispatcher.active = False

    return detach
