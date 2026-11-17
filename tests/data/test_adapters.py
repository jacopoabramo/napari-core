import numpy as np
import pytest

from napari_core.data import (
    adapter_for,
    as_layer_data,
    register_array_adapter,
)
from napari_core.typing import BasicKey, LayerDataProtocol, SliceArray


class FakeArray:
    dtype = np.dtype(np.uint8)
    ndim = 1
    shape = (3,)
    size = 3

    def __getitem__(self, key: BasicKey) -> object:
        return self


class AcceptAll:
    in_memory = True

    def accepts(self, data: LayerDataProtocol) -> bool:
        return True

    def materialize(self, data: LayerDataProtocol, key: BasicKey) -> SliceArray:
        return np.zeros(1)


def test_numpy_adapter_is_in_memory_and_materializes() -> None:
    """Slice a NumPy array through its adapter."""
    array = np.arange(24).reshape(2, 3, 4)
    adapter = adapter_for(array)
    assert adapter.in_memory
    np.testing.assert_array_equal(adapter.materialize(array, (1, ...)), array[1])


def test_dask_adapter_is_lazy_and_returns_numpy(dask_stack: LayerDataProtocol) -> None:
    """Compute a dask slice into a NumPy array."""
    adapter = adapter_for(dask_stack)
    assert not adapter.in_memory
    result = adapter.materialize(dask_stack, (1, ...))
    assert isinstance(result, np.ndarray)
    np.testing.assert_array_equal(result, np.arange(12, 24).reshape(3, 4))


def test_higher_priority_adapter_wins(restore_adapters: None) -> None:
    """Prefer the adapter registered with the higher priority."""
    special = AcceptAll()
    register_array_adapter(special, priority=10)
    assert adapter_for(np.zeros(3)) is special


def test_unknown_array_type_is_refused() -> None:
    """Raise when no adapter accepts the data."""
    with pytest.raises(TypeError, match="no array adapter"):
        adapter_for(as_layer_data(FakeArray()))
