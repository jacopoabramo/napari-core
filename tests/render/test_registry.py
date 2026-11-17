import numpy as np
import pytest
from helpers import Closer, image

from napari_core.model import Image, Layer, ViewerModel
from napari_core.render import create_layer_adapter, register_layer_adapter


def test_adapter_is_found_through_the_layer_type(
    restore_layer_adapters: None,
) -> None:
    """Create the adapter registered for the layer's type."""
    made: list[Layer] = []
    register_layer_adapter(
        "fake", Image, lambda layer, view: made.append(layer) or Closer()
    )
    layer, viewer = image(name="a", data=np.zeros((3, 4))), ViewerModel()
    adapter = create_layer_adapter("fake", layer, viewer.view)
    assert made == [layer]
    assert isinstance(adapter, Closer)


def test_subclass_uses_its_base_class_adapter(restore_layer_adapters: None) -> None:
    """Walk the layer type's bases to find an adapter."""

    class Special(Image): ...

    register_layer_adapter("fake", Image, lambda layer, view: Closer())
    create_layer_adapter(
        "fake",
        Special.model_validate({"name": "a", "data": np.zeros((3, 4))}),
        ViewerModel().view,
    )


def test_missing_adapter_names_backend_and_layer_type() -> None:
    """Raise an error naming the backend and the layer type."""
    with pytest.raises(LookupError, match="nothing.*Image"):
        create_layer_adapter(
            "nothing", image(name="a", data=np.zeros((3, 4))), ViewerModel().view
        )
