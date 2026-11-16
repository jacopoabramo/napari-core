"""Show a 30-plane image stack in a window with a slider over the planes.

Plane `k` is a horizontal gradient shifted by `k` columns, so stepping is
visible. Drag with the left button to pan and turn the wheel to zoom.

Run with `uv run python examples/show_image.py`, or add `--dask` to wrap the
stack in a dask array first.
"""

import argparse
import sys

import dask.array as da
import numpy as np
import numpy.typing as npt
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import QApplication, QMainWindow, QSlider, QVBoxLayout, QWidget
from vispy.app import use_app

from napari_core.data import as_layer_data
from napari_core.interaction import attach
from napari_core.model import Image, ViewerModel
from napari_core.render.vispy import VispyBackend

PLANES = 30
SIZE = 256


def make_stack() -> npt.NDArray[np.uint8]:
    """Return a stack of horizontal gradients, each shifted by its plane index."""
    row = np.arange(SIZE, dtype=np.uint8)
    return np.stack([np.tile(np.roll(row, k), (SIZE, 1)) for k in range(PLANES)])


class ImageWindow(QMainWindow):
    """A window with the image above a slider over the planes."""

    def __init__(self, use_dask: bool) -> None:
        super().__init__()
        stack = make_stack()
        if use_dask:
            stack = da.from_array(stack, chunks=(1, SIZE, SIZE))
        self.viewer = ViewerModel()
        self.viewer.layers.append(Image(name="stack", data=as_layer_data(stack)))
        self.viewer.camera.center = (SIZE / 2, SIZE / 2)
        self.viewer.camera.zoom = 2.0
        self.surface = VispyBackend[QWidget]().create_surface(self.viewer.view, None)
        attach(self.viewer.view, self.surface)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, self.viewer.dims.nsteps[0] - 1)
        self.slider.valueChanged.connect(self.set_plane)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(self.surface.native, 1)
        layout.addWidget(self.slider)
        self.setCentralWidget(central)
        self.resize(600, 640)

    def set_plane(self, plane: int) -> None:
        """Show plane `plane` of the stack."""
        self.viewer.dims.current_step = (plane, 0, 0)

    def closeEvent(self, event: QCloseEvent | None) -> None:
        """Close the surface, so it stops following the model, then the window."""
        self.surface.close()
        super().closeEvent(event)


def main() -> None:
    """Parse the arguments, show the window and run the event loop."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--dask", action="store_true", help="wrap the stack in dask")
    args = parser.parse_args()
    use_app("pyqt6")
    app = QApplication.instance() or QApplication(sys.argv)
    window = ImageWindow(args.dask)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
