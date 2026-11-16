"""Run-time checks and adapters for layer data."""

from ._adapter import (
    ArrayAdapter,
    adapter_for,
    register_array_adapter,
)
from ._dask import DaskAdapter
from ._numpy import NumpyAdapter
from ._validate import as_layer_data

register_array_adapter(NumpyAdapter())
register_array_adapter(DaskAdapter())

__all__ = [
    "ArrayAdapter",
    "adapter_for",
    "as_layer_data",
    "register_array_adapter",
]
