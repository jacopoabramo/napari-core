from typing import Annotated, ClassVar

import numpy as np
import numpy.typing as npt
import pytest
from cmap import Colormap
from helpers import assign
from psygnal import SignalInstance

from napari_core.model import (
    Dims,
    Image,
    IntensityAppearance,
    Interpolation,
    Layer,
    Transform,
)
from napari_core.typing import LayerDataProtocol, SliceArray


def stack() -> npt.NDArray[np.uint8]:
    """Return a small 3D array."""
    return np.arange(2 * 3 * 4, dtype=np.uint8).reshape(2, 3, 4)


def test_image_fills_in_transform_and_appearance() -> None:
    """Give a new image an identity transform, gray colormap and data limits."""
    layer = Image(name="a", data=stack())
    assert layer.scale == (1.0, 1.0, 1.0)
    assert layer.translate == (0.0, 0.0, 0.0)
    assert layer.colormap == Colormap("gray")
    assert layer.contrast_limits == (0.0, 23.0)


def test_shortcuts_write_through_to_components() -> None:
    """Emit the component's signal when a shortcut property is set."""
    layer = Image(name="a", data=stack())
    seen: list[float] = []
    layer.appearance.events.gamma.connect(seen.append)
    layer.gamma = 0.5
    assert seen == [0.5]
    assert layer.appearance.gamma == 0.5

    layer.colormap = "blue"
    assert layer.colormap == Colormap("blue")

    changes: dict[str, tuple[object, SignalInstance]] = {
        "colormap": (Colormap("red"), layer.appearance.events.colormap),
        "contrast_limits": ((1.0, 5.0), layer.appearance.events.contrast_limits),
        "scale": ((2.0, 2.0, 2.0), layer.transform.events.scale),
        "translate": ((1.0, 0.0, 0.0), layer.transform.events.translate),
    }
    for name, (value, signal) in changes.items():
        emitted: list[object] = []
        signal.connect(emitted.append)
        setattr(layer, name, value)
        assert len(emitted) == 1, name
    assert layer.appearance.colormap == Colormap("red")
    assert layer.transform.scale == (2.0, 2.0, 2.0)


def test_unknown_colormap_name_is_refused() -> None:
    """Refuse a name that is not in the catalogue and keep the old colormap."""
    layer = Image(name="a", data=np.zeros((2, 2)))
    before = layer.colormap
    with pytest.raises(ValueError, match="not found"):
        layer.colormap = "no_such_colormap"
    assert layer.colormap == before


def test_invalid_data_is_refused_on_assignment() -> None:
    """Raise the validation error of as_layer_data when data is assigned."""
    layer = Image(name="a", data=stack())
    with pytest.raises(TypeError, match="dtype"):
        assign(layer, "data", [1, 2, 3])


def test_assigning_equal_but_distinct_data_emits() -> None:
    """Compare data by identity, so a new array always emits."""
    layer = Image(name="a", data=stack())
    seen: list[LayerDataProtocol] = []
    layer.events.data.connect(seen.append)
    layer.data = stack()
    assert len(seen) == 1


def test_assigning_the_same_data_does_not_emit() -> None:
    """Stay silent when the very same array is assigned again."""
    layer = Image(name="a", data=stack())
    seen: list[LayerDataProtocol] = []
    layer.events.data.connect(seen.append)
    layer.data = layer.data
    assert seen == []


@pytest.mark.parametrize(
    ("step", "expected"),
    [((0, 0, 0), 0), ((1, 0, 0), 1), ((7, 0, 0), 1)],
)
def test_slice_follows_the_step_and_stops_at_the_last_plane(
    step: tuple[int, ...], expected: int
) -> None:
    """Slice the plane of the step, or the last plane when the step is past it."""
    layer = Image(name="a", data=stack())
    dims = Dims(ndim=3, nsteps=(8, 3, 4), current_step=step)
    np.testing.assert_array_equal(layer.slice(dims), stack()[expected])


def test_layer_with_fewer_axes_aligns_to_the_last_axes() -> None:
    """Ignore the leading axes of the view that a 2D image does not have."""
    plane = np.ones((3, 4), dtype=np.uint8)
    layer = Image(name="a", data=plane)
    dims = Dims(ndim=3, nsteps=(8, 3, 4), current_step=(5, 0, 0))
    assert layer.slice_key(dims) == (slice(None), slice(None))
    np.testing.assert_array_equal(layer.slice(dims), plane)


