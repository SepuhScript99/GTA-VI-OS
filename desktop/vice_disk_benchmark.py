#!/usr/bin/env python3
"""Vice OS — Disk Benchmark. dd-based read/write tests with results history."""

import sys
import os
import subprocess
import json
import datetime

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QComboBox, QLineEdit, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QTextEdit, QMessageBox, QProgressBar, QAbstractItemView
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QBrush

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 960
WINDOW_HEIGHT = 600

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: "Noto Sans Mono CJK JP", "Noto Sans CJK JP", "Noto Sans CJK SC", monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 6px 16px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QComboBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 4px; }
QLineEdit { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px; }
QTextEdit { background: #0d0d0d; color: #aaffff; border: 1px solid #1a4a4a; font-size: 11px; }
QTableWidget { background: #0d0d0d; color: #00ffff; gridline-color: #1a4a4a; border: 1px solid #00ffff; }
QHeaderView::section { background: #00ffff; color: #0a0a0a; padding: 4px; font-weight: bold; }
QTableWidget::item:selected { background: #003333; color: #00ffff; }
QTabBar::tab { background: #1a1a1a; color: #00ffff; padding: 6px 14px; }
QTabBar::tab:selected { background: #00ffff; color: #0a0a0a; }
QTabWidget::pane { border: 1px solid #00ffff; }
QProgressBar { border: 1px solid #00ffff; background: #1a1a1a; text-align: center; color: #00ffff; }
QProgressBar::chunk { background: #00ffff; }
QLabel { color: #00ffff; }
"""

HISTORY_FILE = os.path.expanduser("~/.local/share/vice-os/disk_bench_history.json")
TEST_FILE_DEFAULT = "/tmp/vice_bench_test"
SIZES_MB = [25, 100, 256, 512, 1024]


def get_mounts():
    """Return a list of (device, mountpoint) for real filesystems."""
    try:
        out = subprocess.check_output(
            ["df", "-h", "--output=source,size,target"],
            text=True, timeout=5
        ).splitlines()[1:]
    except Exception:
        return []
    mounts = []
    for line in out:
        parts = line.split()
        if len(parts) < 3:
            continue
        source, size, target = parts[0], parts[1], parts[2]
        if any(x in source for x in ("tmpfs", "udev", "loop", "devtmpfs", "efivarfs")):
            continue
        mounts.append((f"{source} ({size}) — {target}", target))
    return mounts


class BenchWorker(QThread):
    """Runs one dd benchmark. Writes then reads a temp file."""
    line = pyqtSignal(str)
    finished = pyqtSignal(bool, dict)

    def __init__(self, mode, test_file, size_mb, target_dir):
        super().__init__()
        self._mode = mode  # 'write' or 'read'
        self._test_file = test_file
        self._size_mb = size_mb
        self._target_dir = target_dir

    def _run_dd(self, args, timeout=300):
        proc = subprocess.Popen(args, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True)
        output = []
        for line in proc.stdout:
            output.append(line.rstrip())
        proc.wait()
        return proc.returncode, "\n".join(output)

    def run(self):
        bs = "1M"
        count = str(self._size_mb)
        result = {"mode": self._mode, "size_mb": self._size_mb,
                  "target": self._target_dir, "speed": "", "time": ""}

        if self._mode == "write":
            self.line.emit(f"$ dd if=/dev/zero of={self._test_file} bs={bs} count={count} oflag=direct conv=fdatasync")
            code, out = self._run_dd(
                ["dd", "if=/dev/zero", f"of={self._test_file}", f"bs={bs}",
                 f"count={count}", "oflag=direct", "conv=fdatasync"]
            )
        else:
            self.line.emit(f"$ dd if={self._test_file} of=/dev/null bs={bs} iflag=direct")
            code, out = self._run_dd(
                ["dd", f"if={self._test_file}", "of=/dev/null", f"bs={bs}",
                 "iflag=direct"]
            )

        for line in out.splitlines():
            self.line.emit(line)

        # Parse dd speed: "1073741824 bytes (1.1 GB, 1.0 GiB) copied, 2.5 s, 429 MB/s"
        import re
        m = re.search(r"copied,\s*([\d.]+)\s*s,\s*([\d.]+\s*[MG]B/s)", out)
        if m:
            result["time"] = m.group(1) + "s"
            result["speed"] = m.group(2)
        elif code == 0:
            # oflag=direct may be unsupported on some FS; retry without
            self.line.emit("[WARN] direct I/O failed; retrying buffered...")
            if self._mode == "write":
                code, out = self._run_dd(
                    ["dd", "if=/dev/zero", f"of={self._test_file}", f"bs={bs}",
                     f"count={count}", "conv=fdatasync"]
                )
            else:
                code, out = self._run_dd(
                    ["dd", f"if={self._test_file}", "of=/dev/null", f"bs={bs}"]
                )
            for line in out.splitlines():
                self.line.emit(line)
            m = re.search(r"copied,\s*([\d.]+)\s*s,\s*([\d.]+\s*[MG]B/s)", out)
            if m:
                result["time"] = m.group(1) + "s"
                result["speed"] = m.group(2)

        ok = code == 0 and bool(result["speed"])
        self.finished.emit(ok, result)


def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE) as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_history(entries):
    try:
        os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
        with open(HISTORY_FILE, "w") as f:
            json.dump(entries[-100:], f, indent=2)
    except Exception as e:
        log_error(f"Bench history save failed: {e}")


class DiskBenchmark(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Disk Benchmark")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._worker = None
        self._init_ui()
        self._load_mounts()
        self._load_history_table()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Disk Benchmark")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 13, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        # Test config
        cfg_row = QHBoxLayout()
        cfg_row.addWidget(QLabel("Target:"))
        self._mount_combo = QComboBox()
        self._mount_combo.currentIndexChanged.connect(self._on_target_changed)
        cfg_row.addWidget(self._mount_combo, 1)

        cfg_row.addWidget(QLabel("Size:"))
        self._size_combo = QComboBox()
        for s in SIZES_MB:
            self._size_combo.addItem(f"{s} MB" if s < 1024 else "1 GB")
        self._size_combo.setCurrentIndex(2)
        cfg_row.addWidget(self._size_combo)
        root.addLayout(cfg_row)

        # Buttons
        btn_row = QHBoxLayout()
        write_btn = QPushButton("Write Test")
        write_btn.setStyleSheet("QPushButton { border-color: #ff00ff; color: #ff00ff; } QPushButton:hover { background: #ff00ff; color: #0a0a0a; }")
        write_btn.clicked.connect(lambda: self._run_bench("write"))
        btn_row.addWidget(write_btn)

        read_btn = QPushButton("Read Test")
        read_btn.setStyleSheet("QPushButton { border-color: #00ff88; color: #00ff88; } QPushButton:hover { background: #00ff88; color: #0a0a0a; }")
        read_btn.clicked.connect(lambda: self._run_bench("read"))
        btn_row.addWidget(read_btn)

        both_btn = QPushButton("Run Both")
        both_btn.clicked.connect(self._run_both)
        btn_row.addWidget(both_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        # Big result
        self._result_label = QLabel("—")
        self._result_label.setFont(QFont("monospace", 22, QFont.Bold))
        self._result_label.setStyleSheet("color: #00ffff; border: none;")
        self._result_label.setAlignment(Qt.AlignCenter)
        root.addWidget(self._result_label)

        tabs = QTabWidget()
        root.addWidget(tabs, 1)

        # Log tab
        log_tab = QWidget()
        ll = QVBoxLayout(log_tab)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        ll.addWidget(self._log)
        tabs.addTab(log_tab, "Output")

        # History tab
        hist_tab = QWidget()
        hl = QVBoxLayout(hist_tab)
        self._hist_table = QTableWidget()
        self._hist_table.setColumnCount(5)
        self._hist_table.setHorizontalHeaderLabels(["Time", "Target", "Test", "Size", "Speed"])
        self._hist_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._hist_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for i in [2, 3, 4]:
            self._hist_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self._hist_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._hist_table.setEditTriggers(QTableWidget.NoEditTriggers)
        hl.addWidget(self._hist_table)
        clear_row = QHBoxLayout()
        clear_btn = QPushButton("Clear History")
        clear_btn.setStyleSheet("QPushButton { border-color: #ff4444; color: #ff4444; } QPushButton:hover { background: #ff4444; color: #0a0a0a; }")
        clear_btn.clicked.connect(self._clear_history)
        clear_row.addWidget(clear_btn)
        clear_row.addStretch()
        hl.addLayout(clear_row)
        tabs.addTab(hist_tab, "History")

        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self._status)

    def _load_mounts(self):
        self._mount_combo.clear()
        for label, mount in get_mounts():
            self._mount_combo.addItem(label, mount)

    def _on_target_changed(self):
        pass

    def _get_test_dir(self):
        mount = self._mount_combo.currentData()
        if not mount:
            QMessageBox.warning(self, "No Target", "Select a target disk first.")
            return None
        return mount

    def _run_bench(self, mode):
        test_dir = self._get_test_dir()
        if not test_dir:
            return
        size_mb = SIZES_MB[self._size_combo.currentIndex()]
        test_file = os.path.join(test_dir, os.path.basename(TEST_FILE_DEFAULT))

        # Sanity: check free space before write test
        if mode == "write":
            try:
                free = shutil_disk_usage(test_dir)
                if free < size_mb * 1024 * 1024 * 1.2:
                    QMessageBox.warning(
                        self, "Insufficient Space",
                        f"Not enough free space on {test_dir} for a {size_mb} MB test."
                    )
                    return
            except Exception:
                pass

        self._progress.setVisible(True)
        self._result_label.setText("...")
        self._status.setText(f"Running {mode} test on {test_dir}...")
        self._worker = BenchWorker(mode, test_file, size_mb, test_dir)
        self._worker.line.connect(self._log.append)
        self._worker.finished.connect(self._bench_done)
        self._worker.start()

    def _run_both(self):
        test_dir = self._get_test_dir()
        if not test_dir:
            return
        self._pending_read = True
        self._run_bench("write")

    def _bench_done(self, ok, result):
        self._progress.setVisible(False)
        if ok:
            speed = result["speed"]
            mode = result["mode"].upper()
            self._result_label.setText(f"{mode}: {speed}")
            self._status.setText(f"{result['mode'].title()} test complete: {speed}")

            history = load_history()
            history.append({
                "time": datetime.datetime.now().isoformat(timespec="seconds"),
                "target": result["target"],
                "mode": result["mode"],
                "size_mb": result["size_mb"],
                "speed": speed,
            })
            save_history(history)
            self._load_history_table()
            log_info(f"Disk bench {result['mode']}: {speed} on {result['target']}")

            # Chain: after a write test, run the read test on the same file
            if getattr(self, "_pending_read", False):
                self._pending_read = False
                self._log.append("")
                self._run_bench("read")
                return
        else:
            self._result_label.setText("FAILED")
            self._status.setText("Benchmark failed — check output")

        # Cleanup test file after read completes or failure
        self._cleanup()

    def _cleanup(self):
        test_dir = self._mount_combo.currentData()
        if not test_dir:
            return
        test_file = os.path.join(test_dir, os.path.basename(TEST_FILE_DEFAULT))
        if os.path.exists(test_file):
            try:
                os.remove(test_file)
                self._log.append(f"[CLEANUP] Removed {test_file}")
            except Exception as e:
                self._log.append(f"[WARN] Could not remove {test_file}: {e}")

    def _load_history_table(self):
        self._hist_table.setRowCount(0)
        for entry in reversed(load_history()):
            row = self._hist_table.rowCount()
            self._hist_table.insertRow(row)
            self._hist_table.setItem(row, 0, QTableWidgetItem(entry.get("time", "")))
            self._hist_table.setItem(row, 1, QTableWidgetItem(entry.get("target", "")))
            mode_item = QTableWidgetItem(entry.get("mode", ""))
            mode_item.setForeground(QBrush(QColor(
                "#ff00ff" if entry.get("mode") == "write" else "#00ff88")))
            self._hist_table.setItem(row, 2, mode_item)
            self._hist_table.setItem(row, 3, QTableWidgetItem(f"{entry.get('size_mb', '')} MB"))
            self._hist_table.setItem(row, 4, QTableWidgetItem(entry.get("speed", "")))

    def _clear_history(self):
        if QMessageBox.question(self, "Clear", "Delete all benchmark history?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        save_history([])
        self._load_history_table()


def shutil_disk_usage(path):
    import shutil
    return shutil.disk_usage(path).free


def main():
    app = QApplication(sys.argv)
    win = DiskBenchmark()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()