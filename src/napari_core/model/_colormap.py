"""Colormaps and the built-in set."""

from collections.abc import Mapping
from types import MappingProxyType

import numpy as np
import numpy.typing as npt
from psygnal import EventedModel
from pydantic import ConfigDict


class Colormap(EventedModel):
    """A named table of RGBA colours in `[0, 1]`, one row per level."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    colors: npt.NDArray[np.float32]


def _ramp(name: str, rgb: tuple[float, float, float]) -> Colormap:
    levels = np.linspace(0, 1, 256, dtype=np.float32)[:, np.newaxis]
    colors = np.concatenate(
        [levels * np.asarray(rgb, dtype=np.float32), np.ones_like(levels)], axis=1
    )
    colors.flags.writeable = False
    return Colormap(name=name, colors=colors)


COLORMAPS: Mapping[str, Colormap] = MappingProxyType(
    {
        cm.name: cm
        for cm in (
            _ramp("gray", (1, 1, 1)),
            _ramp("red", (1, 0, 0)),
            _ramp("green", (0, 1, 0)),
            _ramp("blue", (0, 0, 1)),
            _ramp("magenta", (1, 0, 1)),
        )
    }
)


def colormap_named(name: str) -> Colormap:
    """Return the built-in colormap called `name`, or raise `ValueError`."""
    if name not in COLORMAPS:
        raise ValueError(f"unknown colormap {name!r}, use one of {list(COLORMAPS)}")
    return COLORMAPS[name]
