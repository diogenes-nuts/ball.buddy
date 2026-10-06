"""Shared status-banner helper (tactile-cream spec: status colors, never
color alone).

Banners are QLabels whose objectName carries the status: ``banner`` /
``banner-info`` (neutral notes, blue-grey), ``banner-success`` (green),
``banner-danger`` (red). ``set_status`` switches the objectName when the
status changes and re-polishes so the stylesheet rule applies.
"""

from PySide6.QtWidgets import QLabel

_KINDS = ("info", "success", "danger")  # "banner" alone is an alias for info


def set_status(label: QLabel, kind: str, text: str) -> None:
    """Show ``text`` on ``label`` with status ``kind`` ("" hides it)."""
    if kind not in ("", "info", "success", "danger"):
        raise ValueError(f"unknown banner kind: {kind!r}")
    object_name = "banner" if kind in ("", "info") else f"banner-{kind}"
    if label.objectName() != object_name:
        label.setObjectName(object_name)
        label.style().unpolish(label)
        label.style().polish(label)
    label.setText(text)
    label.setVisible(bool(text))


__all__ = ["set_status"]
