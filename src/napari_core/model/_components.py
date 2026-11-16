"""Models that describe how a layer is placed and drawn."""

from psygnal import EventedModel
from pydantic import Field, field_validator

from ._colormap import COLORMAPS, Colormap
from ._config import EventedConfigDict


class Transform(EventedModel):
    """Scale and translation from data to world coordinates, one entry per axis."""

    scale: tuple[float, ...]
    translate: tuple[float, ...]


class IntensityAppearance(EventedModel):
    """How an intensity image is mapped to colour."""

    model_config = EventedConfigDict(
        validate_assignment=True,
        field_dependencies={"colormap": ["colormap"]},
    )

    colormap: Colormap = Field(default_factory=lambda: COLORMAPS["gray"])
    contrast_limits: tuple[float, float] = (0.0, 1.0)
    gamma: float = 1.0

    @field_validator("colormap", mode="before")
    @classmethod
    def _look_up_colormap(cls, value: object) -> object:
        """Replace a colormap name with the built-in colormap of that name."""
        if not isinstance(value, str):
            return value
        if value not in COLORMAPS:
            raise ValueError(
                f"unknown colormap {value!r}, use one of {list(COLORMAPS)}"
            )
        return COLORMAPS[value]
