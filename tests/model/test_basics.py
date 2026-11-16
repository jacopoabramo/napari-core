import numpy as np
import pytest

from napari_core.model import COLORMAPS, Camera, Colormap, Dims, IntensityAppearance


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
