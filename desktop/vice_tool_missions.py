#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) — Vice Mission Board.
Persistent JSON-backed task and mission manager (~/.local/share/vice-os/missions.json)
with GTA Wanted-Star priority (1-5 stars), status filters, and Markdown/JSON export.
Styled via vice_theme (Noto Sans CJK fallback).
"""

from datetime import datetime
import json
import os
import signal
import sys
import tempfile
import uuid

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QFileDialog, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in ("/opt/vice-os", _HERE, "/opt/vice-os/lib"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from vice_theme import (  # noqa: E402
    apply_app_theme,
    load_tool_icon,
    make_button,
    make_card,
    make_header,
    qcolor,
)

try:
    from python.vice_utils import log_error, log_info  # noqa: E402
except ImportError:
    def log_info(msg: str) -> None:
        print(f"[INFO] {msg}")

    def log_error(msg: str) -> None:
        print(f"[ERROR] {msg}", file=sys.stderr)


MISSIONS_PATH = os.path.expanduser("~/.local/share/vice-os/missions.json")
CATEGORIES = ["System", "Dev", "Security", "Office", "Ops", "Personal"]


def _star_str(level: int) -> str:
    n = max(1, min(5, int(level)))
    return ("★" * n) + ("☆" * (5 - n))


class ViceMissionBoardApp(QMainWindow):
    """Main window for Vice Mission Board."""

    def __init__(self, store_path: str = MISSIONS_PATH):
        super().__init__()
        self.setWindowTitle("Vice Mission Board — Vice OS")
        self.resize(920, 640)
        self.setMinimumSize(740, 480)
        icon = load_tool_icon("vice-tool-missions", "view-pim-tasks")
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

        self._header = make_header(
            title="Vice Mission Board",
            subtitle="Persistent task & wanted-priority objective tracker",
            icon_name="vice-tool-missions",
            badge_text="0 Active",
            badge_variant="coral",
            parent=root,
        )
        layout.addWidget(self._header)

        self._progress = QProgressBar(root)
        self._progress.setRange(0, 100)
        self._progress.setFormat("Completion: %p%")
        layout.addWidget(self._progress)

        # Add Mission Card
        add_card = make_card(parent=root, margins=(12, 10, 12, 10), spacing=8)
        add_row = QHBoxLayout()
        add_row.setSpacing(8)
        self._title_edit = QLineEdit(add_card)
        self._title_edit.setPlaceholderText("New mission objective...")
        self._title_edit.returnPressed.connect(self._add_mission)
        add_row.addWidget(self._title_edit, 2)

        self._notes_edit = QLineEdit(add_card)
        self._notes_edit.setPlaceholderText("Notes / target / details (optional)")
        self._notes_edit.returnPressed.connect(self._add_mission)
        add_row.addWidget(self._notes_edit, 1)

        self._cat_combo = QComboBox(add_card)
        self._cat_combo.addItems(CATEGORIES)
        add_row.addWidget(self._cat_combo)

        self._stars_combo = QComboBox(add_card)
        for s in range(1, 6):
            self._stars_combo.addItem(f"Wanted {s}", s)
        self._stars_combo.setCurrentIndex(2)
        add_row.addWidget(self._stars_combo)

        add_btn = make_button("Add Mission", variant="primary", parent=add_card)
        add_btn.clicked.connect(self._add_mission)
        add_row.addWidget(add_btn)
        add_card.body_layout.addLayout(add_row)
        layout.addWidget(add_card)

        # Filter + Search Row
        flt_row = QHBoxLayout()
        flt_row.setSpacing(8)
        for label in ("All", "Active", "Completed"):
            btn = QPushButton(label, root)
            btn.setObjectName("SegButton")
            btn.setCheckable(True)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setChecked(label == "All")
            btn.clicked.connect(lambda _=False, f=label: self._set_filter(f))
            self._filter_btns[label] = btn
            flt_row.addWidget(btn)

        self._search_edit = QLineEdit(root)
        self._search_edit.setPlaceholderText("Filter missions by title, category, or notes...")
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.textChanged.connect(self._render_table)
        flt_row.addWidget(self._search_edit, 1)

        export_btn = make_button("Export...", variant="secondary", parent=root)
        export_btn.clicked.connect(self._export_missions)
        flt_row.addWidget(export_btn)
        layout.addLayout(flt_row)

        # Missions Table
        self._table = QTableWidget(0, 5, root)
        self._table.setHorizontalHeaderLabels(["Status", "Priority", "Category", "Mission", "Notes"])
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
        toggle_btn = make_button("Toggle Complete", variant="primary", parent=root)
        toggle_btn.clicked.connect(self._toggle_selected)
        act_row.addWidget(toggle_btn)

        bump_btn = make_button("Cycle Priority", variant="secondary", parent=root)
        bump_btn.clicked.connect(self._cycle_stars_selected)
        act_row.addWidget(bump_btn)

        del_btn = make_button("Delete Selected", variant="danger", parent=root)
        del_btn.clicked.connect(self._delete_selected)
        act_row.addWidget(del_btn)

        act_row.addStretch(1)

        self._stats_lbl = QLabel("0 Total", root)
        self._stats_lbl.setObjectName("MutedLabel")
        act_row.addWidget(self._stats_lbl)

        clear_btn = make_button("Clear Completed", variant="secondary", parent=root)
        clear_btn.clicked.connect(self._clear_completed)
        act_row.addWidget(clear_btn)
        layout.addLayout(act_row)

    def _default_missions(self) -> list:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        return [
            {
                "id": str(uuid.uuid4()),
                "title": "Explore Vice Tool Hub (425 / 500)",
                "notes": "Browse GTA VI Originals, Office Studio, and Security tools",
                "category": "System",
                "stars": 5,
                "completed": False,
                "created_at": now,
            },
            {
                "id": str(uuid.uuid4()),
                "title": "Check VPN, Tor & DNS in Vice Net Shield",
                "notes": "Configure secure DNS or WireGuard/OpenVPN tunnel on demand",
                "category": "Security",
                "stars": 4,
                "completed": False,
                "created_at": now,
            },
            {
                "id": str(uuid.uuid4()),
                "title": "Sync Host Clock & Timezone",
                "notes": "Verify VirtualBox host time and local IANA timezone in Clock Sync",
                "category": "Ops",
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
            col = qcolor("text_muted") if done else qcolor("text_primary")
            for idx, it in enumerate(items):
                if idx == 1 and not done:
                    it.setForeground(qcolor("accent_gold"))
                elif idx == 0:
                    it.setForeground(qcolor("success") if done else qcolor("accent_coral"))
                else:
                    it.setForeground(col)
                self._table.setItem(row, idx, it)

        total = len(self._missions)
        completed = sum(1 for m in self._missions if m.get("completed"))
        active = total - completed
        pct = int(round((completed / total) * 100)) if total else 0
        self._progress.setValue(pct)
        self._header.set_badge(f"{active} Active · {completed} Done", "coral" if active else "success")
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
    apply_app_theme(app)
    win = ViceMissionBoardApp()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
