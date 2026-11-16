from typing import Protocol

from napari_core.typing import BasicKey, LayerDataProtocol, SliceArray


class ArrayAdapter(Protocol):
    """Holds what differs between array libraries."""

    in_memory: bool

    def accepts(self, data: LayerDataProtocol) -> bool:
        """Return whether this adapter handles the type of `data`."""
        ...

    def materialize(self, data: LayerDataProtocol, key: BasicKey) -> SliceArray:
        """Return `data[key]` as a NumPy array."""
        ...


registry: list[tuple[int, ArrayAdapter]] = []


def register_array_adapter(adapter: ArrayAdapter, *, priority: int = 0) -> None:
    """Add an adapter; a higher priority is asked first, ties by registration."""
    registry.append((priority, adapter))
    registry.sort(key=lambda entry: -entry[0])


def adapter_for(data: LayerDataProtocol) -> ArrayAdapter:
    """Return the first registered adapter that accepts `data`."""
    for _, adapter in registry:
        if adapter.accepts(data):
            return adapter
    raise TypeError(f"no array adapter accepts {type(data).__name__}")
