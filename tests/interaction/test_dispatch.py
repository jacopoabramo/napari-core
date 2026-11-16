import numpy as np
from helpers import pointer, view_with_image, wheel

from napari_core.interaction import attach, surface_to_world
from napari_core.model import Image, Modifier


def test_layer_callback_receives_napari_events_with_world_position(surface):
    """Hand the top layer a ButtonEvent of type mouse_press with a world position."""
    v, layer, seen = view_with_image()
    layer.mouse_drag_callbacks.append(lambda lyr, event: seen.append(event))
    attach(v, surface)
    surface.emit(pointer("pointer_down", 110, 40, button=1, modifiers=("Shift",)))
    (event,) = seen
    assert event.type == "mouse_press"
    assert event.position == surface_to_world(v, 110, 40)
    assert event.modifiers == frozenset({Modifier.SHIFT})
    assert event.button == 1


def test_generator_callback_runs_across_press_move_release(surface):
    """Resume a generator callback on each move and finish it on release."""
    v, layer, seen = view_with_image()

    def drag(lyr, event):
        seen.append(event.type)
        yield
        while event.type == "mouse_move":
            seen.append(event.type)
            yield
        seen.append(event.type)

    layer.mouse_drag_callbacks.append(drag)
    attach(v, surface)
    for kind in ("pointer_down", "pointer_move", "pointer_move", "pointer_up"):
        surface.emit(pointer(kind, 100, 50, button=1))
    assert seen == ["mouse_press", "mouse_move", "mouse_move", "mouse_release"]


def test_handled_event_does_not_reach_the_camera(surface):
    """Skip the camera controller when a callback sets handled."""
    v, layer, _ = view_with_image()

    def claim(lyr, event):
        event.handled = True

    layer.mouse_wheel_callbacks.append(claim)
    attach(v, surface)
    zoom = v.camera.zoom
    surface.emit(wheel(100, 50, dy=-120))
    assert v.camera.zoom == zoom


def test_only_the_top_visible_layer_gets_callbacks(surface):
    """Send events to the last visible layer in the list."""
    v, bottom, seen = view_with_image()
    top = Image(name="top", data=np.zeros((3, 4)), visible=False)
    v.layers.append(top)
    top.mouse_drag_callbacks.append(lambda lyr, event: seen.append("top"))
    bottom.mouse_drag_callbacks.append(lambda lyr, event: seen.append("bottom"))
    attach(v, surface)
    surface.emit(pointer("pointer_down", 100, 50, button=1))
    assert seen == ["bottom"]


def test_detach_stops_dispatch(surface):
    """Stop reacting to the surface after detaching."""
    v, layer, seen = view_with_image()
    layer.mouse_drag_callbacks.append(lambda lyr, event: seen.append(event))
    detach = attach(v, surface)
    detach()
    surface.emit(pointer("pointer_down", 100, 50, button=1))
    assert seen == []
