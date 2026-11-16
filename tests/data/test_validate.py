import dask.array as da
import numpy as np
import pytest

from napari_core.data import as_layer_data


def test_returns_a_numpy_array_unchanged():
    """Return the same object when it is valid layer data."""
    array = np.zeros((2, 3))
    assert as_layer_data(array) is array


def test_names_the_missing_members():
    """Name every missing member in the error."""
    with pytest.raises(TypeError, match="dtype.*ndim.*shape.*size"):
        as_layer_data([1, 2, 3])


def test_rejects_dask_array_with_unknown_sizes():
    """Reject a dask array whose shape is not known and name the fix."""
    array = da.arange(10)
    with pytest.raises(TypeError, match=r"compute_chunk_sizes\(\)"):
        as_layer_data(array[array > 3])


def test_accepts_dask_array_with_known_sizes():
    """Accept a dask array whose shape is known."""
    array = da.zeros((4, 5, 6), chunks=(1, 5, 6))
    assert as_layer_data(array) is array
