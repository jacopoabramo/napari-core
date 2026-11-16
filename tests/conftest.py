"""Shared test fixtures."""

from importlib import import_module

import pytest


@pytest.fixture
def restore_adapters(monkeypatch: pytest.MonkeyPatch) -> None:
    """Restore the array adapter registry after the test."""
    registry = import_module("napari_core.data._adapter").registry
    monkeypatch.setattr("napari_core.data._adapter.registry", list(registry))
