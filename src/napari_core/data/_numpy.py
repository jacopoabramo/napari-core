import numpy as np

from napari_core.typing import BasicKey, LayerDataProtocol, SliceArray


class NumpyAdapter:
    """Adapter for NumPy arrays."""

    in_memory = True

    def accepts(self, data: LayerDataProtocol) -> bool:
        """Return whether `data` is a NumPy array."""
        return isinstance(data, np.ndarray)

    def materialize(self, data: LayerDataProtocol, key: BasicKey) -> SliceArray:
        """Return `data[key]` as an array."""
        return np.asarray(data[key])