def test_constant_image_gets_distinct_contrast_limits() -> None:
    """Give an image of one value limits that differ."""
    layer = Image(name="a", data=np.full((3, 4), 7, dtype=np.uint8))
    low, high = layer.contrast_limits
    assert low == 7.0
    assert high > low


def test_callbacks_are_kept_per_layer() -> None:
    """Keep each layer's callback list separate."""
    first, second = Image(name="a", data=stack()), Image(name="b", data=stack())
    first.mouse_drag_callbacks.append(lambda layer, event: None)
    assert len(first.mouse_drag_callbacks) == 1
    assert second.mouse_drag_callbacks == []


def test_transform_with_the_wrong_length_is_refused() -> None:
    """Name both lengths when a transform does not match the data's axes."""
    transform = Transform(scale=(1.0, 1.0), translate=(0.0, 0.0))
    with pytest.raises(ValueError, match="3 axes.*2 scale and 2 translate"):
        Image(name="a", data=stack(), transform=transform)


def test_refused_data_assignment_leaves_the_image_unchanged() -> None:
    """Refuse data of another ndim, keep the old data and emit nothing."""
    data = stack()
    layer = Image(name="a", data=data)
    seen: list[LayerDataProtocol] = []
    layer.events.data.connect(seen.append)
    with pytest.raises(ValueError, match="2 axes.*3 scale"):
        layer.data = np.zeros((3, 4))
    assert layer.data is data
    assert len(layer.scale) == 3
    assert seen == []
    layer.data = stack()
    assert len(seen) == 1


def test_refused_transform_assignment_leaves_the_image_unchanged() -> None:
    """Refuse a transform of the wrong length and keep the old one."""
    layer = Image(name="a", data=stack())
    old = layer.transform
    seen: list[Transform] = []
    layer.events.transform.connect(seen.append)
    with pytest.raises(ValueError, match="3 axes.*2 scale"):
        layer.transform = Transform(scale=(1.0, 1.0), translate=(0.0, 0.0))
    assert layer.transform is old
    assert seen == []
    layer.transform = Transform(scale=(2.0,) * 3, translate=(0.0,) * 3)
    assert len(seen) == 1


@pytest.mark.parametrize("data", [np.zeros(()), np.zeros(3)])
def test_image_with_fewer_than_two_axes_is_refused(
    data: npt.NDArray[np.float64],
) -> None:
    """Refuse data of 0 or 1 axes on construction, naming the number found."""
    with pytest.raises(ValueError, match=f"at least 2 axes, data has {data.ndim}"):
        Image(name="a", data=data)


def test_assigning_data_with_one_axis_is_refused() -> None:
    """Refuse 1-D data on assignment, keep the old data and emit nothing."""
    data = np.zeros((3, 4))
    layer = Image(name="a", data=data)
    seen: list[LayerDataProtocol] = []
    layer.events.data.connect(seen.append)
    with pytest.raises(ValueError, match="at least 2 axes, data has 1"):
        layer.data = np.zeros(3)
    assert layer.data is data
    assert seen == []


def test_gamma_shortcut_refuses_a_value_that_is_not_positive() -> None:
    """Refuse a gamma of zero or less through the shortcut and keep the old one."""
    layer = Image(name="a", data=stack())
    with pytest.raises(ValueError, match="gamma"):
        layer.gamma = -1.0
    assert layer.gamma == 1.0


@pytest.mark.parametrize("opacity", [-0.1, 1.1])
def test_opacity_outside_zero_to_one_is_refused(opacity: float) -> None:
    """Refuse an opacity outside 0 to 1, on construction and on assignment."""
    with pytest.raises(ValueError, match="opacity"):
        Image(name="a", data=stack(), opacity=opacity)
    layer = Image(name="a", data=stack(), opacity=0.5)
    with pytest.raises(ValueError, match="opacity"):
        layer.opacity = opacity
    assert layer.opacity == 0.5
    layer.opacity = 0.0
    layer.opacity = 1.0


