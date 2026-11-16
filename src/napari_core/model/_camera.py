"""The camera model."""

from psygnal import EventedModel
from pydantic import Field

from ._config import EventedConfigDict


class Camera(EventedModel):
    """Position and magnification of the view of a two-dimensional scene.

    Attributes
    ----------
    center
        World point `(row, column)` at the middle of the surface.
    zoom
        Surface pixels per world unit.
    """

    model_config = EventedConfigDict(
        validate_assignment=True,
        field_dependencies={"center": ["center"], "zoom": ["zoom"]},
    )

    center: tuple[float, float] = (0.0, 0.0)
    zoom: float = Field(default=1.0, gt=0)
    mouse_pan: bool = True
    mouse_zoom: bool = True
