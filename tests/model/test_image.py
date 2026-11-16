import numpy as np
import pytest

from napari_core.model import COLORMAPS, Dims, Image, Transform


def stack():
    """Return a small 3D array."""
    return np.arange(2 * 3 * 4, dtype=np.uint8).reshape(2, 3, 4)


def test_image_fills_in_transform_and_appearance():
    """Give a new image an identity transform, gray colormap and data limits."""
    layer = Image(name="a", data=stack())
    assert layer.scale == (1.0, 1.0, 1.0)
    assert layer.translate == (0.0, 0.0, 0.0)
    assert layer.colormap.name == "gray"
    assert layer.contrast_limits == (0.0, 23.0)


def test_shortcuts_write_through_to_components():
    """Emit the component's signal when a shortcut property is set."""
    layer = Image(name="a", data=stack())
    seen = []
    layer.appearance.events.gamma.connect(seen.append)
    layer.gamma = 0.5
    assert seen == [0.5]
    assert layer.appearance.gamma == 0.5

    changes = {
        "colormap": (COLORMAPS["red"], layer.appearance.events.colormap),
        "contrast_limits": ((1.0, 5.0), layer.appearance.events.contrast_limits),
        "scale": ((2.0, 2.0, 2.0), layer.transform.events.scale),
        "translate": ((1.0, 0.0, 0.0), layer.transform.events.translate),
    }
    for name, (value, signal) in changes.items():
        emitted = []
        signal.connect(emitted.append)
        setattr(layer, name, value)
        assert len(emitted) == 1, name
    assert layer.appearance.colormap.name == "red"
    assert layer.transform.scale == (2.0, 2.0, 2.0)


def test_invalid_data_is_refused_on_assignment():
    """Raise the validation error of as_layer_data when data is assigned."""
    layer = Image(name="a", data=stack())
    with pytest.raises(TypeError, match="dtype"):
        layer.data = [1, 2, 3]


def test_assigning_equal_but_distinct_data_emits():
    """Compare data by identity, so a new array always emits."""
    layer = Image(name="a", data=stack())
    seen = []
    layer.events.data.connect(seen.append)
    layer.data = stack()
    assert len(seen) == 1
    layer.data = layer.data
    assert len(seen) == 1


@pytest.mark.parametrize(
    ("step", "expected"),
    [((0, 0, 0), 0), ((1, 0, 0), 1), ((7, 0, 0), 1)],
)
def test_slice_follows_the_step_and_stops_at_the_last_plane(step, expected):
    """Slice the plane of the step, or the last plane when the step is past it."""
    layer = Image(name="a", data=stack())
    dims = Dims(ndim=3, nsteps=(8, 3, 4), current_step=step)
    np.testing.assert_array_equal(layer.slice(dims), stack()[expected])


def test_layer_with_fewer_axes_aligns_to_the_last_axes():
    """Ignore the leading axes of the view that a 2D image does not have."""
    plane = np.ones((3, 4), dtype=np.uint8)
    layer = Image(name="a", data=plane)
    dims = Dims(ndim=3, nsteps=(8, 3, 4), current_step=(5, 0, 0))
    assert layer.slice_key(dims) == (slice(None), slice(None))
    np.testing.assert_array_equal(layer.slice(dims), plane)


def test_constant_image_gets_distinct_contrast_limits():
    """Give an image of one value limits that differ."""
    layer = Image(name="a", data=np.full((3, 4), 7, dtype=np.uint8))
    low, high = layer.contrast_limits
    assert low == 7.0
    assert high > low


def test_callbacks_are_kept_per_layer():
    """Keep each layer's callback list separate."""
    first, second = Image(name="a", data=stack()), Image(name="b", data=stack())
    first.mouse_drag_callbacks.append(lambda layer, event: None)
    assert len(first.mouse_drag_callbacks) == 1
    assert second.mouse_drag_callbacks == []


def test_transform_with_the_wrong_length_is_refused():
    """Name both lengths when a transform does not match the data's axes."""
    transform = Transform(scale=(1.0, 1.0), translate=(0.0, 0.0, 0.0))
    with pytest.raises(ValueError, match="2.*3"):
        Image(name="a", data=stack(), transform=transform)
