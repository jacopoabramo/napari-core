"""What a rendering backend and its surface must provide."""

from ._events import (
    SurfaceEnterLeaveEvent,
    SurfaceEvent,
    SurfaceEventType,
    SurfacePointerEvent,
    SurfaceResizeEvent,
    SurfaceWheelEvent,
)
from ._protocols import LayerAdapter, RenderBackend, RenderSurface
from ._registry import create_layer_adapter, register_layer_adapter

__all__ = [
    "LayerAdapter",
    "RenderBackend",
    "RenderSurface",
    "SurfaceEnterLeaveEvent",
    "SurfaceEvent",
    "SurfaceEventType",
    "SurfacePointerEvent",
    "SurfaceResizeEvent",
    "SurfaceWheelEvent",
    "create_layer_adapter",
    "register_layer_adapter",
]
