"""A vispy canvas that follows the camera of a view and emits surface events."""

# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import logging
from collections.abc import Callable
from typing import Generic, Literal, Protocol, TypeVar, cast, runtime_checkable

import numpy as np
import numpy.typing as npt
from vispy.app.canvas import MouseEvent
from vispy.geometry import Rect
from vispy.scene import PanZoomCamera, SceneCanvas

from napari_core.model import Layer, View, visible_rect
from napari_core.render import (
    LayerAdapter,
    SurfaceEvent,
    SurfaceEventType,
    SurfacePointerEvent,
    SurfaceWheelEvent,
    create_layer_adapter,
)

from ._image import BACKEND_NAME

logger = logging.getLogger(__name__)

NativeT = TypeVar("NativeT")

WHEEL_NOTCH = 120
OWNER_ATTRIBUTE = "napari_core_surface"


class Attachable(Protocol):
    parent: object | None


@runtime_checkable
class VispyLayerAdapter(LayerAdapter, Protocol):
    """A layer adapter whose drawing is a visual the surface can attach."""

    @property
    def visual(self) -> Attachable: ...


class ViewSync:
    """Keeps the vispy camera and the layer adapters in step with a view.

    The signals hold these connections to bound methods weakly, so dropping
    the object is what disconnects them.
    """

    def __init__(self, view: View, camera: PanZoomCamera, scene: object) -> None:
        self._view = view
        self._camera = camera
        self._scene = scene
        self._adapters: dict[int, VispyLayerAdapter] = {}
        self._undrawable: set[int] = set()
        for layer in view.layers:
            if id(layer) not in self._adapters:
                self._adapters[id(layer)] = self._make_adapter(layer)
        view.camera.events.center.connect(self.update_camera)
        view.camera.events.zoom.connect(self.update_camera)
        view.events.canvas_size.connect(self.update_camera)
        for signal in (
            view.layers.events.inserted,
            view.layers.events.removed,
            view.layers.events.changed,
        ):
            signal.connect(self.sync_layers)
        self.update_camera()

    def update_camera(self) -> None:
        """Show the world rectangle the model camera sees, rows downwards."""
        width, height = self._view.canvas_size
        if width == 0 or height == 0:
            return
        rect = visible_rect(self._view)
        self._camera.rect = Rect(rect.left, rect.top, rect.width, rect.height)

    def sync_layers(self) -> None:
        """Close the adapters of removed layers and make those of new ones.

        A new layer that gets no adapter is logged once and drawn as nothing.
        """
        present = {id(layer): layer for layer in self._view.layers}
        for key in self._adapters.keys() - present.keys():
            self._adapters.pop(key).close()
        self._undrawable &= present.keys()
        for key, layer in present.items():
            if key in self._adapters or key in self._undrawable:
                continue
            try:
                self._adapters[key] = self._make_adapter(layer)
            except Exception:
                self._undrawable.add(key)
                logger.exception(
                    "cannot draw layer %r of type %s", layer.name, type(layer).__name__
                )

    def _make_adapter(self, layer: Layer) -> VispyLayerAdapter:
        adapter = create_layer_adapter(BACKEND_NAME, layer, self._view)
        if not isinstance(adapter, VispyLayerAdapter):
            adapter.close()
            raise TypeError(
                f"the adapter of {type(layer).__name__} has no vispy visual"
            )
        adapter.visual.parent = self._scene
        return adapter

    def close(self) -> None:
        for adapter in self._adapters.values():
            adapter.close()
        self._adapters.clear()


def modifier_names(event: MouseEvent) -> tuple[str, ...]:
    return tuple(str(key.name) for key in event.modifiers)


def pressed_buttons(event: MouseEvent) -> tuple[int, ...]:
    return tuple(int(button) for button in event.buttons)


