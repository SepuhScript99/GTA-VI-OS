#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) — Vice Hardware & System Deck.
Multi-tab hardware and OS inspector covering CPU/Arch, Memory/Swap,
Storage/Mounts, PCI/USB, Audio Sinks/Cards (pactl/aplay/wpctl),
and Network interfaces with JSON and text report export.
Styled via vice_theme (Noto Sans CJK fallback).
"""

from datetime import datetime
import json
import os
import platform
import shutil
import signal
import subprocess
import sys

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication, QFileDialog, QMainWindow, QMessageBox,
    QPlainTextEdit, QTabWidget, QVBoxLayout, QWidget
)

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in ("/opt/vice-os", _HERE, "/opt/vice-os/lib"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from vice_theme import (  # noqa: E402
    apply_app_theme,
    load_tool_icon,
    make_button,
    make_header,
)

try:
    from python.vice_utils import log_info  # noqa: E402
except ImportError:
    def log_info(msg: str) -> None:
        print(f"[INFO] {msg}")


def _read_text(path: str, limit: int = 8000) -> str:
    if not os.path.isfile(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fp:
            return fp.read(limit).strip()
    except OSError:
        return ""


def _run_tool(cmd: list, timeout: int = 3) -> str:
    sbin_path = os.pathsep.join([
        os.environ.get("PATH", ""),
        "/usr/local/sbin",
        "/usr/sbin",
        "/sbin",
    ])
    exe = shutil.which(cmd[0]) or shutil.which(cmd[0], path=sbin_path)
    if not exe:
        return f"[{cmd[0]} not installed]"
    try:
        res = subprocess.run([exe] + cmd[1:], capture_output=True, text=True, timeout=timeout)
        out = res.stdout.strip() or res.stderr.strip()
        return out or "(no output)"
    except Exception as exc:
        return f"Error running {' '.join(cmd)}: {exc}"


class SysDeckWorker(QThread):
    """Collects multi-subsystem hardware & OS inspection data off the UI thread."""
    report_ready = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self._stopped = False

    def stop(self) -> None:
        self._stopped = True

    def run(self) -> None:
        data = {}

        u = platform.uname()
        dmi_lines = []
        for field in ("sys_vendor", "product_name", "bios_version"):
            val = _read_text(f"/sys/class/dmi/id/{field}", 256)
            if val:
                dmi_lines.append(f"{field}: {val}")
        os_rel = _read_text("/etc/os-release", 2048)
        cpu_parts = [
            f"=== System & Kernel ===\nNode: {u.node}\nSystem: {u.system} {u.release}\nVersion: {u.version}\nArch: {u.machine}",
        ]
        if dmi_lines:
            cpu_parts.append("=== DMI / Hardware ===\n" + "\n".join(dmi_lines))
        if os_rel:
            cpu_parts.append("=== /etc/os-release ===\n" + os_rel)
        cpu_parts.append("=== CPU (lscpu) ===\n" + _run_tool(["lscpu"]))
        data["cpu"] = "\n\n".join(cpu_parts)
        if self._stopped:
            return

        mem_parts = ["=== Memory Overview (free -h) ===\n" + _run_tool(["free", "-h"])]
        if _run_tool(["zramctl"]) != "[zramctl not installed]":
            mem_parts.append("=== ZRAM Devices (zramctl) ===\n" + _run_tool(["zramctl"]))
        swaps = _read_text("/proc/swaps", 2048)
        if swaps:
            mem_parts.append("=== Swap Devices (/proc/swaps) ===\n" + swaps)
        meminfo = _read_text("/proc/meminfo", 4096)
        if meminfo:
            mem_parts.append("=== /proc/meminfo ===\n" + meminfo)
        data["memory"] = "\n\n".join(mem_parts)
        if self._stopped:
            return

        stor_parts = [
            "=== Block Devices (lsblk) ===\n" + _run_tool(["lsblk", "-o", "NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,MODEL"]),
            "=== Filesystem Usage (df -hT) ===\n" + _run_tool(["df", "-hT"]),
        ]
        mounts = _read_text("/proc/mounts", 4096)
        if mounts:
            real_mounts = [
                ln for ln in mounts.splitlines()
                if ln.startswith(("/dev/", "overlay", "tmpfs /"))
            ]
            if real_mounts:
                stor_parts.append("=== Key Mounts (/proc/mounts) ===\n" + "\n".join(real_mounts))
        data["storage"] = "\n\n".join(stor_parts)
        if self._stopped:
            return

        pci_out = _run_tool(["lspci"])
        usb_out = _run_tool(["lsusb"])
        data["devices"] = f"=== PCI Devices (lspci) ===\n{pci_out}\n\n=== USB Devices (lsusb) ===\n{usb_out}"
        if self._stopped:
            return

        aud_parts = [
            "=== PipeWire / Pulse Server (pactl info) ===\n" + _run_tool(["pactl", "info"]),
            "=== Audio Sinks (pactl list short sinks) ===\n" + _run_tool(["pactl", "list", "short", "sinks"]),
            "=== Audio Sources (pactl list short sources) ===\n" + _run_tool(["pactl", "list", "short", "sources"]),
            "=== ALSA Playback Hardware (aplay -l) ===\n" + _run_tool(["aplay", "-l"]),
            "=== WirePlumber Status (wpctl status) ===\n" + _run_tool(["wpctl", "status"]),
        ]
        data["audio"] = "\n\n".join(aud_parts)
        if self._stopped:
            return

        net_parts = [
            "=== Interfaces (ip -br addr) ===\n" + _run_tool(["ip", "-br", "addr"]),
            "=== Routing Table (ip route) ===\n" + _run_tool(["ip", "route"]),
            "=== NetworkManager (nmcli dev status) ===\n" + _run_tool(["nmcli", "dev", "status"]),
        ]
        resolv = _read_text("/etc/resolv.conf", 2048)
        if resolv:
            net_parts.append("=== /etc/resolv.conf ===\n" + resolv)
        data["network"] = "\n\n".join(net_parts)

        if not self._stopped:
            self.report_ready.emit(data)


class ViceSysDeckApp(QMainWindow):
    """Main window for Vice Hardware & System Deck."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice Hardware & System Deck — Vice OS")
        self.resize(960, 660)
        self.setMinimumSize(760, 520)
        icon = load_tool_icon("vice-tool-sys-deck", "computer")
        if not icon.isNull():
            self.setWindowIcon(icon)

        self._worker = None
        self._report = {}
        self._views = {}

        self._init_ui()
        self._refresh_all()

    def _init_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("RootWidget")
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.setSpacing(12)

        self._header = make_header(
            title="Vice Hardware & System Deck",
            subtitle="Loading hardware telemetry...",
            icon_name="vice-tool-sys-deck",
            badge_text="6 SUBSYSTEMS",
            badge_variant="neutral",
            parent=root,
        )
        ref_btn = make_button("Refresh All", variant="primary", icon_name="view-refresh", parent=self._header)
        ref_btn.clicked.connect(self._refresh_all)
        self._header.right_layout.addWidget(ref_btn)

        exp_json = make_button("Export JSON...", variant="secondary", parent=self._header)
        exp_json.clicked.connect(lambda: self._export_report("json"))
        self._header.right_layout.addWidget(exp_json)

        exp_txt = make_button("Export Text...", variant="secondary", parent=self._header)
        exp_txt.clicked.connect(lambda: self._export_report("txt"))
        self._header.right_layout.addWidget(exp_txt)
        layout.addWidget(self._header)

        tabs = QTabWidget(root)
        for key, label in (
            ("cpu", "CPU & OS"),
            ("memory", "Memory & Swap"),
            ("storage", "Storage & Mounts"),
            ("devices", "PCI & USB"),
            ("audio", "Audio Sinks / ALSA"),
            ("network", "Network Interfaces"),
        ):
            edit = QPlainTextEdit()
            edit.setReadOnly(True)
            edit.setPlainText("Probing subsystem...")
            self._views[key] = edit
            tabs.addTab(edit, label.replace("&", "&&"))
        layout.addWidget(tabs, 1)

    def _refresh_all(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self._header.subtitle_label.setText(
            "Inspecting CPU, Memory, Storage, PCI/USB, Audio, and Network..."
        )
        self._header.set_badge("PROBING", "aqua")
        self._worker = SysDeckWorker()
        self._worker.report_ready.connect(self._on_report_ready)
        self._worker.start()

    def _on_report_ready(self, data: dict) -> None:
        self._report = data
        for key, edit in self._views.items():
            edit.setPlainText(data.get(key, ""))
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._header.subtitle_label.setText(f"Inspection complete at {ts}")
        self._header.set_badge("READY", "success")
        log_info("Vice Hardware & System Deck refreshed")

    def _export_report(self, fmt: str) -> None:
        if not self._report:
            QMessageBox.information(self, "No Data", "Wait for inspection to complete first.")
            return
        default_name = os.path.expanduser(f"~/vice-sys-deck-report.{fmt}")
        flt = "JSON (*.json)" if fmt == "json" else "Text (*.txt)"
        path, _ = QFileDialog.getSaveFileName(self, "Export System Deck Report", default_name, flt)
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="\n") as fp:
                if fmt == "json":
                    payload = {
                        "generated_at": datetime.now().isoformat(),
                        "host": platform.node(),
                        "sections": self._report,
                    }
                    json.dump(payload, fp, indent=2, ensure_ascii=False)
                    fp.write("\n")
                else:
                    fp.write(f"Vice OS Hardware & System Deck Report ({datetime.now().isoformat()})\n")
                    fp.write("=" * 72 + "\n\n")
                    for key, content in self._report.items():
                        fp.write(f"[{key.upper()}]\n{content}\n\n")
            QMessageBox.information(self, "Exported", f"Report saved to:\n{path}")
        except OSError as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))

    def closeEvent(self, event) -> None:
        if self._worker is not None:
            self._worker.stop()
            if self._worker.isRunning():
                self._worker.wait(2000)
        event.accept()


def main() -> None:
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    apply_app_theme(app)
    win = ViceSysDeckApp()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
