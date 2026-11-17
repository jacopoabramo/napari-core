"""Shared test fixtures."""

# pyright: reportMissingTypeStubs=false, reportUnknownVariableType=false

from importlib import import_module

import pytest
from helpers import FakeSurface
from PyQt6.QtWidgets import QApplication
from vispy.app import use_app


@pytest.fixture
def restore_adapters(monkeypatch: pytest.MonkeyPatch) -> None:
    """Restore the array adapter registry after the test."""
    registry = import_module("napari_core.data._adapter").registry
    monkeypatch.setattr("napari_core.data._adapter.registry", list(registry))


@pytest.fixture
def restore_layer_adapters(monkeypatch: pytest.MonkeyPatch) -> None:
    """Restore the layer adapter registry after the test."""
    registry = import_module("napari_core.render._registry").registry
    monkeypatch.setattr("napari_core.render._registry.registry", dict(registry))


@pytest.fixture
def surface() -> FakeSurface:
    """Return a new fake surface."""
    return FakeSurface()


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    """Return the Qt application that vispy uses on PyQt6, once per process.

    A Qt application can exist only once per process, so it is shared.
    """
    try:
        app = use_app("pyqt6").native
    except (ImportError, RuntimeError) as error:
        pytest.skip(f"no PyQt6 backend for vispy: {error}")
    assert isinstance(app, QApplication)
    return app
