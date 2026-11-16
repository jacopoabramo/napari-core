from typing import TYPE_CHECKING

import numpy as np
from typing_extensions import TypeIs

from napari_core.typing import BasicKey, LayerDataProtocol, SliceArray

if TYPE_CHECKING:
    import dask.array


def is_dask_array(obj: object) -> TypeIs["dask.array.Array"]:
    """Return whether `obj` is a dask array, without importing dask."""
    return type(obj).__module__.split(".")[0] == "dask"


class DaskAdapter:
    """Adapter for dask arrays."""

    in_memory = False

    def accepts(self, data: LayerDataProtocol) -> bool:
        """Return whether `data` is a dask array."""
        return is_dask_array(data)

    def materialize(self, data: LayerDataProtocol, key: BasicKey) -> SliceArray:
        """Return `data[key]` computed into a NumPy array."""
        array: object = data
        if not is_dask_array(array):
            raise TypeError(f"{type(data).__name__} is not a dask array")
        return np.asarray(array[key])
