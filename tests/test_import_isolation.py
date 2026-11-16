import subprocess
import sys


def test_model_imports_no_renderer_gui_or_dask():
    """Import the model in a fresh interpreter without loading vispy, Qt or dask."""
    code = (
        "import sys, napari_core.model;"
        "bad = sorted(m for m in sys.modules if m.split('.')[0] in"
        " {'vispy', 'PyQt6', 'PyQt5', 'PySide6', 'PySide2', 'qtpy', 'dask'});"
        "print(bad)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "[]"