@pytest.mark.parametrize("name", ["scale", "translate"])
def test_shortcut_refuses_a_length_other_than_the_number_of_axes(name: str) -> None:
    """Name both numbers, store nothing and emit nothing for a wrong length."""
    layer = Image(name="a", data=stack())
    before = layer.transform.model_copy()
    seen: list[object] = []
    layer.transform.events.connect(seen.append)
    with pytest.raises(ValueError, match="3 axes.*1 entries"):
        setattr(layer, name, (2.0,))
    assert layer.transform == before
    assert seen == []


def test_slice_key_refuses_dims_with_fewer_axes() -> None:
    """Raise when the layer has more axes than the dims."""
    layer = Image(name="a", data=stack())
    with pytest.raises(ValueError, match="3.*2"):
        layer.slice_key(Dims(ndim=2))


def test_contrast_limits_come_from_the_finite_values() -> None:
    """Ignore NaN when taking the limits."""
    data = np.array([[np.nan, 2.0], [5.0, np.inf]])
    assert Image(name="a", data=data).contrast_limits == (2.0, 5.0)


@pytest.mark.parametrize("data", [np.full((2, 2), np.nan), np.zeros((0, 3))])
def test_contrast_limits_fall_back_without_finite_values(
    data: npt.NDArray[np.float64],
) -> None:
    """Use (0, 1) for all-NaN or empty data, without a numpy warning."""
    assert Image(name="a", data=data).contrast_limits == (0.0, 1.0)


def test_lazy_data_takes_limits_from_the_middle_plane_only(
    dask_four_axes: LayerDataProtocol,
) -> None:
    """Read only the middle plane of dask data for the contrast limits."""
    assert Image(name="a", data=dask_four_axes).contrast_limits == (80.0, 99.0)


def test_equal_but_distinct_components_replace_the_old_ones() -> None:
    """Emit for an equal component object that is a different object, not the same."""
    layer = Image(name="a", data=stack())
    appearance, transform = layer.appearance, layer.transform
    seen_appearance: list[IntensityAppearance] = []
    seen_transform: list[Transform] = []
    layer.events.appearance.connect(seen_appearance.append)
    layer.events.transform.connect(seen_transform.append)
    layer.appearance = appearance
    layer.transform = transform
    assert seen_appearance == [] and seen_transform == []
    new_appearance = appearance.model_copy()
    new_transform = transform.model_copy()
    assert new_appearance == appearance and new_transform == transform
    layer.appearance = new_appearance
    layer.transform = new_transform
    assert seen_appearance == [new_appearance]
    assert seen_transform == [new_transform]
    assert layer.appearance is new_appearance and layer.transform is new_transform


def test_shortcut_setters_write_through_to_the_existing_components() -> None:
    """Keep the component objects when a shortcut property is set."""
    layer = Image(name="a", data=stack())
    appearance, transform = layer.appearance, layer.transform
    layer.colormap = "red"
    layer.contrast_limits = (1.0, 5.0)
    layer.gamma = 0.5
    layer.scale = (2.0,) * 3
    layer.translate = (1.0,) * 3
    assert layer.appearance is appearance and layer.transform is transform
    assert appearance.gamma == 0.5 and transform.scale == (2.0,) * 3


class Token:
    """A value that is equal to every other token."""

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Token)

    def __hash__(self) -> int:
        return 0


class Special(Image):
    """An image type that adds nothing."""


class Tagged(Image):
    """An image type with a field that is replaced by object."""

    compared_by_identity: ClassVar[tuple[str, ...]] = ("token",)

    token: Token = Token()


class WithOptional(Image):
    """An image type with an optional component."""

    extra: Transform | None = None


class WithAnnotatedOptional(Image):
    """An image type with an optional component wrapped in `Annotated`."""

    extra: Annotated[Transform, "note"] | None = None


class WithList(Image):
    """An image type with a list of components."""

    extras: list[Transform] = []


class Plain(Layer):
    """A layer type that is not an image, with a component of its own."""

    data: int = 0
    extra: Transform

    @property
    def ndim(self) -> int:
        return 2

    @property
    def extent_steps(self) -> tuple[int, ...]:
        return (2, 2)

    def slice(self, dims: Dims) -> SliceArray:
        return np.zeros((2, 2), dtype=np.uint8)


