from collections.abc import Callable, Generator

import numpy as np
import pytest
from helpers import FakeSurface, pointer, view_with_image, wheel

from napari_core.interaction import attach
from napari_core.model import (
    ButtonEvent,
    Image,
    Modifier,
    View,
    WheelEvent,
    surface_to_world,
)


def test_layer_callback_receives_napari_events_with_world_position(
    surface: FakeSurface,
) -> None:
    """Hand the top layer a ButtonEvent of type mouse_press with a world position."""
    v, layer = view_with_image()
    seen: list[ButtonEvent] = []
    layer.mouse_drag_callbacks.append(lambda lyr, event: seen.append(event))
    attach(v, surface)
    surface.emit(pointer("pointer_down", 110, 40, button=1, modifiers=("Shift",)))
    (event,) = seen
    assert event.type == "mouse_press"
    assert event.position == surface_to_world(v, 110, 40)
    assert event.modifiers == frozenset({Modifier.SHIFT})
    assert event.button == 1


def test_generator_callback_runs_across_press_move_release(
    surface: FakeSurface,
) -> None:
    """Resume a generator callback on each move and finish it on release."""
    v, layer = view_with_image()
    seen: list[str] = []

    def drag(lyr: Image, event: ButtonEvent) -> Generator[None, None, None]:
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


def test_handled_event_does_not_reach_the_camera(surface: FakeSurface) -> None:
    """Skip the camera controller when a callback sets handled."""
    v, layer = view_with_image()

    def claim(lyr: Image, event: WheelEvent) -> None:
        event.handled = True

    layer.mouse_wheel_callbacks.append(claim)
    attach(v, surface)
    zoom = v.camera.zoom
    surface.emit(wheel(100, 50, dy=-120))
    assert v.camera.zoom == zoom


def test_only_the_top_visible_layer_gets_callbacks(surface: FakeSurface) -> None:
    """Send events to the last visible layer in the list."""
    v, bottom = view_with_image()
    seen: list[str] = []
    top = Image(name="top", data=np.zeros((3, 4)), visible=False)
    v.layers.append(top)
    top.mouse_drag_callbacks.append(lambda lyr, event: seen.append("top"))
    bottom.mouse_drag_callbacks.append(lambda lyr, event: seen.append("bottom"))
    attach(v, surface)
    surface.emit(pointer("pointer_down", 100, 50, button=1))
    assert seen == ["bottom"]


def test_detach_stops_dispatch(surface: FakeSurface) -> None:
    """Stop reacting to the surface after detaching."""
    v, layer = view_with_image()
    seen: list[ButtonEvent] = []
    layer.mouse_drag_callbacks.append(lambda lyr, event: seen.append(event))
    detach = attach(v, surface)
    detach()
    surface.emit(pointer("pointer_down", 100, 50, button=1))
    assert seen == []


def test_attaching_a_surface_twice_raises(surface: FakeSurface) -> None:
    """Refuse a second attachment of a surface until the first is detached."""
    v, _ = view_with_image()
    detach = attach(v, surface)
    with pytest.raises(RuntimeError, match="already attached"):
        attach(v, surface)
    with pytest.raises(RuntimeError, match="already attached"):
        attach(View(), surface)
    detach()
    attach(v, surface)


def test_detach_removes_the_handler_and_can_be_repeated(surface: FakeSurface) -> None:
    """Leave no handler on the surface after detaching, however often."""
    v, _ = view_with_image()
    detach = attach(v, surface)
    detach()
    detach()
    assert surface.handlers == []


def test_surface_closed_while_attached_can_be_attached_again(
    surface: FakeSurface,
) -> None:
    """Count a closed surface as detached without a call to detach."""
    v, _ = view_with_image()
    attach(v, surface)
    surface.close()
    attach(v, surface)


def test_detach_during_an_event_stops_the_later_handlers_of_the_dispatcher(
    surface: FakeSurface,
) -> None:
    """Leave the view alone when an event reaches the dispatcher after a detach."""
    v, _ = view_with_image()
    detach_ref: list[Callable[[], None]] = []
    surface.add_event_handler(lambda event: detach_ref[0](), "resize")
    detach_ref.append(attach(v, surface))
    surface.emit(
        {"event_type": "resize", "width": 640.0, "height": 480.0, "pixel_ratio": 1.0}
    )
    assert v.canvas_size == (200, 100)


