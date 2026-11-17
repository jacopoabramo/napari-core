"""Fixtures of the vispy backend tests."""

# pyright: reportMissingTypeStubs=false

from collections.abc import Callable, Generator
from typing import Protocol, runtime_checkable

import pytest
from PyQt6.QtCore import QCoreApplication, QEvent
from PyQt6.QtWidgets import QApplication
from typing_extensions import override
from vispy.scene import SceneCanvas

from napari_core.render import LayerAdapter


class DrawnVisual(Protocol):
    """The gamma and contrast limits of a vispy visual."""

    gamma: float
    clim: tuple[float, float]


@runtime_checkable
class VisualHolder(LayerAdapter, Protocol):
    """A layer adapter that draws with a vispy visual."""

    @property
    def visual(self) -> DrawnVisual: ...


@pytest.fixture(autouse=True)
def delete_closed_widgets(qapp: QApplication) -> Generator[None, None, None]:
    """Have Qt delete the widgets that the test scheduled for deletion."""
    yield
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)


@pytest.fixture
def closed_canvases(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    """Return the canvases the vispy surface closes, recorded by a canvas subclass."""
    closed: list[object] = []

    class RecordingCanvas(SceneCanvas):
        @override
        def close(self) -> None:
            closed.append(self)
            super().close()

    monkeypatch.setattr(
        "napari_core.render.vispy._surface.SceneCanvas", RecordingCanvas
    )
    return closed


@pytest.fixture
def visual_state() -> Callable[[LayerAdapter], tuple[float, tuple[float, float]]]:
    """Return a function that reads the gamma and contrast limits of a visual."""

    def read(adapter: LayerAdapter) -> tuple[float, tuple[float, float]]:
        assert isinstance(adapter, VisualHolder)
        low, high = adapter.visual.clim
        return adapter.visual.gamma, (low, high)

    return read
