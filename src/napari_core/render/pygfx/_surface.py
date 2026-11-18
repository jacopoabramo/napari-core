"""A rendercanvas canvas drawn by pygfx that follows a view and emits surface events."""

# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false

import logging
from collections.abc import Callable
from typing import Final, Generic, Protocol, runtime_checkable

import numpy as np
import numpy.typing as npt
import pygfx as gfx
from rendercanvas import BaseRenderCanvas

from napari_core.model import Layer, View, visible_rect
from napari_core.render import (
    LayerAdapter,
    NativeT,
    SurfaceEvent,
    SurfaceEventType,
    create_layer_adapter,
)

from ._image import BACKEND_NAME

logger = logging.getLogger(__name__)

POINTER_TYPES: Final = ("pointer_down", "pointer_up", "pointer_move", "double_click")
ENTER_LEAVE_TYPES: Final = ("pointer_enter", "pointer_leave")
EVENT_TYPES: tuple[SurfaceEventType, ...] = (
    *POINTER_TYPES,
    *ENTER_LEAVE_TYPES,
    "wheel",
    "resize",
)


@runtime_checkable
class PygfxLayerAdapter(LayerAdapter, Protocol):
    """A layer adapter whose drawing is a world object the surface can add.

    The adapter calls `on_change` after every change it shows.
    """

    on_change: Callable[[], None]

    @property
    def visual(self) -> gfx.WorldObject: ...


class ViewSync:
    """Keeps the pygfx camera and the layer adapters in step with a view.

    Every change it shows, and every change an adapter shows, calls
    `request_draw`. The signals hold these connections to bound methods
    weakly, so dropping the object is what disconnects them.
    """

    def __init__(
        self,
        view: View,
        camera: gfx.OrthographicCamera,
        scene: gfx.Scene,
        request_draw: Callable[[], None],
    ) -> None:
        self._view = view
        self._camera = camera
        self._scene = scene
        self._request_draw = request_draw
        self._adapters: dict[int, PygfxLayerAdapter] = {}
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
        self._camera.show_rect(rect.left, rect.right, rect.top, rect.bottom)
        self._request_draw()

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
        self._request_draw()

    def _make_adapter(self, layer: Layer) -> PygfxLayerAdapter:
        adapter = create_layer_adapter(BACKEND_NAME, layer, self._view)
        if not isinstance(adapter, PygfxLayerAdapter):
            adapter.close()
            raise TypeError(
                f"the adapter of {type(layer).__name__} has no pygfx world object"
            )
        self._scene.add(adapter.visual)
        adapter.on_change = self._request_draw
        return adapter

    def close(self) -> None:
        for adapter in self._adapters.values():
            adapter.close()
        self._adapters.clear()