def test_raising_callback_is_logged_and_the_rest_still_run(
    surface: FakeSurface, caplog: pytest.LogCaptureFixture
) -> None:
    """Log a callback that raises, then call the next one and move the camera."""
    v, layer = view_with_image()
    seen: list[str] = []

    def broken(lyr: Image, event: WheelEvent) -> None:
        raise RuntimeError("boom")

    layer.mouse_wheel_callbacks.append(broken)
    layer.mouse_wheel_callbacks.append(lambda lyr, event: seen.append(event.type))
    attach(v, surface)
    zoom = v.camera.zoom
    surface.emit(wheel(100, 50, dy=-120))
    assert seen == ["mouse_wheel"]
    assert v.camera.zoom > zoom
    assert "broken" in caplog.text
    assert "image" in caplog.text


def test_generator_raising_on_a_move_does_not_break_later_drags(
    surface: FakeSurface, caplog: pytest.LogCaptureFixture
) -> None:
    """Log a generator that raises, keeping other callbacks and later drags working."""
    v, layer = view_with_image()
    seen: list[str] = []

    def broken(lyr: Image, event: ButtonEvent) -> Generator[None, None, None]:
        yield
        raise RuntimeError("boom")

    def tracker(lyr: Image, event: ButtonEvent) -> Generator[None, None, None]:
        seen.append(event.type)
        yield
        while event.type == "mouse_move":
            seen.append(event.type)
            yield
        seen.append(event.type)

    layer.mouse_drag_callbacks.extend([broken, tracker])
    attach(v, surface)
    for kind in ("pointer_down", "pointer_move", "pointer_up") * 2:
        surface.emit(pointer(kind, 100, 50, button=1))
    assert seen == ["mouse_press", "mouse_move", "mouse_release"] * 2
    assert len(caplog.records) == 2
    assert "broken" in caplog.text


def test_generator_that_finishes_early_is_not_resumed(surface: FakeSurface) -> None:
    """Drop a generator that ends at once and keep driving the others."""
    v, layer = view_with_image()
    seen: list[str] = []

    def early(lyr: Image, event: ButtonEvent) -> Generator[None, None, None]:
        seen.append("early")
        return
        yield

    def tracker(lyr: Image, event: ButtonEvent) -> Generator[None, None, None]:
        while event.type != "mouse_release":
            seen.append(event.type)
            yield
        seen.append(event.type)

    layer.mouse_drag_callbacks.extend([early, tracker])
    attach(v, surface)
    for kind in ("pointer_down", "pointer_move", "pointer_up"):
        surface.emit(pointer(kind, 100, 50, button=1))
    assert seen == ["early", "mouse_press", "mouse_move", "mouse_release"]


def test_plain_callback_runs_once_on_press(surface: FakeSurface) -> None:
    """Call a callback that is not a generator on the press only."""
    v, layer = view_with_image()
    seen: list[str] = []
    layer.mouse_drag_callbacks.append(lambda lyr, event: seen.append(event.type))
    attach(v, surface)
    for kind in ("pointer_down", "pointer_move", "pointer_up"):
        surface.emit(pointer(kind, 100, 50, button=1))
    assert seen == ["mouse_press"]


def test_generator_setting_handled_keeps_the_camera_still(
    surface: FakeSurface,
) -> None:
    """Skip the camera for the moves of a drag where the generator sets handled."""
    v, layer = view_with_image()

    def claim(lyr: Image, event: ButtonEvent) -> Generator[None, None, None]:
        yield
        while event.type == "mouse_move":
            event.handled = True
            yield

    layer.mouse_drag_callbacks.append(claim)
    attach(v, surface)
    center = v.camera.center
    surface.emit(pointer("pointer_down", 100, 50, button=1))
    surface.emit(pointer("pointer_move", 120, 60, button=1))
    surface.emit(pointer("pointer_up", 120, 60, button=1))
    assert v.camera.center == center
