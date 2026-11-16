"""The slicer of a view."""

from collections.abc import Callable

from psygnal import Signal

from napari_core.typing import SliceArray

from ._dims import Dims
from ._layer import Layer


class _Follower:
    """The slice of one layer, and the connection that refreshes it.

    The layer's `data` signal holds the connection to a bound method weakly,
    so dropping the follower is what disconnects it.
    """

    def __init__(self, layer: Layer, refresh: Callable[[Layer], None]) -> None:
        self.layer = layer
        self.plane: SliceArray | None = None
        self._refresh = refresh
        layer.events.data.connect(self.on_data)

    def on_data(self, _data: object) -> None:
        self._refresh(self.layer)


class Slicer:
    """Keeps the displayed plane of each layer of a view up to date.

    A layer is sliced when it is added, when its data is replaced and when the
    current step of the dims changes. `sliced` then emits the layer.
    """

    sliced = Signal(Layer)

    def __init__(self, dims: Dims) -> None:
        self._dims = dims
        self._followers: dict[int, _Follower] = {}
        dims.events.current_step.connect(self._slice_all)

    def response(self, layer: Layer) -> SliceArray | None:
        """Return the last slice of `layer`, or `None` when it is not followed."""
        follower = self._followers.get(id(layer))
        return None if follower is None else follower.plane

    def add(self, layer: Layer) -> None:
        """Slice `layer` and follow it; does nothing if it is already followed."""
        if id(layer) not in self._followers:
            self._followers[id(layer)] = _Follower(layer, self._slice)
            self._slice(layer)

    def remove(self, layer: Layer) -> None:
        """Forget `layer` and stop following it."""
        self._followers.pop(id(layer), None)

    def _slice(self, layer: Layer) -> None:
        self._followers[id(layer)].plane = layer.slice(self._dims)
        self.sliced.emit(layer)

    def _slice_all(self) -> None:
        for follower in list(self._followers.values()):
            self._slice(follower.layer)
