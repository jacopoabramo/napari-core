"""The image layer."""

from typing import ClassVar

import numpy as np
from pydantic import Field, ValidationInfo, field_validator, model_validator
from typing_extensions import override

from napari_core.data import adapter_for, as_layer_data
from napari_core.typing import BasicKey, LayerDataProtocol, SliceArray

from ._colormap import Colormap, colormap_named
from ._components import IntensityAppearance, Transform
from ._config import EventedConfigDict
from ._dims import Dims
from ._layer import Layer


def check_axes(ndim: int, transform: Transform) -> None:
    lengths = (len(transform.scale), len(transform.translate))
    if lengths != (ndim, ndim):
        raise ValueError(
            f"data has {ndim} axes, but the transform has {lengths[0]} scale "
            f"and {lengths[1]} translate entries"
        )


def check_entries(ndim: int, name: str, value: tuple[float, ...]) -> None:
    """Raise `ValueError` unless `value` has one entry per axis."""
    if len(value) != ndim:
        raise ValueError(f"data has {ndim} axes, but {name} has {len(value)} entries")


class Image(Layer):
    """A layer that shows array data as intensities through a colormap.

    Without `transform` the layer is placed with scale 1 and translation 0 on
    every axis of its data. Without `appearance` it gets the `gray` colormap
    and contrast limits from `reset_contrast_limits`.

    An image has at least 2 axes and keeps their number. The `scale` and
    `translate` properties are the checked way to change one of the two:
    they refuse a tuple whose length is not the number of axes. Assigning to
    `transform.scale` or `transform.translate` directly is refused only when
    the lengths of the two then differ.

    Raises
    ------
    ValueError
        If `data` has fewer than 2 axes, or `transform` does not have one
        scale and one translation per axis of `data`, whether given on
        construction or assigned later. pydantic reports it as its
        `ValidationError`, a subclass of `ValueError`. Nothing is stored then,
        and assigning data of another number of axes is refused the same way.
    TypeError
        If `data` is not layer data, from
        [`as_layer_data`][napari_core.data.as_layer_data], unchanged.
    """

    model_config = EventedConfigDict(arbitrary_types_allowed=True)
    compared_by_identity: ClassVar[tuple[str, ...]] = ("data",)

    # Never used: `_default_transform` supplies the real default from the data. The
    # default only tells the checkers that `transform` may be left out.
    transform: Transform = Field(
        default_factory=lambda: Transform(scale=(), translate=())
    )
    data: LayerDataProtocol
    appearance: IntensityAppearance = Field(default_factory=IntensityAppearance)

    @field_validator("data", mode="before")
    @classmethod
    def _validate_data(cls, value: object, info: ValidationInfo) -> LayerDataProtocol:
        """Return `value` as layer data with at least 2 axes and the transform's."""
        data = as_layer_data(value)
        if data.ndim < 2:
            raise ValueError(f"an image needs at least 2 axes, data has {data.ndim}")
        transform = info.data.get("transform")
        if isinstance(transform, Transform):
            check_axes(data.ndim, transform)
        return data

    @field_validator("transform", mode="after")
    @classmethod
    def _validate_transform(cls, value: Transform, info: ValidationInfo) -> Transform:
        """Raise `ValueError` unless `value` has the axes of the data."""
        data = info.data.get("data")
        if isinstance(data, LayerDataProtocol):
            check_axes(data.ndim, value)
        return value

    @model_validator(mode="before")
    @classmethod
    def _default_transform(cls, values: dict[str, object]) -> dict[str, object]:
        """Add an identity transform when a new image is built without one."""
        if "data" not in values or "transform" in values:
            return values
        ndim = as_layer_data(values["data"]).ndim
        transform = Transform(scale=(1.0,) * ndim, translate=(0.0,) * ndim)
        return {**values, "transform": transform}

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
    def colormap(self, value: Colormap | str) -> None:
        self.appearance.colormap = (
            colormap_named(value) if isinstance(value, str) else value
        )

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
        check_entries(self.ndim, "scale", value)
        self.transform.scale = value

    @property
    def translate(self) -> tuple[float, ...]:
        """The translation of the transform."""
        return self.transform.translate

    @translate.setter
    def translate(self, value: tuple[float, ...]) -> None:
        check_entries(self.ndim, "translate", value)
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
        finite = plane[np.isfinite(plane)]
        if finite.size == 0:
            self.appearance.contrast_limits = (0.0, 1.0)
            return
        low, high = float(finite.min()), float(finite.max())
        self.appearance.contrast_limits = (low, high if high > low else low + 1.0)
