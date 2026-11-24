#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Canonical Design System & Theme Helpers.
Enforces the Leonida Coastal Sunset palette: 85% calm slate-midnight surfaces
(#0D0E15 / #141621 / #1B1E2D), high-contrast alabaster typography (#F5F6FA / #A6AEBF),
Noto Sans + CJK font fallbacks, and disciplined GTA VI sunset accents (#FF5E7E -> #FF9A62).
"""

import os
from PyQt5 import QtCore as _qt_core
from PyQt5 import QtGui as _qt_gui
from PyQt5 import QtWidgets as _qt_widgets

Qt = _qt_core.Qt
QPoint = getattr(_qt_core, "QPoint", lambda x=0, y=0: (x, y))
QRect = getattr(_qt_core, "QRect", lambda *a: None)
QSize = _qt_core.QSize
QColor = getattr(_qt_gui, "QColor", lambda *a, **kw: None)
QFont = _qt_gui.QFont
QIcon = _qt_gui.QIcon
QApplication = _qt_widgets.QApplication
QFrame = getattr(_qt_widgets, "QFrame", _qt_widgets.QWidget)
QHBoxLayout = _qt_widgets.QHBoxLayout
QLabel = _qt_widgets.QLabel
QLayout = getattr(_qt_widgets, "QLayout", object)
QPushButton = _qt_widgets.QPushButton
QVBoxLayout = _qt_widgets.QVBoxLayout
QWidget = _qt_widgets.QWidget


COLORS = {
    # Surfaces (85% calm slate-midnight hierarchy)
    "bg_canvas": "#0D0E15",
    "bg_surface": "#141621",
    "bg_elevated": "#1B1E2D",
    "bg_hover": "#23273A",
    "bg_active": "#2B2230",
    "border": "#2C3147",
    "border_strong": "#3B425E",
    # Typography
    "text_primary": "#F5F6FA",
    "text_secondary": "#A6AEBF",
    "text_muted": "#6E778C",
    # Disciplined GTA VI Leonida Sunset accents (10-15%)
    "accent_coral": "#FF5E7E",
    "accent_peach": "#FF9A62",
    "accent_aqua": "#36D6C3",
    "accent_gold": "#F7C873",
    # Semantic status colors
    "danger": "#F25C6E",
    "success": "#3ED598",
    "warning": "#F5B963",
    # Convenient short aliases
    "bg": "#0D0E15",
    "surface": "#141621",
    "elevated": "#1B1E2D",
    "text": "#F5F6FA",
    "muted": "#A6AEBF",
    "coral": "#FF5E7E",
    "peach": "#FF9A62",
    "aqua": "#36D6C3",
    "gold": "#F7C873",
}

CJK_FONT_FAMILIES = [
    "Noto Sans",
    "Noto Sans CJK JP",
    "Noto Sans CJK SC",
    "Noto Sans CJK TC",
    "Noto Sans CJK KR",
    "DejaVu Sans",
]

MONO_FONT_FAMILIES = [
    "JetBrains Mono",
    "DejaVu Sans Mono",
    "Noto Sans Mono CJK JP",
    "Noto Sans Mono CJK SC",
    "monospace",
]

FONT_STACK = (
    '"Noto Sans", "Noto Sans CJK JP", "Noto Sans CJK SC", '
    '"Noto Sans CJK TC", "Noto Sans CJK KR", "DejaVu Sans", sans-serif'
)
FONT_FAMILY = FONT_STACK

MONO_STACK = (
    '"JetBrains Mono", "DejaVu Sans Mono", '
    '"Noto Sans Mono CJK JP", "Noto Sans Mono CJK SC", monospace'
)

_ICON_EXTRA_DIRS = (
    "/usr/share/icons/hicolor/64x64/apps",
    "/usr/share/icons/hicolor/48x48/apps",
    "/usr/share/icons/hicolor/scalable/apps",
    "/usr/share/pixmaps",
    os.path.expanduser("~/.local/share/icons/hicolor/64x64/apps"),
)

_BADGE_STYLES = {
    "neutral": (
        "background-color: #1B1E2D; color: #A6AEBF; "
        "border: 1px solid #2C3147; border-radius: 9px; "
        "padding: 3px 9px; font-size: 11px; font-weight: bold;"
    ),
    "gold": (
        "background-color: #252017; color: #F7C873; "
        "border: 1px solid #4A3E24; border-radius: 8px; "
        "padding: 3px 9px; font-size: 11px; font-weight: bold;"
    ),
    "aqua": (
        "background-color: #122427; color: #36D6C3; "
        "border: 1px solid #224B4F; border-radius: 8px; "
        "padding: 3px 9px; font-size: 11px; font-weight: bold;"
    ),
    "coral": (
        "background-color: #291822; color: #FF9A62; "
        "border: 1px solid #592C3D; border-radius: 8px; "
        "padding: 3px 9px; font-size: 11px; font-weight: bold;"
    ),
    "success": (
        "background-color: #132520; color: #3ED598; "
        "border: 1px solid #254D3E; border-radius: 8px; "
        "padding: 3px 9px; font-size: 11px; font-weight: bold;"
    ),
    "danger": (
        "background-color: #2B171D; color: #F25C6E; "
        "border: 1px solid #5C2833; border-radius: 8px; "
        "padding: 3px 9px; font-size: 11px; font-weight: bold;"
    ),
}


def configure_cjk_fonts(app: QApplication, size: int = 10) -> None:
    """Register Noto Sans CJK and monospace substitutions on *app*."""
    for base in ("Noto Sans", "DejaVu Sans", "Sans", "sans-serif", "Arial"):
        QFont.insertSubstitutions(base, CJK_FONT_FAMILIES)
    for mono in ("monospace", "Monospace", "DejaVu Sans Mono", "JetBrains Mono"):
        QFont.insertSubstitutions(mono, MONO_FONT_FAMILIES)
    if app is not None:
        font = QFont("Noto Sans", size)
        if hasattr(font, "setFamilies"):
            font.setFamilies(CJK_FONT_FAMILIES)
        app.setFont(font)


def configure_icon_theme() -> str:
    """Ensure PyQt5 resolves Papirus-Dark / Adwaita / hicolor icons cleanly."""
    QIcon.setThemeSearchPaths([
        "/usr/share/icons",
        "/usr/local/share/icons",
        os.path.expanduser("~/.local/share/icons"),
    ])
    for theme in ("Papirus-Dark", "Papirus", "Adwaita", "Tango", "hicolor"):
        if os.path.isdir(os.path.join("/usr/share/icons", theme)):
            QIcon.setThemeName(theme)
            return theme
    return ""


def resolve_icon(*names: str) -> QIcon:
    """Return the first valid QIcon from file paths, Freedesktop theme, or Vice pixmaps."""
    for name in names:
        if not name:
            continue
        if os.path.isfile(name):
            icon = QIcon(name)
            if not icon.isNull():
                return icon
        icon = QIcon.fromTheme(name)
        if not icon.isNull():
            return icon
        for base_dir in _ICON_EXTRA_DIRS:
            for ext in (".png", ".svg", ".xpm", ""):
                candidate = os.path.join(base_dir, f"{name}{ext}")
                if os.path.isfile(candidate):
                    ic = QIcon(candidate)
                    if not ic.isNull():
                        return ic
    return QIcon()


def load_tool_icon(tool_id_or_name: str, *fallbacks: str) -> QIcon:
    """Resolve a Vice OS tool icon by ID/slug (auto-prefixing 'vice-tool-') with fallbacks."""
    raw = str(tool_id_or_name or "").strip().lower().replace(" ", "-")
    candidates = []
    if raw:
        candidates.append(raw)
        if not raw.startswith("vice-tool-"):
            candidates.insert(0, f"vice-tool-{raw}")
    candidates.extend(fallbacks)
    candidates.extend(("application-x-executable", "applications-other"))
    return resolve_icon(*candidates)


def get_logo_icon() -> QIcon:
    """Return the canonical GTA VI x Debian Swirl emblem icon."""
    return resolve_icon(
        "/usr/share/pixmaps/vice-debian-gta6.png",
        "/usr/share/pixmaps/vice-app.png",
        "vice-debian-gta6",
        "start-here",
        "view-app-grid",
    )


def build_app_qss(extra_qss: str = "") -> str:
    """Build the unified, uncluttered Leonida dark slate QSS for Vice OS applications."""
    c = COLORS
    base_qss = f"""
QWidget {{
    background-color: {c['bg_canvas']};
    color: {c['text_primary']};
    font-family: {FONT_STACK};
    font-size: 13px;
}}

QMainWindow, QDialog, QMessageBox, QWidget#RootWidget {{
    background-color: {c['bg_canvas']};
    color: {c['text_primary']};
}}

