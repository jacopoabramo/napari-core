"""The base class of layers."""

from abc import abstractmethod
from typing import Self

from psygnal import EventedModel
from pydantic import PrivateAttr

from napari_core.typing import BasicKey, SliceArray

from ._components import Transform
from ._config import EventedConfigDict
from ._dims import Dims
from ._input import MouseCallback, WheelCallback


class Layer(EventedModel):
    """A drawable item of a view; subclasses supply the data-specific parts."""

    model_config = EventedConfigDict(
        validate_assignment=True,
        field_dependencies={
            "name": ["name"],
            "visible": ["visible"],
            "opacity": ["opacity"],
        },
    )

    name: str
    visible: bool = True
    opacity: float = 1.0
    transform: Transform

    _mouse_drag_callbacks: list[MouseCallback[Self]] = PrivateAttr(
        default_factory=lambda: []
    )
    _mouse_wheel_callbacks: list[WheelCallback[Self]] = PrivateAttr(
        default_factory=lambda: []
    )

    @property
    def mouse_drag_callbacks(self) -> list[MouseCallback[Self]]:
        """Callbacks called on a mouse press, then driven through the drag."""
        return self._mouse_drag_callbacks

    @property
    def mouse_wheel_callbacks(self) -> list[WheelCallback[Self]]:
        """Callbacks called on a turn of the mouse wheel."""
        return self._mouse_wheel_callbacks

    @property
    @abstractmethod
    def ndim(self) -> int:
        """Number of axes of the layer."""

    @property
    @abstractmethod
    def extent_steps(self) -> tuple[int, ...]:
        """Number of steps on each of the layer's axes."""

    @abstractmethod
    def slice(self, dims: Dims) -> SliceArray:
        """Return the displayed plane for `dims`, materialised."""

    def slice_key(self, dims: Dims) -> BasicKey:
        """Return the key that picks the displayed plane of the layer's data.

        The layer's axes line up with the last `ndim` axes of `dims`. A
        displayed axis is kept whole and any other is cut at the current step,
        or at the last step of the layer when the step is past it.
        """
        offset = dims.ndim - self.ndim
        return tuple(
            slice(None)
            if axis + offset in dims.displayed
            else min(dims.current_step[axis + offset], steps - 1)
            for axis, steps in enumerate(self.extent_steps)
        )