def moving(transform: Transform) -> Transform:
    """Return an equal transform that is another object."""
    return transform.model_copy()


def test_image_subclass_replaces_equal_components_by_object() -> None:
    """Emit once for an equal but distinct component and not for the same one."""
    layer = Special(name="a", data=stack())
    seen: list[IntensityAppearance | Transform] = []
    layer.events.appearance.connect(seen.append)
    layer.events.transform.connect(seen.append)
    layer.appearance, layer.transform = layer.appearance, layer.transform
    assert seen == []
    layer.appearance = layer.appearance.model_copy()
    layer.transform = layer.transform.model_copy()
    assert len(seen) == 2


def test_layer_that_is_not_an_image_replaces_equal_components_by_object() -> None:
    """Compare every component of a new layer type, including its own, by object."""
    transform = Transform(scale=(1.0, 1.0), translate=(0.0, 0.0))
    layer = Plain(name="p", transform=transform, extra=transform.model_copy())
    seen: list[Transform] = []
    layer.events.transform.connect(seen.append)
    layer.events.extra.connect(seen.append)
    layer.transform, layer.extra = layer.transform, layer.extra
    assert seen == []
    new_transform, new_extra = moving(layer.transform), moving(layer.extra)
    layer.transform = new_transform
    layer.extra = new_extra
    assert seen == [new_transform, new_extra]


def test_subclass_adds_identity_fields_and_keeps_those_of_its_parent() -> None:
    """Replace a named field by object, and the data and components as well."""
    layer = Tagged(name="a", data=stack())
    seen: list[object] = []
    layer.events.token.connect(seen.append)
    layer.events.data.connect(seen.append)
    layer.events.appearance.connect(seen.append)
    layer.token = layer.token
    layer.data = layer.data
    layer.appearance = layer.appearance
    assert seen == []
    token = Token()
    layer.token = token
    layer.data = stack()
    layer.appearance = layer.appearance.model_copy()
    assert len(seen) == 3 and seen[0] is token


@pytest.mark.parametrize("kind", [WithOptional, WithAnnotatedOptional])
def test_optional_component_is_replaced_by_object(
    kind: type[WithOptional] | type[WithAnnotatedOptional],
) -> None:
    """Emit for each new optional component or `None`, and not for the same object."""
    layer = kind(name="a", data=stack())
    seen: list[Transform | None] = []
    layer.events.extra.connect(seen.append)
    first = layer.transform.model_copy()
    second = moving(first)
    for value in (None, first, first, second, None, first):
        layer.extra = value
    assert [id(value) for value in seen] == [id(first), id(second), id(None), id(first)]


def test_list_of_components_is_compared_by_contents() -> None:
    """Emit nothing when an equal list of other component objects is assigned."""
    layer = WithList(name="a", data=stack())
    transform = layer.transform.model_copy()
    seen: list[list[Transform]] = []
    layer.events.extras.connect(seen.append)
    layer.extras = [transform]
    layer.extras = [moving(transform)]
    assert len(seen) == 1


def test_identity_name_that_is_not_a_field_is_refused() -> None:
    """Refuse a class whose `compared_by_identity` names a field it does not have."""
    with pytest.raises(TypeError, match="Misspelled.*'dta'"):
        type("Misspelled", (Image,), {"compared_by_identity": ("dta",)})


def test_interpolation_defaults_to_nearest_and_emits_the_stored_value() -> None:
    """Start at nearest and emit the enum member when a name is assigned."""
    layer = Image(name="a", data=stack())
    seen: list[Interpolation] = []
    layer.appearance.events.interpolation.connect(seen.append)
    assert layer.interpolation is Interpolation.NEAREST
    layer.interpolation = "linear"
    assert layer.interpolation is Interpolation.LINEAR
    assert seen == [Interpolation.LINEAR]


def test_unknown_interpolation_is_refused() -> None:
    """Refuse an unknown name, keep the old value and emit nothing."""
    layer = Image(name="a", data=stack())
    seen: list[Interpolation] = []
    layer.appearance.events.interpolation.connect(seen.append)
    with pytest.raises(ValueError, match="bogus"):
        layer.interpolation = "bogus"
    assert layer.interpolation is Interpolation.NEAREST
    assert seen == []
