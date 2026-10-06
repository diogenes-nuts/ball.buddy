"""Tactile-cream UI theme (light + dark) as Qt stylesheets.

Tokens come from the tactile-cream-ui skill (tokens.json, light and dark
blocks) and are kept as named dicts so the palettes can be swapped at
runtime (``apply_theme(app, "dark")``) without touching the stylesheet
layout. All colors, radii, and sizes are token values; no off-scale
literals.

User deviation (over the M0 documented approximation): control gradients
are rendered as a FLAT fill (``control-top`` per state) with NO light top
border — the user asked to drop the gradient frame.

Documented Qt deviations (Qt stylesheets cannot express these):
- No box-shadow: ``--shadow-raised``/``--shadow-pressed`` read as flat
  fills; keyboard focus is a sunken fill (inset approximation of
  ``--shadow-focus``).
- No true linear gradients (see above).
- Table hover-row and the selected-row 4px inset outline bar are not
  expressible in QSS; row selection is flat sunken instead.
- ``--font-display`` degrades to "Trebuchet MS" (first available rounded
  sans on Windows; Quicksand is not bundled).
- Dialogs render on canvas with no outline frame (QDialog frame chrome is
  platform-owned); content inside dialogs follows the panel recipes.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

# --- base tokens ----------------------------------------------------------
BORDER = "2px"
DIVIDER = "1px"
RADIUS_CONTAINER = "0px"
RADIUS_CONTROL = "8px"
RADIUS_CHECK = "4px"
CONTROL_H = 32
SIDEBAR_W = 200  # noqa: F841 - kept for reference; shell sets it explicitly
ROW_H = 28  # table rows
FONT_MONO = '"IBM Plex Mono", Consolas, monospace'
FONT_DISPLAY = (
    '"Quicksand", "Varela Round", "Arial Rounded MT Bold", "Trebuchet MS", '
    "sans-serif"
)
TEXT_XS = "11px"
TEXT_MD = "14px"
TEXT_BASE = "13px"
TEXT_LG = "16px"
WEIGHT_MEDIUM = 500
WEIGHT_SEMIBOLD = 600

# --- palette tokens (tokens.json) ------------------------------------------
LIGHT: dict[str, str] = {
    "canvas": "#F5EFE0",
    "surface": "#FBF7EC",
    "sunken": "#EBE4D1",
    "control_top": "#FFFCF3",
    "control_bottom": "#F0E8D3",
    "control_hover_top": "#FFFFFA",
    "control_hover_bottom": "#F5EEDB",
    "outline": "#000000",
    "divider": "#CFC6AE",
    "text": "#1C1A16",
    "text_secondary": "#5E584B",
    "text_muted": "#736C5B",  # never used on sunken surfaces
    "ink_fill": "#1C1A16",
    "text_on_ink": "#F5EFE0",
    "success": "#5F7F52",
    "success_bg": "#DCE6CF",
    "success_text": "#34502A",
    "warning": "#B8872E",
    "warning_bg": "#F1E2BD",
    "warning_text": "#6B4C0F",
    "danger": "#A9473C",
    "danger_bg": "#EFD3CC",
    "danger_text": "#7A2A21",
    "info": "#4F7280",
    "info_bg": "#D3E0E4",
    "info_text": "#2F4D59",
}

DARK: dict[str, str] = {
    "canvas": "#1B1913",
    "surface": "#25221A",
    "sunken": "#14120D",
    "control_top": "#3A352A",
    "control_bottom": "#2C281F",
    "control_hover_top": "#433D30",
    "control_hover_bottom": "#332E24",
    "outline": "#F5EFE0",
    "divider": "#3F3A2E",
    "text": "#F5EFE0",
    "text_secondary": "#BDB5A0",
    "text_muted": "#8F8874",
    "ink_fill": "#F5EFE0",
    "text_on_ink": "#1B1913",
    "success": "#8FB07F",
    "success_bg": "#2B3626",
    "success_text": "#B5D2A6",
    "warning": "#D9AE5B",
    "warning_bg": "#3A3120",
    "warning_text": "#EBCB8A",
    "danger": "#D4786C",
    "danger_bg": "#3C2723",
    "danger_text": "#EBA498",
    "info": "#84A6B4",
    "info_bg": "#263339",
    "info_text": "#A9C6D2",
}

THEMES: dict[str, dict[str, str]] = {"light": LIGHT, "dark": DARK}


def _style(p: dict[str, str]) -> str:
    """Build the stylesheet for one palette (see module docstring for
    documented Qt approximations)."""
    hard = f"{BORDER} solid {p['outline']}"
    thin = f"{DIVIDER} solid {p['divider']}"
    return f"""
