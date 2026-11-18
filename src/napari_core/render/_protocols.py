"""What a rendering backend and its surface must provide."""

from collections.abc import Callable
from typing import Protocol, TypeVar

import numpy as np
import numpy.typing as npt

from napari_core.model import View

from ._capabilities import Capabilities
from ._events import SurfaceEvent, SurfaceEventType

NativeT = TypeVar("NativeT")
NativeT_co = TypeVar("NativeT_co", covariant=True)


class LayerAdapter(Protocol):
    """The drawn counterpart of one layer."""

    def close(self) -> None:
        """Release what the adapter holds."""
        ...


class RenderSurface(Protocol[NativeT_co]):
    """A drawing area that emits events and shows a view.

    A change of the view or of a layer in it shows on the surface without the
    caller asking for a draw.

    A surface is hashable and compared by identity, and it can be weakly
    referenced, so that other code can keep a record of surfaces without
    keeping them alive.
    """

    @property
    def native(self) -> NativeT_co:
        """The object to embed in a window."""
        ...

    def get_physical_size(self) -> tuple[int, int]:
        """Return the size in device pixels, `(width, height)`."""
        ...

    def get_logical_size(self) -> tuple[float, float]:
        """Return the size in logical pixels, `(width, height)`."""
        ...

    def get_pixel_ratio(self) -> float:
        """Return the device pixels per logical pixel."""
        ...

    def request_draw(self) -> None:
        """Ask for a redraw."""
        ...

    def add_event_handler(
        self, handler: Callable[[SurfaceEvent], None], *types: SurfaceEventType
    ) -> None:
        """Call `handler` for each event of one of `types`.

        The surface holds the handler strongly until it is removed or the
        surface is closed. A surface may call the handler later than the
        toolkit reported the event, after the toolkit's own call has
        returned. Pointer moves that arrive before the handler is called may
        reach it as one move to the last position, and wheel turns as one
        turn that carries their sum.
        """
        ...

    def remove_event_handler(
        self, handler: Callable[[SurfaceEvent], None], *types: SurfaceEventType
    ) -> None:
        """Stop calling `handler` for `types`, or for every type when none is given.

        A handler is matched by equality, so a bound method written anew
        matches the one that was added. Does nothing for a handler that is not
        registered.
        """
        ...

    def screenshot(self) -> npt.NDArray[np.uint8]:
        """Return the drawn image as RGBA rows."""
        ...

    def close(self) -> None:
        """Release the surface and the adapters of its layers, and drop its handlers."""
        ...


class RenderBackend(Protocol[NativeT]):
    """A rendering library that can make surfaces."""

    name: str
    capabilities: Capabilities

    def create_surface(
        self, view: View, parent: NativeT | None
    ) -> RenderSurface[NativeT]:
        """Return a surface that shows `view` inside `parent`."""
        ...
