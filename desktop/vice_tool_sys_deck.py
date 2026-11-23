#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) — Vice Hardware & System Deck.
Multi-tab hardware and OS inspector covering CPU/Arch, Memory/Swap,
Storage/Mounts, PCI/USB, Audio Sinks/Cards (pactl/aplay/wpctl),
and Network interfaces with JSON and text report export.
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
from PyQt5.QtGui import QFont, QIcon, QPixmap
from PyQt5.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QPlainTextEdit, QPushButton, QTabWidget, QVBoxLayout, QWidget
)

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
        stop:0 #1d1433, stop:0.6 #2e143a, stop:1 #13253a);
    border: 1px solid #ff8a5b;
    border-radius: 12px;
}
QTabWidget::pane {
    border: 1px solid #3c2e5e;
    border-radius: 10px;
    background-color: #161126;
}
QTabBar::tab {
    background-color: #1b152e;
    color: #cfc6e6;
    border: 1px solid #322650;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 8px 14px;
    margin-right: 4px;
    font-weight: bold;
}
QTabBar::tab:selected {
    background-color: #311d46;
    color: #ffd166;
    border-color: #ff4da6;
}
QPlainTextEdit {
    background-color: #0d0a18;
    color: #b8f5ff;
    border: 1px solid #30244a;
    border-radius: 8px;
    font-family: "Noto Sans Mono CJK JP", "Noto Sans Mono CJK SC", "DejaVu Sans Mono", monospace;
    font-size: 12px;
    padding: 10px;
}
QPushButton {
    background-color: #1f1836;
    color: #00e5ff;
    border: 1px solid #00e5ff;
    border-radius: 8px;
    padding: 7px 14px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #00e5ff;
    color: #120e1e;
}
QPushButton#ExportBtn {
    color: #ffd166;
    border-color: #ff8a5b;
}
QPushButton#ExportBtn:hover {
    background-color: #ff8a5b;
    color: #120e1e;
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
        "/usr/share/icons/hicolor/64x64/apps/vice-tool-sys-deck.png",
        "/usr/share/pixmaps/vice-tool-sys-deck.png",
    ):
        if os.path.isfile(path):
            pm = QPixmap(path)
            if not pm.isNull():
                return QIcon(pm)
    return QIcon.fromTheme("computer")


def _read_text(path: str, limit: int = 8000) -> str:
    if not os.path.isfile(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fp:
            return fp.read(limit).strip()
    except OSError:
        return ""


def _run_tool(cmd: list, timeout: int = 4) -> str:
    if not shutil.which(cmd[0]):
        return f"[{cmd[0]} not installed]"
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
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

        # 1. CPU & OS
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

        # 2. Memory & Swap
        mem_parts = ["=== Memory Overview (free -h) ===\n" + _run_tool(["free", "-h"])]
        swaps = _read_text("/proc/swaps", 2048)
        if swaps:
            mem_parts.append("=== Swap Devices (/proc/swaps) ===\n" + swaps)
        meminfo = _read_text("/proc/meminfo", 4096)
        if meminfo:
            mem_parts.append("=== /proc/meminfo ===\n" + meminfo)
        data["memory"] = "\n\n".join(mem_parts)
        if self._stopped:
            return

        # 3. Storage & Mounts
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

        # 4. PCI & USB
        pci_out = _run_tool(["lspci"])
        usb_out = _run_tool(["lsusb"])
        data["devices"] = f"=== PCI Devices (lspci) ===\n{pci_out}\n\n=== USB Devices (lsusb) ===\n{usb_out}"
        if self._stopped:
            return

        # 5. Audio Stack
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

        # 6. Network
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
        self.setWindowTitle("Vice Hardware & System Deck — Leonida Inspector")
        self.resize(960, 660)
        self.setMinimumSize(760, 520)
        icon = _load_app_icon()
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

        banner = QFrame(root)
        banner.setObjectName("Banner")
        bh = QHBoxLayout(banner)
        bh.setContentsMargins(16, 12, 16, 12)

        col = QVBoxLayout()
        title = QLabel("VICE HARDWARE & SYSTEM DECK", banner)
        title.setStyleSheet("color: #ffd166; font-size: 19px; font-weight: bold; background: transparent;")
        col.addWidget(title)
        self._sub_lbl = QLabel("Loading hardware telemetry...", banner)
        self._sub_lbl.setStyleSheet("color: #cfc6e6; font-size: 12px; background: transparent;")
        col.addWidget(self._sub_lbl)
        bh.addLayout(col, 1)

        ref_btn = QPushButton("Refresh All", banner)
        ref_btn.clicked.connect(self._refresh_all)
        bh.addWidget(ref_btn)

        exp_json = QPushButton("Export JSON...", banner)
        exp_json.setObjectName("ExportBtn")
        exp_json.clicked.connect(lambda: self._export_report("json"))
        bh.addWidget(exp_json)

        exp_txt = QPushButton("Export Text...", banner)
        exp_txt.setObjectName("ExportBtn")
        exp_txt.clicked.connect(lambda: self._export_report("txt"))
        bh.addWidget(exp_txt)

        layout.addWidget(banner)

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
            tabs.addTab(edit, label)
        layout.addWidget(tabs, 1)

    def _refresh_all(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self._sub_lbl.setText("Inspecting CPU, Memory, Storage, PCI/USB, Audio, and Network...")
        self._worker = SysDeckWorker()
        self._worker.report_ready.connect(self._on_report_ready)
        self._worker.start()

    def _on_report_ready(self, data: dict) -> None:
        self._report = data
        for key, edit in self._views.items():
            edit.setPlainText(data.get(key, ""))
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._sub_lbl.setText(f"Inspection complete at {ts} — 6 hardware & OS subsystems")
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
    _configure_cjk_fonts(app)
    app.setStyleSheet(STYLE)
    win = ViceSysDeckApp()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