* {{
    font-family: {FONT_MONO};
    font-size: {TEXT_BASE};
    font-weight: {WEIGHT_MEDIUM};
    color: {p['text']};
    outline: none;
}}

QMainWindow, QWidget {{
    background-color: {p['canvas']};
}}

/* Containers: 2px hard outline, square corners, flat surface fill */
QWidget#panel {{
    background-color: {p['surface']};
    border: {hard};
    border-radius: {RADIUS_CONTAINER};
}}

/* Sidebar: surface fill, 2px right edge; no double borders (the left edge
   sits on the canvas) */
QFrame#sidebar {{
    background-color: {p['surface']};
    border: none;
    border-right: {hard};
    border-radius: {RADIUS_CONTAINER};
}}

/* Controls: 2px outline, 8px radius, flat fill (gradient dropped by user
   request; states shift the flat fill, no top-border frame) */
QPushButton {{
    min-height: {CONTROL_H}px;
    background-color: {p['control_top']};
    border: {hard};
    border-radius: {RADIUS_CONTROL};
    padding: 2px 12px;
    text-align: left;
}}
QPushButton:hover {{
    background-color: {p['control_hover_top']};
}}
QPushButton:pressed {{
    background-color: {p['control_bottom']};
}}
QPushButton:disabled {{
    color: {p['text_secondary']};
    background-color: {p['surface']};
    border-color: {p['divider']};
}}

/* Visible keyboard focus (inset approximation of --shadow-focus) */
QPushButton:focus {{
    background-color: {p['sunken']};
}}

/* Ink-fill primary buttons (one per region); tokens invert in dark so the
   primary is cream-filled with dark text there */
QPushButton[ink="true"] {{
    background-color: {p['ink_fill']};
    border: {hard};
    color: {p['text_on_ink']};
    text-align: center;
}}
QPushButton[ink="true"]:hover {{
    background-color: {p['text_secondary']};
}}
QPushButton[ink="true"]:disabled {{
    background-color: {p['text_muted']};
    color: {p['canvas']};
}}

/* Nav: control-styled buttons, 32px; ACTIVE = ink fill (the only
   persistent inverted element in the sidebar) */
QButtonGroup::button, QPushButton#nav {{
    min-height: {CONTROL_H}px;
    background-color: {p['control_top']};
    border: {hard};
    border-radius: {RADIUS_CONTROL};
    text-align: left;
    padding: 2px 8px;
}}
QPushButton#nav:hover {{
    background-color: {p['control_hover_top']};
}}
QPushButton#nav:checked {{
    background-color: {p['ink_fill']};
    color: {p['text_on_ink']};
}}

QLabel {{
    background: transparent;
    border: none;
}}
QLabel#title {{
    font-family: {FONT_DISPLAY};
    font-size: {TEXT_LG};
    font-weight: {WEIGHT_SEMIBOLD};
}}
QLabel#secondary {{
    color: {p['text_secondary']};
}}
QLabel#appname {{
    font-family: {FONT_DISPLAY};
    font-size: {TEXT_MD};
    font-weight: {WEIGHT_SEMIBOLD};
}}
QLabel#version {{
    font-size: {TEXT_XS};
    color: {p['text_secondary']};
}}
QFrame#divider {{
    background: transparent;
    border: none;
    border-top: {thin};
    max-height: {DIVIDER};
}}

