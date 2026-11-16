"""Static cases for `LayerDataProtocol`, checked by pyright and pyrefly only."""

from typing import assert_type

import numpy as np

from napari_core.typing import LayerDataProtocol

uint8_array: np.ndarray[tuple[int, ...], np.dtype[np.uint8]] = np.zeros(
    (2, 3), dtype=np.uint8
)
float64_array: np.ndarray[tuple[int, ...], np.dtype[np.float64]] = np.zeros((2, 3))

bare: LayerDataProtocol = uint8_array
typed: LayerDataProtocol[np.dtype[np.uint8]] = uint8_array
mismatched: LayerDataProtocol[np.dtype[np.uint8]] = float64_array  # type: ignore


def dtype_of_bare(data: LayerDataProtocol) -> str:
    """Return the dtype kind of bare layer data."""
    assert_type(data.dtype, np.dtype[np.generic])
    return data.dtype.kind
