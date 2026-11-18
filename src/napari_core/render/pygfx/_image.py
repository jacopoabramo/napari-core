"""The pygfx drawing of an image layer."""

# pyright: reportMissingTypeStubs=false

from collections.abc import Callable
from typing import Protocol, TypeGuard

import numpy as np
import pygfx as gfx

from napari_core.model import (
    Image,
    IntensityAppearance,
    Interpolation,
    Layer,
    Transform,
    View,
)
from napari_core.render import Capabilities, supported
from napari_core.typing import SliceArray

BACKEND_NAME = "pygfx"
CAPABILITIES = Capabilities(
    interpolation=frozenset(
        {Interpolation.NEAREST, Interpolation.LINEAR, Interpolation.CUBIC}
    )
)


class Material(Protocol):
    """The parts of a pygfx image material that the adapter sets.

    pygfx annotates `interpolation` with an enum class whose members are plain
    strings, which no value fits; the setter takes the strings.
    """

    map: gfx.TextureMap
    clim: tuple[float, float]
    gamma: float
    interpolation: str
    opacity: float


def is_material(material: object) -> TypeGuard[Material]:
    return isinstance(material, gfx.ImageBasicMaterial)


def texture_data(plane: SliceArray) -> SliceArray:
    """Return `plane` in a dtype a pygfx texture takes.

    Numbers of 8 bytes become `float32` and booleans `uint8`; other dtypes are
    returned as they are.
    """
    match plane.dtype.kind:
        case "b":
            return plane.astype(np.uint8)
        case "i" | "u" | "f" if plane.dtype.itemsize == 8:
            return plane.astype(np.float32)
        case _:
            return plane


class AppearanceReactions:
    """The connections that show an appearance on a material.

    Every change of the appearance calls `changed`. The signals hold these
    connections to bound methods weakly, so dropping the object is what
    disconnects them.
    """

    def __init__(
        self,
        appearance: IntensityAppearance,
        material: Material,
        warned: set[Interpolation],
        changed: Callable[[], None],
    ) -> None:
        self.appearance = appearance
        self.material = material
        self.warned = warned
        self.changed = changed
        appearance.events.colormap.connect(self.show_colormap)
        appearance.events.contrast_limits.connect(self.show_contrast_limits)
        appearance.events.gamma.connect(self.show_gamma)
        appearance.events.interpolation.connect(self.show_interpolation)
        appearance.events.all.connect(self.on_change)

    def on_change(self) -> None:
        self.changed()

    def show_colormap(self) -> None:
        self.material.map = self.appearance.colormap.to_pygfx()

    def show_contrast_limits(self) -> None:
        self.material.clim = self.appearance.contrast_limits

    def show_gamma(self) -> None:
        self.material.gamma = self.appearance.gamma

    def show_interpolation(self) -> None:
        self.material.interpolation = supported(
            self.appearance.interpolation,
            CAPABILITIES.interpolation,
            Interpolation.NEAREST,
            self.warned,
            "interpolation",
            BACKEND_NAME,
        ).value

    def show_all(self) -> None:
        self.show_colormap()
        self.show_contrast_limits()
        self.show_gamma()
        self.show_interpolation()


class TransformReactions:
    """The connections that place a visual by a transform.

    Pygfx centres pixel `j` on `j`, so the translation needs no offset. Every
    change of the transform calls `changed`. The signals hold these
    connections to bound methods weakly, so dropping the object is what
    disconnects them.
    """

    def __init__(
        self, transform: Transform, visual: gfx.Image, changed: Callable[[], None]
    ) -> None:
        self.transform = transform
        self.visual = visual
        self.changed = changed
        transform.events.scale.connect(self.show_transform)
        transform.events.translate.connect(self.show_transform)
        transform.events.all.connect(self.on_change)

    def on_change(self) -> None:
        self.changed()

    def show_transform(self) -> None:
        scale_row, scale_column = self.transform.scale[-2:]
        translate_row, translate_column = self.transform.translate[-2:]
        self.visual.local.scale = (scale_column, scale_row, 1.0)
        self.visual.local.position = (translate_column, translate_row, 0.0)


class Reactions:
    """The connections that keep a visual in step with an image layer.

    A replaced appearance or transform is followed from then on, and the old
    one is not. Every change of the layer, its appearance or its transform,
    and every new slice of it, calls `changed`. The signals hold these
    connections to bound methods weakly, so dropping the object is what
    disconnects them.
    """

    def __init__(
        self,
        layer: Image,
        view: View,
        visual: gfx.Image,
        material: Material,
        changed: Callable[[], None],
    ) -> None:
        self.layer = layer
        self.view = view
        self.visual = visual
        self.material = material
        self.changed = changed
        self.warned: set[Interpolation] = set()
        self.appearance = AppearanceReactions(
            layer.appearance, material, self.warned, changed
        )
        self.transform = TransformReactions(layer.transform, visual, changed)
        view.slicer.sliced.connect(self.on_sliced)
        layer.events.visible.connect(self.show_visible)
        layer.events.opacity.connect(self.show_opacity)
        layer.events.appearance.connect(self.follow_appearance)
        layer.events.transform.connect(self.follow_transform)
        layer.events.all.connect(self.on_change)

    def on_change(self) -> None:
        self.changed()

    def on_sliced(self, layer: Layer) -> None:
        if layer is self.layer:
            self.show_plane()
            self.changed()

    def show_plane(self) -> None:
        if (plane := self.view.slicer.response(self.layer)) is not None:
            texture = gfx.Texture(texture_data(plane), dim=2)
            self.visual.geometry = gfx.Geometry(grid=texture)

    def show_visible(self) -> None:
        self.visual.visible = self.layer.visible

    def show_opacity(self) -> None:
        self.material.opacity = self.layer.opacity

    def follow_appearance(self) -> None:
        self.appearance = AppearanceReactions(
            self.layer.appearance, self.material, self.warned, self.changed
        )
        self.appearance.show_all()

    def follow_transform(self) -> None:
        self.transform = TransformReactions(
            self.layer.transform, self.visual, self.changed
        )
        self.transform.show_transform()

    def show_all(self) -> None:
        self.show_plane()
        self.show_visible()
        self.show_opacity()
        self.appearance.show_all()
        self.transform.show_transform()


def do_nothing() -> None:
    pass


class PygfxImageAdapter:
    """Draws an [`Image`][napari_core.model.Image] layer with a pygfx image.

    The visual is created without a parent: the surface that owns the adapter
    adds it to its scene. The adapter calls `on_change` after every change it
    shows, so that the surface can ask for a draw; it does nothing until the
    surface sets it.
    """

    def __init__(self, layer: Image, view: View) -> None:
        material = gfx.ImageBasicMaterial()
        self.visual = gfx.Image(None, material)
        if not is_material(material):
            raise TypeError("pygfx made no image material")
        self.on_change: Callable[[], None] = do_nothing
        self._reactions: Reactions | None = Reactions(
            layer, view, self.visual, material, self.notify
        )
        self._reactions.show_all()

    def notify(self) -> None:
        """Call `on_change`."""
        self.on_change()

    def close(self) -> None:
        """Stop following the layer and take the visual out of its scene."""
        self._reactions = None
        if (parent := self.visual.parent) is not None:
            parent.remove(self.visual)
