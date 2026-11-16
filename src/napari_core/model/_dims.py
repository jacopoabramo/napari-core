"""The dimension slider model."""

from typing import Self

from psygnal import EventedModel
from pydantic import Field, model_validator

from ._config import EventedConfigDict


def _fit(values: tuple[int, ...], size: int, fill: int) -> tuple[int, ...]:
    return (fill,) * (size - len(values)) + values[max(len(values) - size, 0) :]


class Dims(EventedModel):
    """Number of axes and the position along each, with both kept consistent.

    `nsteps` and `current_step` always have one entry per axis. Growing `ndim`
    pads them on the left, shrinking it drops entries from the left, and
    `current_step` is clamped to each axis.
    """

    model_config = EventedConfigDict(
        validate_assignment=True,
        field_dependencies={
            "nsteps": ["ndim"],
            "current_step": ["ndim", "nsteps", "current_step"],
        },
    )

    ndim: int = Field(default=2, ge=2)
    nsteps: tuple[int, ...] = (1, 1)
    current_step: tuple[int, ...] = (0, 0)

    @property
    def displayed(self) -> tuple[int, int]:
        """The two axes shown on the surface."""
        return (self.ndim - 2, self.ndim - 1)

    @model_validator(mode="after")
    def _make_consistent(self) -> Self:
        nsteps = _fit(self.nsteps, self.ndim, 1)
        current_step = tuple(
            max(0, min(step, n - 1))
            for step, n in zip(
                _fit(self.current_step, self.ndim, 0), nsteps, strict=True
            )
        )
        object.__setattr__(self, "nsteps", nsteps)
        object.__setattr__(self, "current_step", current_step)
        return self
