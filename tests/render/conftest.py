"""Fixtures of the shared render suite, which runs on every backend."""

# pyright: reportMissingTypeStubs=false

import weakref
from collections.abc import Generator
from typing import Final

import pytest
from helpers import BackendFactory, Show
from PyQt6.QtCore import QCoreApplication, QEvent
from PyQt6.QtWidgets import QApplication, QWidget
from rendercanvas.qt import QRenderWidget

from napari_core.model import ViewerModel
from napari_core.render import RenderBackend, RenderSurface
from napari_core.render.pygfx import PygfxBackend
from napari_core.render.vispy import VispyBackend

BACKENDS: Final[dict[str, BackendFactory]] = {
    "pygfx": lambda: PygfxBackend[QWidget](canvas_class=QRenderWidget),
    "vispy": VispyBackend[QWidget],
}


@pytest.fixture(params=sorted(BACKENDS))
def backend(
    request: pytest.FixtureRequest, qapp: QApplication
) -> RenderBackend[QWidget]:
    """Return each render backend in turn."""
    name: object = request.param
    if not isinstance(name, str):
        raise TypeError(f"backend name must be a string, got {name!r}")
    return BACKENDS[name]()


@pytest.fixture
def shown(
    backend: RenderBackend[QWidget], qapp: QApplication
) -> Generator[Show, None, None]:
    """Return a function that shows a view at 200 by 100; close its surfaces after."""
    made: list[weakref.ref[RenderSurface[QWidget]]] = []

    def show(viewer: ViewerModel) -> RenderSurface[QWidget]:
        surface = backend.create_surface(viewer.view, None)
        made.append(weakref.ref(surface))
        viewer.view.canvas_size = (200, 100)
        surface.native.resize(200, 100)
        surface.native.show()
        qapp.processEvents()
        return surface

    yield show
    for reference in made:
        if (surface := reference()) is not None:
            surface.close()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
