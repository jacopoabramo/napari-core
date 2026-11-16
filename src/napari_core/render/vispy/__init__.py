"""The vispy rendering backend. Importing it registers the image adapter."""

from napari_core.model import Image
from napari_core.render import register_layer_adapter

from ._backend import VispyBackend
from ._image import BACKEND_NAME, VispyImageAdapter

register_layer_adapter(BACKEND_NAME, Image, VispyImageAdapter)

__all__ = ["VispyBackend"]
