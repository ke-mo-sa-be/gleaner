"""Draw the Gleaner icon (packaging/gleaner.ico). Run once when the design changes: py packaging/make_icon.py"""

import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPainterPath

OUT = Path(__file__).with_name("gleaner.ico")
SIZE = 256


def draw() -> QImage:
    img = QImage(SIZE, SIZE, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(8, 8, SIZE - 16, SIZE - 16), 48, 48)
    p.fillPath(path, QColor("#1F4E78"))
    # three "grain" dots: gathering what is left in the field
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#F39C12"))
    for x in (78, 128, 178):
        p.drawEllipse(QRectF(x - 14, 186, 28, 28))
    p.setPen(QColor("white"))
    p.setFont(QFont("Segoe UI", 110, QFont.Weight.Bold))
    p.drawText(QRectF(0, 0, SIZE, 196), Qt.AlignmentFlag.AlignCenter, "G")
    p.end()
    return img


if __name__ == "__main__":
    app = QGuiApplication(sys.argv)
    if not draw().save(str(OUT), "ICO"):
        sys.exit("could not write icon")
    print(f"wrote {OUT}")
