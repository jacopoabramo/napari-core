"""The pygfx drawing of an image layer."""

# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pygfx annotates `interpolation` with an enum class whose members are plain
# strings, so no value can be typed to fit it; the setter takes the strings.
# pyright: reportAttributeAccessIssue=false
# pyrefly: ignore-errors[bad-argument-type]

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

BACKEND_NAME = "pygfx"
CAPABILITIES = Capabilities(
    interpolation=frozenset(
        {Interpolation.NEAREST, Interpolation.LINEAR, Interpolation.CUBIC}
    )
)


class AppearanceReactions:
    """The connections that show an appearance on a material.

    The signals hold these connections to bound methods weakly, so dropping
    the object is what disconnects them.
    """

    def __init__(
        self,
        appearance: IntensityAppearance,
        material: gfx.ImageBasicMaterial,
        warned: set[Interpolation],
    ) -> None:
        self.appearance = appearance
        self.material = material
        self.warned = warned
        appearance.events.colormap.connect(self.show_colormap)
        appearance.events.contrast_limits.connect(self.show_contrast_limits)
        appearance.events.gamma.connect(self.show_gamma)
        appearance.events.interpolation.connect(self.show_interpolation)

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

    Pygfx centres pixel `j` on `j`, so the translation needs no offset. The
    signals hold these connections to bound methods weakly, so dropping the
    object is what disconnects them.
    """

    def __init__(self, transform: Transform, visual: gfx.Image) -> None:
        self.transform = transform
        self.visual = visual
        transform.events.scale.connect(self.show_transform)
        transform.events.translate.connect(self.show_transform)

    def show_transform(self) -> None:
        scale_row, scale_column = self.transform.scale[-2:]
        translate_row, translate_column = self.transform.translate[-2:]
        self.visual.local.scale = (scale_column, scale_row, 1.0)
        self.visual.local.position = (translate_column, translate_row, 0.0)


class Reactions:
    """The connections that keep a visual in step with an image layer.

    A replaced appearance or transform is followed from then on, and the old
    one is not. The signals hold these connections to bound methods weakly,
    so dropping the object is what disconnects them.
    """

    def __init__(
        self,
        layer: Image,
        view: View,
        visual: gfx.Image,
        material: gfx.ImageBasicMaterial,
        warned: set[Interpolation],
    ) -> None:
        self.layer = layer
        self.view = view
        self.visual = visual
        self.material = material
        self.warned = warned
        self.appearance = AppearanceReactions(layer.appearance, material, warned)
        self.transform = TransformReactions(layer.transform, visual)
        view.slicer.sliced.connect(self.on_sliced)
        layer.events.visible.connect(self.show_visible)
        layer.events.opacity.connect(self.show_opacity)
        layer.events.appearance.connect(self.follow_appearance)
        layer.events.transform.connect(self.follow_transform)

    def on_sliced(self, layer: Layer) -> None:
        if layer is self.layer:
            self.show_plane()

    def show_plane(self) -> None:
        if (plane := self.view.slicer.response(self.layer)) is not None:
            self.visual.geometry = gfx.Geometry(grid=gfx.Texture(plane, dim=2))

    def show_visible(self) -> None:
        self.visual.visible = self.layer.visible

    def show_opacity(self) -> None:
        self.material.opacity = self.layer.opacity

    def follow_appearance(self) -> None:
        self.appearance = AppearanceReactions(
            self.layer.appearance, self.material, self.warned
        )
        self.appearance.show_all()

    def follow_transform(self) -> None:
        self.transform = TransformReactions(self.layer.transform, self.visual)
        self.transform.show_transform()

    def show_all(self) -> None:
        self.show_plane()
        self.show_visible()
        self.show_opacity()
        self.appearance.show_all()
        self.transform.show_transform()


class PygfxImageAdapter:
    """Draws an [`Image`][napari_core.model.Image] layer with a pygfx image.

    The visual is created without a parent: the surface that owns the adapter
    adds it to its scene.
    """

    def __init__(self, layer: Image, view: View) -> None:
        material = gfx.ImageBasicMaterial()
        self.visual = gfx.Image(None, material)
        self._reactions: Reactions | None = Reactions(
            layer, view, self.visual, material, set()
        )
        self._reactions.show_all()

    def close(self) -> None:
        """Stop following the layer and take the visual out of its scene."""
        self._reactions = None
        if (parent := self.visual.parent) is not None:
            parent.remove(self.visual)
