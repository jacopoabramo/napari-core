"""The view model."""

from psygnal import EventedModel
from pydantic import Field

from ._camera import Camera
from ._dims import Dims


class View(EventedModel):
    """What is shown: the dimension sliders, the camera and the canvas size."""

    dims: Dims = Field(default_factory=Dims)
    camera: Camera = Field(default_factory=Camera)
    canvas_size: tuple[int, int] = (640, 480)
