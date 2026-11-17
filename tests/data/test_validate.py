import numpy as np
import pytest

from napari_core.data import as_layer_data


def test_returns_a_numpy_array_unchanged() -> None:
    """Return the same object when it is valid layer data."""
    array = np.zeros((2, 3))
    assert as_layer_data(array) is array


def test_names_the_missing_members() -> None:
    """Name every missing member in the error."""
    with pytest.raises(TypeError, match="dtype.*ndim.*shape.*size"):
        as_layer_data([1, 2, 3])


def test_rejects_dask_array_with_unknown_sizes(dask_unknown_sizes: object) -> None:
    """Reject a dask array whose shape is not known and name the fix."""
    with pytest.raises(TypeError, match=r"compute_chunk_sizes\(\)"):
        as_layer_data(dask_unknown_sizes)


class BoolShaped:
    dtype = np.dtype(np.uint8)
    ndim = 2
    shape = (True, 3)
    size = 3

    def __getitem__(self, key: object) -> object:
        return self


def test_rejects_a_bool_in_the_shape() -> None:
    """Refuse a shape entry that is a bool, although bool is a subclass of int."""
    with pytest.raises(TypeError, match="integers"):
        as_layer_data(BoolShaped())


def test_accepts_dask_array_with_known_sizes(dask_known_sizes: object) -> None:
    """Accept a dask array whose shape is known."""
    assert as_layer_data(dask_known_sizes) is dask_known_sizes