QDialog, QMessageBox {{
    border: 1px solid {c['border']};
    border-radius: 12px;
}}

QFrame#HeaderCard, QFrame#HeroBanner {{
    background-color: {c['bg_surface']};
    border: 1px solid {c['border']};
    border-radius: 14px;
}}

QFrame#Card, QFrame#ToolCard, QFrame#SurfaceCard {{
    background-color: {c['bg_surface']};
    border: 1px solid {c['border']};
    border-radius: 12px;
}}

QFrame#ToolCard:hover {{
    background-color: #181B28;
    border-color: {c['border_strong']};
}}

QLabel {{
    background-color: transparent;
    border: none;
    color: {c['text_primary']};
}}

QLabel#HeaderTitle, QLabel#HeroTitle {{
    color: {c['text_primary']};
    font-size: 18px;
    font-weight: bold;
    background-color: transparent;
}}

QLabel#HeaderSubtitle, QLabel#HeroSub, QLabel#MutedLabel {{
    color: {c['text_secondary']};
    font-size: 12px;
    background-color: transparent;
}}

QLabel#SectionTitle {{
    color: {c['text_primary']};
    font-size: 13px;
    font-weight: bold;
    background-color: transparent;
}}

QLabel#ValueReadout {{
    color: {c['accent_aqua']};
    font-size: 15px;
    font-weight: bold;
    background-color: transparent;
}}

