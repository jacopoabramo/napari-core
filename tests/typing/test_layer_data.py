import numpy as np
import pytest

from napari_core.typing import LayerDataProtocol


def test_numpy_array_is_layer_data():
    """Accept a NumPy array as layer data."""
    assert isinstance(np.zeros((2, 3)), LayerDataProtocol)


@pytest.mark.parametrize("value", [[1, 2, 3], 5, "abc", None])
def test_non_arrays_are_not_layer_data(value):
    """Reject values that lack the array members."""
    assert not isinstance(value, LayerDataProtocol)
