#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) — Vice Turbo Mode & HUD.
Real system booster and live telemetry HUD: CPU, RAM, Disk, Load, Temperature,
picom compositor pause/resume toggle for VM smoothness, top-process renice,
and swappiness/memory tuning via non-blocking QThread/pkexec.
Styled via vice_theme (Noto Sans CJK fallback).
"""

import glob
import os
import shutil
import signal
import subprocess
import sys

from PyQt5.QtCore import QProcess, QThread, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QMainWindow, QMessageBox, QProgressBar,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

try:
    import psutil
except ImportError:
    psutil = None

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in ("/opt/vice-os", _HERE, "/opt/vice-os/lib"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from vice_theme import (  # noqa: E402
    COLORS,
    apply_app_theme,
    load_tool_icon,
    make_button,
    make_card,
    make_header,
)

try:
    from python.vice_utils import log_info  # noqa: E402
except ImportError:
    def log_info(msg: str) -> None:
        print(f"[INFO] {msg}")


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


class PrivActionWorker(QThread):
    """Executes one-off privileged actions off the UI thread."""
    finished_msg = pyqtSignal(bool, str)

    def __init__(self, cmd: list, ok_msg: str):
        super().__init__()
        self._cmd = cmd
        self._ok_msg = ok_msg
        self._stopped = False
        self._proc = None

    def stop(self) -> None:
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

    def run(self) -> None:
        try:
            self._proc = subprocess.Popen(
                self._cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            stdout, stderr = self._proc.communicate(timeout=30)
            if self._stopped:
                return
            if self._proc.returncode == 0:
                self.finished_msg.emit(True, self._ok_msg)
            else:
                err = (stderr or "").strip() or (stdout or "").strip() or f"Exit {self._proc.returncode}"
                self.finished_msg.emit(False, err)
        except subprocess.TimeoutExpired:
            if self._proc is not None:
                self._proc.kill()
                self._proc.communicate()
            if not self._stopped:
                self.finished_msg.emit(False, "Privileged action timed out after 30s.")
        except Exception as exc:
            if not self._stopped:
                self.finished_msg.emit(False, str(exc))
        finally:
            self._proc = None


class ViceTurboApp(QMainWindow):
    """Main window for Vice Turbo Mode & Telemetry HUD."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice Turbo Mode & HUD — Vice OS")
        self.resize(940, 650)
        self.setMinimumSize(760, 520)
        icon = load_tool_icon("vice-tool-turbo", "utilities-system-monitor")
        if not icon.isNull():
            self.setWindowIcon(icon)

        self._worker = None
        self._priv_worker = None
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

        self._header = make_header(
            title="Vice Turbo Mode & Telemetry HUD",
            subtitle="Compositor control, memory tuning, and live process prioritization",
            icon_name="vice-tool-turbo",
            badge_text="CHECKING",
            badge_variant="neutral",
            parent=root,
        )
        self._pause_picom_btn = make_button("Enable Turbo", variant="primary", parent=self._header)
        self._pause_picom_btn.clicked.connect(self._pause_compositor)
        self._header.right_layout.addWidget(self._pause_picom_btn)

        self._resume_picom_btn = make_button("Resume Compositor", variant="secondary", parent=self._header)
        self._resume_picom_btn.clicked.connect(self._resume_compositor)
        self._header.right_layout.addWidget(self._resume_picom_btn)
        layout.addWidget(self._header)

        # Telemetry Grid (4 calm surface cards)
        grid = QGridLayout()
        grid.setSpacing(10)

        self._cpu_lbl, self._cpu_bar = self._make_meter_card("CPU Utilization", grid, 0, 0)
        self._ram_lbl, self._ram_bar = self._make_meter_card("Memory & Swap", grid, 0, 1)
        self._disk_lbl, self._disk_bar = self._make_meter_card("Root Storage (/)", grid, 1, 0)

        info_card = make_card(title="Thermals, Load & VM Tuning", parent=root)
        self._kernel_lbl = QLabel("Load: - · Temp: - · vm.swappiness: -", info_card)
        self._kernel_lbl.setWordWrap(True)
        self._kernel_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-weight: 600;")
        info_card.body_layout.addWidget(self._kernel_lbl)
        grid.addWidget(info_card, 1, 1)

        layout.addLayout(grid)

        # Memory & Swappiness Quick Tune Row
        mem_row = QHBoxLayout()
        mem_row.setSpacing(8)
        drop_btn = make_button("Drop Page Cache (pkexec)", variant="secondary", parent=root)
        drop_btn.clicked.connect(self._drop_caches)
        mem_row.addWidget(drop_btn)

        swap_zram_btn = make_button("Set vm.swappiness=100 (ZRAM)", variant="secondary", parent=root)
        swap_zram_btn.clicked.connect(lambda: self._set_swappiness(100))
        mem_row.addWidget(swap_zram_btn)

        swap_bal_btn = make_button("Set vm.swappiness=60 (Balanced)", variant="secondary", parent=root)
        swap_bal_btn.clicked.connect(lambda: self._set_swappiness(60))
        mem_row.addWidget(swap_bal_btn)
        mem_row.addStretch(1)
        layout.addLayout(mem_row)

        proc_lbl = QLabel("Top Active Processes (select row to renice or terminate)", root)
        proc_lbl.setObjectName("SectionTitle")
        layout.addWidget(proc_lbl)

        self._proc_table = QTableWidget(0, 5, root)
        self._proc_table.setHorizontalHeaderLabels(["PID", "Process", "CPU %", "RAM %", "Nice"])
        self._proc_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._proc_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._proc_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._proc_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        layout.addWidget(self._proc_table, 1)

        pact = QHBoxLayout()
        pact.setSpacing(8)
        boost_btn = make_button("Boost Priority (Nice -5)", variant="primary", parent=root)
        boost_btn.clicked.connect(lambda: self._renice_selected(-5))
        pact.addWidget(boost_btn)

        throttle_btn = make_button("Throttle Priority (Nice +10)", variant="secondary", parent=root)
        throttle_btn.clicked.connect(lambda: self._renice_selected(10))
        pact.addWidget(throttle_btn)

        kill_btn = make_button("Terminate Selected", variant="danger", parent=root)
        kill_btn.clicked.connect(self._terminate_selected)
        pact.addWidget(kill_btn)

        pact.addStretch(1)
        self._action_status = QLabel("Ready.", root)
        self._action_status.setObjectName("MutedLabel")
        pact.addWidget(self._action_status)
        layout.addLayout(pact)

    def _make_meter_card(self, title: str, grid: QGridLayout, row: int, col: int) -> tuple:
        card = make_card(title=title, parent=self)
        val_lbl = QLabel("Sampling...", card)
        val_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-weight: 600;")
        card.body_layout.addWidget(val_lbl)
        bar = QProgressBar(card)
        bar.setRange(0, 100)
        card.body_layout.addWidget(bar)
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
            f"Load: {s['load']}  ·  Temp: {s['temp']}  ·  vm.swappiness: {s['swappiness']}"
        )

        picom_on = bool(s["picom_on"])
        if picom_on:
            self._header.set_badge("COMPOSITOR ON", "aqua")
        else:
            self._header.set_badge("TURBO ACTIVE", "gold")

        selected_pid = self._selected_pid()
        self._proc_table.setRowCount(0)
        for pid, name, cpu, mem, nice_val in s["procs"]:
            row = self._proc_table.rowCount()
            self._proc_table.insertRow(row)
            vals = [str(pid), str(name), f"{cpu:.1f}", f"{mem:.1f}", str(nice_val)]
            for col_idx, txt in enumerate(vals):
                self._proc_table.setItem(row, col_idx, QTableWidgetItem(txt))
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

    def _run_priv_async(self, cmd: list, ok_msg: str) -> None:
        if self._priv_worker is not None and self._priv_worker.isRunning():
            self._action_status.setText("Another privileged task is already running...")
            return
        self._action_status.setText("Running privileged action...")
        self._priv_worker = PrivActionWorker(cmd, ok_msg)
        self._priv_worker.finished_msg.connect(self._on_priv_done)
        self._priv_worker.start()

    def _on_priv_done(self, ok: bool, msg: str) -> None:
        color = COLORS["success"] if ok else COLORS["danger"]
        self._action_status.setStyleSheet(f"color: {color}; font-weight: 600;")
        self._action_status.setText(msg)
        self._poll_telemetry()

    def _pause_compositor(self) -> None:
        if not shutil.which("pkill"):
            self._action_status.setText("pkill not available.")
            return
        for proc_name in ("picom", "compton"):
            subprocess.run(["pkill", "-x", proc_name], capture_output=True)
        self._action_status.setStyleSheet(f"color: {COLORS['accent_gold']}; font-weight: 600;")
        self._action_status.setText("Turbo Mode ON: compositor paused for smoother frame pacing.")
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
        self._action_status.setStyleSheet(f"color: {COLORS['accent_aqua']}; font-weight: 600;")
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
        if res.returncode == 0:
            self._on_priv_done(True, f"Set PID {pid} nice={nice_val}.")
        elif shutil.which("pkexec"):
            self._run_priv_async(
                ["pkexec", "renice", "-n", str(nice_val), "-p", str(pid)],
                f"Set PID {pid} nice={nice_val}.",
            )
        else:
            self._on_priv_done(False, f"Renice failed: {res.stderr.strip()}")

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
            self._on_priv_done(True, f"Sent SIGTERM to PID {pid}.")
        except PermissionError:
            if shutil.which("pkexec"):
                self._run_priv_async(
                    ["pkexec", "kill", "-TERM", str(pid)],
                    f"Sent SIGTERM to PID {pid}.",
                )
            else:
                self._on_priv_done(False, f"Permission denied terminating PID {pid}.")
        except Exception as exc:
            self._on_priv_done(False, f"Error: {exc}")

    def _drop_caches(self) -> None:
        if not shutil.which("pkexec"):
            self._action_status.setText("pkexec required for privileged cache drop.")
            return
        self._run_priv_async(
            ["pkexec", "sh", "-c", "sync; echo 3 > /proc/sys/vm/drop_caches"],
            "Dropped Linux page/inode caches.",
        )

    def _set_swappiness(self, val: int) -> None:
        if not shutil.which("pkexec"):
            self._action_status.setText("pkexec required for sysctl tuning.")
            return
        self._run_priv_async(
            ["pkexec", "sysctl", "-w", f"vm.swappiness={int(val)}"],
            f"vm.swappiness set to {int(val)}.",
        )

    def closeEvent(self, event) -> None:
        self._timer.stop()
        if self._worker is not None:
            self._worker.stop()
            if self._worker.isRunning():
                self._worker.wait(1500)
        if self._priv_worker is not None:
            self._priv_worker.stop()
            if self._priv_worker.isRunning():
                self._priv_worker.wait(2500)
        event.accept()


def main() -> None:
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    apply_app_theme(app)
    win = ViceTurboApp()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
