"""Shared test fixtures."""

# pyright: reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false

from importlib import import_module

import dask.array as da
import pytest
from helpers import FakeSurface
from PyQt6.QtWidgets import QApplication
from vispy.app import use_app

from napari_core.data import as_layer_data
from napari_core.typing import LayerDataProtocol


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


@pytest.fixture
def dask_stack() -> LayerDataProtocol:
    """Return a 3D dask array, as layer data."""
    return as_layer_data(da.arange(24).reshape(2, 3, 4))


@pytest.fixture
def dask_four_axes() -> LayerDataProtocol:
    """Return a 4D dask array, as layer data."""
    return as_layer_data(da.arange(120).reshape(2, 3, 4, 5))


@pytest.fixture
def dask_unknown_sizes() -> object:
    """Return a dask array whose shape holds NaN."""
    array = da.arange(10)
    return array[array > 3]


@pytest.fixture
def dask_known_sizes() -> object:
    """Return a dask array whose shape is known."""
    return da.zeros((4, 5, 6), chunks=(1, 5, 6))
