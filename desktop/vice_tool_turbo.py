#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) — Vice Turbo Mode & HUD.
Real system booster and live telemetry HUD: CPU, RAM, Disk, Load, Temperature,
picom compositor pause/resume toggle for YouTube/VM smoothness, top-process
renice helper, and swappiness/memory tuning.
"""

import glob
import os
import shutil
import signal
import subprocess
import sys

from PyQt5.QtCore import QProcess, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QIcon, QPixmap
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QFrame, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

try:
    import psutil
except ImportError:
    psutil = None

sys.path.insert(0, "/opt/vice-os/lib")

try:
    from python.vice_utils import log_info  # noqa: E402
except ImportError:
    def log_info(msg: str) -> None:
        print(f"[INFO] {msg}")


CJK_FONTS = [
    "Noto Sans",
    "Noto Sans CJK JP",
    "Noto Sans CJK SC",
    "Noto Sans CJK TC",
    "Noto Sans CJK KR",
    "DejaVu Sans",
]

STYLE = """
QMainWindow, QWidget#RootWidget {
    background-color: #120e1e;
    color: #f4f1fa;
    font-family: "Noto Sans", "Noto Sans CJK JP", "Noto Sans CJK SC", "Noto Sans CJK TC", "Noto Sans CJK KR", "DejaVu Sans", sans-serif;
    font-size: 13px;
}
QFrame#Banner {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #1d1433, stop:0.6 #33133b, stop:1 #16223d);
    border: 1px solid #ff4da6;
    border-radius: 12px;
}
QFrame#StatCard {
    background-color: #181229;
    border: 1px solid #382b57;
    border-radius: 10px;
}
QProgressBar {
    background-color: #151026;
    border: 1px solid #43346b;
    border-radius: 6px;
    height: 14px;
    text-align: center;
    color: #ffffff;
    font-weight: bold;
}
QProgressBar::chunk {
    border-radius: 5px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #00e5ff, stop:0.55 #ff4da6, stop:1 #ffd166);
}
QPushButton {
    background-color: #1f1836;
    color: #00e5ff;
    border: 1px solid #00e5ff;
    border-radius: 8px;
    padding: 7px 12px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #00e5ff;
    color: #120e1e;
}
QPushButton#TurboBtn {
    color: #ffd166;
    border-color: #ff4da6;
    background-color: #341b42;
}
QPushButton#TurboBtn:hover {
    background-color: #ff4da6;
    color: #120e1e;
}
QPushButton#WarnBtn {
    color: #ff6b8b;
    border-color: #ff6b8b;
}
QPushButton#WarnBtn:hover {
    background-color: #ff6b8b;
    color: #120e1e;
}
QTableWidget {
    background-color: #141024;
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
    color: #ff8a5b;
    border: none;
    border-bottom: 1px solid #3c2e5e;
    padding: 6px;
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
        "/usr/share/icons/hicolor/64x64/apps/vice-tool-turbo.png",
        "/usr/share/pixmaps/vice-tool-turbo.png",
    ):
        if os.path.isfile(path):
            pm = QPixmap(path)
            if not pm.isNull():
                return QIcon(pm)
    return QIcon.fromTheme("utilities-system-monitor")


def _read_proc_meminfo() -> tuple:
    info = {}
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as fp:
            for line in fp:
                if ":" in line:
                    k, val = line.split(":", 1)
                    parts = val.strip().split()
                    if parts:
                        info[k] = int(parts[0])
        total_kb = info.get("MemTotal", 0)
        avail_kb = info.get("MemAvailable", info.get("MemFree", 0))
        used_kb = max(0, total_kb - avail_kb)
        pct = int(round((used_kb / total_kb) * 100)) if total_kb else 0
        swap_tot = info.get("SwapTotal", 0)
        swap_free = info.get("SwapFree", 0)
        swap_used = max(0, swap_tot - swap_free)
        return used_kb / 1048576.0, total_kb / 1048576.0, pct, swap_used / 1048576.0, swap_tot / 1048576.0
    except Exception:
        return 0.0, 0.0, 0, 0.0, 0.0


def _read_temperature() -> str:
    temps = []
    for path in sorted(glob.glob("/sys/class/thermal/thermal_zone*/temp")) + sorted(
        glob.glob("/sys/class/hwmon/hwmon*/temp*_input")
    ):
        try:
            with open(path, "r", encoding="utf-8") as fp:
                raw = int(fp.read().strip())
            c = raw / 1000.0 if raw > 200 else float(raw)
            if 5.0 <= c <= 125.0:
                temps.append(c)
        except Exception:
            continue
    if temps:
        return f"{max(temps):.1f} °C"
    return "N/A (VM)"


