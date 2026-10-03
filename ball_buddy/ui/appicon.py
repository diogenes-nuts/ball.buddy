"""Shared ball.buddy mark painter: window icon (runtime) + assets/icon.ico (build).

Mark: warm-cream rounded square, 2px-class dark outline, orange basketball with
a vertical seam and two bulging side seams (arcs of 2r circles centered at +/-2r).
"""

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen

CREAM = QColor(0xF4, 0xEB, 0xDD)
DARK = QColor(0x2B, 0x26, 0x20)
ORANGE = QColor(0xE8, 0x75, 0x2A)


def draw_app_icon(size: int) -> QImage:
    """Render the app mark at `size` px on a transparent ARGB32 image."""
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    s = float(size)
    outline = max(1.0, round(s * 2.0 / 64.0))  # 2px at 64, 8px at 256
    seam_width = max(1.0, round(outline * 0.6))

    # Background: rounded square, cream fill + dark outline.
    margin = s * 0.04
    bg = QPen(DARK, outline)
    painter.setPen(bg)
    painter.setBrush(CREAM)
    bg_rect = QRectF(margin, margin, s - 2 * margin, s - 2 * margin)
    painter.drawRoundedRect(bg_rect, s * 0.18, s * 0.18)

    # Basketball: centered circle.
    cx, cy = s / 2, s / 2
    r = s * 0.30
    ball = QRectF(cx - r, cy - r, 2 * r, 2 * r)
    painter.setPen(QPen(DARK, outline))
    painter.setBrush(ORANGE)
    painter.drawEllipse(ball)

    # Seams (dark, thinner than the outline): vertical line + two side arcs.
    painter.setPen(QPen(DARK, seam_width))
    painter.drawLine(QPointF(cx, cy - r), QPointF(cx, cy + r))
    # Right seam: arc of a 4r square centered at (cx + 2r, cy); the seam circle
    # crosses the ball where cos(theta) = 0.25 (theta ~= +/-75.5deg), so the
    # visible arc runs 75.5deg -> -75.5deg through 0deg (3 o'clock).
    theta = math.degrees(math.acos(0.25))
    painter.drawArc(
        QRectF(cx + r, cy - 2 * r, 4 * r, 4 * r), int(theta * 16), int(-2 * theta * 16)
    )
    painter.drawArc(
        QRectF(cx - 3 * r, cy - 2 * r, 4 * r, 4 * r), int((180 - theta) * 16), int(2 * theta * 16)
    )
    painter.end()
    return image


__all__ = ["draw_app_icon", "CREAM", "DARK", "ORANGE"]
