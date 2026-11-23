#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) — Vice Mission Board.
Persistent JSON-backed task and mission manager (~/.local/share/vice-os/missions.json)
with GTA Wanted-Star priority (1-5 stars), status filters, and Markdown/JSON export.
"""

from datetime import datetime
import json
import os
import signal
import sys
import tempfile
import uuid

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QIcon, QPixmap
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QFileDialog, QFrame,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QProgressBar, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget
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

MISSIONS_PATH = os.path.expanduser("~/.local/share/vice-os/missions.json")
CATEGORIES = ["System", "Dev", "Security", "Ops", "Personal"]

STYLE = """
QMainWindow, QWidget#RootWidget {
    background-color: #120e1e;
    color: #f4f1fa;
    font-family: "Noto Sans", "Noto Sans CJK JP", "Noto Sans CJK SC", "Noto Sans CJK TC", "Noto Sans CJK KR", "DejaVu Sans", sans-serif;
    font-size: 13px;
}
QFrame#Banner {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #201435, stop:0.55 #2c153c, stop:1 #16223a);
    border: 1px solid #ff8a5b;
    border-radius: 12px;
}
QProgressBar {
    background-color: #161028;
    border: 1px solid #43346b;
    border-radius: 7px;
    height: 14px;
    text-align: center;
    color: #ffffff;
    font-weight: bold;
}
QProgressBar::chunk {
    border-radius: 6px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #ffd166, stop:0.5 #ff8a5b, stop:1 #ff4da6);
}
QLineEdit, QComboBox {
    background-color: #1b152e;
    color: #f4f1fa;
    border: 1px solid #3c2e5e;
    border-radius: 8px;
    padding: 7px 10px;
}
QLineEdit:focus {
    border-color: #ffd166;
}
QPushButton {
    background-color: #1f1836;
    color: #ffd166;
    border: 1px solid #ff8a5b;
    border-radius: 8px;
    padding: 7px 14px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #ff8a5b;
    color: #120e1e;
}
QPushButton#FilterBtn {
    color: #cfc6e6;
    border-color: #3c2e5e;
}
QPushButton#FilterBtn:checked {
    background-color: #3a1f47;
    color: #ffd166;
    border-color: #ff4da6;
}
QPushButton#DeleteBtn {
    color: #ff6b8b;
    border-color: #ff6b8b;
}
QPushButton#DeleteBtn:hover {
    background-color: #ff6b8b;
    color: #120e1e;
}
QTableWidget {
    background-color: #151025;
    color: #f4f1fa;
    border: 1px solid #382b57;
    border-radius: 10px;
    gridline-color: #292042;
}
QTableWidget::item:selected {
    background-color: #34214d;
    color: #ffd166;
}
QHeaderView::section {
    background-color: #1e1633;
    color: #00e5ff;
    border: none;
    border-bottom: 1px solid #3c2e5e;
    padding: 8px;
    font-weight: bold;
}
"""


def _configure_cjk_fonts(app: QApplication) -> None:
    for fam in ("Noto Sans", "DejaVu Sans", "Sans", "sans-serif"):
        QFont.insertSubstitutions(fam, CJK_FONTS)
    font = QFont("Noto Sans", 10)
    if hasattr(font, "setFamilies"):
        font.setFamilies(CJK_FONTS)
    app.setFont(font)


def _load_app_icon() -> QIcon:
    for path in (
        "/usr/share/icons/hicolor/64x64/apps/vice-tool-missions.png",
        "/usr/share/pixmaps/vice-tool-missions.png",
    ):
        if os.path.isfile(path):
            pm = QPixmap(path)
            if not pm.isNull():
                return QIcon(pm)
    return QIcon.fromTheme("view-pim-tasks")


def _star_str(level: int) -> str:
    n = max(1, min(5, int(level)))
    return ("★" * n) + ("☆" * (5 - n))


class ViceMissionBoardApp(QMainWindow):
    """Main window for Vice Mission Board."""

    def __init__(self, store_path: str = MISSIONS_PATH):
        super().__init__()
        self.setWindowTitle("Vice Mission Board — Leonida Tasks")
        self.resize(900, 620)
        self.setMinimumSize(720, 480)
        icon = _load_app_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)

        self._store_path = store_path
        self._missions = []
        self._status_filter = "All"
        self._filter_btns = {}

        self._init_ui()
        self._load_missions()

    def _init_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("RootWidget")
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.setSpacing(12)

        # Header banner
        banner = QFrame(root)
        banner.setObjectName("Banner")
        bv = QVBoxLayout(banner)
        bv.setContentsMargins(16, 12, 16, 12)
        bv.setSpacing(8)

        bh = QHBoxLayout()
        title = QLabel("VICE MISSION BOARD · WANTED PRIORITY TRACKER", banner)
        title.setStyleSheet("color: #ffd166; font-size: 19px; font-weight: bold; background: transparent;")
        bh.addWidget(title)
        bh.addStretch(1)
        self._stats_lbl = QLabel("0 Active · 0 Completed", banner)
        self._stats_lbl.setStyleSheet("color: #00e5ff; font-weight: bold; background: transparent;")
        bh.addWidget(self._stats_lbl)
        bv.addLayout(bh)

        self._progress = QProgressBar(banner)
        self._progress.setRange(0, 100)
        self._progress.setFormat("Mission Completion: %p%")
        bv.addWidget(self._progress)
        layout.addWidget(banner)

        # Add Mission Row
        add_row = QHBoxLayout()
        add_row.setSpacing(8)
        self._title_edit = QLineEdit(root)
        self._title_edit.setPlaceholderText("New mission objective...")
        self._title_edit.returnPressed.connect(self._add_mission)
        add_row.addWidget(self._title_edit, 2)

        self._notes_edit = QLineEdit(root)
        self._notes_edit.setPlaceholderText("Notes / target / details (optional)")
        self._notes_edit.returnPressed.connect(self._add_mission)
        add_row.addWidget(self._notes_edit, 1)

        self._cat_combo = QComboBox(root)
        self._cat_combo.addItems(CATEGORIES)
        add_row.addWidget(self._cat_combo)

        self._stars_combo = QComboBox(root)
        for s in range(1, 6):
            self._stars_combo.addItem(f"{s}★", s)
        self._stars_combo.setCurrentIndex(2)
        add_row.addWidget(self._stars_combo)

        add_btn = QPushButton("Add Mission", root)
        add_btn.clicked.connect(self._add_mission)
        add_row.addWidget(add_btn)
        layout.addLayout(add_row)

        # Filter + Search Row
        flt_row = QHBoxLayout()
        flt_row.setSpacing(8)
        for label in ("All", "Active", "Completed"):
            btn = QPushButton(label, root)
            btn.setObjectName("FilterBtn")
            btn.setCheckable(True)
            btn.setChecked(label == "All")
            btn.clicked.connect(lambda _=False, f=label: self._set_filter(f))
            self._filter_btns[label] = btn
            flt_row.addWidget(btn)

        self._search_edit = QLineEdit(root)
        self._search_edit.setPlaceholderText("Filter missions...")
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.textChanged.connect(self._render_table)
        flt_row.addWidget(self._search_edit, 1)

        export_btn = QPushButton("Export...", root)
        export_btn.clicked.connect(self._export_missions)
        flt_row.addWidget(export_btn)
        layout.addLayout(flt_row)

        # Missions Table
        self._table = QTableWidget(0, 5, root)
        self._table.setHorizontalHeaderLabels(["Status", "Wanted", "Category", "Mission", "Notes"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self._table.itemDoubleClicked.connect(lambda _it: self._toggle_selected())
        layout.addWidget(self._table, 1)

        # Action Row
        act_row = QHBoxLayout()
        act_row.setSpacing(8)
        toggle_btn = QPushButton("Toggle Complete", root)
        toggle_btn.clicked.connect(self._toggle_selected)
        act_row.addWidget(toggle_btn)

        bump_btn = QPushButton("Cycle Wanted ★", root)
        bump_btn.clicked.connect(self._cycle_stars_selected)
        act_row.addWidget(bump_btn)

        del_btn = QPushButton("Delete Selected", root)
        del_btn.setObjectName("DeleteBtn")
        del_btn.clicked.connect(self._delete_selected)
        act_row.addWidget(del_btn)

        act_row.addStretch(1)

        clear_btn = QPushButton("Clear Completed", root)
        clear_btn.clicked.connect(self._clear_completed)
        act_row.addWidget(clear_btn)
        layout.addLayout(act_row)

    def _default_missions(self) -> list:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        return [
            {
                "id": str(uuid.uuid4()),
                "title": "Explore Vice Tool Hub (100 / 500 Batch 1)",
                "notes": "Browse GTA VI Originals and Debian power utilities",
                "category": "System",
                "stars": 5,
                "completed": False,
                "created_at": now,
            },
            {
                "id": str(uuid.uuid4()),
                "title": "Tune Leonida FM Radio & Verify Audio",
                "notes": "Test PipeWire playback on Vice Sunset 104.5 FM",
                "category": "Ops",
                "stars": 4,
                "completed": False,
                "created_at": now,
            },
            {
                "id": str(uuid.uuid4()),
                "title": "Encrypt Sensitive Keys with Vice Vault",
                "notes": "AES-256-CBC PBKDF2 protection",
                "category": "Security",
                "stars": 3,
                "completed": False,
                "created_at": now,
            },
        ]

    def _load_missions(self) -> None:
        if os.path.isfile(self._store_path):
            try:
                with open(self._store_path, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                if isinstance(data, dict) and isinstance(data.get("missions"), list):
                    self._missions = data["missions"]
                elif isinstance(data, list):
                    self._missions = data
                else:
                    self._missions = self._default_missions()
            except Exception as exc:
                log_error(f"Corrupt missions.json, resetting cleanly: {exc}")
                self._missions = self._default_missions()
        else:
            self._missions = self._default_missions()
            self._save_missions()
        self._render_table()

    def _save_missions(self) -> None:
        parent = os.path.dirname(self._store_path)
        os.makedirs(parent, exist_ok=True)
        payload = {"missions": self._missions}
        fd, tmp_path = tempfile.mkstemp(prefix="missions_", suffix=".tmp", dir=parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fp:
                json.dump(payload, fp, indent=2, ensure_ascii=False)
                fp.write("\n")
            os.replace(tmp_path, self._store_path)
        except Exception as exc:
            log_error(f"Failed saving missions: {exc}")
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    def _set_filter(self, label: str) -> None:
        self._status_filter = label
        for name, btn in self._filter_btns.items():
            btn.setChecked(name == label)
        self._render_table()

    def _filtered_missions(self) -> list:
        query = self._search_edit.text().strip().lower()
        out = []
        for m in self._missions:
            done = bool(m.get("completed"))
            if self._status_filter == "Active" and done:
                continue
            if self._status_filter == "Completed" and not done:
                continue
            if query:
                hay = f"{m.get('title', '')} {m.get('notes', '')} {m.get('category', '')}".lower()
                if query not in hay:
                    continue
            out.append(m)
        out.sort(key=lambda x: (bool(x.get("completed")), -int(x.get("stars", 1))))
        return out

    def _render_table(self) -> None:
        self._table.setRowCount(0)
        rows = self._filtered_missions()
        for m in rows:
            row = self._table.rowCount()
            self._table.insertRow(row)
            done = bool(m.get("completed"))
            stars = int(m.get("stars", 1))
            items = [
                QTableWidgetItem("DONE" if done else "ACTIVE"),
                QTableWidgetItem(_star_str(stars)),
                QTableWidgetItem(str(m.get("category", "System"))),
                QTableWidgetItem(str(m.get("title", ""))),
                QTableWidgetItem(str(m.get("notes", ""))),
            ]
            items[0].setData(Qt.UserRole, m.get("id"))
            col = QColor("#8f84ad") if done else QColor("#f4f1fa")
            for idx, it in enumerate(items):
                if idx == 1 and not done:
                    it.setForeground(QColor("#ffd166"))
                elif idx == 0:
                    it.setForeground(QColor("#64ffda" if done else "#ff4da6"))
                else:
                    it.setForeground(col)
                self._table.setItem(row, idx, it)

        total = len(self._missions)
        completed = sum(1 for m in self._missions if m.get("completed"))
        active = total - completed
        pct = int(round((completed / total) * 100)) if total else 0
        self._progress.setValue(pct)
        self._stats_lbl.setText(f"{active} Active · {completed} Completed · {total} Total")

    def _selected_mission_id(self):
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return item.data(Qt.UserRole) if item is not None else None

    def _add_mission(self) -> None:
        title = self._title_edit.text().strip()
        if not title:
            return
        mission = {
            "id": str(uuid.uuid4()),
            "title": title,
            "notes": self._notes_edit.text().strip(),
            "category": self._cat_combo.currentText(),
            "stars": int(self._stars_combo.currentData()),
            "completed": False,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        self._missions.append(mission)
        self._title_edit.clear()
        self._notes_edit.clear()
        self._save_missions()
        self._render_table()
        log_info(f"Added mission: {title}")

    def _toggle_selected(self) -> None:
        mid = self._selected_mission_id()
        if not mid:
            return
        for m in self._missions:
            if m.get("id") == mid:
                m["completed"] = not bool(m.get("completed"))
                break
        self._save_missions()
        self._render_table()

    def _cycle_stars_selected(self) -> None:
        mid = self._selected_mission_id()
        if not mid:
            return
        for m in self._missions:
            if m.get("id") == mid:
                m["stars"] = (int(m.get("stars", 1)) % 5) + 1
                break
        self._save_missions()
        self._render_table()

    def _delete_selected(self) -> None:
        mid = self._selected_mission_id()
        if not mid:
            return
        self._missions = [m for m in self._missions if m.get("id") != mid]
        self._save_missions()
        self._render_table()

    def _clear_completed(self) -> None:
        self._missions = [m for m in self._missions if not m.get("completed")]
        self._save_missions()
        self._render_table()

    def _export_missions(self) -> None:
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Missions",
            os.path.expanduser("~/vice-missions.md"),
            "Markdown (*.md);;JSON (*.json)",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="\n") as fp:
                if path.endswith(".json") or "JSON" in selected_filter:
                    json.dump({"missions": self._missions}, fp, indent=2, ensure_ascii=False)
                    fp.write("\n")
                else:
                    fp.write("# Vice OS — Leonida Mission Board\n\n")
                    for m in self._missions:
                        mark = "x" if m.get("completed") else " "
                        stars = _star_str(int(m.get("stars", 1)))
                        line = f"- [{mark}] {stars} **[{m.get('category', 'System')}]** {m.get('title', '')}"
                        if m.get("notes"):
                            line += f" — {m['notes']}"
                        fp.write(line + "\n")
            QMessageBox.information(self, "Exported", f"Missions saved to:\n{path}")
        except OSError as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))

    def closeEvent(self, event) -> None:
        self._save_missions()
        event.accept()


def main() -> None:
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    _configure_cjk_fonts(app)
    app.setStyleSheet(STYLE)
    win = ViceMissionBoardApp()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
