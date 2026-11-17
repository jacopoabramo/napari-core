import logging

import pytest

from napari_core.model import Interpolation
from napari_core.render import supported


def test_supported_value_is_returned_without_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Return a value the backend can draw and log nothing."""
    warned: set[Interpolation] = set()
    allowed = frozenset({Interpolation.NEAREST, Interpolation.LINEAR})
    with caplog.at_level(logging.WARNING, logger="napari_core"):
        value = supported(
            Interpolation.LINEAR,
            allowed,
            Interpolation.NEAREST,
            warned,
            "interpolation",
            "x",
        )
    assert value is Interpolation.LINEAR
    assert caplog.records == []


def test_unsupported_value_falls_back_and_warns_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Return the default for a value the backend lacks and warn only the first time."""
    warned: set[Interpolation] = set()
    allowed = frozenset({Interpolation.NEAREST})
    with caplog.at_level(logging.WARNING, logger="napari_core"):
        first = supported(
            Interpolation.LANCZOS,
            allowed,
            Interpolation.NEAREST,
            warned,
            "interpolation",
            "x",
        )
        second = supported(
            Interpolation.LANCZOS,
            allowed,
            Interpolation.NEAREST,
            warned,
            "interpolation",
            "x",
        )
    assert (first, second) == (Interpolation.NEAREST, Interpolation.NEAREST)
    assert [record.getMessage() for record in caplog.records] == [
        "x cannot draw interpolation 'lanczos', using 'nearest'"
    ]
