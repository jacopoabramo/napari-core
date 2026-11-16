# napari-core

A prototype of a viewer core: a layer model, slicing and a rendering
interface, with a vispy backend. It is not napari, it shares no code with
napari, and it is not released.

## What this shows

The prototype shows one image layer in a window, with pan, zoom and a slider
through a stack, from a NumPy or a dask array, in an environment where napari
is not installed. Its model, slicing and input dispatch import no renderer and
no GUI toolkit, and the whole package passes pyright and pyrefly in strict
mode, with a few rules relaxed inside the vispy backend. Where the code had to differ from the target architecture it was built
to test, and why, is listed in [`DEVIATIONS.md`](DEVIATIONS.md).

## Run the example

```
uv sync
uv run python examples/show_image.py
```

The example needs an OpenGL driver and a Qt binding (PyQt6 is in the
development group). It opens a window, so it needs a display, and it needs the
`vispy` and `dask` extras, which the development group already installs.

## Run the checks

```
uv run pytest -q
uv run ruff check
uv run ruff format --check
uv run pyrefly check
uv run pyright
uv run lint-imports
```
