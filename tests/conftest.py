"""Shared test fixtures."""

from importlib import import_module

import pytest
from helpers import FakeSurface


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
