"""The image layer."""

import operator
from typing import Self

from pydantic import Field, field_validator, model_validator
from typing_extensions import override

from napari_core.data import adapter_for, as_layer_data
from napari_core.typing import BasicKey, LayerDataProtocol, SliceArray

from ._colormap import Colormap
from ._components import IntensityAppearance, Transform
from ._config import EventedConfigDict
from ._dims import Dims
from ._layer import Layer


class Image(Layer):
    """A layer that shows array data as intensities through a colormap.

    Without `transform` the layer is placed with scale 1 and translation 0 on
    every axis of its data. Without `appearance` it gets the `gray` colormap
    and contrast limits from `reset_contrast_limits`.

    Raises
    ------
    ValueError
        If `transform` does not have one scale and one translation per axis
        of `data`.
    """

    model_config = EventedConfigDict(arbitrary_types_allowed=True)

    data: LayerDataProtocol
    appearance: IntensityAppearance = Field(default_factory=IntensityAppearance)

    @field_validator("data", mode="before")
    @classmethod
    def _validate_data(cls, value: object) -> LayerDataProtocol:
        """Raise `TypeError` unless `value` is layer data."""
        return as_layer_data(value)

    @model_validator(mode="before")
    @classmethod
    def _default_transform(cls, values: dict[str, object]) -> dict[str, object]:
        """Add an identity transform when a new image is built without one."""
        if "data" not in values or "transform" in values:
            return values
        ndim = as_layer_data(values["data"]).ndim
        transform = Transform(scale=(1.0,) * ndim, translate=(0.0,) * ndim)
        return {**values, "transform": transform}

    @model_validator(mode="after")
    def _check_transform(self) -> Self:
        lengths = (len(self.transform.scale), len(self.transform.translate))
        if lengths != (self.data.ndim, self.data.ndim):
            raise ValueError(
                f"transform has {lengths[0]} scale and {lengths[1]} translate "
                f"entries, but the data has {self.data.ndim} axes"
            )
        return self

    @override
    def model_post_init(self, context: object, /) -> None:
        """Take contrast limits from the data unless an appearance was passed."""
        super().model_post_init(context)
        if "appearance" not in self.model_fields_set:
            self.reset_contrast_limits()

    @property
    def ndim(self) -> int:
        """Number of axes of the data."""
        return self.data.ndim

    @property
    def extent_steps(self) -> tuple[int, ...]:
        """The shape of the data."""
        return self.data.shape

    @property
    def colormap(self) -> Colormap:
        """The colormap of the appearance."""
        return self.appearance.colormap

    @colormap.setter
    def colormap(self, value: Colormap) -> None:
        self.appearance.colormap = value

    @property
    def contrast_limits(self) -> tuple[float, float]:
        """The contrast limits of the appearance."""
        return self.appearance.contrast_limits

    @contrast_limits.setter
    def contrast_limits(self, value: tuple[float, float]) -> None:
        self.appearance.contrast_limits = value

    @property
    def gamma(self) -> float:
        """The gamma of the appearance."""
        return self.appearance.gamma

    @gamma.setter
    def gamma(self, value: float) -> None:
        self.appearance.gamma = value

    @property
    def scale(self) -> tuple[float, ...]:
        """The scale of the transform."""
        return self.transform.scale

    @scale.setter
    def scale(self, value: tuple[float, ...]) -> None:
        self.transform.scale = value

    @property
    def translate(self) -> tuple[float, ...]:
        """The translation of the transform."""
        return self.transform.translate

    @translate.setter
    def translate(self, value: tuple[float, ...]) -> None:
        self.transform.translate = value

    def slice(self, dims: Dims) -> SliceArray:
        """Return the displayed plane for `dims` as a NumPy array."""
        return adapter_for(self.data).materialize(self.data, self.slice_key(dims))

    def reset_contrast_limits(self) -> None:
        """Set the contrast limits to the range of the data.

        In-memory data is scanned whole. Other data is read at the middle step
        of every axis but the last two, to avoid computing all of it.
        """
        adapter = adapter_for(self.data)
        key: BasicKey = ...
        if not adapter.in_memory:
            key = tuple(
                slice(None) if axis >= self.ndim - 2 else steps // 2
                for axis, steps in enumerate(self.extent_steps)
            )
        plane = adapter.materialize(self.data, key)
        low, high = float(plane.min()), float(plane.max())
        self.appearance.contrast_limits = (low, high if high > low else low + 1.0)


# psygnal rebuilds __eq_operators__ from the annotations when the class is
# created, so an entry in the class body would be overwritten.
Image.__eq_operators__["data"] = operator.is_
