# Origin of these protocols:
#
# - HasDType is copied from array-api-typing, commit 18c97e7
#   (src/array_api_typing/_array.py), which is MIT licensed:
#
#     MIT License
#
#     Copyright (c) 2020-2024 Consortium for Python Data API Standards
#     contributors
#
#     Permission is hereby granted, free of charge, to any person obtaining a
#     copy of this software and associated documentation files (the
#     "Software"), to deal in the Software without restriction, including
#     without limitation the rights to use, copy, modify, merge, publish,
#     distribute, sublicense, and/or sell copies of the Software, and to
#     permit persons to whom the Software is furnished to do so, subject to
#     the following conditions:
#
#     The above copyright notice and this permission notice shall be included
#     in all copies or substantial portions of the Software.
#
#     THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
#     OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
#     MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#     IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
#     CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
#     TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
#     SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
# - HasShape, HasNDim and HasSize follow data-apis/array-api-typing pull
#   request 34, and HasGetItem follows pull request 69 (both open when
#   written).
#
# Deliberate differences from the pull requests:
#
# - shape and size hold int only. The pull requests allow None for unknown
#   dimensions, which layer data never has.
# - __getitem__ returns object. The pull request returns Self, which a Dask
#   array or a view of one would not satisfy for every key.

from typing import Protocol

import numpy as np
from typing_extensions import TypeVar

DTypeT_co = TypeVar("DTypeT_co", covariant=True, default=np.dtype[np.generic])
KeyT_contra = TypeVar("KeyT_contra", contravariant=True, default=object)


class HasDType(Protocol[DTypeT_co]):
    """Protocol for array classes that have a data type attribute."""

    @property
    def dtype(self, /) -> DTypeT_co:
        """Data type of the array elements."""
        ...


class HasShape(Protocol):
    """Protocol for array classes that have a shape attribute."""

    @property
    def shape(self, /) -> tuple[int, ...]:
        """Shape of the array."""
        ...


class HasNDim(Protocol):
    """Protocol for array classes that have a number of dimensions attribute."""

    @property
    def ndim(self, /) -> int:
        """Number of array dimensions."""
        ...


class HasSize(Protocol):
    """Protocol for array classes that have a size attribute."""

    @property
    def size(self, /) -> int:
        """Number of elements in the array."""
        ...


class HasGetItem(Protocol[KeyT_contra]):
    """Protocol for array classes that support indexing with a key."""

    def __getitem__(self, key: KeyT_contra, /) -> object:
        """Return the array element or sub-array at the key."""
        ...
