from collections.abc import Sequence

import numpy as np
from typing_extensions import TypeIs

from napari_core.typing import LayerDataProtocol

MEMBERS = ("dtype", "ndim", "shape", "size", "__getitem__")


def is_layer_data(obj: object) -> TypeIs[LayerDataProtocol]:
    """Return whether `obj` has every member of the layer data protocol."""
    return isinstance(obj, LayerDataProtocol)


def check_values(dtype: object, shape: Sequence[object]) -> None:
    """Raise `TypeError` unless `dtype` is a NumPy dtype and `shape` holds ints."""
    if not isinstance(dtype, np.dtype):
        raise TypeError(f"dtype must be a numpy dtype, got {type(dtype).__name__}")
    if not all(isinstance(n, int) for n in shape):
        hint = (
            ", call compute_chunk_sizes() first"
            if any(isinstance(n, float) for n in shape)
            else ""
        )
        raise TypeError(f"shape {tuple(shape)} must hold integers{hint}")


def as_layer_data(obj: object) -> LayerDataProtocol:
    """Return `obj` as layer data, or raise `TypeError` when it is not.

    Raises
    ------
    TypeError
        If `obj` lacks a member of the layer data protocol, its `dtype` is not
        a NumPy dtype, or its shape holds anything but integers.
    """
    if not is_layer_data(obj):
        missing = [name for name in MEMBERS if not hasattr(obj, name)]
        raise TypeError(
            f"{type(obj).__name__} is not layer data, it lacks: {', '.join(missing)}"
        )
    check_values(obj.dtype, obj.shape)
    return obj
