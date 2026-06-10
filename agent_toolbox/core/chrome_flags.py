"""Zentrale Chrome-Launch-Flags — eine Quelle der Wahrheit für macOS HDMI/GPU-Fix.

Verhindert, dass der Chromium-GPU-Prozess einen Display-Reset auf dem
externen Monitor auslöst (Metal/ANGLE-Pfad meiden).
Verwendet von: fireworks_service.py, rotate.py (alle chromium.launch() sites).
"""
CHROMIUM_GPU_FLAGS = [
    "--disable-gpu",
    "--disable-gpu-compositing",
    "--disable-software-rasterizer",
    "--use-angle=swiftshader",
]
