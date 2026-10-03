"""Draft board page — the one non-placeholder page in M0. Real draft mode lands in M2."""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class DraftView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        panel = QWidget()
        panel.setObjectName("panel")
        layout.addWidget(panel)

        inner = QVBoxLayout(panel)
        inner.setContentsMargins(16, 16, 16, 16)
        inner.setSpacing(8)

        title = QLabel("draft board")
        title.setObjectName("title")
        inner.addWidget(title)

        body = QLabel("draft mode lands in M2")
        body.setObjectName("secondary")
        inner.addWidget(body)

        inner.addStretch(1)


__all__ = ["DraftView"]
