"""The view model."""

from psygnal import EventedModel
from psygnal.containers import EventedList
from pydantic import ConfigDict, Field, PrivateAttr
from typing_extensions import override

from ._camera import Camera
from ._dims import Dims
from ._layer import Layer
from ._slicer import Slicer


class View(EventedModel):
    """The layers shown together, with their dims, camera and canvas size.

    The `dims` and the `layers` list can be changed but not replaced. Dims
    follow the layers: `ndim` is the largest number of axes among them, at
    least 2, and `nsteps` the largest extent on each axis, aligned to the last
    axis.

    Attributes
    ----------
    canvas_size
        Size of the canvas in logical pixels, `(width, height)`.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, validate_assignment=True)

    dims: Dims = Field(default_factory=Dims, frozen=True)
    camera: Camera = Field(default_factory=Camera)
    canvas_size: tuple[int, int] = (640, 480)
    layers: EventedList[Layer] = Field(
        default_factory=lambda: EventedList(child_events=False), frozen=True
    )

    _slicer: Slicer = PrivateAttr()

    @override
    def model_post_init(self, context: object, /) -> None:
        """Connect the slicer and the dims to the layer list."""
        super().model_post_init(context)
        self._slicer = Slicer(self.dims)
        self.layers.events.inserted.connect(self._on_inserted)
        self.layers.events.removed.connect(self._on_removed)
        self.layers.events.changed.connect(self._on_changed)
        for layer in self.layers:
            self._add(layer)

    @property
    def slicer(self) -> Slicer:
        """The slicer that keeps the layers' planes up to date."""
        return self._slicer

    def _on_inserted(self, _index: int, layer: Layer) -> None:
        self._add(layer)

    def _on_removed(self, _index: int, layer: Layer) -> None:
        self._drop(layer)

    def _on_changed(
        self,
        _key: int | slice,
        old: Layer | list[Layer],
        new: Layer | list[Layer],
    ) -> None:
        for layer in old if isinstance(old, list) else [old]:
            self._drop(layer)
        for layer in new if isinstance(new, list) else [new]:
            self._add(layer)

    def _add(self, layer: Layer) -> None:
        self._fit_dims()
        self._slicer.add(layer)

    def _drop(self, layer: Layer) -> None:
        if any(other is layer for other in self.layers):
            return
        self._slicer.remove(layer)
        self._fit_dims()

    def _fit_dims(self) -> None:
        ndim = max([2, *(layer.ndim for layer in self.layers)])
        nsteps = [1] * ndim
        for layer in self.layers:
            for axis, steps in enumerate(reversed(layer.extent_steps), start=1):
                nsteps[-axis] = max(nsteps[-axis], steps)
        self.dims.ndim = ndim
        self.dims.nsteps = tuple(nsteps)