class VispySurface(Generic[NativeT]):
    """A vispy scene canvas that shows a view and emits surface events.

    The camera of the view moves the picture and the surface never writes to
    it. Pointer moves are coalesced: the latest one is emitted at the next draw.
    Vispy drops a pointer move that arrives within 10 ms of the previous one,
    so the last position of a fast burst may not be reported. Layers are drawn
    in the order they were added, not in list order after a reorder.

    A layer that the backend cannot draw makes the constructor raise, with the
    canvas closed, when it is in the view already. One that joins the list
    later is logged once with `logging.exception` and drawn as nothing.

    The surface lives as long as its native widget object does, whether or not
    the caller keeps the surface. Calling `close` on the surface is the
    reliable way to release it, and it also deletes the widget. Dropping the
    widget object releases it only at the next cyclic garbage collection,
    because the surface and the widget refer to each other through the vispy
    canvas; until then model changes still reach the widget, and if its Qt
    object was already deleted, vispy logs an error for each. Closing the
    widget with its own `close()` does not release it at all: a widget that is
    closed but still referenced keeps following the model.
    """

    def __init__(self, view: View, parent: NativeT | None) -> None:
        self._canvas = SceneCanvas(
            bgcolor="black",
            parent=parent,  # pyrefly: ignore[bad-argument-type]
            show=False,
        )
        box = self._canvas.central_widget.add_view()
        camera = PanZoomCamera()
        camera.interactive = False
        camera.flip = (False, True, False)
        box.camera = camera
        self._handlers: list[
            tuple[Callable[[SurfaceEvent], None], tuple[str, ...]]
        ] = []
        self._pending_move: SurfacePointerEvent | None = None
        events = self._canvas.events  # pyrefly: ignore[missing-attribute]
        events["mouse_press"].connect(self._on_press)
        events["mouse_release"].connect(self._on_release)
        events["mouse_double_click"].connect(self._on_double_click)
        events["mouse_move"].connect(self._on_move)
        events["mouse_wheel"].connect(self._on_wheel)
        events["resize"].connect(self._on_resize)
        events["draw"].connect(self._flush_move)
        try:
            self._sync: ViewSync | None = ViewSync(view, camera, box.scene)
        except BaseException:
            self._close_canvas()
            raise
        # vispy and psygnal hold the handlers weakly, so the widget keeps the surface.
        setattr(self._canvas.native, OWNER_ATTRIBUTE, self)

    @property
    def native(self) -> NativeT:
        """The widget to embed in a window."""
        # vispy leaves the native widget unannotated.
        return cast(NativeT, self._canvas.native)

    def get_physical_size(self) -> tuple[int, int]:
        """Return the size in device pixels, `(width, height)`."""
        width, height = self._canvas.physical_size
        return (int(width), int(height))

    def get_logical_size(self) -> tuple[float, float]:
        """Return the size in logical pixels, `(width, height)`."""
        width, height = self._canvas.size
        return (float(width), float(height))

    def get_pixel_ratio(self) -> float:
        """Return the device pixels per logical pixel."""
        return float(self._canvas.pixel_scale)

    def request_draw(self) -> None:
        """Ask for a redraw."""
        self._canvas.update()

    def add_event_handler(
        self, handler: Callable[[SurfaceEvent], None], *types: SurfaceEventType
    ) -> None:
        """Call `handler` for each event of one of `types`."""
        self._handlers.append((handler, types))

    def screenshot(self) -> npt.NDArray[np.uint8]:
        """Return the drawn image as RGBA rows."""
        return np.asarray(self._canvas.render(), dtype=np.uint8)

    def close(self) -> None:
        """Close the layer adapters and the canvas, and delete the native widget.

        A Qt widget is scheduled for deletion with its `deleteLater`, so it
        must not be used after this call. Closing again does nothing.
        """
        if self._sync is None:
            return
        self._sync.close()
        self._sync = None
        if getattr(self._canvas.native, OWNER_ATTRIBUTE, None) is self:
            delattr(self._canvas.native, OWNER_ATTRIBUTE)
        self._close_canvas()

    def _close_canvas(self) -> None:
        native = self._canvas.native
        self._canvas.close()
        # Qt must destroy the widget at a point it chooses: left to Python's
        # cyclic collector, the destruction crashed a later canvas on show.
        if callable(delete_later := getattr(native, "deleteLater", None)):
            delete_later()

    def _emit(self, event: SurfaceEvent) -> None:
        for handler, types in self._handlers:
            if event["event_type"] in types:
                handler(event)

    def _flush_move(self, _event: object = None) -> None:
        if (move := self._pending_move) is not None:
            self._pending_move = None
            self._emit(move)

    def _pointer(
        self,
        kind: Literal["pointer_down", "pointer_up", "pointer_move", "double_click"],
        event: MouseEvent,
    ) -> SurfacePointerEvent:
        x, y = event.pos[:2]
        return {
            "event_type": kind,
            "x": float(x),
            "y": float(y),
            "button": int(event.button or 0),
            "buttons": pressed_buttons(event),
            "modifiers": modifier_names(event),
        }

    def _emit_pointer(
        self,
        kind: Literal["pointer_down", "pointer_up", "double_click"],
        event: MouseEvent,
    ) -> None:
        self._flush_move()
        self._emit(self._pointer(kind, event))

    def _on_press(self, event: MouseEvent) -> None:
        self._emit_pointer("pointer_down", event)

    def _on_release(self, event: MouseEvent) -> None:
        self._emit_pointer("pointer_up", event)

    def _on_double_click(self, event: MouseEvent) -> None:
        self._emit_pointer("double_click", event)

    def _on_move(self, event: MouseEvent) -> None:
        self._pending_move = self._pointer("pointer_move", event)
        self._canvas.update()

    def _on_wheel(self, event: MouseEvent) -> None:
        self._flush_move()
        x, y = event.pos[:2]
        dx, dy = event.delta[:2]
        wheel: SurfaceWheelEvent = {
            "event_type": "wheel",
            "x": float(x),
            "y": float(y),
            "dx": -WHEEL_NOTCH * float(dx),
            "dy": -WHEEL_NOTCH * float(dy),
            "buttons": pressed_buttons(event),
            "modifiers": modifier_names(event),
        }
        self._emit(wheel)

    def _on_resize(self, _event: object) -> None:
        width, height = self.get_logical_size()
        self._emit(
            {
                "event_type": "resize",
                "width": width,
                "height": height,
                "pixel_ratio": self.get_pixel_ratio(),
            }
        )
