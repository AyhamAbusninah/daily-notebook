"""Regenerates the embedded PNG (daily_notebook/icon.py) and data/icon.ico from the SVG."""
import base64
import io
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

root = Path(__file__).resolve().parent.parent
app = QGuiApplication(sys.argv)
renderer = QSvgRenderer(str(root / "data" / "io.github.dailynotebook.svg"))


def render(size: int) -> QImage:
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    renderer.render(p)
    p.end()
    return img


buf = QBuffer()
buf.open(QIODevice.OpenModeFlag.WriteOnly)
render(256).save(buf, "PNG")
b64 = base64.b64encode(bytes(buf.data())).decode()
icon_py = root / "daily_notebook" / "icon.py"
src = icon_py.read_text()
icon_py.write_text(re.sub(r'PNG_BASE64 = ".*"', 'PNG_BASE64 = "%s"' % b64, src))

try:
    from PIL import Image
    big = Image.open(io.BytesIO(bytes(buf.data()))).convert("RGBA")
    big.save(root / "data" / "icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("icon.ico written")
except ImportError:
    print("Pillow not installed: skipped icon.ico")
print("icon.py updated (%d bytes of base64)" % len(b64))
