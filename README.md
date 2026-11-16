# napari-core

A prototype of a viewer core: a layer model, slicing and a rendering
interface, with a vispy backend. It is not napari, it shares no code with
napari, and it is not released.

## Run the example

```
uv sync --all-extras
uv run python examples/image_slice.py
```

The example needs an OpenGL driver and a Qt binding (PyQt6 is in the
development group).

## Run the checks

```
uv run pytest -q
uv run ruff check
uv run ruff format --check
uv run pyrefly check
uv run pyright
uv run lint-imports
```
