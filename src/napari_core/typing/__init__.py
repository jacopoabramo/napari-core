"""Protocols and type aliases that describe layer data."""

from ._array_api import DTypeT_co, HasDType, HasGetItem, HasNDim, HasShape, HasSize
from ._layer_data import BasicKey, LayerDataProtocol, SliceArray

__all__ = [
    "BasicKey",
    "DTypeT_co",
    "HasDType",
    "HasGetItem",
    "HasNDim",
    "HasShape",
    "HasSize",
    "LayerDataProtocol",
    "SliceArray",
]
