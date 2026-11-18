"""The vispy drawing of an image layer."""

# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from typing import Protocol, cast

import numpy as np
from vispy.color import Colormap as VispyColormap
from vispy.scene.visuals import Image as ImageVisual
from vispy.visuals.transforms import STTransform

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

BACKEND_NAME = "vispy"
CAPABILITIES = Capabilities(interpolation=frozenset(Interpolation))


class Visual(Protocol):
    """The parts of a vispy image node that the adapter uses."""

    visible: bool
    opacity: float
    cmap: VispyColormap
    clim: tuple[float, float]
    gamma: float
    interpolation: str
    transform: STTransform
    parent: object | None

    def set_data(self, data: SliceArray) -> None: ...


class AppearanceReactions:
    """The connections that show an appearance on a visual.

    The signals hold these connections to bound methods weakly, so dropping
    the object is what disconnects them.
    """

    def __init__(
        self,
        appearance: IntensityAppearance,
        visual: Visual,
        warned: set[Interpolation],
    ) -> None:
        self.appearance = appearance
        self.visual = visual
        self.warned = warned
        appearance.events.colormap.connect(self.show_colormap)
        appearance.events.contrast_limits.connect(self.show_contrast_limits)
        appearance.events.gamma.connect(self.show_gamma)
        appearance.events.interpolation.connect(self.show_interpolation)

    def show_colormap(self) -> None:
        self.visual.cmap = self.appearance.colormap.to_vispy()

    def show_contrast_limits(self) -> None:
        self.visual.clim = self.appearance.contrast_limits

    def show_gamma(self) -> None:
        self.visual.gamma = self.appearance.gamma

    def show_interpolation(self) -> None:
        self.visual.interpolation = supported(
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

    The signals hold these connections to bound methods weakly, so dropping
    the object is what disconnects them.
    """

    def __init__(self, transform: Transform, visual: Visual) -> None:
        self.transform = transform
        self.visual = visual
        transform.events.scale.connect(self.show_transform)
        transform.events.translate.connect(self.show_transform)

    def show_transform(self) -> None:
        """Scale and place the displayed axes, with pixel centres on integers.

        Vispy puts pixel `j` between `j` and `j + 1`, so the translation moves
        the image back by half a scaled pixel.
        """
        scale_row, scale_column = self.transform.scale[-2:]
        translate_row, translate_column = self.transform.translate[-2:]
        self.visual.transform = STTransform(
            scale=(scale_column, scale_row),
            translate=(
                translate_column - scale_column / 2,
                translate_row - scale_row / 2,
            ),
        )


class Reactions:
    """The connections that keep a visual in step with an image layer.

    A replaced appearance or transform is followed from then on, and the old
    one is not. The signals hold these connections to bound methods weakly,
    so dropping the object is what disconnects them.
    """

    def __init__(
        self, layer: Image, view: View, visual: Visual, warned: set[Interpolation]
    ) -> None:
        self.layer = layer
        self.view = view
        self.visual = visual
        self.warned = warned
        self.appearance = AppearanceReactions(layer.appearance, visual, warned)
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
            # vispy finds no value limits for booleans when it builds the texture.
            if plane.dtype == np.bool_:
                plane = plane.astype(np.uint8)
            self.visual.set_data(plane)

    def show_visible(self) -> None:
        self.visual.visible = self.layer.visible

    def show_opacity(self) -> None:
        self.visual.opacity = self.layer.opacity

    def follow_appearance(self) -> None:
        self.appearance = AppearanceReactions(
            self.layer.appearance, self.visual, self.warned
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


class VispyImageAdapter:
    """Draws an [`Image`][napari_core.model.Image] layer with a vispy visual.

    The visual is created without a parent: the surface that owns the adapter
    attaches it to its scene.
    """

    def __init__(self, layer: Image, view: View) -> None:
        # The checkers see only the visual part of the node, not its scene part.
        self.visual = cast(Visual, ImageVisual(interpolation="nearest"))
        self._reactions: Reactions | None = Reactions(layer, view, self.visual, set())
        self._reactions.show_all()

    def close(self) -> None:
        """Stop following the layer and take the visual out of its scene."""
        self._reactions = None
        self.visual.parent = None
