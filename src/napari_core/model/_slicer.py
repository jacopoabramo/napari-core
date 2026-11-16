"""The slicer of a view."""

from collections.abc import Callable, Sequence
from weakref import WeakMethod

from psygnal import Signal

from napari_core.typing import SliceArray

from ._dims import Dims
from ._layer import Layer


class Follower:
    """The slice of one layer, and the connection that refreshes it.

    The layer's `data` signal holds the connection to a bound method weakly,
    so dropping the follower is what disconnects it. The follower reaches the
    slicer through a weak reference, so it does not keep the slicer alive.
    """

    def __init__(self, layer: Layer, on_data: Callable[[Layer], None]) -> None:
        self.layer = layer
        self.plane: SliceArray | None = None
        self._on_data = WeakMethod(on_data)
        layer.events.data.connect(self.refresh)

    def refresh(self, _data: object) -> None:
        if (on_data := self._on_data()) is not None:
            on_data(self.layer)


class Slicer:
    """Keeps the displayed plane of each layer of a view up to date.

    It also fits `dims` to `layers`: `ndim` is the largest number of axes among
    them, at least 2, and `nsteps` the largest extent on each axis, aligned to
    the last axis. A layer is sliced when it joins the list, when its data is
    replaced and when the current step of the dims changes. `sliced` then emits
    the layer, and the dims it is emitted under are already fitted.
    """

    sliced = Signal(Layer)

    def __init__(self, dims: Dims, layers: Sequence[Layer]) -> None:
        self._dims = dims
        self._layers = layers
        self._followers: dict[int, Follower] = {}
        self._fitting = False
        dims.events.current_step.connect(self._on_step)

    def response(self, layer: Layer) -> SliceArray | None:
        """Return the last slice of `layer`, or `None` when it is not followed."""
        follower = self._followers.get(id(layer))
        return None if follower is None else follower.plane

    def sync(self) -> None:
        """Follow the layers now in the list and forget the others.

        The dims are refitted in between, so no layer is sliced with dims that
        do not fit it.
        """
        present = {id(layer): layer for layer in self._layers}
        for key in self._followers.keys() - present.keys():
            del self._followers[key]
        self._fit()
        for key, layer in present.items():
            if key not in self._followers:
                self._followers[key] = Follower(layer, self._on_data)
                self._slice(layer)

    def _on_data(self, layer: Layer) -> None:
        if not self._fit():
            self._slice(layer)

    def _on_step(self) -> None:
        if not self._fitting:
            self._slice_all()

    def _fit(self) -> bool:
        """Fit the dims to the layers; return whether the current step changed."""
        ndim = max([2, *(layer.ndim for layer in self._layers)])
        nsteps = [1] * ndim
        for layer in self._layers:
            for axis, steps in enumerate(reversed(layer.extent_steps), start=1):
                nsteps[-axis] = max(nsteps[-axis], steps)
        before = self._dims.current_step
        self._fitting = True
        try:
            self._dims.ndim = ndim
            self._dims.nsteps = tuple(nsteps)
        finally:
            self._fitting = False
        changed = self._dims.current_step != before
        if changed:
            self._slice_all()
        return changed

    def _slice(self, layer: Layer) -> None:
        self._followers[id(layer)].plane = layer.slice(self._dims)
        self.sliced.emit(layer)

    def _slice_all(self) -> None:
        for follower in list(self._followers.values()):
            self._slice(follower.layer)