QLabel#ClockDisplay {{
    color: {c['text_primary']};
    font-family: {MONO_STACK};
    font-size: 38px;
    font-weight: bold;
    background-color: transparent;
}}

QPushButton {{
    background-color: {c['bg_elevated']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    border-radius: 9px;
    padding: 7px 14px;
    font-weight: normal;
    min-width: 56px;
}}

QPushButton:hover {{
    background-color: {c['bg_hover']};
    border-color: {c['border_strong']};
    color: {c['text_primary']};
}}

QPushButton:focus {{
    border: 1px solid {c['accent_coral']};
    outline: none;
}}

QPushButton:pressed {{
    background-color: #2B3046;
    border-color: {c['accent_coral']};
}}

QPushButton:disabled {{
    background-color: #11131C;
    color: {c['text_muted']};
    border-color: #1E2130;
}}

QPushButton#PrimaryButton, QPushButton[variant="primary"] {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {c['accent_coral']}, stop:1 {c['accent_peach']});
    color: #0D0E15;
    border: none;
    border-radius: 9px;
    padding: 8px 18px;
    font-weight: bold;
}}

QPushButton#PrimaryButton:hover, QPushButton[variant="primary"]:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #FF708D, stop:1 #FFA975);
    color: #0D0E15;
}}

QPushButton#PrimaryButton:pressed, QPushButton[variant="primary"]:pressed {{
    background: {c['accent_coral']};
    color: #0D0E15;
}}

QPushButton#PrimaryButton:disabled, QPushButton[variant="primary"]:disabled {{
    background: #23273A;
    color: {c['text_muted']};
}}

QPushButton#DangerButton, QPushButton[variant="danger"] {{
    background-color: #2A161D;
    color: {c['danger']};
    border: 1px solid #592835;
    border-radius: 9px;
    padding: 7px 14px;
    font-weight: bold;
}}

QPushButton#DangerButton:hover, QPushButton[variant="danger"]:hover {{
    background-color: #3B1D26;
    border-color: {c['danger']};
    color: {c['text_primary']};
}}

QPushButton#CatTab, QPushButton#SegButton {{
    background-color: {c['bg_surface']};
    color: {c['text_secondary']};
    border: 1px solid {c['border']};
    border-radius: 9px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 600;
    min-width: 0px;
}}

QPushButton#CatTab:hover, QPushButton#SegButton:hover {{
    background-color: {c['bg_elevated']};
    color: {c['text_primary']};
    border-color: {c['border_strong']};
}}

QPushButton#CatTab:checked, QPushButton#SegButton:checked {{
    background-color: {c['bg_active']};
    color: {c['accent_peach']};
    border: 1px solid {c['accent_coral']};
}}

QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {{
    background-color: {c['bg_elevated']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    border-radius: 9px;
    padding: 6px 10px;
    selection-background-color: #4A2438;
    selection-color: {c['text_primary']};
}}

QTextEdit, QPlainTextEdit {{
    background-color: #10121B;
    font-family: {MONO_STACK};
    font-size: 12px;
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QComboBox:focus {{
    border: 1px solid {c['accent_coral']};
    background-color: #1F2334;
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox::down-arrow {{
    width: 0px;
    height: 0px;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {c['text_secondary']};
    margin-right: 6px;
}}

QComboBox QAbstractItemView {{
    background-color: {c['bg_elevated']};
    color: {c['text_primary']};
    border: 1px solid {c['border_strong']};
    border-radius: 12px;
    outline: none;
    padding: 4px;
}}

QComboBox QAbstractItemView::item {{
    padding: 6px 10px;
    border-radius: 8px;
}}

QComboBox QAbstractItemView::item:selected {{
    background-color: {c['bg_active']};
    color: {c['accent_peach']};
}}

QTabWidget::pane {{
    background-color: {c['bg_surface']};
    border: 1px solid {c['border']};
    border-radius: 12px;
    top: -1px;
}}

QTabBar::tab {{
    background-color: {c['bg_surface']};
    color: {c['text_secondary']};
    border: 1px solid {c['border']};
    border-bottom: none;
    padding: 8px 18px;
    margin-right: 3px;
    border-top-left-radius: 9px;
    border-top-right-radius: 9px;
    font-weight: normal;
}}

QTabBar::tab:hover {{
    background-color: {c['bg_elevated']};
    color: {c['text_primary']};
}}

QTabBar::tab:selected {{
    background-color: {c['bg_elevated']};
    color: {c['text_primary']};
    border-color: {c['border_strong']};
    border-bottom: 2px solid {c['accent_coral']};
}}

QTableWidget, QTreeView, QListView, QListWidget {{
    background-color: {c['bg_surface']};
    alternate-background-color: #171A26;
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    border-radius: 10px;
    gridline-color: {c['border']};
    outline: none;
}}

QTreeView::item, QListView::item, QTableWidget::item, QListWidget::item {{
    padding: 6px 8px;
    border-radius: 8px;
}}

QTreeView::item:hover, QListView::item:hover, QListWidget::item:hover {{
    background-color: {c['bg_elevated']};
}}

QTreeView::item:selected, QListView::item:selected,
QTableWidget::item:selected, QListWidget::item:selected {{
    background-color: {c['bg_active']};
    color: {c['accent_peach']};
}}

QHeaderView::section {{
    background-color: {c['bg_elevated']};
    color: {c['text_secondary']};
    padding: 7px 8px;
    border: none;
    border-right: 1px solid {c['border']};
    border-bottom: 1px solid {c['border']};
    font-weight: bold;
    font-size: 12px;
}}

QGroupBox {{
    background-color: {c['bg_surface']};
    border: 1px solid {c['border']};
    border-radius: 12px;
    margin-top: 14px;
    padding: 14px 12px 12px 12px;
    color: {c['text_primary']};
    font-weight: bold;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: {c['accent_gold']};
    font-size: 12px;
}}

QCheckBox, QRadioButton {{
    background-color: transparent;
    color: {c['text_primary']};
    spacing: 8px;
}}

QCheckBox::indicator, QRadioButton::indicator {{
    width: 15px;
    height: 15px;
    border: 1px solid {c['border_strong']};
    background-color: {c['bg_elevated']};
    border-radius: 5px;
}}

QCheckBox::indicator:focus, QRadioButton::indicator:focus {{
    border: 1px solid {c['accent_coral']};
}}

QRadioButton::indicator {{
    border-radius: 8px;
}}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background-color: {c['accent_coral']};
    border-color: {c['accent_coral']};
}}

QSlider::groove:horizontal {{
    border: none;
    height: 5px;
    background: {c['bg_elevated']};
    border-radius: 3px;
}}

QSlider::sub-page:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {c['accent_coral']}, stop:1 {c['accent_peach']});
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    background: {c['text_primary']};
    border: 2px solid {c['accent_coral']};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 8px;
}}

QProgressBar {{
    background-color: {c['bg_elevated']};
    border: 1px solid {c['border']};
    border-radius: 9px;
    height: 14px;
    text-align: center;
    color: {c['text_primary']};
    font-size: 11px;
    font-weight: bold;
}}

