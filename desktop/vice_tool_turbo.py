#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) — Vice Turbo Mode & HUD.
Real Linux system tuning & live telemetry HUD: per-core CPU, RAM/swap/ZRAM,
root storage, live Disk/Net I/O rates, CPU frequency governor switcher
(/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor via pkexec), picom
compositor pause/resume toggle, sysctl vm.drop_caches=3 & swappiness tuning,
and interactive top-process renice/terminate controls.
Styled via vice_theme (Noto Sans CJK fallback).
"""

import glob
import os
import shutil
import signal
import subprocess
import sys
import time

from PyQt5.QtCore import QProcess, QThread, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QGridLayout, QHBoxLayout,
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


_SBIN_PATH = os.pathsep.join([
    os.environ.get("PATH", ""),
    "/usr/local/sbin",
    "/usr/sbin",
    "/sbin",
])


def _which(cmd: str) -> str:
    return shutil.which(cmd) or shutil.which(cmd, path=_SBIN_PATH) or ""


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


def _read_cpufreq_info() -> tuple:
    """Return (active_governor, available_governors_list) from sysfs cpufreq."""
    gov_path = "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"
    avail_path = "/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors"
    current = ""
    avail = []
    if os.path.isfile(gov_path):
        try:
            with open(gov_path, "r", encoding="utf-8") as fp:
                current = fp.read().strip()
        except OSError:
            pass
    if os.path.isfile(avail_path):
        try:
            with open(avail_path, "r", encoding="utf-8") as fp:
                avail = [g for g in fp.read().split() if g.strip()]
        except OSError:
            pass
    return current or "Host-managed (VM)", avail


def _read_zram_stats() -> str:
    """Read real ZRAM mm_stat compression telemetry if active."""
    mm_paths = sorted(glob.glob("/sys/block/zram*/mm_stat"))
    if not mm_paths:
        return "Inactive"
    orig_total = 0
    compr_total = 0
    active_devs = 0
    for path in mm_paths:
        try:
            with open(path, "r", encoding="utf-8") as fp:
                parts = fp.read().split()
            if len(parts) >= 3:
                orig_b = int(parts[0])
                compr_b = int(parts[1])
                if orig_b > 0 or compr_b > 0:
                    active_devs += 1
                    orig_total += orig_b
                    compr_total += compr_b
        except (OSError, ValueError):
            continue
    if active_devs == 0:
        return f"{len(mm_paths)} dev(s), 0 MiB used"
    orig_mib = orig_total / 1048576.0
    compr_mib = compr_total / 1048576.0
    ratio = (orig_total / compr_total) if compr_total > 0 else 1.0
    return f"{compr_mib:.1f}/{orig_mib:.1f} MiB ({ratio:.1f}x)"


def _read_proc_stat_cpus() -> tuple:
    """Return (overall_idle_total_tuple, per_core_dict) from /proc/stat."""
    overall = (0, 0)
    cores = {}
    try:
        with open("/proc/stat", "r", encoding="utf-8") as fp:
            for line in fp:
                parts = line.split()
                if not parts:
                    continue
                if parts[0] == "cpu":
                    fields = [int(x) for x in parts[1:]]
                    idle = fields[3] + (fields[4] if len(fields) > 4 else 0)
                    overall = (idle, sum(fields))
                elif parts[0].startswith("cpu") and parts[0][3:].isdigit():
                    idx = int(parts[0][3:])
                    fields = [int(x) for x in parts[1:]]
                    idle = fields[3] + (fields[4] if len(fields) > 4 else 0)
                    cores[idx] = (idle, sum(fields))
    except OSError:
        pass
    return overall, cores


def _read_proc_io_bytes() -> tuple:
    """Return (disk_read_bytes, disk_write_bytes, net_rx_bytes, net_tx_bytes)."""
    d_read, d_write = 0, 0
    if psutil is not None:
        try:
            dio = psutil.disk_io_counters()
            if dio is not None:
                d_read, d_write = dio.read_bytes, dio.write_bytes
        except Exception:
            pass
    if d_read == 0 and d_write == 0 and os.path.isfile("/proc/diskstats"):
        try:
            with open("/proc/diskstats", "r", encoding="utf-8") as fp:
                for line in fp:
                    parts = line.split()
                    if len(parts) >= 10:
                        dev = parts[2]
                        if dev.startswith(("sd", "vd", "nvme", "mmcblk")) and not dev[-1].isdigit():
                            d_read += int(parts[5]) * 512
                            d_write += int(parts[9]) * 512
        except (OSError, ValueError):
            pass

    n_rx, n_tx = 0, 0
    if psutil is not None:
        try:
            nio = psutil.net_io_counters()
            if nio is not None:
                n_rx, n_tx = nio.bytes_recv, nio.bytes_sent
        except Exception:
            pass
    if n_rx == 0 and n_tx == 0 and os.path.isfile("/proc/net/dev"):
        try:
            with open("/proc/net/dev", "r", encoding="utf-8") as fp:
                for line in fp.readlines()[2:]:
                    if ":" not in line:
                        continue
                    iface, rest = line.split(":", 1)
                    if iface.strip() == "lo":
                        continue
                    cols = rest.split()
                    if len(cols) >= 9:
                        n_rx += int(cols[0])
                        n_tx += int(cols[8])
        except (OSError, ValueError):
            pass
    return d_read, d_write, n_rx, n_tx


def _is_compositor_running() -> bool:
    pgrep_bin = _which("pgrep")
    if not pgrep_bin:
        return False
    for proc_name in ("picom", "compton"):
        res = subprocess.run([pgrep_bin, "-x", proc_name], capture_output=True)
        if res.returncode == 0:
            return True
    return False


class TelemetryWorker(QThread):
    """Collects per-core CPU, RAM/ZRAM, Disk/Net I/O, Load, Temp, Governor, and top processes."""
    snapshot_ready = pyqtSignal(dict)

    def __init__(self, prev_state: dict = None):
        super().__init__()
        self._stopped = False
        self._state = prev_state if prev_state is not None else {}

    def stop(self) -> None:
        self._stopped = True

    def _cpu_metrics(self) -> tuple:
        if psutil is not None:
            try:
                per_core = [int(round(v)) for v in psutil.cpu_percent(interval=None, percpu=True)]
                if per_core:
                    avg = int(round(sum(per_core) / len(per_core)))
                    return avg, per_core
            except Exception:
                pass

        overall, cores = _read_proc_stat_cpus()
        prev_overall = self._state.get("overall_cpu", (0, 0))
        prev_cores = self._state.get("per_core_cpu", {})
        self._state["overall_cpu"] = overall
        self._state["per_core_cpu"] = cores

        avg = 0
        if prev_overall[1] > 0:
            d_idle = overall[0] - prev_overall[0]
            d_total = overall[1] - prev_overall[1]
            if d_total > 0:
                avg = max(0, min(100, int(round(100.0 * (1.0 - d_idle / d_total)))))

        per_core = []
        for idx in sorted(cores):
            cur_i, cur_t = cores[idx]
            old_i, old_t = prev_cores.get(idx, (0, 0))
            if old_t > 0 and cur_t > old_t:
                pct = max(0, min(100, int(round(100.0 * (1.0 - (cur_i - old_i) / (cur_t - old_t))))))
            else:
                pct = 0
            per_core.append(pct)
        return avg, per_core

    def _io_rates(self) -> tuple:
        now = time.monotonic()
        dr, dw, rx, tx = _read_proc_io_bytes()
        prev_ts = self._state.get("io_ts", 0.0)
        prev_vals = self._state.get("io_vals")
        self._state["io_ts"] = now
        self._state["io_vals"] = (dr, dw, rx, tx)
        if not prev_vals or prev_ts <= 0.0 or now <= prev_ts:
            return 0.0, 0.0, 0.0, 0.0
        dt = now - prev_ts
        r_mbs = max(0.0, (dr - prev_vals[0]) / dt / 1048576.0)
        w_mbs = max(0.0, (dw - prev_vals[1]) / dt / 1048576.0)
        rx_kbs = max(0.0, (rx - prev_vals[2]) / dt / 1024.0)
        tx_kbs = max(0.0, (tx - prev_vals[3]) / dt / 1024.0)
        return r_mbs, w_mbs, rx_kbs, tx_kbs

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
        ps_bin = _which("ps")
        if ps_bin:
            try:
                res = subprocess.run(
                    [ps_bin, "-eo", "pid,comm,%cpu,%mem,ni", "--sort=-%cpu", "--no-headers"],
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
        cpu_pct, per_core = self._cpu_metrics()
        r_mbs, w_mbs, rx_kbs, tx_kbs = self._io_rates()
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

        gov_cur, gov_avail = _read_cpufreq_info()
        snap = {
            "cpu_pct": cpu_pct,
            "per_core": per_core,
            "ram_used": ram_used,
            "ram_tot": ram_tot,
            "ram_pct": ram_pct,
            "swap_used": swap_used,
            "swap_tot": swap_tot,
            "zram": _read_zram_stats(),
            "disk_used": disk_used,
            "disk_tot": disk_tot,
            "disk_pct": disk_pct,
            "io_r": r_mbs,
            "io_w": w_mbs,
            "net_rx": rx_kbs,
            "net_tx": tx_kbs,
            "load": load_str,
            "temp": _read_temperature(),
            "swappiness": _read_swappiness(),
            "gov_cur": gov_cur,
            "gov_avail": gov_avail,
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
        self.resize(980, 690)
        self.setMinimumSize(780, 550)
        icon = load_tool_icon("vice-tool-turbo", "utilities-system-monitor")
        if not icon.isNull():
            self.setWindowIcon(icon)

        self._worker = None
        self._priv_worker = None
        self._telemetry_state = {}
        self._gov_populated = False
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
            subtitle="Live per-core telemetry, CPU governor, compositor control, ZRAM/cache & process tuning",
            icon_name="vice-tool-turbo",
            badge_text="CHECKING",
            badge_variant="neutral",
            parent=root,
        )
        self._pause_picom_btn = make_button("Pause Compositor", variant="primary", parent=self._header)
        self._pause_picom_btn.clicked.connect(self._pause_compositor)
        self._header.right_layout.addWidget(self._pause_picom_btn)

        self._resume_picom_btn = make_button("Resume Compositor", variant="secondary", parent=self._header)
        self._resume_picom_btn.clicked.connect(self._resume_compositor)
        self._header.right_layout.addWidget(self._resume_picom_btn)
        layout.addWidget(self._header)

        # Telemetry Grid (4 calm surface cards)
        grid = QGridLayout()
        grid.setSpacing(10)

        self._cpu_lbl, self._cpu_bar, self._cores_lbl = self._make_meter_card(
            "CPU Utilization (Per-Core)", grid, 0, 0, extra="Sampling cores..."
        )
        self._ram_lbl, self._ram_bar, self._zram_lbl = self._make_meter_card(
            "Memory, Swap && ZRAM", grid, 0, 1, extra="ZRAM: checking..."
        )
        self._disk_lbl, self._disk_bar, self._io_lbl = self._make_meter_card(
            "Storage (/) && Live I/O", grid, 1, 0, extra="Disk R/W: - · Net: -"
        )

        info_card = make_card(title="Thermals, Load && CPU Governor", parent=root)
        self._kernel_lbl = QLabel("Load: - · Temp: - · vm.swappiness: -", info_card)
        self._kernel_lbl.setWordWrap(True)
        self._kernel_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-weight: 600;")
        info_card.body_layout.addWidget(self._kernel_lbl)

        self._gov_lbl = QLabel("CPU Governor: checking...", info_card)
        self._gov_lbl.setWordWrap(True)
        self._gov_lbl.setStyleSheet(f"color: {COLORS['accent_aqua']}; font-size: 12px; font-weight: 600;")
        info_card.body_layout.addWidget(self._gov_lbl)
        grid.addWidget(info_card, 1, 1)

        layout.addLayout(grid)

        # Kernel / CPU Governor / Memory Tuning Row
        tune_row = QHBoxLayout()
        tune_row.setSpacing(8)
        self._gov_combo = QComboBox(root)
        self._gov_combo.setMinimumWidth(150)
        tune_row.addWidget(self._gov_combo)

        self._gov_btn = make_button("Apply Governor (pkexec)", variant="primary", parent=root)
        self._gov_btn.clicked.connect(self._apply_governor)
        tune_row.addWidget(self._gov_btn)

        drop_btn = make_button("Drop Caches (sysctl)", variant="secondary", parent=root)
        drop_btn.clicked.connect(self._drop_caches)
        tune_row.addWidget(drop_btn)

        swap_zram_btn = make_button("Swappiness=100 (ZRAM)", variant="secondary", parent=root)
        swap_zram_btn.clicked.connect(lambda: self._set_swappiness(100))
        tune_row.addWidget(swap_zram_btn)

        swap_bal_btn = make_button("Swappiness=60 (Balanced)", variant="secondary", parent=root)
        swap_bal_btn.clicked.connect(lambda: self._set_swappiness(60))
        tune_row.addWidget(swap_bal_btn)
        tune_row.addStretch(1)
        layout.addLayout(tune_row)

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

        normal_btn = make_button("Normal (Nice 0)", variant="secondary", parent=root)
        normal_btn.clicked.connect(lambda: self._renice_selected(0))
        pact.addWidget(normal_btn)

        throttle_btn = make_button("Throttle (Nice +10)", variant="secondary", parent=root)
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

    def _make_meter_card(self, title: str, grid: QGridLayout, row: int, col: int, extra: str = "") -> tuple:
        card = make_card(title=title, parent=self)
        val_lbl = QLabel("Sampling...", card)
        val_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-weight: 600;")
        card.body_layout.addWidget(val_lbl)
        bar = QProgressBar(card)
        bar.setRange(0, 100)
        card.body_layout.addWidget(bar)
        sub_lbl = QLabel(extra, card)
        sub_lbl.setWordWrap(True)
        sub_lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        card.body_layout.addWidget(sub_lbl)
        grid.addWidget(card, row, col)
        return val_lbl, bar, sub_lbl

    def _poll_telemetry(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self._worker = TelemetryWorker(self._telemetry_state)
        self._worker.snapshot_ready.connect(self._apply_snapshot)
        self._worker.start()

    def _apply_snapshot(self, s: dict) -> None:
        self._cpu_lbl.setText(f"{s['cpu_pct']}% Active ({len(s['per_core'])} cores)")
        self._cpu_bar.setValue(s["cpu_pct"])
        if s["per_core"]:
            core_str = "  ".join(f"C{i}:{v}%" for i, v in enumerate(s["per_core"][:16]))
            if len(s["per_core"]) > 16:
                core_str += f" (+{len(s['per_core']) - 16})"
            self._cores_lbl.setText(core_str)
        else:
            self._cores_lbl.setText("Per-core counters unavailable.")

        self._ram_lbl.setText(
            f"{s['ram_used']:.2f} / {s['ram_tot']:.2f} GiB · Swap {s['swap_used']:.2f} / {s['swap_tot']:.2f} GiB"
        )
        self._ram_bar.setValue(s["ram_pct"])
        self._zram_lbl.setText(f"ZRAM: {s['zram']}")

        self._disk_lbl.setText(f"{s['disk_used']:.1f} / {s['disk_tot']:.1f} GiB Used")
        self._disk_bar.setValue(s["disk_pct"])
        self._io_lbl.setText(
            f"Disk R {s['io_r']:.2f} / W {s['io_w']:.2f} MiB/s · Net ↓{s['net_rx']:.1f} / ↑{s['net_tx']:.1f} KiB/s"
        )

        self._kernel_lbl.setText(
            f"Load: {s['load']}  ·  Temp: {s['temp']}  ·  vm.swappiness: {s['swappiness']}"
        )
        self._gov_lbl.setText(f"CPU Governor: {s['gov_cur']}")

        avail_govs = s.get("gov_avail") or []
        if not self._gov_populated:
            self._gov_populated = True
            self._gov_combo.clear()
            if avail_govs:
                self._gov_combo.addItems(avail_govs)
                idx = self._gov_combo.findText(s["gov_cur"])
                if idx >= 0:
                    self._gov_combo.setCurrentIndex(idx)
                self._gov_combo.setEnabled(True)
                self._gov_btn.setEnabled(True)
            else:
                self._gov_combo.addItem("Host-managed (VM)")
                self._gov_combo.setEnabled(False)
                self._gov_btn.setEnabled(False)
                self._gov_btn.setToolTip("cpufreq sysfs is not exposed inside this VM")

        picom_on = bool(s["picom_on"])
        self._pause_picom_btn.setEnabled(picom_on)
        self._resume_picom_btn.setEnabled(not picom_on)
        if picom_on:
            self._header.set_badge("COMPOSITOR ON", "aqua")
        else:
            self._header.set_badge("COMPOSITOR PAUSED", "gold")

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
        pkill_bin = _which("pkill")
        if not pkill_bin:
            self._action_status.setText("pkill not available.")
            return
        for proc_name in ("picom", "compton"):
            subprocess.run([pkill_bin, "-x", proc_name], capture_output=True)
        self._action_status.setStyleSheet(f"color: {COLORS['accent_gold']}; font-weight: 600;")
        self._action_status.setText("Compositor paused (picom stopped) to reduce desktop frame overhead.")
        log_info("Vice Turbo paused picom/compton")
        self._poll_telemetry()

    def _resume_compositor(self) -> None:
        if _is_compositor_running():
            self._action_status.setText("Compositor is already running.")
            return
        comp_bin = _which("picom") or _which("compton")
        if not comp_bin:
            self._action_status.setText("picom/compton is not installed.")
            return
        args = ["-b"]
        user_conf = os.path.expanduser("~/.config/picom.conf")
        if os.path.isfile(user_conf):
            args.extend(["--config", user_conf])
        elif os.path.isfile("/etc/xdg/picom.conf"):
            args.extend(["--config", "/etc/xdg/picom.conf"])
        elif os.path.isfile("/etc/xdg/compton.conf"):
            args.extend(["--config", "/etc/xdg/compton.conf"])
        elif os.path.basename(comp_bin) == "picom":
            args.extend(["--backend", "xrender", "--no-fading-openclose"])
        QProcess.startDetached(comp_bin, args, os.path.expanduser("~"))
        self._action_status.setStyleSheet(f"color: {COLORS['accent_aqua']}; font-weight: 600;")
        self._action_status.setText("Resumed picom compositor.")
        QTimer.singleShot(500, self._poll_telemetry)

    def _apply_governor(self) -> None:
        gov = self._gov_combo.currentText().strip()
        if not gov or gov.startswith("Host-managed"):
            return
        pkexec_bin = _which("pkexec")
        if not pkexec_bin:
            self._action_status.setText("pkexec required to switch CPU governor.")
            return
        script = (
            'for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do '
            '[ -w "$g" ] && printf "%s" "$1" > "$g"; '
            'done'
        )
        self._run_priv_async(
            [pkexec_bin, "bash", "-c", script, "vice-gov", gov],
            f"CPU governor switched to '{gov}'.",
        )

    def _renice_selected(self, nice_val: int) -> None:
        pid = self._selected_pid()
        if pid is None:
            self._action_status.setText("Select a process first.")
            return
        renice_bin = _which("renice")
        if not renice_bin:
            self._action_status.setText("renice binary missing.")
            return
        res = subprocess.run([renice_bin, "-n", str(nice_val), "-p", str(pid)], capture_output=True, text=True)
        if res.returncode == 0:
            self._on_priv_done(True, f"Set PID {pid} nice={nice_val}.")
        elif _which("pkexec"):
            self._run_priv_async(
                [_which("pkexec"), renice_bin, "-n", str(nice_val), "-p", str(pid)],
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
            pkexec_bin = _which("pkexec")
            if pkexec_bin:
                self._run_priv_async(
                    [pkexec_bin, "kill", "-TERM", str(pid)],
                    f"Sent SIGTERM to PID {pid}.",
                )
            else:
                self._on_priv_done(False, f"Permission denied terminating PID {pid}.")
        except Exception as exc:
            self._on_priv_done(False, f"Error: {exc}")

    def _drop_caches(self) -> None:
        pkexec_bin = _which("pkexec")
        if not pkexec_bin:
            self._action_status.setText("pkexec required for privileged cache drop.")
            return
        sysctl_bin = _which("sysctl") or "sysctl"
        self._run_priv_async(
            [pkexec_bin, "sh", "-c", f"sync && {sysctl_bin} -w vm.drop_caches=3"],
            "Dropped Linux page/dentry/inode caches (vm.drop_caches=3).",
        )

    def _set_swappiness(self, val: int) -> None:
        pkexec_bin = _which("pkexec")
        if not pkexec_bin:
            self._action_status.setText("pkexec required for sysctl tuning.")
            return
        sysctl_bin = _which("sysctl") or "sysctl"
        self._run_priv_async(
            [pkexec_bin, sysctl_bin, "-w", f"vm.swappiness={int(val)}"],
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
