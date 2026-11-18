"""Say whether Qt gives a working OpenGL widget, with and without vispy.

Run by the probe workflow on the macOS runner, where Qt logs that
`QOpenGLWidget` is not supported and vispy's widget shows nothing. Prints, for
a plain `QOpenGLWidget` and for a vispy canvas: whether the widget is valid,
its OpenGL context and version, how often Qt called its initialise and paint
methods, and the middle pixel of Qt's grab of it.
"""

import time

import numpy as np
from PyQt6.QtGui import QImage, QOpenGLContext, QSurfaceFormat
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtWidgets import QApplication, QWidget
from vispy.app import use_app
from vispy.scene import SceneCanvas

use_app("pyqt6")
app = QApplication.instance() or QApplication([])
print("Qt platform:", app.platformName())
print("default surface format:", QSurfaceFormat.defaultFormat().version())
print("shared OpenGL context:", QOpenGLContext.globalShareContext())


def process(seconds: float) -> None:
    deadline = time.perf_counter() + seconds
    while time.perf_counter() < deadline:
        app.processEvents()
        time.sleep(0.01)


def middle(widget: QWidget) -> tuple[int, ...]:
    image = widget.grab().toImage().convertToFormat(QImage.Format.Format_RGBA8888)
    data = np.frombuffer(
        image.constBits().asstring(image.sizeInBytes()), dtype=np.uint8
    )
    pixels = data.reshape(image.height(), image.width(), 4)
    return tuple(int(v) for v in pixels[pixels.shape[0] // 2, pixels.shape[1] // 2])


def describe(name: str, widget: QOpenGLWidget) -> None:
    context = widget.context()
    print(f"{name}: valid={widget.isValid()} context={context is not None}")
    if context is not None:
        surface_format = context.format()
        print(
            f"{name}: context valid={context.isValid()} version={surface_format.version()}"
            f" profile={surface_format.profile()} renderable={surface_format.renderableType()}"
        )
    print(f"{name}: grab middle pixel {middle(widget)}")


class Plain(QOpenGLWidget):
    def __init__(self) -> None:
        super().__init__()
        self.calls = {"initializeGL": 0, "paintGL": 0}

    def initializeGL(self) -> None:  # noqa: N802
        self.calls["initializeGL"] += 1

    def paintGL(self) -> None:  # noqa: N802
        self.calls["paintGL"] += 1


plain = Plain()
plain.resize(200, 100)
plain.show()
process(1.0)
describe("plain QOpenGLWidget", plain)
print("plain QOpenGLWidget: calls", plain.calls)
plain.close()

canvas = SceneCanvas(bgcolor="white", size=(200, 100), show=True)
process(1.0)
native = canvas.native
print("vispy native widget class:", type(native).__mro__[1].__name__)
if isinstance(native, QOpenGLWidget):
    describe("vispy canvas", native)
rendered = np.asarray(canvas.render())
print(
    "vispy canvas.render() middle pixel:",
    tuple(int(v) for v in rendered[rendered.shape[0] // 2, rendered.shape[1] // 2]),
)
canvas.close()
