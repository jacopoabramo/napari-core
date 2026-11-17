"""What a backend can draw, and the fallback for what it cannot."""

import logging
from dataclasses import dataclass
from typing import TypeVar

from napari_core.model import Interpolation

T = TypeVar("T")

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Capabilities:
    """The values of the model's vocabulary a backend can draw."""

    interpolation: frozenset[Interpolation]


def supported(
    value: T,
    allowed: frozenset[T],
    default: T,
    warned: set[T],
    field: str,
    backend: str,
) -> T:
    """Return `value` if the backend can draw it, else `default`, warning once.

    The warning is logged once per value. `warned` records the values already
    warned about; the caller owns it.
    """
    if value in allowed:
        return value
    if value not in warned:
        warned.add(value)
        # str() so that a StrEnum member shows as its quoted value, not as its repr.
        logger.warning(
            "%s cannot draw %s %r, using %r", backend, field, str(value), str(default)
        )
    return default
