from types import EllipsisType
from typing import Protocol, runtime_checkable

import numpy as np
import numpy.typing as npt

from ._array_api import (
    DTypeT_co,
    HasDType,
    HasGetItem,
    HasNDim,
    HasShape,
    HasSize,
)

BasicKey = int | slice | EllipsisType | tuple[int | slice | EllipsisType, ...]
SliceArray = npt.NDArray[np.generic]


@runtime_checkable
class LayerDataProtocol(
    HasDType[DTypeT_co],
    HasShape,
    HasNDim,
    HasSize,
    HasGetItem[BasicKey],
    Protocol[DTypeT_co],
):
    """Protocol for the array data of a layer."""
