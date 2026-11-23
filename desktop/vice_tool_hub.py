#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) — Vice Tool Hub (X / 500).
Leonida-themed interactive Tools Explorer reading /opt/vice-os/tools_registry.json
(with repo config/tools_registry.json fallback), showing live Batch progress,
category tabs, instant search, custom GTA VI icons, and one-click tool launch.
"""

import json
import os
import shlex
import shutil
import signal
import sys

from PyQt5.QtCore import Qt, QProcess
from PyQt5.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QScrollArea, QVBoxLayout, QWidget
)

sys.path.insert(0, "/opt/vice-os/lib")

try:
    from python.vice_utils import log_error, log_info  # noqa: E402
except ImportError:
    def log_info(msg: str) -> None:
        print(f"[INFO] {msg}")

    def log_error(msg: str) -> None:
        print(f"[ERROR] {msg}", file=sys.stderr)


CJK_FONTS = [
    "Noto Sans",
    "Noto Sans CJK JP",
    "Noto Sans CJK SC",
    "Noto Sans CJK TC",
    "Noto Sans CJK KR",
    "DejaVu Sans",
]

CATEGORIES = [
    "All",
    "GTA VI Originals",
    "System",
    "Network",
    "Security",
    "Developer",
    "Files & Disk",
    "Media",
    "Productivity",
]

STYLE = """
QMainWindow, QWidget#RootWidget {
    background-color: #120e1e;
    color: #f4f1fa;
    font-family: "Noto Sans", "Noto Sans CJK JP", "Noto Sans CJK SC", "Noto Sans CJK TC", "Noto Sans CJK KR", "DejaVu Sans", sans-serif;
    font-size: 13px;
}
QFrame#HeroBanner {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #1d1433, stop:0.55 #27153a, stop:1 #152238);
    border: 1px solid #ff4da6;
    border-radius: 14px;
}
QLabel#HeroTitle {
    color: #ffd166;
    font-size: 22px;
    font-weight: bold;
    letter-spacing: 1px;
    background: transparent;
}
QLabel#HeroSub {
    color: #cfc6e6;
    font-size: 12px;
    background: transparent;
}
QLabel#ProgressReadout {
    color: #00e5ff;
    font-size: 16px;
    font-weight: bold;
    background: transparent;
}
QProgressBar#HubProgress {
    background-color: #161028;
    border: 1px solid #49386e;
    border-radius: 8px;
    height: 16px;
    text-align: center;
    color: #ffffff;
    font-weight: bold;
}
QProgressBar#HubProgress::chunk {
    border-radius: 7px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #ff4da6, stop:0.5 #ff8a5b, stop:1 #00e5ff);
}
QLineEdit#SearchBox {
    background-color: #1b152e;
    color: #f4f1fa;
    border: 1px solid #3c2e5e;
    border-radius: 10px;
    padding: 8px 14px;
    font-size: 13px;
}
QLineEdit#SearchBox:focus {
    border-color: #ff4da6;
    background-color: #221a39;
}
QComboBox#TypeFilter {
    background-color: #1b152e;
    color: #f4f1fa;
    border: 1px solid #3c2e5e;
    border-radius: 10px;
    padding: 7px 12px;
    min-width: 140px;
}
QPushButton#CatTab {
    background-color: #1b152e;
    color: #cfc6e6;
    border: 1px solid #322650;
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: bold;
}
QPushButton#CatTab:hover {
    border-color: #ff8a5b;
    color: #ffffff;
    background-color: #261d40;
}
QPushButton#CatTab:checked {
    background-color: #3a1f47;
    border-color: #ff4da6;
    color: #ffd166;
}
QScrollArea {
    border: none;
    background: transparent;
}
QScrollBar:vertical {
    background: #140f24;
    width: 10px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #3d2e61;
    border-radius: 5px;
    min-height: 28px;
}
QScrollBar::handle:vertical:hover {
    background: #ff4da6;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QFrame#ToolCard {
    background-color: #19132b;
    border: 1px solid #322650;
    border-radius: 12px;
}
QFrame#ToolCard:hover {
    background-color: #211938;
    border: 1px solid #ff4da6;
}
QFrame#ToolCardGta {
    background-color: #201636;
    border: 1px solid #ff8a5b;
    border-radius: 12px;
}
QFrame#ToolCardGta:hover {
    background-color: #2b1d45;
    border: 1px solid #ffd166;
}
QPushButton#LaunchBtn {
    background-color: #261c42;
    color: #00e5ff;
    border: 1px solid #00e5ff;
    border-radius: 8px;
    padding: 6px 14px;
    font-weight: bold;
    font-size: 12px;
}
QPushButton#LaunchBtn:hover {
    background-color: #00e5ff;
    color: #120e1e;
}
QPushButton#ReloadBtn {
    background-color: #241a3d;
    color: #ff8a5b;
    border: 1px solid #ff8a5b;
    border-radius: 8px;
    padding: 7px 14px;
    font-weight: bold;
}
QPushButton#ReloadBtn:hover {
    background-color: #ff8a5b;
    color: #120e1e;
}
QLabel#StatusBarLbl {
    color: #a99ec9;
    font-size: 12px;
    padding: 4px 2px;
    background: transparent;
}
"""


def _configure_cjk_fonts(app: QApplication) -> None:
    for fam in ("Noto Sans", "DejaVu Sans", "Sans", "sans-serif"):
        QFont.insertSubstitutions(fam, CJK_FONTS)
    font = QFont("Noto Sans", 10)
    if hasattr(font, "setFamilies"):
        font.setFamilies(CJK_FONTS)
    app.setFont(font)


def _tool_slug(tool_id: str) -> str:
    clean = str(tool_id).strip().lower().replace(" ", "-")
    return clean if clean.startswith("vice-tool-") else f"vice-tool-{clean}"


def _find_registry_path() -> str:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    candidates = [
        "/opt/vice-os/tools_registry.json",
        os.path.join(repo_root, "config", "tools_registry.json"),
        os.path.join(os.path.dirname(__file__), "tools_registry.json"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return candidates[0]


def _resolve_tool_pixmap(slug: str, size: int = 48) -> QPixmap:
    candidates = [
        f"/usr/share/icons/hicolor/64x64/apps/{slug}.png",
        f"/usr/share/pixmaps/{slug}.png",
        "/usr/share/pixmaps/vice-app.png",
    ]
    for path in candidates:
        if os.path.isfile(path):
            pm = QPixmap(path)
            if not pm.isNull():
                return pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    theme_icon = QIcon.fromTheme(slug)
    if not theme_icon.isNull():
        return theme_icon.pixmap(size, size)

    # Minimal painted fallback badge if icons aren't generated yet in local test mode
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor("#1b152e"))
    painter.setPen(QColor("#ff4da6"))
    painter.drawRoundedRect(2, 2, size - 4, size - 4, 10, 10)
    painter.setPen(QColor("#00e5ff"))
    painter.setFont(QFont("Noto Sans", 11, QFont.Bold))
    painter.drawText(pm.rect(), Qt.AlignCenter, "VI")
    painter.end()
    return pm


class ViceToolHub(QMainWindow):
    """Main window for Vice Tool Hub (X / 500)."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice Tool Hub — Leonida Arsenal")
        self.resize(1120, 740)
        self.setMinimumSize(860, 560)
        self._desktop_dir = os.path.dirname(os.path.abspath(__file__))
        self._repo_root = os.path.abspath(os.path.join(self._desktop_dir, ".."))
        self._registry = {}
        self._tools = []
        self._selected_category = "All"
        self._cat_buttons = {}
        self._icon_cache = {}
        self._current_cols = 2

        win_pm = _resolve_tool_pixmap("vice-tool-hub", 64)
        if not win_pm.isNull():
            self.setWindowIcon(QIcon(win_pm))

        self._init_ui()
        self._load_registry()

    def _init_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("RootWidget")
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(12)

        # Hero banner + Live X / 500 Progress Bar
        hero = QFrame(root)
        hero.setObjectName("HeroBanner")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(18, 14, 18, 14)
        hero_layout.setSpacing(8)

        top_row = QHBoxLayout()
        logo_lbl = QLabel(hero)
        logo_lbl.setPixmap(_resolve_tool_pixmap("vice-tool-hub", 52))
        logo_lbl.setStyleSheet("background: transparent;")
        top_row.addWidget(logo_lbl)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self._hero_title = QLabel("VICE TOOL HUB · LEONIDA ARSENAL", hero)
        self._hero_title.setObjectName("HeroTitle")
        self._hero_sub = QLabel("Curated Vice OS Originals & Debian Power Tools", hero)
        self._hero_sub.setObjectName("HeroSub")
        title_col.addWidget(self._hero_title)
        title_col.addWidget(self._hero_sub)
        top_row.addLayout(title_col, 1)

        right_col = QVBoxLayout()
        right_col.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._progress_lbl = QLabel("0 / 500 — 0%", hero)
        self._progress_lbl.setObjectName("ProgressReadout")
        self._progress_lbl.setAlignment(Qt.AlignRight)
        right_col.addWidget(self._progress_lbl)

        self._counts_lbl = QLabel("Batch 1 · Loading...", hero)
        self._counts_lbl.setObjectName("HeroSub")
        self._counts_lbl.setAlignment(Qt.AlignRight)
        right_col.addWidget(self._counts_lbl)
        top_row.addLayout(right_col)

        hero_layout.addLayout(top_row)

        self._progress_bar = QProgressBar(hero)
        self._progress_bar.setObjectName("HubProgress")
        self._progress_bar.setRange(0, 500)
        self._progress_bar.setValue(0)
        self._progress_bar.setFormat("%v / %m Tools Unlocked (%p%)")
        hero_layout.addWidget(self._progress_bar)

        layout.addWidget(hero)

        # Search + Type filter + Reload row
        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)

        self._search = QLineEdit(root)
        self._search.setObjectName("SearchBox")
        self._search.setPlaceholderText("Search 100+ tools by name, package, command, or description...")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._render_cards)
        filter_row.addWidget(self._search, 1)

        self._type_filter = QComboBox(root)
        self._type_filter.setObjectName("TypeFilter")
        self._type_filter.addItems(["All Modes", "GTA VI Originals", "GUI Apps", "CLI / TUI Tools"])
        self._type_filter.currentIndexChanged.connect(self._render_cards)
        filter_row.addWidget(self._type_filter)

        reload_btn = QPushButton("Reload", root)
        reload_btn.setObjectName("ReloadBtn")
        reload_btn.clicked.connect(self._load_registry)
        filter_row.addWidget(reload_btn)

        layout.addLayout(filter_row)

        # Category tabs row
        tabs_wrap = QHBoxLayout()
        tabs_wrap.setSpacing(6)
        for cat in CATEGORIES:
            btn = QPushButton(cat, root)
            btn.setObjectName("CatTab")
            btn.setCheckable(True)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setChecked(cat == "All")
            btn.clicked.connect(lambda _checked=False, c=cat: self._select_category(c))
            self._cat_buttons[cat] = btn
            tabs_wrap.addWidget(btn)
        tabs_wrap.addStretch(1)
        layout.addLayout(tabs_wrap)

        # Scrollable tool cards area
        self._scroll = QScrollArea(root)
        self._scroll.setWidgetResizable(True)
        self._cards_host = QWidget()
        self._cards_host.setStyleSheet("background: transparent;")
        self._grid = QGridLayout(self._cards_host)
        self._grid.setContentsMargins(2, 4, 6, 4)
        self._grid.setSpacing(10)
        self._scroll.setWidget(self._cards_host)
        layout.addWidget(self._scroll, 1)

        # Footer status bar
        self._status_lbl = QLabel("Ready.", root)
        self._status_lbl.setObjectName("StatusBarLbl")
        layout.addWidget(self._status_lbl)

    def _select_category(self, category: str) -> None:
        self._selected_category = category
        for cat, btn in self._cat_buttons.items():
            btn.setChecked(cat == category)
        self._render_cards()

    def _load_registry(self) -> None:
        path = _find_registry_path()
        try:
            with open(path, "r", encoding="utf-8") as fp:
                self._registry = json.load(fp)
            self._tools = list(self._registry.get("tools", []))
        except FileNotFoundError:
            self._registry = {}
            self._tools = []
            self._status_lbl.setText(f"Registry not found at {path}. Waiting for tools_registry.json.")
        except Exception as exc:
            self._registry = {}
            self._tools = []
            log_error(f"Failed loading {path}: {exc}")
            self._status_lbl.setText(f"Error reading {path}: {exc}")

        target = int(self._registry.get("target_count", 500) or 500)
        current = int(self._registry.get("current_count", len(self._tools)) or len(self._tools))
        batch = self._registry.get("batch", 1)
        theme = self._registry.get("theme", "GTA VI Leonida Neon")
        pct = int(round((current / max(1, target)) * 100))

        self._progress_bar.setMaximum(max(1, target))
        self._progress_bar.setValue(min(current, target))
        self._progress_lbl.setText(f"{current} / {target} — {pct}%")
        gta_count = sum(1 for t in self._tools if t.get("gta_themed"))
        power_count = max(0, len(self._tools) - gta_count)
        self._counts_lbl.setText(
            f"Batch {batch} · {gta_count} Originals · {power_count} Curated Tools · {theme}"
        )

        # Update category button counts
        for cat, btn in self._cat_buttons.items():
            if cat == "All":
                count = len(self._tools)
            elif cat == "GTA VI Originals":
                count = sum(1 for t in self._tools if t.get("gta_themed") or t.get("category") == cat)
            else:
                count = sum(1 for t in self._tools if t.get("category") == cat)
            btn.setText(f"{cat} ({count})")

        self._render_cards()
        if self._tools:
            self._status_lbl.setText(f"Loaded {len(self._tools)} tools from {path}")

    def _matches_filters(self, tool: dict) -> bool:
        cat = self._selected_category
        if cat == "GTA VI Originals":
            if not (tool.get("gta_themed") or tool.get("category") == "GTA VI Originals"):
                return False
        elif cat != "All" and tool.get("category") != cat:
            return False

        mode = self._type_filter.currentText()
        if mode == "GTA VI Originals" and not tool.get("gta_themed"):
            return False
        if mode == "GUI Apps" and tool.get("terminal"):
            return False
        if mode == "CLI / TUI Tools" and not tool.get("terminal"):
            return False

        query = self._search.text().strip().lower()
        if query:
            hay = " ".join([
                str(tool.get("id", "")),
                str(tool.get("name", "")),
                str(tool.get("description", "")),
                str(tool.get("category", "")),
                str(tool.get("package", "")),
                str(tool.get("exec", "")),
            ]).lower()
            if query not in hay:
                return False
        return True

    def _clear_grid(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _get_pixmap(self, slug: str) -> QPixmap:
        if slug not in self._icon_cache:
            self._icon_cache[slug] = _resolve_tool_pixmap(slug, 48)
        return self._icon_cache[slug]

    def _render_cards(self) -> None:
        self._clear_grid()
        filtered = [t for t in self._tools if self._matches_filters(t)]

        if not filtered:
            empty = QLabel(
                "No tools match your current filter."
                if self._tools else "No tools registered yet.",
                self._cards_host,
            )
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet("color: #cfc6e6; font-size: 14px; padding: 36px;")
            self._grid.addWidget(empty, 0, 0)
            return

        cols = 3 if self.width() >= 1260 else 2
        self._current_cols = cols

        for idx, tool in enumerate(filtered):
            card = self._build_card(tool)
            row, col = divmod(idx, cols)
            self._grid.addWidget(card, row, col)

        for c in range(cols):
            self._grid.setColumnStretch(c, 1)
        last_row = (len(filtered) - 1) // cols + 1
        self._grid.setRowStretch(last_row, 1)
        self._status_lbl.setText(f"Showing {len(filtered)} of {len(self._tools)} tools.")

    def _build_card(self, tool: dict) -> QFrame:
        is_gta = bool(tool.get("gta_themed"))
        card = QFrame(self._cards_host)
        card.setObjectName("ToolCardGta" if is_gta else "ToolCard")
        card.setMinimumHeight(138)

        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(12, 12, 12, 12)
        vbox.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(10)

        slug = _tool_slug(tool.get("id", "tool"))
        icon_lbl = QLabel(card)
        icon_lbl.setFixedSize(48, 48)
        icon_lbl.setPixmap(self._get_pixmap(slug))
        icon_lbl.setStyleSheet("background: transparent;")
        head.addWidget(icon_lbl)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        name_lbl = QLabel(str(tool.get("name", slug)), card)
        name_lbl.setStyleSheet(
            "color: #ffd166; font-weight: bold; font-size: 14px; background: transparent;"
            if is_gta else
            "color: #ffffff; font-weight: bold; font-size: 14px; background: transparent;"
        )
        name_lbl.setWordWrap(True)
        title_box.addWidget(name_lbl)

        badge_text = "GTA VI ORIGINAL" if is_gta else ("CLI / TUI" if tool.get("terminal") else "GUI")
        pkg_text = str(tool.get("package", "system"))
        cat_text = str(tool.get("category", ""))
        meta_lbl = QLabel(f"[{badge_text}] · {cat_text} · pkg: {pkg_text}", card)
        meta_lbl.setStyleSheet(
            "color: #ff8a5b; font-size: 11px; font-weight: bold; background: transparent;"
            if is_gta else
            "color: #9f94c2; font-size: 11px; background: transparent;"
        )
        title_box.addWidget(meta_lbl)
        head.addLayout(title_box, 1)
        vbox.addLayout(head)

        desc_lbl = QLabel(str(tool.get("description", "")), card)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color: #d6cee8; font-size: 12px; background: transparent;")
        vbox.addWidget(desc_lbl, 1)

        foot = QHBoxLayout()
        foot.setSpacing(8)
        exec_str = str(tool.get("exec", ""))
        cmd_lbl = QLabel(f"$ {exec_str}", card)
        cmd_lbl.setStyleSheet(
            "color: #00e5ff; font-family: 'Noto Sans Mono CJK JP', 'DejaVu Sans Mono', monospace; "
            "font-size: 11px; background: transparent;"
        )
        cmd_lbl.setToolTip(exec_str)
        foot.addWidget(cmd_lbl, 1)

        launch_btn = QPushButton("Launch", card)
        launch_btn.setObjectName("LaunchBtn")
        launch_btn.setFocusPolicy(Qt.NoFocus)
        launch_btn.clicked.connect(lambda _=False, t=tool: self._launch_tool(t))
        foot.addWidget(launch_btn)
        vbox.addLayout(foot)

        return card

    def _resolve_exec_args(self, exec_str: str) -> list:
        try:
            args = shlex.split(exec_str)
        except ValueError:
            args = exec_str.split()
        if not args:
            return []
        # Repo-checkout fallback if /opt/vice-os/<script>.py does not exist yet
        if len(args) >= 2 and args[1].startswith("/opt/vice-os/") and not os.path.exists(args[1]):
            local_script = os.path.join(self._desktop_dir, os.path.basename(args[1]))
            if os.path.isfile(local_script):
                args[1] = local_script
        if args[0] == "python3" and not shutil.which("python3"):
            args[0] = sys.executable
        return args

    def _find_vice_runner(self) -> str:
        found = shutil.which("vice-run-tool")
        if found:
            return found
        candidates = [
            "/usr/local/bin/vice-run-tool",
            "/usr/local/system_scripts/vice-run-tool.sh",
            os.path.join(self._repo_root, "system_scripts", "vice-run-tool.sh"),
        ]
        for path in candidates:
            if os.path.isfile(path):
                return path
        return ""

    def _launch_tool(self, tool: dict) -> None:
        name = str(tool.get("name", tool.get("id", "Tool")))
        exec_str = str(tool.get("exec", "")).strip()
        args = self._resolve_exec_args(exec_str)
        if not args:
            QMessageBox.warning(self, "Launch Error", f"No executable command defined for {name}.")
            return

        home = os.path.expanduser("~")
        if tool.get("terminal"):
            runner = self._find_vice_runner()
            if runner:
                if runner.endswith(".sh") and shutil.which("bash"):
                    launch_prog = "bash"
                    launch_args = [runner, name] + args
                else:
                    launch_prog = runner
                    launch_args = [name] + args
            else:
                term = shutil.which("xfce4-terminal") or shutil.which("x-terminal-emulator") or "xterm"
                if "xfce4-terminal" in os.path.basename(term):
                    launch_prog = term
                    launch_args = ["-T", f"Vice OS - {name}", "-x"] + args
                else:
                    launch_prog = term
                    launch_args = ["-e", " ".join(shlex.quote(a) for a in args)]
        else:
            launch_prog = args[0]
            launch_args = args[1:]

        ok = QProcess.startDetached(launch_prog, launch_args, home)
        if ok:
            self._status_lbl.setText(f"Launched {name}: {launch_prog} {' '.join(launch_args)}")
            log_info(f"ViceToolHub launched {name}")
        else:
            self._status_lbl.setText(f"Failed to launch {name} ({launch_prog}).")
            QMessageBox.warning(
                self, "Launch Failed",
                f"Could not start '{name}'.\nCommand: {launch_prog} {' '.join(launch_args)}"
            )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        new_cols = 3 if self.width() >= 1260 else 2
        if new_cols != self._current_cols and self._tools:
            self._render_cards()

    def closeEvent(self, event) -> None:
        event.accept()


def main() -> None:
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    _configure_cjk_fonts(app)
    app.setStyleSheet(STYLE)
    win = ViceToolHub()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
