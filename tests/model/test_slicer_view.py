import weakref

import numpy as np
import pytest
from helpers import assign, image

from napari_core.model import Camera, Layer, View, ViewerModel
from napari_core.typing import SliceArray


def response(viewer: ViewerModel, layer: Layer) -> SliceArray:
    """Return the slice the viewer's slicer holds for `layer`."""
    plane = viewer.view.slicer.response(layer)
    assert plane is not None
    return plane


def test_camera_cannot_be_replaced() -> None:
    """Refuse a new camera and keep the old one, which still takes field changes."""
    view = View()
    camera = view.camera
    with pytest.raises(ValueError, match="frozen"):
        assign(view, "camera", Camera(center=(1e4, 1e4)))
    assert view.camera is camera
    view.camera.zoom = 3.0
    assert camera.zoom == 3.0


def test_adding_a_layer_sizes_the_dims_and_slices_it() -> None:
    """Fit dims to the layers and slice a layer when it is added."""
    viewer = ViewerModel()
    layer = image(name="a", data=np.zeros((5, 3, 4)))
    viewer.layers.append(layer)
    assert viewer.dims.ndim == 3
    assert viewer.dims.nsteps == (5, 3, 4)
    assert response(viewer, layer).shape == (3, 4)


def test_changing_the_step_slices_again_and_emits_the_layer() -> None:
    """Emit sliced with the layer when the current step changes."""
    viewer = ViewerModel()
    data = np.arange(60).reshape(5, 3, 4)
    layer = image(name="a", data=data)
    viewer.layers.append(layer)
    seen: list[Layer] = []
    viewer.view.slicer.sliced.connect(seen.append)
    viewer.dims.current_step = (2, 0, 0)
    assert seen == [layer]
    np.testing.assert_array_equal(response(viewer, layer), data[2])


def test_assigning_data_slices_again() -> None:
    """Slice a layer again when its data is replaced."""
    viewer = ViewerModel()
    layer = image(name="a", data=np.zeros((5, 3, 4)))
    viewer.layers.append(layer)
    layer.data = np.ones((5, 3, 4))
    assert response(viewer, layer).max() == 1


def test_removed_layer_is_forgotten() -> None:
    """Drop the slice of a removed layer and stop following it."""
    viewer = ViewerModel()
    layer = image(name="a", data=np.zeros((5, 3, 4)))
    viewer.layers.append(layer)
    viewer.layers.remove(layer)
    seen: list[Layer] = []
    viewer.view.slicer.sliced.connect(seen.append)
    layer.data = np.ones((5, 3, 4))
    assert viewer.view.slicer.response(layer) is None
    assert seen == []
    assert viewer.dims.nsteps == (1, 1)


def test_one_layer_in_two_views_has_a_slice_in_each() -> None:
    """Keep a separate slice of the same layer for each view."""
    data = np.arange(60).reshape(5, 3, 4)
    layer = image(name="a", data=data)
    first, second = ViewerModel(), ViewerModel()
    first.layers.append(layer)
    second.layers.append(layer)
    second.dims.current_step = (4, 0, 0)
    np.testing.assert_array_equal(response(first, layer), data[0])
    np.testing.assert_array_equal(response(second, layer), data[4])


def test_every_way_of_changing_the_list_keeps_the_slices_in_step() -> None:
    """Track the layers through insert, pop, slice assignment, del and clear."""
    viewer = ViewerModel()
    slicer = viewer.view.slicer
    big = image(name="big", data=np.zeros((5, 3, 4)))
    flat = image(name="flat", data=np.zeros((6, 7)))
    other = image(name="other", data=np.zeros((2, 3, 4)))

    viewer.layers.insert(0, big)
    viewer.layers.extend([flat, other])
    assert viewer.dims.nsteps == (5, 6, 7)
    assert response(viewer, flat).shape == (6, 7)

    assert viewer.layers.pop() is other
    assert slicer.response(other) is None

    viewer.layers[0:2] = [other]
    assert slicer.response(big) is slicer.response(flat) is None
    assert response(viewer, other).shape == (3, 4)
    assert viewer.dims.nsteps == (2, 3, 4)

    viewer.layers[0] = big
    assert slicer.response(other) is None
    assert response(viewer, big).shape == (3, 4)

    viewer.layers.append(big)
    del viewer.layers[0]
    assert slicer.response(big) is not None
    assert len(big.events.data) == 1

    viewer.layers.clear()
    assert slicer.response(big) is None
    assert len(big.events.data) == 0
    assert viewer.dims.ndim == 2


def test_view_is_freed_with_its_layer_still_alive() -> None:
    """Free the view without the cycle collector and leave no connection behind."""
    layer = image(name="a", data=np.zeros((5, 3, 4)))
    viewer = ViewerModel()
    viewer.layers.append(layer)
    kept = weakref.ref(viewer.view.slicer)
    del viewer
    assert kept() is None
    assert len(layer.events.data) == 0
    layer.data = np.ones((5, 3, 4))


def test_replacing_data_with_another_shape_refits_the_dims() -> None:
    """Refit nsteps when data changes shape, then slice with the new dims."""
    viewer = ViewerModel()
    layer = image(name="a", data=np.zeros((5, 3, 4)))
    viewer.layers.append(layer)
    longer = np.arange(108).reshape(9, 3, 4)
    layer.data = longer
    assert viewer.dims.nsteps == (9, 3, 4)
    viewer.dims.current_step = (8, 0, 0)
    np.testing.assert_array_equal(response(viewer, layer), longer[8])

    shorter = np.arange(24).reshape(2, 3, 4)
    layer.data = shorter
    assert viewer.dims.current_step == (1, 0, 0)
    np.testing.assert_array_equal(response(viewer, layer), shorter[1])


@pytest.mark.filterwarnings("error")
def test_list_given_to_the_view_behaves_like_the_default_one() -> None:
    """Slice and fit for layers passed on construction, without warnings."""
    layer = image(name="a", data=np.zeros((5, 3, 4)))
    view = View.model_validate({"layers": [layer]})
    assert view.dims.nsteps == (5, 3, 4)
    assert view.slicer.response(layer) is not None
    assert len(layer.events.data) == 1
    view.layers.append(image(name="b", data=np.zeros((2, 3, 4))))
    assert len(layer.events.data) == 1


def test_listeners_of_sliced_see_the_fitted_dims() -> None:
    """Fit the dims before any layer is sliced again."""
    viewer = ViewerModel()
    viewer.layers.append(image(name="flat", data=np.zeros((6, 7))))
    seen: set[tuple[int, ...]] = set()

    def record(layer: Layer) -> None:
        seen.add(viewer.dims.nsteps)

    viewer.view.slicer.sliced.connect(record)
    viewer.layers.append(image(name="big", data=np.zeros((5, 3, 4))))
    assert seen == {(5, 6, 7)}