QProgressBar::chunk {{
    border-radius: 8px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {c['accent_coral']}, stop:1 {c['accent_peach']});
}}

QSplitter::handle {{
    background-color: {c['border']};
    width: 2px;
    height: 2px;
}}

QStatusBar {{
    background-color: {c['bg_surface']};
    color: {c['text_secondary']};
    border-top: 1px solid {c['border']};
    font-size: 12px;
}}

QStatusBar::item {{
    border: none;
}}

QScrollArea {{
    border: none;
    background-color: transparent;
}}

QScrollBar:vertical {{
    border: none;
    background-color: transparent;
    width: 8px;
    margin: 2px;
}}

QScrollBar::handle:vertical {{
    background-color: #2D3248;
    min-height: 26px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {c['accent_coral']};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    border: none;
    background: transparent;
    height: 0px;
}}

QScrollBar:horizontal {{
    border: none;
    background-color: transparent;
    height: 8px;
    margin: 2px;
}}

QScrollBar::handle:horizontal {{
    background-color: #2D3248;
    min-width: 26px;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {c['accent_coral']};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    border: none;
    background: transparent;
    width: 0px;
}}

QMenu {{
    background-color: {c['bg_elevated']};
    color: {c['text_primary']};
    border: 1px solid {c['border_strong']};
    border-radius: 12px;
    padding: 6px;
}}

QMenu::item {{
    padding: 6px 16px;
    border-radius: 8px;
}}

QMenu::item:selected {{
    background-color: {c['bg_active']};
    color: {c['accent_peach']};
}}

QMenu::separator {{
    height: 1px;
    background-color: {c['border']};
    margin: 4px 8px;
}}

QToolTip {{
    background-color: {c['bg_elevated']};
    color: {c['text_primary']};
    border: 1px solid {c['border_strong']};
    border-radius: 9px;
    padding: 6px 10px;
}}
"""
    if extra_qss:
        return base_qss + "\n" + extra_qss
    return base_qss


def style_badge(label: QLabel, variant: str = "neutral") -> None:
    """Apply a clean pill badge style ('neutral', 'gold', 'aqua', 'coral', 'success', 'danger')."""
    label.setStyleSheet(_BADGE_STYLES.get(variant, _BADGE_STYLES["neutral"]))


def make_badge(text: str, variant: str = "neutral", parent: QWidget = None) -> QLabel:
    """Create a styled status/category pill QLabel."""
    lbl = QLabel(text, parent)
    lbl.setAlignment(Qt.AlignCenter)
    style_badge(lbl, variant)
    return lbl


class HeaderWidget(QFrame):
    """Unified header bar widget with icon, title, subtitle, badge, and right-side slot."""

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        icon_name: str = "",
        badge_text: str = "",
        badge_variant: str = "gold",
        parent: QWidget = None,
    ):
        super().__init__(parent)
        self.setObjectName("HeaderCard")
        row = QHBoxLayout(self)
        row.setContentsMargins(16, 12, 16, 12)
        row.setSpacing(12)

        self.icon_label = QLabel(self)
        self.icon_label.setFixedSize(40, 40)
        self.icon_label.setAlignment(Qt.AlignCenter)
        icon = load_tool_icon(icon_name) if icon_name else get_logo_icon()
        if not icon.isNull():
            self.icon_label.setPixmap(icon.pixmap(36, 36))
        else:
            self.icon_label.hide()
        row.addWidget(self.icon_label)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        self.title_label = QLabel(title, self)
        self.title_label.setObjectName("HeaderTitle")
        text_col.addWidget(self.title_label)

        self.subtitle_label = QLabel(subtitle, self)
        self.subtitle_label.setObjectName("HeaderSubtitle")
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setVisible(bool(subtitle))
        text_col.addWidget(self.subtitle_label)
        row.addLayout(text_col, 1)

        self.right_layout = QHBoxLayout()
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setSpacing(8)

        self.badge_label = make_badge(badge_text, badge_variant, self)
        self.badge_label.setVisible(bool(badge_text))
        self.right_layout.addWidget(self.badge_label)

        row.addLayout(self.right_layout)

    def set_badge(self, text: str, variant: str = "gold") -> None:
        self.badge_label.setText(text)
        style_badge(self.badge_label, variant)
        self.badge_label.setVisible(bool(text))


def make_header(
    title: str,
    subtitle: str = "",
    icon_name: str = "",
    badge_text: str = "",
    badge_variant: str = "gold",
    parent: QWidget = None,
) -> HeaderWidget:
    """Build a refined GTA VI header card with title, subtitle, icon, and optional badge."""
    return HeaderWidget(
        title=title,
        subtitle=subtitle,
        icon_name=icon_name,
        badge_text=badge_text,
        badge_variant=badge_variant,
        parent=parent,
    )


class CardWidget(QFrame):
    """Elevated slate card container exposing `.body_layout` (QVBoxLayout)."""

    def __init__(
        self,
        title: str = "",
        subtitle: str = "",
        margins: tuple = (14, 12, 14, 12),
        spacing: int = 8,
        parent: QWidget = None,
    ):
        super().__init__(parent)
        self.setObjectName("Card")
        self.body_layout = QVBoxLayout(self)
        self.body_layout.setContentsMargins(*margins)
        self.body_layout.setSpacing(spacing)

        self.title_label = None
        self.subtitle_label = None
        if title:
            self.title_label = QLabel(title, self)
            self.title_label.setObjectName("SectionTitle")
            self.body_layout.addWidget(self.title_label)
        if subtitle:
            self.subtitle_label = QLabel(subtitle, self)
            self.subtitle_label.setObjectName("MutedLabel")
            self.subtitle_label.setWordWrap(True)
            self.body_layout.addWidget(self.subtitle_label)


def make_card(
    title: str = "",
    subtitle: str = "",
    margins: tuple = (14, 12, 14, 12),
    spacing: int = 8,
    parent: QWidget = None,
) -> CardWidget:
    """Create an elevated #141621 surface card with 1px #262A3D structural hairline."""
    return CardWidget(
        title=title,
        subtitle=subtitle,
        margins=margins,
        spacing=spacing,
        parent=parent,
    )