class PygfxSurface(Generic[NativeT]):
    """A rendercanvas canvas, drawn by pygfx, that shows a view and emits events.

    The camera of the view moves the picture and the surface never writes to
    it. Each change of the view or of a layer asks the canvas for a draw. The
    canvas queues the events of its toolkit and emits them at its next
    scheduler turn, merging pointer moves and wheel turns sent in between.
    The sizes are those of the canvas, which reports 1 by 1 until the widget
    has been shown and has received its first resize.

    A layer that the backend cannot draw makes the constructor raise, with the
    canvas closed, when it is in the view already. One that joins the list
    later is logged once with `logging.exception` and drawn as nothing.

    The surface lives as long as its canvas holds the surface's event handler,
    whether or not the caller keeps the surface. Calling `close` on the
    surface is the reliable way to release it. Closing a canvas that is a
    window of its own, with the window's close, also closes the surface; a
    canvas embedded in another window gets no close when that window closes,
    so the surface keeps following the model until its `close` is called.
    """

    def __init__(
        self,
        view: View,
        canvas_class: Callable[[NativeT | None], NativeT],
        parent: NativeT | None,
    ) -> None:
        native = canvas_class(parent)
        if not isinstance(native, BaseRenderCanvas):
            if callable(close := getattr(native, "close", None)):
                close()
            raise TypeError(f"{canvas_class!r} does not make a rendercanvas canvas")
        self._native = native
        self._canvas: BaseRenderCanvas = native
        self._renderer = gfx.WgpuRenderer(self._canvas, pixel_scale=1)
        scene = gfx.Scene()
        # pygfx clears only in a render pass, and draws none when nothing is
        # visible, so an opaque black background is always drawn.
        scene.add(gfx.Background(None, gfx.BackgroundMaterial((0.0, 0.0, 0.0, 1.0))))
        camera = gfx.OrthographicCamera(maintain_aspect=False)
        camera.local.scale_y = -1
        self._handlers: list[
            tuple[Callable[[SurfaceEvent], None], tuple[str, ...]]
        ] = []
        self._closed = False
        try:
            self._sync: ViewSync | None = ViewSync(
                view, camera, scene, self._canvas.request_draw
            )
        except BaseException:
            self._closed = True
            self._close_canvas()
            raise
        renderer = self._renderer
        self._canvas.request_draw(lambda: renderer.render(scene, camera))
        # rendercanvas holds handlers strongly, so the canvas keeps the surface.
        self._canvas.add_event_handler(self._on_event, *EVENT_TYPES, "close")

    @property
    def native(self) -> NativeT:
        """The canvas, to embed in a window."""
        return self._native

    def get_physical_size(self) -> tuple[int, int]:
        """Return the size in device pixels, `(width, height)`."""
        return self._canvas.get_physical_size()

    def get_logical_size(self) -> tuple[float, float]:
        """Return the size in logical pixels, `(width, height)`."""
        width, height = self._canvas.get_logical_size()
        return (float(width), float(height))

    def get_pixel_ratio(self) -> float:
        """Return the device pixels per logical pixel."""
        return float(self._canvas.get_pixel_ratio())

    def request_draw(self) -> None:
        """Ask for a redraw."""
        self._canvas.request_draw()

    def add_event_handler(
        self, handler: Callable[[SurfaceEvent], None], *types: SurfaceEventType
    ) -> None:
        """Call `handler` for each event of one of `types`."""
        self._handlers.append((handler, types))

    def remove_event_handler(
        self, handler: Callable[[SurfaceEvent], None], *types: SurfaceEventType
    ) -> None:
        """Stop calling `handler` for `types`, or for every type when none is given."""
        kept: list[tuple[Callable[[SurfaceEvent], None], tuple[str, ...]]] = []
        for registered, registered_types in self._handlers:
            if registered != handler:
                kept.append((registered, registered_types))
            elif types and (
                rest := tuple(t for t in registered_types if t not in types)
            ):
                kept.append((registered, rest))
        self._handlers = kept

    def screenshot(self) -> npt.NDArray[np.uint8]:
        """Draw now and return the drawn image as RGBA rows of the physical size."""
        if not self._closed:
            self._canvas.force_draw()
        return np.asarray(self._renderer.snapshot(), dtype=np.uint8)

    def close(self) -> None:
        """Close the layer adapters and the canvas, and drop the event handlers.

        A Qt canvas deletes its widget when closed, so the widget must not be
        used after this call. Closing again does nothing.
        """
        if self._closed:
            return
        self._release()
        self._close_canvas()

    def _release(self) -> None:
        self._closed = True
        if self._sync is not None:
            self._sync.close()
            self._sync = None
        self._handlers = []

    def _close_canvas(self) -> None:
        try:
            self._canvas.close()
        except RuntimeError:
            # The toolkit deleted the widget already; the canvas is closed anyway.
            pass

    def _emit(self, event: SurfaceEvent) -> None:
        for handler, types in self._handlers:
            if event["event_type"] in types:
                handler(event)

    def _on_event(self, event: dict[str, object]) -> None:
        """Emit a canvas event as a surface event, with only the surface's keys.

        Of `buttons` and `modifiers`, only the integers and the strings are kept.
        """
        match event:
            case {"event_type": "close"}:
                if not self._closed:
                    self._release()
            case {
                "event_type": kind,
                "x": int() | float() as x,
                "y": int() | float() as y,
                "button": int() as button,
                "buttons": tuple() as buttons,
                "modifiers": tuple() as modifiers,
            } if kind in POINTER_TYPES:
                self._emit(
                    {
                        "event_type": kind,
                        "x": float(x),
                        "y": float(y),
                        "button": button,
                        "buttons": tuple(b for b in buttons if isinstance(b, int)),
                        "modifiers": tuple(m for m in modifiers if isinstance(m, str)),
                    }
                )
            case {
                "event_type": "wheel",
                "x": int() | float() as x,
                "y": int() | float() as y,
                "dx": int() | float() as dx,
                "dy": int() | float() as dy,
                "buttons": tuple() as buttons,
                "modifiers": tuple() as modifiers,
            }:
                self._emit(
                    {
                        "event_type": "wheel",
                        "x": float(x),
                        "y": float(y),
                        "dx": float(dx),
                        "dy": float(dy),
                        "buttons": tuple(b for b in buttons if isinstance(b, int)),
                        "modifiers": tuple(m for m in modifiers if isinstance(m, str)),
                    }
                )
            case {"event_type": kind} if kind in ENTER_LEAVE_TYPES:
                self._emit({"event_type": kind})
            case {
                "event_type": "resize",
                "width": int() | float() as width,
                "height": int() | float() as height,
                "pixel_ratio": int() | float() as pixel_ratio,
            }:
                self._emit(
                    {
                        "event_type": "resize",
                        "width": float(width),
                        "height": float(height),
                        "pixel_ratio": float(pixel_ratio),
                    }
                )
            case _:
                pass
