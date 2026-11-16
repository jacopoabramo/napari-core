"""The base class of layers."""

import operator
from abc import abstractmethod
from types import UnionType
from typing import Annotated, ClassVar, Self, Union, get_args, get_origin

from psygnal import EventedModel
from pydantic import Field, PrivateAttr

from napari_core.typing import BasicKey, SliceArray

from ._components import Transform
from ._config import EventedConfigDict
from ._dims import Dims
from ._input import MouseCallback, WheelCallback


def holds_evented_model(annotation: object) -> bool:
    """Return whether `annotation` is an evented model or a union that has one.

    `Annotated` is unwrapped; a container of models, such as a list, is not.
    """
    origin = get_origin(annotation)
    if origin is Union or origin is UnionType:
        return any(holds_evented_model(arg) for arg in get_args(annotation))
    if origin is Annotated:
        return holds_evented_model(get_args(annotation)[0])
    return isinstance(annotation, type) and issubclass(annotation, EventedModel)


def use_identity_comparison(cls: type) -> None:
    """Replace the equality check of the fields that `cls` replaces by object.

    Raises
    ------
    TypeError
        If a name in `compared_by_identity` is not a field of `cls`.
    """
    if not issubclass(cls, EventedModel):
        return
    for klass in cls.__mro__:
        for field in vars(klass).get("compared_by_identity", ()):
            if field not in cls.model_fields:
                raise TypeError(
                    f"{cls.__name__} lists {field!r} in compared_by_identity, "
                    "but has no such field"
                )
            cls.__eq_operators__[field] = operator.is_
    for field, info in cls.model_fields.items():
        if holds_evented_model(info.annotation):
            cls.__eq_operators__[field] = operator.is_


class LayerMeta(type(EventedModel)):
    """Makes the fields of a layer class that are replaced by object compare so.

    psygnal builds the comparison of each field when it creates a class, after
    any hook of pydantic has run, so only a metaclass can change it.
    """

    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, object],
        **kwargs: object,
    ) -> "LayerMeta":
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)
        use_identity_comparison(cls)
        return cls


class Layer(EventedModel, metaclass=LayerMeta):
    """A drawable item of a view; subclasses supply the data-specific parts.

    A field whose type is an evented model, such as `transform`, or a union
    with one, such as `Transform | None`, is replaced when another object is
    assigned, even one equal to the old. A container of models keeps comparing
    by its contents, since it is changed in place rather than replaced. A
    class names further fields that behave so in `compared_by_identity`, which
    adds to the names of its bases.

    `opacity` must be within 0 to 1 inclusive.
    """

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
    opacity: float = Field(default=1.0, ge=0, le=1)
    transform: Transform

    compared_by_identity: ClassVar[tuple[str, ...]] = ()

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

        Raises
        ------
        ValueError
            If the layer has more axes than `dims`.
        """
        if self.ndim > dims.ndim:
            raise ValueError(
                f"layer has {self.ndim} axes, but dims has only {dims.ndim}"
            )
        offset = dims.ndim - self.ndim
        return tuple(
            slice(None)
            if axis + offset in dims.displayed
            else min(dims.current_step[axis + offset], steps - 1)
            for axis, steps in enumerate(self.extent_steps)
        )