def _read_swappiness() -> str:
    try:
        with open("/proc/sys/vm/swappiness", "r", encoding="utf-8") as fp:
            return fp.read().strip()
    except Exception:
        return "N/A"


def _is_compositor_running() -> bool:
    for proc_name in ("picom", "compton"):
        if shutil.which("pgrep"):
            res = subprocess.run(["pgrep", "-x", proc_name], capture_output=True)
            if res.returncode == 0:
                return True
    return False


class TelemetryWorker(QThread):
    """Collects CPU, RAM, Disk, Load, Temp, Compositor, and top processes off UI thread."""
    snapshot_ready = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self._stopped = False
        self._prev_idle = 0
        self._prev_total = 0

    def stop(self) -> None:
        self._stopped = True

    def _cpu_percent(self) -> int:
        if psutil is not None:
            try:
                return int(round(psutil.cpu_percent(interval=None)))
            except Exception:
                pass
        try:
            with open("/proc/stat", "r", encoding="utf-8") as fp:
                fields = [int(x) for x in fp.readline().split()[1:]]
            idle = fields[3] + (fields[4] if len(fields) > 4 else 0)
            total = sum(fields)
            d_idle = idle - self._prev_idle
            d_total = total - self._prev_total
            self._prev_idle = idle
            self._prev_total = total
            if d_total > 0:
                return max(0, min(100, int(round(100.0 * (1.0 - d_idle / d_total)))))
        except Exception:
            pass
        return 0

    def _top_processes(self) -> list:
        rows = []
        if psutil is not None:
            try:
                procs = []
                for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "nice"]):
                    info = p.info
                    procs.append((
                        info.get("pid", 0),
                        info.get("name", ""),
                        float(info.get("cpu_percent") or 0.0),
                        float(info.get("memory_percent") or 0.0),
                        info.get("nice", 0),
                    ))
                procs.sort(key=lambda x: (x[2], x[3]), reverse=True)
                return procs[:15]
            except Exception:
                pass
        if shutil.which("ps"):
            try:
                res = subprocess.run(
                    ["ps", "-eo", "pid,comm,%cpu,%mem,ni", "--sort=-%cpu", "--no-headers"],
                    capture_output=True, text=True, timeout=2
                )
                for line in res.stdout.splitlines()[:15]:
                    parts = line.split()
                    if len(parts) >= 5:
                        rows.append((
                            int(parts[0]), parts[1], float(parts[2]),
                            float(parts[3]), int(parts[4])
                        ))
            except Exception:
                pass
        return rows

    def run(self) -> None:
        if self._stopped:
            return
        cpu_pct = self._cpu_percent()
        if psutil is not None:
            try:
                vm = psutil.virtual_memory()
                sm = psutil.swap_memory()
                ram_used = vm.used / 1073741824.0
                ram_tot = vm.total / 1073741824.0
                ram_pct = int(round(vm.percent))
                swap_used = sm.used / 1073741824.0
                swap_tot = sm.total / 1073741824.0
            except Exception:
                ram_used, ram_tot, ram_pct, swap_used, swap_tot = _read_proc_meminfo()
        else:
            ram_used, ram_tot, ram_pct, swap_used, swap_tot = _read_proc_meminfo()

        try:
            du = shutil.disk_usage("/")
            disk_used = du.used / 1073741824.0
            disk_tot = du.total / 1073741824.0
            disk_pct = int(round((du.used / du.total) * 100)) if du.total else 0
        except Exception:
            disk_used, disk_tot, disk_pct = 0.0, 0.0, 0

        try:
            load_str = " ".join(f"{x:.2f}" for x in os.getloadavg())
        except Exception:
            load_str = "N/A"

        snap = {
            "cpu_pct": cpu_pct,
            "ram_used": ram_used,
            "ram_tot": ram_tot,
            "ram_pct": ram_pct,
            "swap_used": swap_used,
            "swap_tot": swap_tot,
            "disk_used": disk_used,
            "disk_tot": disk_tot,
            "disk_pct": disk_pct,
            "load": load_str,
            "temp": _read_temperature(),
            "swappiness": _read_swappiness(),
            "picom_on": _is_compositor_running(),
            "procs": self._top_processes(),
        }
        if not self._stopped:
            self.snapshot_ready.emit(snap)


