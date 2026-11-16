"""The layer adapters each backend supplies, found through the layer's type."""

from collections.abc import Callable

from napari_core.model import Layer, LayerT, View

from ._protocols import LayerAdapter

registry: dict[tuple[str, type[object]], Callable[[Layer, View], LayerAdapter]] = {}


def register_layer_adapter(
    backend: str,
    layer_type: type[LayerT],
    factory: Callable[[LayerT, View], LayerAdapter],
) -> None:
    """Register `factory` as the adapter of `layer_type` layers for `backend`."""

    def checked(layer: Layer, view: View) -> LayerAdapter:
        if not isinstance(layer, layer_type):
            raise TypeError(
                f"expected {layer_type.__name__}, got {type(layer).__name__}"
            )
        return factory(layer, view)

    registry[(backend, layer_type)] = checked


def create_layer_adapter(backend: str, layer: Layer, view: View) -> LayerAdapter:
    """Return the adapter of `backend` for the layer's type or its nearest base.

    Raises
    ------
    LookupError
        If `backend` has no adapter for the layer's type or any of its bases.
    """
    for layer_type in type(layer).__mro__:
        if (factory := registry.get((backend, layer_type))) is not None:
            return factory(layer, view)
    raise LookupError(f"backend {backend!r} has no adapter for {type(layer).__name__}")