def make_button(
    text: str,
    variant: str = "secondary",
    icon_name: str = "",
    parent: QWidget = None,
) -> QPushButton:
    """Create a styled QPushButton ('primary', 'secondary', or 'danger')."""
    btn = QPushButton(text, parent)
    if variant == "primary":
        btn.setObjectName("PrimaryButton")
        btn_font = btn.font()
        btn_font.setBold(True)
        btn.setFont(btn_font)
    elif variant == "danger":
        btn.setObjectName("DangerButton")
        btn_font = btn.font()
        btn_font.setBold(True)
        btn.setFont(btn_font)
    if icon_name:
        ic = resolve_icon(icon_name)
        if not ic.isNull():
            btn.setIcon(ic)
            btn.setIconSize(QSize(16, 16))
    return btn


def apply_app_theme(target, extra_qss: str = "", font_size: int = 10) -> str:
    """Configure CJK fonts, Papirus-Dark icons, and apply build_app_qss() to *target*."""
    app = QApplication.instance()
    if app is not None:
        configure_cjk_fonts(app, size=font_size)
        configure_icon_theme()
    qss = build_app_qss(extra_qss=extra_qss)
    if target is not None and hasattr(target, "setStyleSheet"):
        target.setStyleSheet(qss)
    return qss


def qcolor(key: str) -> QColor:
    """Return a QColor for any key in COLORS or hex string."""
    return QColor(COLORS.get(key, key))


class FlowLayout(QLayout):
    """Responsive wrapping layout for buttons, badges, or category pills."""

    def __init__(self, parent: QWidget = None, h_spacing: int = 6, v_spacing: int = 6):
        super().__init__(parent)
        self._items = []
        self._h_space = h_spacing
        self._v_space = v_spacing

    def __del__(self):
        try:
            while getattr(self, "_items", None):
                self.takeAt(0)
        except RuntimeError:
            pass

    def addItem(self, item) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        left, top, right, bottom = self.getContentsMargins()
        size += QSize(left + right, top + bottom)
        return size

    def _do_layout(self, rect, test_only: bool) -> int:
        left, top, right, bottom = self.getContentsMargins()
        eff = rect.adjusted(left, top, -right, -bottom)
        x = eff.x()
        y = eff.y()
        line_h = 0

        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + self._h_space
            if next_x - self._h_space > eff.right() and line_h > 0:
                x = eff.x()
                y += line_h + self._v_space
                next_x = x + hint.width() + self._h_space
                line_h = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_h = max(line_h, hint.height())
        return y + line_h - rect.y() + bottom
