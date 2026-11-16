"""The view model."""

from collections.abc import Iterable
from typing import Annotated

from psygnal import EventedModel
from psygnal.containers import EventedList
from pydantic import ConfigDict, Field, PlainValidator, PrivateAttr
from typing_extensions import override

from ._camera import Camera
from ._dims import Dims
from ._layer import Layer
from ._slicer import Slicer


def _layer_list(layers: Iterable[object] = ()) -> EventedList[Layer]:
    """Return a list of layers that does not re-emit the layers' events.

    Raises
    ------
    ValueError
        If an item is not a [`Layer`][napari_core.model.Layer].
    """
    result: EventedList[Layer] = EventedList(child_events=False)
    for layer in layers:
        if not isinstance(layer, Layer):
            raise ValueError(f"expected a Layer, got {type(layer).__name__}")
        result.append(layer)
    return result


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
    layers: Annotated[EventedList[Layer], PlainValidator(_layer_list)] = Field(
        default_factory=_layer_list, frozen=True
    )

    _slicer: Slicer = PrivateAttr()

    @override
    def model_post_init(self, context: object, /) -> None:
        """Connect the slicer to the layer list and follow the layers it holds."""
        super().model_post_init(context)
        self._slicer = Slicer(self.dims, self.layers)
        for signal in (
            self.layers.events.inserted,
            self.layers.events.removed,
            self.layers.events.changed,
        ):
            signal.connect(self._slicer.sync)
        self._slicer.sync()

    @property
    def slicer(self) -> Slicer:
        """The slicer that keeps the layers' planes up to date."""
        return self._slicer
