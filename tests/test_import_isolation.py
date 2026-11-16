import subprocess
import sys


def test_core_imports_no_renderer_gui_or_dask():
    """Import the core in a fresh interpreter without loading vispy, Qt or dask."""
    code = (
        "import sys, napari_core.model, napari_core.render,"
        " napari_core.interaction;"
        "bad = sorted(m for m in sys.modules if m.split('.')[0] in"
        " {'vispy', 'PyQt6', 'PyQt5', 'PySide6', 'PySide2', 'qtpy', 'dask'});"
        "print(bad)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "[]"


def test_vispy_backend_imports_no_qt_binding():
    """Import the vispy backend in a fresh interpreter without loading a Qt binding."""
    code = (
        "import sys, napari_core.render.vispy;"
        "bad = sorted(m for m in sys.modules if m.split('.')[0] in"
        " {'PyQt6', 'PyQt5', 'PySide6', 'PySide2', 'qtpy'});"
        "print(bad)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "[]"
