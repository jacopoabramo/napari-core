"""The pygfx rendering backend. Importing it registers the image adapter."""

from napari_core.model import Image
from napari_core.render import register_layer_adapter

from ._backend import PygfxBackend
from ._image import BACKEND_NAME, PygfxImageAdapter

register_layer_adapter(BACKEND_NAME, Image, PygfxImageAdapter)

__all__ = ["PygfxBackend"]
