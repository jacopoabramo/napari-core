"""Fixtures of the pygfx backend tests."""

# pyright: reportMissingTypeStubs=false

from collections.abc import Generator

import pytest
from PyQt6.QtCore import QCoreApplication, QEvent
from PyQt6.QtWidgets import QApplication, QWidget
from rendercanvas.qt import QRenderWidget

from napari_core.render.pygfx import PygfxBackend


@pytest.fixture(autouse=True)
def delete_closed_widgets(qapp: QApplication) -> Generator[None, None, None]:
    """Have Qt delete the widgets that the test closed."""
    yield
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)


@pytest.fixture
def backend(qapp: QApplication) -> PygfxBackend[QWidget]:
    """Return the pygfx backend on Qt render widgets."""
    return PygfxBackend[QWidget](canvas_class=QRenderWidget)
