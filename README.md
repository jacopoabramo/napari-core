> [!CAUTION]
> Experiment in progress. Do not use.

# napari-core

A prototype of a viewer core: a layer model, slicing and a rendering
interface, with a vispy backend. It is not napari, it shares no code with
napari, and it is not released.

## What this shows

The prototype shows one image layer in a window, with pan, zoom and a slider
through a stack, from a NumPy or a dask array, in an environment where napari
is not installed. Its model, slicing and input dispatch import no renderer and
no GUI toolkit, and the whole package passes pyright and pyrefly in strict
mode, with a few rules relaxed inside the vispy backend. Where the code had
to differ from the target architecture it was built to test, and why, is
listed in [`DEVIATIONS.md`](DEVIATIONS.md).

## Run the example

```
uv sync
uv run python examples/show_image.py
uv run python examples/show_image.py --backend pygfx
```

`--backend` is `vispy` (the default) or `pygfx`, and `--dask` wraps the stack
in a dask array first. The example needs a Qt binding (PyQt6 is in the
development group) and a display, because it opens a window. It needs an
OpenGL driver for `vispy` and a GPU adapter for `pygfx`. It needs the `vispy`,
`pygfx` and `dask` extras, which the development group already installs.

## Run the checks

```
uv run pytest -q
uv run ruff check
uv run ruff format --check
uv run pyrefly check
uv run pyright
uv run lint-imports
```
