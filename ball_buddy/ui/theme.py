"""Tactile-cream UI theme (light, tokens.json) as a single Qt stylesheet.

Tokens are kept as named constants so later milestones can swap values
(e.g. dark theme) without touching the stylesheet layout.

Documented deviation: Qt stylesheets cannot express box-shadow or true
linear gradients, so control gradients are approximated with a flat
``control-top`` fill, a 1px light top border (via border-top-color), and
the 2px hard outline. No emoji; sentence-case labels; 4px spacing scale;
32px nav button height.
"""

from PySide6.QtWidgets import QApplication

# --- tokens (light) -------------------------------------------------------
CANVAS = "#F5EFE0"
SURFACE = "#FBF7EC"
SUNKEN = "#EBE4D1"
CONTROL_TOP = "#FFFCF3"
CONTROL_BOTTOM = "#F0E8D3"
CONTROL_HOVER_TOP = "#FFFFFA"
CONTROL_HOVER_BOTTOM = "#F5EEDB"
OUTLINE = "#000000"
DIVIDER = "#CFC6AE"
TEXT = "#1C1A16"
TEXT_SECONDARY = "#5E584B"
TEXT_MUTED = "#736C5B"  # never used on sunken surfaces
INK_FILL = "#1C1A16"
TEXT_ON_INK = "#F5EFE0"

FONT_FAMILY = '"IBM Plex Mono", Consolas, monospace'
TEXT_BASE = "13px"
TEXT_LG = "16px"

BORDER = f"2px solid {OUTLINE}"
RADIUS_CONTAINER = "0px"
RADIUS_CONTROL = "8px"
NAV_HEIGHT = "32px"

STYLE = f"""
* {{
    font-family: {FONT_FAMILY};
    font-size: {TEXT_BASE};
    color: {TEXT};
    outline: none;
}}

QMainWindow, QWidget {{
    background-color: {CANVAS};
}}

/* Containers: 2px hard outline, square corners */
QWidget#panel {{
    background-color: {SURFACE};
    border: {BORDER};
    border-radius: {RADIUS_CONTAINER};
}}

/* Controls: 2px outline, 8px radius, gradient approximated with a flat
   control-top fill + 1px light top border */
QPushButton {{
    background-color: {CONTROL_TOP};
    border: {BORDER};
    border-top-color: {CONTROL_HOVER_TOP};
    border-radius: {RADIUS_CONTROL};
    padding: 2px 12px;
    text-align: left;
}}
QPushButton:hover {{
    background-color: {CONTROL_HOVER_TOP};
    border-top-color: {SURFACE};
}}
QPushButton:pressed {{
    background-color: {CONTROL_BOTTOM};
    border-top-color: {DIVIDER};
}}
QPushButton:disabled {{
    color: {TEXT_MUTED};
    background-color: {SURFACE};
}}

/* Visible keyboard-focus indicator (compensates for the global
   outline:none; Qt has no box-shadow, so a dark 1px top edge + sunken
   fill approximate the spec's inset focus highlight) */
QPushButton:focus {{
    background-color: {SUNKEN};
    border-top-color: {TEXT_SECONDARY};
}}

/* Ink-fill primary buttons */
QPushButton[ink="true"] {{
    background-color: {INK_FILL};
    border: {BORDER};
    color: {TEXT_ON_INK};
    text-align: center;
}}
QPushButton[ink="true"]:hover {{
    background-color: {TEXT_SECONDARY};
}}
QPushButton[ink="true"]:disabled {{
    background-color: {TEXT_MUTED};
    color: {CANVAS};
}}

/* Nav: control-styled buttons, fixed 32px height; checked = sunken */
QButtonGroup::button, QPushButton#nav {{
    min-height: {NAV_HEIGHT};
    background-color: {CONTROL_TOP};
    border: {BORDER};
    border-top-color: {CONTROL_HOVER_TOP};
    border-radius: {RADIUS_CONTROL};
    text-align: left;
    padding: 2px 8px;
}}
QPushButton#nav:hover {{
    background-color: {CONTROL_HOVER_TOP};
}}
QPushButton#nav:checked {{
    background-color: {SUNKEN};
    border-top-color: {DIVIDER};
}}

QLabel {{
    background: transparent;
    border: none;
}}
QLabel#title {{
    font-size: {TEXT_LG};
    font-weight: 600;
}}
QLabel#secondary {{
    color: {TEXT_SECONDARY};
}}

/* Ink-filled status banners (loud, per R3: unmatched reports are red-on-cream,
   i.e. text on the ink fill using TEXT_ON_INK) */
QLabel#banner {{
    background-color: {SUNKEN};
    border: {BORDER};
    border-radius: {RADIUS_CONTROL};
    padding: 4px 12px;
}}
QLabel#banner-alert {{
    background-color: {INK_FILL};
    border: {BORDER};
    border-radius: {RADIUS_CONTROL};
    padding: 4px 12px;
    color: {TEXT_ON_INK};
}}

/* Tables (League view panes, import dialog report): surface fill, 2px hard
   outline, dividers for grid, sunken header */
QTableWidget {{
    background-color: {SURFACE};
    alternate-background-color: {CANVAS};
    border: {BORDER};
    border-radius: {RADIUS_CONTAINER};
    gridline-color: {DIVIDER};
    selection-background-color: {SUNKEN};
    selection-color: {TEXT};
}}
QTableWidget::item {{
    padding: 1px 6px;
    border: none;
}}
QHeaderView::section {{
    background-color: {SUNKEN};
    color: {TEXT};
    border: none;
    border-right: 1px solid {DIVIDER};
    border-bottom: {BORDER};
    padding: 2px 6px;
}}
QTableCornerButton::section {{
    background-color: {SUNKEN};
    border: none;
    border-bottom: {BORDER};
    border-right: 1px solid {DIVIDER};
}}
"""


def apply_theme(app: QApplication) -> None:
    """Apply the tactile-cream stylesheet to the application."""
    app.setStyleSheet(STYLE)
