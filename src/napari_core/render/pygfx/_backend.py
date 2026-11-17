"""The pygfx rendering backend."""

from collections.abc import Callable
from typing import Generic

from napari_core.model import View
from napari_core.render import Capabilities, NativeT, RenderSurface

from ._image import BACKEND_NAME, CAPABILITIES
from ._surface import PygfxSurface


class PygfxBackend(Generic[NativeT]):
    """Makes surfaces that draw a view with pygfx on a rendercanvas canvas."""

    name: str = BACKEND_NAME
    capabilities: Capabilities = CAPABILITIES

    def __init__(self, canvas_class: Callable[[NativeT | None], NativeT]) -> None:
        """Make surfaces on canvases built with `canvas_class(parent)`.

        Parameters
        ----------
        canvas_class
            A rendercanvas canvas class, such as `rendercanvas.qt.QRenderWidget`.
        """
        self._canvas_class = canvas_class

    def create_surface(
        self, view: View, parent: NativeT | None
    ) -> RenderSurface[NativeT]:
        """Return a surface that shows `view` inside `parent`.

        Raises
        ------
        TypeError
            If `canvas_class` does not make a rendercanvas canvas.
        """
        return PygfxSurface(view, self._canvas_class, parent)
