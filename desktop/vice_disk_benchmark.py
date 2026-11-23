#!/usr/bin/env python3
"""Vice OS — Disk Benchmark. dd-based read/write tests with results history."""

import datetime
import json
import os
import re
import shutil
import subprocess
import sys

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QComboBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QTextEdit, QMessageBox, QProgressBar, QAbstractItemView
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QBrush

sys.path.insert(0, "/opt/vice-os/lib")
sys.path.insert(0, "/opt/vice-os")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from python.vice_utils import log_info, log_error  # noqa: E402
from vice_theme import (  # noqa: E402
    COLORS,
    MONO_STACK,
    apply_app_theme,
    make_button,
    make_header,
)

WINDOW_WIDTH = 960
WINDOW_HEIGHT = 620

HISTORY_FILE = os.path.expanduser("~/.local/share/vice-os/disk_bench_history.json")
TEST_FILE_DEFAULT = ".vice_bench_test"
SIZES_MB = [25, 100, 256, 512, 1024]


def get_mounts():
    """Return writable home folder plus mounted physical filesystems."""
    home = os.path.expanduser("~")
    mounts = [(f"Home Directory ({home})", home)]
    try:
        out = subprocess.check_output(
            ["df", "-h", "--output=source,size,target"],
            text=True, timeout=5
        ).splitlines()[1:]
    except Exception:
        return mounts
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
        self._mode = mode
        self._test_file = test_file
        self._size_mb = size_mb
        self._target_dir = target_dir
        self._stopped = False
        self._proc = None

    def stop(self):
        self._stopped = True
        proc = self._proc
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=0.3)
            except Exception:
                try:
                    proc.kill()
                except OSError:
                    pass

    def _run_dd(self, args, timeout=300):
        try:
            self._proc = subprocess.Popen(
                args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            out, _ = self._proc.communicate(timeout=timeout)
            return self._proc.returncode, (out or "").strip()
        except subprocess.TimeoutExpired:
            if self._proc is not None:
                self._proc.kill()
                self._proc.communicate()
            return 1, f"dd timed out after {timeout}s"
        except Exception as exc:
            return 1, str(exc)
        finally:
            self._proc = None

    def run(self):
        bs = "1M"
        count = str(self._size_mb)
        result = {
            "mode": self._mode,
            "size_mb": self._size_mb,
            "target": self._target_dir,
            "speed": "",
            "time": "",
        }

        if self._mode == "write":
            self.line.emit(f"$ dd if=/dev/zero of={self._test_file} bs={bs} count={count} oflag=direct conv=fdatasync")
            code, out = self._run_dd(
                ["dd", "if=/dev/zero", f"of={self._test_file}", f"bs={bs}", f"count={count}", "oflag=direct", "conv=fdatasync"]
            )
        else:
            self.line.emit(f"$ dd if={self._test_file} of=/dev/null bs={bs} iflag=direct")
            code, out = self._run_dd(
                ["dd", f"if={self._test_file}", "of=/dev/null", f"bs={bs}", "iflag=direct"]
            )

        if self._stopped:
            return
        for line in out.splitlines():
            self.line.emit(line)

        m = re.search(r"copied,\s*([\d.]+)\s*s,\s*([\d.]+\s*[KMG]B/s)", out)
        if m:
            result["time"] = m.group(1) + "s"
            result["speed"] = m.group(2)
        elif code == 0:
            self.line.emit("[WARN] direct I/O failed; retrying buffered...")
            if self._mode == "write":
                code, out = self._run_dd(
                    ["dd", "if=/dev/zero", f"of={self._test_file}", f"bs={bs}", f"count={count}", "conv=fdatasync"]
                )
            else:
                code, out = self._run_dd(
                    ["dd", f"if={self._test_file}", "of=/dev/null", f"bs={bs}"]
                )
            if self._stopped:
                return
            for line in out.splitlines():
                self.line.emit(line)
            m = re.search(r"copied,\s*([\d.]+)\s*s,\s*([\d.]+\s*[KMG]B/s)", out)
            if m:
                result["time"] = m.group(1) + "s"
                result["speed"] = m.group(2)

        ok = code == 0 and bool(result["speed"])
        if not self._stopped:
            self.finished.emit(ok, result)


def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_history(entries):
    try:
        os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
        with open(HISTORY_FILE, "w", encoding="utf-8", newline="\n") as f:
            json.dump(entries[-100:], f, indent=2)
    except Exception as e:
        log_error(f"Bench history save failed: {e}")


class DiskBenchmark(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Disk Benchmark")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(760, 500)
        apply_app_theme(self)
        self._worker = None
        self._pending_read = False
        self._init_ui()
        self._load_mounts()
        self._load_history_table()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 14)
        root.setSpacing(10)

        header = make_header(
            title="Disk Benchmark",
            subtitle="Sequential read and write throughput benchmarks via dd with history tracking",
            icon_name="drive-harddisk",
            badge_text="DISK I/O",
            badge_variant="aqua",
            parent=self,
        )
        root.addWidget(header)

        cfg_row = QHBoxLayout()
        cfg_row.addWidget(QLabel("Target:"))
        self._mount_combo = QComboBox()
        cfg_row.addWidget(self._mount_combo, 1)

        cfg_row.addWidget(QLabel("Size:"))
        self._size_combo = QComboBox()
        for s in SIZES_MB:
            self._size_combo.addItem(f"{s} MB" if s < 1024 else "1 GB")
        self._size_combo.setCurrentIndex(2)
        cfg_row.addWidget(self._size_combo)
        root.addLayout(cfg_row)

        btn_row = QHBoxLayout()
        write_btn = make_button("Write Test", variant="secondary", parent=self)
        write_btn.clicked.connect(lambda: self._run_bench("write"))
        btn_row.addWidget(write_btn)

        read_btn = make_button("Read Test", variant="secondary", parent=self)
        read_btn.clicked.connect(lambda: self._run_bench("read"))
        btn_row.addWidget(read_btn)

        both_btn = make_button("Run Both", variant="primary", parent=self)
        both_btn.clicked.connect(self._run_both)
        btn_row.addWidget(both_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        self._result_label = QLabel("—")
        self._result_label.setStyleSheet(
            f"font-family: {MONO_STACK}; font-size: 22px; font-weight: bold; color: {COLORS['accent_aqua']};"
        )
        self._result_label.setAlignment(Qt.AlignCenter)
        root.addWidget(self._result_label)

        tabs = QTabWidget()
        root.addWidget(tabs, 1)

        log_tab = QWidget()
        ll = QVBoxLayout(log_tab)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        ll.addWidget(self._log)
        tabs.addTab(log_tab, "Output")

        hist_tab = QWidget()
        hl = QVBoxLayout(hist_tab)
        self._hist_table = QTableWidget()
        self._hist_table.setColumnCount(5)
        self._hist_table.setHorizontalHeaderLabels(["Time", "Target", "Test", "Size", "Speed"])
        self._hist_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._hist_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for i in (2, 3, 4):
            self._hist_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self._hist_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._hist_table.setEditTriggers(QTableWidget.NoEditTriggers)
        hl.addWidget(self._hist_table)
        clear_row = QHBoxLayout()
        clear_btn = make_button("Clear History", variant="danger", parent=self)
        clear_btn.clicked.connect(self._clear_history)
        clear_row.addWidget(clear_btn)
        clear_row.addStretch()
        hl.addLayout(clear_row)
        tabs.addTab(hist_tab, "History")

        self._status = QLabel("Ready")
        self._status.setObjectName("MutedLabel")
        root.addWidget(self._status)

    def _load_mounts(self):
        self._mount_combo.clear()
        for label, mount in get_mounts():
            self._mount_combo.addItem(label, mount)

    def _get_test_dir(self):
        mount = self._mount_combo.currentData()
        if not mount:
            QMessageBox.warning(self, "No Target", "Select a target disk first.")
            return None
        return mount

    def _run_bench(self, mode):
        if self._worker is not None and self._worker.isRunning():
            self._status.setText("Benchmark already running...")
            return
        test_dir = self._get_test_dir()
        if not test_dir:
            return
        size_mb = SIZES_MB[self._size_combo.currentIndex()]
        test_file = os.path.join(test_dir, TEST_FILE_DEFAULT)

        if mode == "write":
            if not os.access(test_dir, os.W_OK):
                QMessageBox.warning(self, "Permission Denied", f"Target directory is not writable:\n{test_dir}")
                return
            try:
                free = shutil.disk_usage(test_dir).free
                if free < size_mb * 1024 * 1024 * 1.2:
                    QMessageBox.warning(
                        self, "Insufficient Space",
                        f"Not enough free space on {test_dir} for a {size_mb} MB test."
                    )
                    return
            except Exception:
                pass
        elif not os.path.isfile(test_file):
            QMessageBox.information(self, "Missing Test File", "Run Write Test (or Run Both) first to create the test file.")
            return

        self._progress.setVisible(True)
        self._result_label.setText("...")
        self._status.setText(f"Running {mode} test on {test_dir}...")
        self._worker = BenchWorker(mode, test_file, size_mb, test_dir)
        self._worker.line.connect(self._log.append)
        self._worker.finished.connect(self._bench_done)
        self._worker.start()

    def _run_both(self):
        if self._worker is not None and self._worker.isRunning():
            return
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

            if self._pending_read:
                self._pending_read = False
                self._log.append("")
                self._run_bench("read")
                return
        else:
            self._pending_read = False
            self._result_label.setText("FAILED")
            self._status.setText("Benchmark failed — check output")

        self._cleanup()

    def _cleanup(self):
        test_dir = self._mount_combo.currentData()
        if not test_dir:
            return
        test_file = os.path.join(test_dir, TEST_FILE_DEFAULT)
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
            col = COLORS["accent_peach"] if entry.get("mode") == "write" else COLORS["success"]
            mode_item.setForeground(QBrush(QColor(col)))
            self._hist_table.setItem(row, 2, mode_item)
            self._hist_table.setItem(row, 3, QTableWidgetItem(f"{entry.get('size_mb', '')} MB"))
            self._hist_table.setItem(row, 4, QTableWidgetItem(entry.get("speed", "")))

    def _clear_history(self):
        if QMessageBox.question(
            self, "Clear", "Delete all benchmark history?",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return
        save_history([])
        self._load_history_table()

    def closeEvent(self, event):
        self._pending_read = False
        if self._worker is not None:
            self._worker.stop()
            if self._worker.isRunning():
                self._worker.wait(2500)
        self._cleanup()
        event.accept()


def main():
    app = QApplication(sys.argv)
    win = DiskBenchmark()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
