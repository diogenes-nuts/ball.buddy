"""Generic placeholder page: centered 'coming soon' label on a surface panel."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PlaceholderView(QWidget):
    def __init__(self, message: str = "coming soon", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        panel = QWidget()
        panel.setObjectName("panel")
        layout.addWidget(panel)

        inner = QVBoxLayout(panel)
        inner.addStretch(1)
        label = QLabel(message)
        label.setObjectName("secondary")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(label)
        inner.addStretch(1)


__all__ = ["PlaceholderView"]
