import numpy as np
import pytest

from napari_core.model import (
    COLORMAPS,
    Camera,
    Colormap,
    Dims,
    IntensityAppearance,
    Transform,
)


def test_setting_ndim_resizes_steps():
    """Pad nsteps and current_step on the left when ndim grows."""
    dims = Dims(ndim=2, nsteps=(4, 5), current_step=(1, 2))
    dims.ndim = 3
    assert dims.nsteps == (1, 4, 5)
    assert dims.current_step == (0, 1, 2)
    assert dims.displayed == (1, 2)


def test_current_step_is_clamped_to_nsteps():
    """Clamp a step that is past the end of its axis."""
    dims = Dims(ndim=3, nsteps=(10, 4, 5), current_step=(0, 0, 0))
    dims.current_step = (99, 0, 0)
    assert dims.current_step == (9, 0, 0)


def test_current_step_emits_once_per_change():
    """Emit current_step when it changes and not when it is set to the same value."""
    dims = Dims(ndim=3, nsteps=(10, 4, 5), current_step=(0, 0, 0))
    seen = []
    dims.events.current_step.connect(seen.append)
    dims.current_step = (3, 0, 0)
    dims.current_step = (3, 0, 0)
    assert seen == [(3, 0, 0)]


def test_camera_rejects_non_positive_zoom():
    """Refuse a zoom of zero or less."""
    with pytest.raises(ValueError):
        Camera(zoom=0.0)


def test_appearance_accepts_a_colormap_name():
    """Look a colormap up by name."""
    appearance = IntensityAppearance(colormap="magenta")
    assert appearance.colormap.name == "magenta"
    np.testing.assert_allclose(appearance.colormap.colors[-1], (1, 0, 1, 1))


def test_unknown_colormap_name_is_refused():
    """Refuse a colormap name that is not built in."""
    with pytest.raises(ValueError, match="viridis"):
        IntensityAppearance(colormap="viridis")


def test_colormap_assignment_with_equal_colors_does_not_emit():
    """Compare colormap colours by value."""
    appearance = IntensityAppearance()
    seen = []
    appearance.events.colormap.connect(seen.append)
    appearance.colormap = Colormap(name="gray", colors=COLORMAPS["gray"].colors.copy())
    assert seen == []


def test_appearance_refuses_a_gamma_that_is_not_positive():
    """Refuse a gamma of zero or less on construction and on assignment."""
    with pytest.raises(ValueError, match="gamma"):
        IntensityAppearance(gamma=0.0)
    appearance = IntensityAppearance(gamma=2.0)
    with pytest.raises(ValueError, match="gamma"):
        appearance.gamma = -1.0
    assert appearance.gamma == 2.0


def test_appearance_events_carry_the_stored_values():
    """Emit the stored float and tuple for a gamma and limits given as int and list."""
    appearance = IntensityAppearance()
    seen = []
    appearance.events.gamma.connect(seen.append)
    appearance.events.contrast_limits.connect(seen.append)
    appearance.gamma = 2
    appearance.contrast_limits = [0, 5]
    assert seen == [2.0, (0.0, 5.0)]
    assert isinstance(seen[0], float) and isinstance(seen[1], tuple)


def test_transform_validates_and_emits_the_stored_tuple_on_assignment():
    """Store and emit a tuple of floats when a list of ints is assigned."""
    transform = Transform(scale=(1.0, 1.0), translate=(0.0, 0.0))
    seen = []
    transform.events.scale.connect(seen.append)
    transform.scale = [2, 3]
    assert transform.scale == (2.0, 3.0)
    assert seen == [(2.0, 3.0)]
    assert all(isinstance(value, float) for value in seen[0])


def test_transform_refuses_scale_and_translate_of_different_lengths():
    """Refuse lengths that differ, on construction and on assignment of either."""
    with pytest.raises(ValueError, match="2 scale.*1 translate"):
        Transform(scale=(1.0, 1.0), translate=(0.0,))
    transform = Transform(scale=(1.0, 1.0), translate=(0.0, 0.0))
    seen = []
    transform.events.scale.connect(seen.append)
    transform.events.translate.connect(seen.append)
    with pytest.raises(ValueError, match="1 scale.*2 translate"):
        transform.scale = (2.0,)
    with pytest.raises(ValueError, match="2 scale.*3 translate"):
        transform.translate = (1.0, 1.0, 1.0)
    assert transform == Transform(scale=(1.0, 1.0), translate=(0.0, 0.0))
    assert seen == []


def test_camera_center_event_carries_the_stored_tuple():
    """Emit the stored tuple of floats when a center is assigned as integers."""
    camera = Camera()
    seen = []
    camera.events.center.connect(seen.append)
    camera.center = (1, 2)
    assert seen == [(1.0, 2.0)]
    assert all(isinstance(value, float) for value in seen[0])
