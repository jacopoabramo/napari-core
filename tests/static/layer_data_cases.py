"""Static cases for `LayerDataProtocol`, checked by pyright and pyrefly only."""

from typing import assert_type

import dask.array as da
import numpy as np

from napari_core.data import as_layer_data
from napari_core.model import ButtonEvent, Image, Layer, View
from napari_core.render import (
    LayerAdapter,
    SurfaceEvent,
    SurfaceWheelEvent,
    register_layer_adapter,
)
from napari_core.typing import LayerDataProtocol

uint8_array: np.ndarray[tuple[int, ...], np.dtype[np.uint8]] = np.zeros(
    (2, 3), dtype=np.uint8
)
float64_array: np.ndarray[tuple[int, ...], np.dtype[np.float64]] = np.zeros((2, 3))

bare: LayerDataProtocol = uint8_array
typed: LayerDataProtocol[np.dtype[np.uint8]] = uint8_array
mismatched: LayerDataProtocol[np.dtype[np.uint8]] = float64_array  # type: ignore


def dask_is_not_layer_data(dask_array: da.Array) -> LayerDataProtocol:
    """Return a dask array typed as layer data, which the checkers refuse."""
    return dask_array  # type: ignore


def validated_dask(dask_array: da.Array) -> None:
    """Check the type that validating a dask array gives."""
    assert_type(as_layer_data(dask_array), LayerDataProtocol)


def dtype_of_bare(data: LayerDataProtocol) -> str:
    """Return the dtype kind of bare layer data."""
    assert_type(data.dtype, np.dtype[np.generic])
    return data.dtype.kind


class OtherLayer(Layer):
    """A layer type that is not an image."""


def on_drag(layer: Image, event: ButtonEvent) -> None:
    """Handle a drag on an image."""


def on_other_drag(layer: OtherLayer, event: ButtonEvent) -> None:
    """Handle a drag on another layer type."""


def register(layer: Image) -> None:
    """Add callbacks to an image, where one typed for another layer fails."""
    layer.mouse_drag_callbacks.append(on_drag)
    layer.mouse_drag_callbacks.append(on_other_drag)  # type: ignore


class ImageAdapter:
    """An adapter for images."""

    def close(self) -> None:
        """Release nothing."""


def make_image_adapter(layer: Image, view: View) -> LayerAdapter:
    """Return the adapter of an image."""
    return ImageAdapter()


def make_other_adapter(layer: OtherLayer, view: View) -> LayerAdapter:
    """Return the adapter of another layer type."""
    return ImageAdapter()


register_layer_adapter("x", Image, make_image_adapter)
register_layer_adapter("x", Image, make_other_adapter)  # type: ignore


def wheel_delta(event: SurfaceEvent) -> float:
    """Read `dy` where the event is a wheel event."""
    match event["event_type"]:
        case "wheel":
            assert_type(event, SurfaceWheelEvent)
            return event["dy"]
        case "pointer_down" | "pointer_up" | "pointer_move" | "double_click":
            return event["dy"]  # type: ignore
        case _:
            return 0.0
