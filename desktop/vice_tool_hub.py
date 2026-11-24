#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) — Vice Tool Hub.
Interactive Leonida tools explorer reading /opt/vice-os/tools_registry.json
(with repo config/tools_registry.json fallback), displaying dynamic X / 500
progress, adaptive category pills, instant search, GTA VI squircle icons,
and one-click launch. Styled via vice_theme (Noto Sans CJK fallback).
"""

import json
import os
import shlex
import shutil
import signal
import sys

from PyQt5.QtCore import QProcess, QSize, Qt, QTimer
from PyQt5.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget
)

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in ("/opt/vice-os", _HERE, "/opt/vice-os/lib"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from vice_theme import (  # noqa: E402
    COLORS,
    MONO_STACK,
    FlowLayout,
    apply_app_theme,
    load_tool_icon,
    make_badge,
    make_button,
    make_header,
)

try:
    from python.vice_utils import log_error, log_info  # noqa: E402
except ImportError:
    def log_info(msg: str) -> None:
        print(f"[INFO] {msg}")

    def log_error(msg: str) -> None:
        print(f"[ERROR] {msg}", file=sys.stderr)


PREFERRED_CATEGORIES = [
    "All",
    "GTA VI Originals",
    "Office",
    "System",
    "Network",
    "Security",
    "Developer",
    "Files & Disk",
    "Media",
    "Productivity",
]


def _tool_slug(tool_id: str) -> str:
    clean = str(tool_id).strip().lower().replace(" ", "-")
    return clean if clean.startswith("vice-tool-") else f"vice-tool-{clean}"


def _find_registry_path() -> str:
    repo_root = os.path.abspath(os.path.join(_HERE, ".."))
    candidates = [
        "/opt/vice-os/tools_registry.json",
        os.path.join(repo_root, "config", "tools_registry.json"),
        os.path.join(_HERE, "tools_registry.json"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return candidates[0]


def _resolve_tool_pixmap(slug: str, size: int = 44) -> QPixmap:
    candidates = [
        f"/usr/share/icons/hicolor/64x64/apps/{slug}.png",
        f"/usr/share/pixmaps/{slug}.png",
    ]
    for path in candidates:
        if os.path.isfile(path):
            pm = QPixmap(path)
            if not pm.isNull():
                return pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    theme_icon = load_tool_icon(slug)
    if not theme_icon.isNull():
        pm = theme_icon.pixmap(size, size)
        if not pm.isNull():
            return pm

    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(COLORS["bg_elevated"]))
    painter.setPen(QColor(COLORS["border_strong"]))
    painter.drawRoundedRect(2, 2, size - 4, size - 4, 12, 12)
    painter.setPen(QColor(COLORS["accent_peach"]))
    painter.setFont(QFont("Noto Sans", 11, QFont.Bold))
    painter.drawText(pm.rect(), Qt.AlignCenter, "VI")
    painter.end()
    return pm


class ViceToolHub(QMainWindow):
    """Main window for Vice Tool Hub."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice Tool Hub — Vice OS")
        self.resize(1140, 760)
        self.setMinimumSize(860, 560)
        self._desktop_dir = _HERE
        self._repo_root = os.path.abspath(os.path.join(_HERE, ".."))
        self._registry = {}
        self._tools = []
        self._categories = list(PREFERRED_CATEGORIES)
        self._selected_category = "All"
        self._cat_buttons = {}
        self._icon_cache = {}
        self._current_cols = 2
        self._pending_tools = []
        self._rendered_count = 0
        self._render_total = 0

        win_icon = load_tool_icon("vice-tool-hub", "view-app-grid")
        if not win_icon.isNull():
            self.setWindowIcon(win_icon)

        self._render_timer = QTimer(self)
        self._render_timer.setInterval(12)
        self._render_timer.timeout.connect(self._render_next_batch)

        self._init_ui()
        self._load_registry(defer_cards=True)
        QTimer.singleShot(0, self._render_cards)

    def _init_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("RootWidget")
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header + Progress card
        self._header = make_header(
            title="Vice Tool Hub",
            subtitle="Curated Vice OS Originals and Debian Bookworm tools",
            icon_name="vice-tool-hub",
            badge_text="425 / 500 (85%)",
            badge_variant="coral",
            parent=root,
        )
        self._counts_lbl = QLabel("Loading registry...", self._header)
        self._counts_lbl.setObjectName("MutedLabel")
        self._header.right_layout.insertWidget(0, self._counts_lbl)
        layout.addWidget(self._header)

        progress_row = QHBoxLayout()
        progress_row.setContentsMargins(2, 0, 2, 0)
        progress_row.setSpacing(10)
        self._progress_bar = QProgressBar(root)
        self._progress_bar.setRange(0, 500)
        self._progress_bar.setValue(425)
        self._progress_bar.setFormat("%v / %m Tools Unlocked (%p%)")
        progress_row.addWidget(self._progress_bar, 1)
        layout.addLayout(progress_row)

        # Search + Mode Filter + Reload
        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(110)
        self._search_timer.timeout.connect(self._render_cards)

        self._search = QLineEdit(root)
        self._search.setPlaceholderText("Search tools by name, package, command, or description...")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(lambda _t: self._search_timer.start())
        filter_row.addWidget(self._search, 1)

        self._type_filter = QComboBox(root)
        self._type_filter.setMinimumWidth(155)
        self._type_filter.addItems(["All Modes", "GTA VI Originals", "GUI Apps", "CLI / TUI Tools"])
        self._type_filter.currentIndexChanged.connect(self._render_cards)
        filter_row.addWidget(self._type_filter)

        reload_btn = make_button("Reload", variant="secondary", icon_name="view-refresh", parent=root)
        reload_btn.clicked.connect(self._load_registry)
        filter_row.addWidget(reload_btn)
        layout.addLayout(filter_row)

        # Responsive Category Pills
        self._cats_host = QWidget(root)
        self._cats_host.setStyleSheet("background: transparent;")
        self._cats_flow = FlowLayout(self._cats_host, h_spacing=6, v_spacing=6)
        self._cats_flow.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._cats_host)

        # Scrollable tool cards grid
        self._scroll = QScrollArea(root)
        self._scroll.setWidgetResizable(True)
        self._cards_host = QWidget()
        self._cards_host.setStyleSheet("background: transparent;")
        self._grid = QGridLayout(self._cards_host)
        self._grid.setContentsMargins(2, 4, 8, 4)
        self._grid.setSpacing(10)
        self._scroll.setWidget(self._cards_host)
        layout.addWidget(self._scroll, 1)

        self._status_lbl = QLabel("Ready.", root)
        self._status_lbl.setObjectName("MutedLabel")
        layout.addWidget(self._status_lbl)

    def _rebuild_category_tabs(self) -> None:
        while self._cats_flow.count():
            item = self._cats_flow.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._cat_buttons.clear()

        discovered = []
        seen = set(PREFERRED_CATEGORIES)
        for tool in self._tools:
            cat = str(tool.get("category", "")).strip()
            if cat and cat not in seen:
                seen.add(cat)
                discovered.append(cat)

        self._categories = list(PREFERRED_CATEGORIES) + discovered
        if self._selected_category not in self._categories:
            self._selected_category = "All"

        for cat in self._categories:
            if cat == "All":
                count = len(self._tools)
            elif cat == "GTA VI Originals":
                count = sum(1 for t in self._tools if t.get("gta_themed") or t.get("category") == cat)
            else:
                count = sum(1 for t in self._tools if t.get("category") == cat)

            # Show standard categories and any non-empty discovered category
            if cat not in PREFERRED_CATEGORIES and count == 0:
                continue

            btn = QPushButton(f"{cat} ({count})".replace("&", "&&"), self._cats_host)
            btn.setObjectName("CatTab")
            btn.setCheckable(True)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            btn.setChecked(cat == self._selected_category)
            btn.clicked.connect(lambda _checked=False, c=cat: self._select_category(c))
            self._cat_buttons[cat] = btn
            self._cats_flow.addWidget(btn)

    def _select_category(self, category: str) -> None:
        self._selected_category = category
        for cat, btn in self._cat_buttons.items():
            btn.setChecked(cat == category)
        self._render_cards()

    def _load_registry(self, defer_cards: bool = False) -> None:
        path = _find_registry_path()
        try:
            with open(path, "r", encoding="utf-8") as fp:
                self._registry = json.load(fp)
            self._tools = list(self._registry.get("tools", []))
        except FileNotFoundError:
            self._registry = {}
            self._tools = []
            self._status_lbl.setText(f"Registry not found at {path}.")
        except Exception as exc:
            self._registry = {}
            self._tools = []
            log_error(f"Failed loading {path}: {exc}")
            self._status_lbl.setText(f"Error reading {path}: {exc}")

        target = int(self._registry.get("target_count") or self._registry.get("total_slots") or 500)
        current = int(next(
            (v for v in (
                self._registry.get("current_count"),
                self._registry.get("implemented_count"),
                len(self._tools),
            ) if v),
            425,
        ))
        batch = self._registry.get("batch", 4)
        theme = self._registry.get("theme", "GTA VI Leonida")
        pct = int(round((current / max(1, target)) * 100))

        self._progress_bar.setMaximum(max(1, target))
        self._progress_bar.setValue(min(current, target))
        self._header.set_badge(f"{current} / {target} ({pct}%)", "coral")

        gta_count = sum(1 for t in self._tools if t.get("gta_themed"))
        power_count = max(0, len(self._tools) - gta_count)
        self._counts_lbl.setText(
            f"Batch {batch} · {gta_count} Originals · {power_count} Debian Tools · {theme}"
        )
        self._search.setPlaceholderText(
            f"Search {len(self._tools)} tools by name, package, command, or description..."
        )

        self._rebuild_category_tabs()
        if defer_cards:
            self._status_lbl.setText(f"Loaded {len(self._tools)} tools from {path}")
        else:
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
        self._render_timer.stop()
        self._pending_tools = []
        self._rendered_count = 0
        self._render_total = 0
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _get_pixmap(self, slug: str) -> QPixmap:
        if slug not in self._icon_cache:
            self._icon_cache[slug] = _resolve_tool_pixmap(slug, 44)
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
            empty.setObjectName("MutedLabel")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 14px; padding: 36px;")
            self._grid.addWidget(empty, 0, 0)
            self._status_lbl.setText(f"Showing 0 of {len(self._tools)} tools.")
            return

        cols = 3 if self.width() >= 1240 else 2
        self._current_cols = cols
        for c in range(cols):
            self._grid.setColumnStretch(c, 1)

        self._pending_tools = filtered
        self._rendered_count = 0
        self._render_total = len(filtered)
        self._render_batch(limit=24)
        if self._pending_tools:
            self._render_timer.start()

    def _render_batch(self, limit: int) -> None:
        cols = self._current_cols
        batch = self._pending_tools[:limit]
        self._pending_tools = self._pending_tools[limit:]
        for tool in batch:
            idx = self._rendered_count
            card = self._build_card(tool)
            row, col = divmod(idx, cols)
            self._grid.addWidget(card, row, col)
            self._rendered_count += 1

        if not self._pending_tools:
            self._render_timer.stop()
            last_row = max(0, (self._render_total - 1) // cols + 1)
            self._grid.setRowStretch(last_row, 1)
            self._status_lbl.setText(f"Showing {self._render_total} of {len(self._tools)} tools.")
        else:
            self._status_lbl.setText(
                f"Loading {self._rendered_count} / {self._render_total} tools..."
            )

    def _render_next_batch(self) -> None:
        self._render_batch(limit=36)

    def _build_card(self, tool: dict) -> QFrame:
        is_gta = bool(tool.get("gta_themed"))
        card = QFrame(self._cards_host)
        card.setObjectName("ToolCard")
        card.setMinimumHeight(142)

        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(14, 12, 14, 12)
        vbox.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(10)

        slug = _tool_slug(tool.get("id", "tool"))
        icon_lbl = QLabel(card)
        icon_lbl.setFixedSize(44, 44)
        icon_lbl.setPixmap(self._get_pixmap(slug))
        head.addWidget(icon_lbl)

        title_box = QVBoxLayout()
        title_box.setSpacing(3)

        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        name_lbl = QLabel(str(tool.get("name", slug)), card)
        name_lbl.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-weight: bold; font-size: 14px;"
        )
        name_lbl.setWordWrap(True)
        title_row.addWidget(name_lbl, 1)

        badge_text = "ORIGINAL" if is_gta else ("CLI" if tool.get("terminal") else "GUI")
        badge_var = "coral" if is_gta else ("aqua" if not tool.get("terminal") else "neutral")
        badge = make_badge(badge_text, badge_var, card)
        title_row.addWidget(badge, 0, Qt.AlignTop)
        title_box.addLayout(title_row)

        pkg_text = str(tool.get("package", "system"))
        cat_text = str(tool.get("category", ""))
        meta_lbl = QLabel(f"{cat_text} · pkg: {pkg_text}", card)
        meta_lbl.setWordWrap(True)
        meta_lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        title_box.addWidget(meta_lbl)
        head.addLayout(title_box, 1)
        vbox.addLayout(head)

        desc_lbl = QLabel(str(tool.get("description", "")), card)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        vbox.addWidget(desc_lbl, 1)

        foot = QHBoxLayout()
        foot.setSpacing(8)
        exec_str = str(tool.get("exec", ""))
        display_cmd = "Native Vice OS App" if is_gta else exec_str
        if len(display_cmd) > 46:
            display_cmd = display_cmd[:43] + "..."
        cmd_lbl = QLabel(display_cmd, card)
        cmd_lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        cmd_lbl.setStyleSheet(
            f"color: {COLORS['text_muted']}; font-family: {MONO_STACK}; font-size: 11px;"
        )
        cmd_lbl.setToolTip(exec_str)
        foot.addWidget(cmd_lbl, 1)

        launch_btn = make_button(
            "Launch",
            variant="primary" if is_gta else "secondary",
            parent=card,
        )
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
            self._status_lbl.setText(f"Launched {name}")
            log_info(f"ViceToolHub launched {name}")
        else:
            self._status_lbl.setText(f"Failed to launch {name} ({launch_prog}).")
            QMessageBox.warning(
                self, "Launch Failed",
                f"Could not start '{name}'.\nCommand: {launch_prog} {' '.join(launch_args)}"
            )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        new_cols = 3 if self.width() >= 1240 else 2
        if new_cols != self._current_cols and self._tools:
            self._render_cards()

    def closeEvent(self, event) -> None:
        self._search_timer.stop()
        self._render_timer.stop()
        event.accept()


def main() -> None:
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    apply_app_theme(app)
    win = ViceToolHub()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
