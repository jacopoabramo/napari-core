"""What a rendering backend and its surface must provide."""

from ._capabilities import Capabilities, supported
from ._events import (
    SurfaceEnterLeaveEvent,
    SurfaceEvent,
    SurfaceEventType,
    SurfacePointerEvent,
    SurfaceResizeEvent,
    SurfaceWheelEvent,
)
from ._protocols import LayerAdapter, NativeT, NativeT_co, RenderBackend, RenderSurface
from ._registry import create_layer_adapter, register_layer_adapter

__all__ = [
    "Capabilities",
    "LayerAdapter",
    "NativeT",
    "NativeT_co",
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
    "supported",
]
