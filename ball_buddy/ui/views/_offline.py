"""Shared helpers for the offline manual-team-list mode (see sync.effective_snapshot).

When no Yahoo snapshot exists but the user entered a manual team list in
League -> Settings (``manual_teams``), views render from
:meth:`SyncService.effective_snapshot` and show this banner so the manual
origin is never mistaken for synced league data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QLabel

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from ball_buddy.services.sync import SyncService

OFFLINE_MANUAL_BANNER = (
    "Offline — rendering from the manual team list in League -> Settings. "
    "Sync via Yahoo to get rosters, schedule, and standings."
)


def is_manual(document: dict | None) -> bool:
    """True when ``document`` came from the manual team list (not Yahoo)."""
    return bool(document) and document.get("source") == "manual"


def show_banner(label: QLabel) -> None:
    label.setText(OFFLINE_MANUAL_BANNER)
    label.setVisible(True)


def hide_banner(label: QLabel) -> None:
    label.setText("")
    label.setVisible(False)


def apply_view_fallback(view: object, service: SyncService, banner: QLabel) -> None:
    """Engine views (matchup/waivers/lineups/trades): manual-list fallback.

    When the view holds no snapshot yet (no Yahoo sync), populate it from
    the manual team list so the team pickers and engines work offline,
    and show ``banner``. No-op when a real snapshot exists (views also
    hide their banner in ``apply_result`` on a real sync).
    """
    if getattr(view, "snapshot", None) is not None:
        return
    document = service.effective_snapshot()
    if not is_manual(document):
        return
    view.snapshot = document  # type: ignore[attr-defined]
    show_banner(banner)
    view._refresh_combos()  # type: ignore[attr-defined]
    if hasattr(view, "_recompute"):  # matchup: combos alone don't re-render
        view._recompute()  # type: ignore[attr-defined]


__all__ = [
    "OFFLINE_MANUAL_BANNER",
    "apply_view_fallback",
    "hide_banner",
    "is_manual",
    "show_banner",
]
