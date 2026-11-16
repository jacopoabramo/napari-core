"""The viewer model."""

from psygnal import EventedModel
from psygnal.containers import EventedList
from pydantic import Field

from ._camera import Camera
from ._dims import Dims
from ._layer import Layer
from ._view import View


class ViewerModel(EventedModel):
    """A viewer with one view."""

    view: View = Field(default_factory=View)

    @property
    def layers(self) -> EventedList[Layer]:
        """The layers of the view."""
        return self.view.layers

    @property
    def dims(self) -> Dims:
        """The dims of the view."""
        return self.view.dims

    @property
    def camera(self) -> Camera:
        """The camera of the view."""
        return self.view.camera
