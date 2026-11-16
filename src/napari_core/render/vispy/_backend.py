"""The vispy rendering backend."""

from typing import Generic

from napari_core.model import View
from napari_core.render import RenderSurface

from ._image import BACKEND_NAME
from ._surface import NativeT, VispySurface


class VispyBackend(Generic[NativeT]):
    """Makes surfaces that draw a view on a vispy canvas."""

    name: str = BACKEND_NAME

    def create_surface(
        self, view: View, parent: NativeT | None
    ) -> RenderSurface[NativeT]:
        """Return a surface that shows `view` inside `parent`."""
        return VispySurface(view, parent)