/* Inline alerts: status-colored panel (fill + text from status tokens,
   2px outline, 8px radius). Info = offline/manual mode; danger = errors. */
QLabel#banner, QLabel#banner-info {{
    background-color: {p['info_bg']};
    color: {p['info_text']};
    border: {hard};
    border-radius: {RADIUS_CONTROL};
    padding: 4px 12px;
}}
QLabel#banner-success {{
    background-color: {p['success_bg']};
    color: {p['success_text']};
    border: {hard};
    border-radius: {RADIUS_CONTROL};
    padding: 4px 12px;
}}
QLabel#banner-danger {{
    background-color: {p['danger_bg']};
    color: {p['danger_text']};
    border: {hard};
    border-radius: {RADIUS_CONTROL};
    padding: 4px 12px;
}}

/* Inputs: sunken feel (sunken fill), control outline + radius */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {p['sunken']};
    border: {hard};
    border-radius: {RADIUS_CONTROL};
    padding: 2px 8px;
    color: {p['text']};
    selection-background-color: {p['text']};
    selection-color: {p['text_on_ink']};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    background-color: {p['surface']};
}}
QLineEdit:disabled, QTextEdit:disabled, QSpinBox:disabled,
QComboBox:disabled {{
    background-color: {p['surface']};
    color: {p['text_secondary']};
    border-color: {p['divider']};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background-color: {p['surface']};
    color: {p['text']};
    border: {hard};
    border-radius: {RADIUS_CONTAINER};
    selection-background-color: {p['sunken']};
    selection-color: {p['text']};
}}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    border: none;
    background-color: {p['control_top']};
    width: 16px;
}}
QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed,
QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed {{
    background-color: {p['control_bottom']};
}}

/* Checkbox: 16px, 4px radius, control shell; checked = ink fill
   (tokens invert the ink in dark mode) */
QCheckBox {{
    spacing: 8px;
    color: {p['text']};
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: {hard};
    border-radius: {RADIUS_CHECK};
    background-color: {p['control_top']};
}}
QCheckBox::indicator:checked {{
    background-color: {p['ink_fill']};
}}
QCheckBox::indicator:disabled {{
    border-color: {p['divider']};
    background-color: {p['surface']};
}}

/* Scroll area (roster toggles): sharp sunken well */
QScrollArea {{
    background-color: {p['surface']};
    border: {hard};
    border-radius: {RADIUS_CONTAINER};
}}

/* Tables: 2px outline, square, 28px rows, dividers, sunken header */
QTableWidget {{
    background-color: {p['surface']};
    alternate-background-color: {p['canvas']};
    border: {hard};
    border-radius: {RADIUS_CONTAINER};
    gridline-color: {p['divider']};
    selection-background-color: {p['sunken']};
    selection-color: {p['text']};
}}
QTableWidget::item {{
    padding: 0 12px;
    border: none;
}}
QTableWidget::item:selected {{
    background-color: {p['sunken']};
    color: {p['text']};
}}
QAbstractItemView::item {{
    min-height: {ROW_H}px;
}}
QHeaderView::section {{
    background-color: {p['sunken']};
    color: {p['text']};
    border: none;
    border-right: {thin};
    border-bottom: {hard};
    padding: 2px 6px;
}}
QTableCornerButton::section {{
    background-color: {p['sunken']};
    border: none;
    border-bottom: {hard};
    border-right: {thin};
}}
"""


def apply_theme(app: QApplication, name: str = "light") -> None:
    """Apply the tactile-cream stylesheet (``"light"`` or ``"dark"``)."""
    app.setStyleSheet(_style(THEMES[name]))


__all__ = ["LIGHT", "DARK", "THEMES", "apply_theme"]
