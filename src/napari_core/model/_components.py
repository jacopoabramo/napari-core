"""Models that describe how a layer is placed and drawn."""

from collections.abc import Sized
from enum import StrEnum

from psygnal import EventedModel
from pydantic import Field, ValidationInfo, field_validator

from ._colormap import COLORMAPS, Colormap, colormap_named
from ._config import EventedConfigDict


class Transform(EventedModel):
    """Scale and translation from data to world coordinates, one entry per axis.

    Raises
    ------
    ValueError
        If `scale` and `translate` have different lengths, whether given on
        construction or assigned later. Nothing is stored then.
    """

    model_config = EventedConfigDict(
        validate_assignment=True,
        field_dependencies={"scale": ["scale"], "translate": ["translate"]},
    )

    scale: tuple[float, ...]
    translate: tuple[float, ...]

    @field_validator("scale", "translate")
    @classmethod
    def _check_lengths(
        cls, value: tuple[float, ...], info: ValidationInfo
    ) -> tuple[float, ...]:
        """Raise `ValueError` unless `value` has the length of the other field."""
        other: object = info.data.get(
            "translate" if info.field_name == "scale" else "scale"
        )
        if isinstance(other, Sized) and len(other) != len(value):
            scale, translate = (
                (len(value), len(other))
                if info.field_name == "scale"
                else (len(other), len(value))
            )
            raise ValueError(
                f"the transform has {scale} scale and {translate} translate entries"
            )
        return value


class Interpolation(StrEnum):
    """How an image is resampled when it is drawn at another size."""

    NEAREST = "nearest"
    LINEAR = "linear"
    CUBIC = "cubic"
    LANCZOS = "lanczos"


class IntensityAppearance(EventedModel):
    """How an intensity image is mapped to colour.

    `gamma` must be above 0.
    """

    model_config = EventedConfigDict(
        validate_assignment=True,
        field_dependencies={
            "colormap": ["colormap"],
            "contrast_limits": ["contrast_limits"],
            "gamma": ["gamma"],
            "interpolation": ["interpolation"],
        },
    )

    colormap: Colormap = Field(default_factory=lambda: COLORMAPS["gray"])
    contrast_limits: tuple[float, float] = (0.0, 1.0)
    gamma: float = Field(default=1.0, gt=0)
    interpolation: Interpolation = Interpolation.NEAREST

    @field_validator("colormap", mode="before")
    @classmethod
    def _look_up_colormap(cls, value: object) -> object:
        """Replace a colormap name with the built-in colormap of that name."""
        return colormap_named(value) if isinstance(value, str) else value