class ViceTurboApp(QMainWindow):
    """Main window for Vice Turbo Mode & Telemetry HUD."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice Turbo Mode & HUD — Leonida Booster")
        self.resize(940, 650)
        self.setMinimumSize(760, 520)
        icon = _load_app_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)

        self._worker = None
        self._init_ui()

        self._timer = QTimer(self)
        self._timer.setInterval(1800)
        self._timer.timeout.connect(self._poll_telemetry)
        self._timer.start()
        self._poll_telemetry()

    def _init_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("RootWidget")
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.setSpacing(12)

        # Banner + Compositor Turbo Controls
        banner = QFrame(root)
        banner.setObjectName("Banner")
        bh = QHBoxLayout(banner)
        bh.setContentsMargins(16, 12, 16, 12)
        bh.setSpacing(12)

        tcol = QVBoxLayout()
        title = QLabel("VICE TURBO MODE & TELEMETRY HUD", banner)
        title.setStyleSheet("color: #ffd166; font-size: 19px; font-weight: bold; background: transparent;")
        tcol.addWidget(title)
        self._comp_status_lbl = QLabel("Compositor status: checking...", banner)
        self._comp_status_lbl.setStyleSheet("color: #00e5ff; font-size: 12px; font-weight: bold; background: transparent;")
        tcol.addWidget(self._comp_status_lbl)
        bh.addLayout(tcol, 1)

        self._pause_picom_btn = QPushButton("Enable Turbo (Pause Picom)", banner)
        self._pause_picom_btn.setObjectName("TurboBtn")
        self._pause_picom_btn.clicked.connect(self._pause_compositor)
        bh.addWidget(self._pause_picom_btn)

        self._resume_picom_btn = QPushButton("Resume Compositor", banner)
        self._resume_picom_btn.clicked.connect(self._resume_compositor)
        bh.addWidget(self._resume_picom_btn)

        layout.addWidget(banner)

        # Telemetry Grid (4 cards)
        grid = QGridLayout()
        grid.setSpacing(10)

        self._cpu_lbl, self._cpu_bar = self._make_meter_card("CPU UTILIZATION", grid, 0, 0)
        self._ram_lbl, self._ram_bar = self._make_meter_card("MEMORY & SWAP", grid, 0, 1)
        self._disk_lbl, self._disk_bar = self._make_meter_card("ROOT STORAGE (/)", grid, 1, 0)

        info_card = QFrame(root)
        info_card.setObjectName("StatCard")
        iv = QVBoxLayout(info_card)
        iv.setContentsMargins(12, 10, 12, 10)
        ih = QLabel("THERMALS, LOAD & VM TUNING", info_card)
        ih.setStyleSheet("color: #ff8a5b; font-size: 11px; font-weight: bold; background: transparent;")
        iv.addWidget(ih)
        self._kernel_lbl = QLabel("Load: - · Temp: - · vm.swappiness: -", info_card)
        self._kernel_lbl.setWordWrap(True)
        self._kernel_lbl.setStyleSheet("color: #f4f1fa; font-weight: bold; background: transparent;")
        iv.addWidget(self._kernel_lbl)
        grid.addWidget(info_card, 1, 1)

        layout.addLayout(grid)

        # Memory & Swappiness Quick Tune Row
        mem_row = QHBoxLayout()
        mem_row.setSpacing(8)
        drop_btn = QPushButton("Drop Page Cache (pkexec)", root)
        drop_btn.clicked.connect(self._drop_caches)
        mem_row.addWidget(drop_btn)

        swap_zram_btn = QPushButton("Set vm.swappiness=100 (ZRAM)", root)
        swap_zram_btn.clicked.connect(lambda: self._set_swappiness(100))
        mem_row.addWidget(swap_zram_btn)

        swap_bal_btn = QPushButton("Set vm.swappiness=60 (Balanced)", root)
        swap_bal_btn.clicked.connect(lambda: self._set_swappiness(60))
        mem_row.addWidget(swap_bal_btn)
        mem_row.addStretch(1)
        layout.addLayout(mem_row)

        # Top Processes Table
        proc_lbl = QLabel("Top Active Processes (select row to renice or terminate):", root)
        proc_lbl.setStyleSheet("color: #cfc6e6; font-weight: bold;")
        layout.addWidget(proc_lbl)

        self._proc_table = QTableWidget(0, 5, root)
        self._proc_table.setHorizontalHeaderLabels(["PID", "Process", "CPU %", "RAM %", "Nice"])
        self._proc_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._proc_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._proc_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._proc_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        layout.addWidget(self._proc_table, 1)

        # Process Action Row
        pact = QHBoxLayout()
        boost_btn = QPushButton("Boost Priority (Nice -5)", root)
        boost_btn.clicked.connect(lambda: self._renice_selected(-5))
        pact.addWidget(boost_btn)

        throttle_btn = QPushButton("Throttle Priority (Nice +10)", root)
        throttle_btn.clicked.connect(lambda: self._renice_selected(10))
        pact.addWidget(throttle_btn)

        kill_btn = QPushButton("Terminate Selected", root)
        kill_btn.setObjectName("WarnBtn")
        kill_btn.clicked.connect(self._terminate_selected)
        pact.addWidget(kill_btn)

        pact.addStretch(1)
        self._action_status = QLabel("Ready.", root)
        self._action_status.setStyleSheet("color: #a99ec9;")
        pact.addWidget(self._action_status)
        layout.addLayout(pact)

    def _make_meter_card(self, title: str, grid: QGridLayout, row: int, col: int) -> tuple:
        card = QFrame(self)
        card.setObjectName("StatCard")
        v = QVBoxLayout(card)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(6)
        hdr = QLabel(title, card)
        hdr.setStyleSheet("color: #ff8a5b; font-size: 11px; font-weight: bold; background: transparent;")
        v.addWidget(hdr)
        val_lbl = QLabel("Sampling...", card)
        val_lbl.setStyleSheet("color: #f4f1fa; font-weight: bold; background: transparent;")
        v.addWidget(val_lbl)
        bar = QProgressBar(card)
        bar.setRange(0, 100)
        v.addWidget(bar)
        grid.addWidget(card, row, col)
        return val_lbl, bar

    def _poll_telemetry(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self._worker = TelemetryWorker()
        self._worker.snapshot_ready.connect(self._apply_snapshot)
        self._worker.start()

    def _apply_snapshot(self, s: dict) -> None:
        self._cpu_lbl.setText(f"{s['cpu_pct']}% Active")
        self._cpu_bar.setValue(s["cpu_pct"])

        self._ram_lbl.setText(
            f"{s['ram_used']:.2f} / {s['ram_tot']:.2f} GiB · Swap {s['swap_used']:.2f} / {s['swap_tot']:.2f} GiB"
        )
        self._ram_bar.setValue(s["ram_pct"])

        self._disk_lbl.setText(f"{s['disk_used']:.1f} / {s['disk_tot']:.1f} GiB Used")
        self._disk_bar.setValue(s["disk_pct"])

        self._kernel_lbl.setText(
            f"Load: {s['load']}  |  Temp: {s['temp']}  |  vm.swappiness: {s['swappiness']}"
        )

        picom_on = bool(s["picom_on"])
        self._comp_status_lbl.setText(
            "Compositor: ACTIVE (picom running)" if picom_on
            else "Compositor: PAUSED (Turbo Mode — zero compositing overhead)"
        )
        self._comp_status_lbl.setStyleSheet(
            "color: #00e5ff; font-size: 12px; font-weight: bold; background: transparent;"
            if picom_on else
            "color: #ffd166; font-size: 12px; font-weight: bold; background: transparent;"
        )

        # Preserve selected PID across refresh
        selected_pid = self._selected_pid()
        self._proc_table.setRowCount(0)
        for pid, name, cpu, mem, nice_val in s["procs"]:
            row = self._proc_table.rowCount()
            self._proc_table.insertRow(row)
            vals = [str(pid), str(name), f"{cpu:.1f}", f"{mem:.1f}", str(nice_val)]
            for col_idx, txt in enumerate(vals):
                it = QTableWidgetItem(txt)
                self._proc_table.setItem(row, col_idx, it)
            if selected_pid is not None and pid == selected_pid:
                self._proc_table.selectRow(row)

    def _selected_pid(self):
        row = self._proc_table.currentRow()
        if row < 0:
            return None
        it = self._proc_table.item(row, 0)
        if it is None:
            return None
        try:
            return int(it.text())
        except ValueError:
            return None

    def _pause_compositor(self) -> None:
        if not shutil.which("pkill"):
            self._action_status.setText("pkill not available.")
            return
        for proc_name in ("picom", "compton"):
            subprocess.run(["pkill", "-x", proc_name], capture_output=True)
        self._action_status.setText("Turbo Mode ON: compositor paused for maximum frame smoothness.")
        log_info("Vice Turbo paused picom/compton")
        self._poll_telemetry()

    def _resume_compositor(self) -> None:
        if _is_compositor_running():
            self._action_status.setText("Compositor is already running.")
            return
        comp_bin = shutil.which("picom") or shutil.which("compton")
        if not comp_bin:
            self._action_status.setText("picom/compton is not installed.")
            return
        args = ["-b"]
        if os.path.isfile("/etc/xdg/picom.conf"):
            args.extend(["--config", "/etc/xdg/picom.conf"])
        elif os.path.isfile("/etc/xdg/compton.conf"):
            args.extend(["--config", "/etc/xdg/compton.conf"])
        if os.path.basename(comp_bin) == "picom":
            args.extend(["--backend", "xrender", "--no-fading-openclose"])
        QProcess.startDetached(comp_bin, args, os.path.expanduser("~"))
        self._action_status.setText("Resumed compositor.")
        QTimer.singleShot(500, self._poll_telemetry)

    def _renice_selected(self, nice_val: int) -> None:
        pid = self._selected_pid()
        if pid is None:
            self._action_status.setText("Select a process first.")
            return
        if not shutil.which("renice"):
            self._action_status.setText("renice binary missing.")
            return
        res = subprocess.run(["renice", "-n", str(nice_val), "-p", str(pid)], capture_output=True, text=True)
        if res.returncode != 0 and shutil.which("pkexec"):
            res = subprocess.run(
                ["pkexec", "renice", "-n", str(nice_val), "-p", str(pid)],
                capture_output=True, text=True
            )
        if res.returncode == 0:
            self._action_status.setText(f"Set PID {pid} nice={nice_val}.")
            self._poll_telemetry()
        else:
            self._action_status.setText(f"Renice failed: {res.stderr.strip()}")

    def _terminate_selected(self) -> None:
        pid = self._selected_pid()
        if pid is None:
            self._action_status.setText("Select a process first.")
            return
        if pid == os.getpid():
            return
        ans = QMessageBox.question(
            self, "Terminate Process", f"Send SIGTERM to PID {pid}?"
        )
        if ans != QMessageBox.Yes:
            return
        try:
            os.kill(pid, signal.SIGTERM)
            self._action_status.setText(f"Sent SIGTERM to PID {pid}.")
            QTimer.singleShot(400, self._poll_telemetry)
        except PermissionError:
            if shutil.which("pkexec"):
                subprocess.run(["pkexec", "kill", "-TERM", str(pid)], capture_output=True)
                QTimer.singleShot(400, self._poll_telemetry)
            else:
                self._action_status.setText(f"Permission denied terminating PID {pid}.")
        except Exception as exc:
            self._action_status.setText(f"Error: {exc}")

    def _drop_caches(self) -> None:
        if not shutil.which("pkexec"):
            self._action_status.setText("pkexec required for privileged cache drop.")
            return
        res = subprocess.run(
            ["pkexec", "sh", "-c", "sync; echo 3 > /proc/sys/vm/drop_caches"],
            capture_output=True, text=True
        )
        self._action_status.setText(
            "Dropped Linux page/inode caches." if res.returncode == 0 else f"Cancelled/failed: {res.stderr.strip()}"
        )
        self._poll_telemetry()

    def _set_swappiness(self, val: int) -> None:
        if not shutil.which("pkexec"):
            self._action_status.setText("pkexec required for sysctl tuning.")
            return
        res = subprocess.run(
            ["pkexec", "sysctl", "-w", f"vm.swappiness={val}"],
            capture_output=True, text=True
        )
        self._action_status.setText(
            f"vm.swappiness set to {val}." if res.returncode == 0 else f"Failed: {res.stderr.strip()}"
        )
        self._poll_telemetry()

    def closeEvent(self, event) -> None:
        self._timer.stop()
        if self._worker is not None:
            self._worker.stop()
            if self._worker.isRunning():
                self._worker.wait(1500)
        event.accept()


def main() -> None:
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    _configure_cjk_fonts(app)
    app.setStyleSheet(STYLE)
    win = ViceTurboApp()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
