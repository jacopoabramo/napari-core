"""Say which GPU adapters wgpu sees and whether pygfx draws a white image on one.

Run by the probe workflow, once per value of `WGPU_BACKEND_TYPE`, to find out
on which adapter pygfx draws nothing. It uses an offscreen canvas, so no window
system takes part.
"""

import os

import numpy as np
import pygfx as gfx
import wgpu
from rendercanvas.offscreen import RenderCanvas

# PROBE_ADAPTER is "<backend>:<part of the device name>", such as "D3D12:Basic".
wanted = os.environ.get("PROBE_ADAPTER", "")
print("PROBE_ADAPTER =", wanted or "(not set, pygfx chooses)")
for adapter in wgpu.gpu.enumerate_adapters_sync():
    info = adapter.info
    print(
        "  adapter:",
        info["backend_type"],
        "|",
        info["adapter_type"],
        "|",
        info["device"],
        "|",
        info["description"],
    )
    backend, _, device = wanted.partition(":")
    if wanted and info["backend_type"] == backend and device in info["device"]:
        gfx.renderers.wgpu.select_adapter(adapter)
        wanted = ""
if wanted:
    raise SystemExit(f"no adapter matches {wanted}")

canvas = RenderCanvas(size=(200, 100), pixel_ratio=1)
renderer = gfx.WgpuRenderer(canvas, pixel_scale=1)
used = renderer.device.adapter.info
print("pygfx uses:", used["backend_type"], "|", used["adapter_type"], "|", used["device"])

scene = gfx.Scene()
scene.add(gfx.Background.from_color("#000"))
data = np.full((50, 50), 255, dtype=np.uint8)
image = gfx.Image(
    gfx.Geometry(grid=gfx.Texture(data, dim=2)),
    gfx.ImageBasicMaterial(clim=(0, 255)),
)
scene.add(image)
camera = gfx.OrthographicCamera()
camera.show_rect(-25, 75, 0, 50)

canvas.request_draw(lambda: renderer.render(scene, camera))
frame = np.asarray(canvas.draw())
middle = tuple(int(value) for value in frame[frame.shape[0] // 2, frame.shape[1] // 2])
corner = tuple(int(value) for value in frame[0, 0])
print("frame shape:", frame.shape, "| middle pixel:", middle, "| corner pixel:", corner)
print("RESULT:", "image drawn" if middle[:3] == (255, 255, 255) else "image NOT drawn")
