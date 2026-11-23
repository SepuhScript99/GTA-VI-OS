#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) — Leonida Net Radar.
Real LAN/host ping monitor, TCP port probe, DNS lookup (dig/socket),
and local network interface & routing inspector (ip/ss) with a Leonida neon radar UI.
"""

import math
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time

from PyQt5.QtCore import Qt, QProcess, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMainWindow, QPlainTextEdit, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget
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
QFrame#RadarBanner {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #15142d, stop:0.6 #221438, stop:1 #112438);
    border: 1px solid #00e5ff;
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
    padding: 8px 16px;
    margin-right: 4px;
    font-weight: bold;
}
QTabBar::tab:selected {
    background-color: #2f1d45;
    color: #00e5ff;
    border-color: #ff4da6;
}
QLineEdit, QComboBox, QSpinBox {
    background-color: #1b152e;
    color: #f4f1fa;
    border: 1px solid #3c2e5e;
    border-radius: 8px;
    padding: 7px 10px;
}
QLineEdit:focus {
    border-color: #00e5ff;
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
QPushButton#StopBtn {
    color: #ff4da6;
    border-color: #ff4da6;
}
QPushButton#StopBtn:hover {
    background-color: #ff4da6;
    color: #120e1e;
}
QPlainTextEdit {
    background-color: #0d0a18;
    color: #b8f5ff;
    border: 1px solid #30244a;
    border-radius: 8px;
    font-family: "Noto Sans Mono CJK JP", "Noto Sans Mono CJK SC", "DejaVu Sans Mono", monospace;
    font-size: 12px;
    padding: 8px;
}
QTableWidget {
    background-color: #0e0b19;
    color: #f4f1fa;
    border: 1px solid #30244a;
    gridline-color: #2a2042;
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
        "/usr/share/icons/hicolor/64x64/apps/vice-tool-net-radar.png",
        "/usr/share/pixmaps/vice-tool-net-radar.png",
    ):
        if os.path.isfile(path):
            pm = QPixmap(path)
            if not pm.isNull():
                return QIcon(pm)
    return QIcon.fromTheme("network-wired")


def parse_port_spec(spec: str) -> list:
    """Parse comma-separated ports and ranges (e.g. '22,80,443,8000-8005')."""
    ports = []
    seen = set()
    for token in spec.split(","):
        part = token.strip()
        if not part:
            continue
        if "-" in part:
            bounds = part.split("-", 1)
            try:
                lo, hi = int(bounds[0]), int(bounds[1])
            except ValueError:
                continue
            if lo > hi:
                lo, hi = hi, lo
            for p in range(max(1, lo), min(65535, hi) + 1):
                if p not in seen:
                    seen.add(p)
                    ports.append(p)
                if len(ports) >= 256:
                    return ports
        else:
            try:
                p = int(part)
            except ValueError:
                continue
            if 1 <= p <= 65535 and p not in seen:
                seen.add(p)
                ports.append(p)
                if len(ports) >= 256:
                    return ports
    return ports


class RadarScopeWidget(QWidget):
    """Custom Leonida neon radar scope widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(94, 94)
        self._angle = 0.0
        self._active = False
        self._blips = []
        self._timer = QTimer(self)
        self._timer.setInterval(65)
        self._timer.timeout.connect(self._tick)

    def set_active(self, active: bool) -> None:
        self._active = active
        if active and not self._timer.isActive():
            self._timer.start()
        elif not active and self._timer.isActive():
            self._timer.stop()
        self.update()

    def set_blips(self, count: int) -> None:
        self._blips = [
            ((i * 1.15) % (2 * math.pi), 0.35 + ((i * 0.23) % 0.55))
            for i in range(min(12, max(0, count)))
        ]
        self.update()

    def _tick(self) -> None:
        self._angle = (self._angle + 0.16) % (2 * math.pi)
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        cx, cy = self.width() / 2.0, self.height() / 2.0
        max_r = min(cx, cy) - 6.0

        painter.setBrush(QColor("#0d0919"))
        painter.setPen(QPen(QColor("#00e5ff"), 1.5))
        painter.drawEllipse(int(cx - max_r), int(cy - max_r), int(max_r * 2), int(max_r * 2))

        painter.setPen(QPen(QColor(0, 229, 255, 85), 1))
        for factor in (0.33, 0.66):
            r = max_r * factor
            painter.drawEllipse(int(cx - r), int(cy - r), int(r * 2), int(r * 2))
        painter.drawLine(int(cx - max_r), int(cy), int(cx + max_r), int(cy))
        painter.drawLine(int(cx), int(cy - max_r), int(cx), int(cy + max_r))

        if self._active:
            painter.setPen(QPen(QColor("#ff4da6"), 2.2))
            ex = cx + math.cos(self._angle) * max_r
            ey = cy + math.sin(self._angle) * max_r
            painter.drawLine(int(cx), int(cy), int(ex), int(ey))

        painter.setBrush(QColor("#ffd166"))
        painter.setPen(Qt.NoPen)
        for ang, dist in self._blips:
            bx = cx + math.cos(ang) * (max_r * dist)
            by = cy + math.sin(ang) * (max_r * dist)
            painter.drawEllipse(int(bx - 3), int(by - 3), 6, 6)
        painter.end()


class PortProbeWorker(QThread):
    """Non-blocking TCP port scanner using Python sockets."""
    port_result = pyqtSignal(int, str, str, str)
    scan_done = pyqtSignal(int, int)

    def __init__(self, host: str, ports: list, timeout_sec: float):
        super().__init__()
        self._host = host
        self._ports = ports
        self._timeout = timeout_sec
        self._stopped = False

    def stop(self) -> None:
        self._stopped = True

    def run(self) -> None:
        open_count = 0
        total = len(self._ports)
        for port in self._ports:
            if self._stopped:
                break
            try:
                service = socket.getservbyport(port, "tcp")
            except OSError:
                service = "unknown"

            t0 = time.monotonic()
            sock = None
            state = "CLOSED"
            latency = "-"
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self._timeout)
                rc = sock.connect_ex((self._host, port))
                elapsed_ms = (time.monotonic() - t0) * 1000.0
                if rc == 0:
                    state = "OPEN"
                    latency = f"{elapsed_ms:.1f} ms"
                    open_count += 1
            except socket.timeout:
                state = "TIMEOUT"
            except OSError as exc:
                state = f"ERR ({exc.errno or 'socket'})"
            finally:
                if sock is not None:
                    try:
                        sock.close()
                    except OSError:
                        pass
            self.port_result.emit(port, service, state, latency)
        self.scan_done.emit(open_count, total)


class DnsLookupWorker(QThread):
    """Non-blocking DNS query worker using dig or Python socket fallback."""
    lookup_done = pyqtSignal(str)

    def __init__(self, domain: str, rtype: str):
        super().__init__()
        self._domain = domain
        self._rtype = rtype
        self._stopped = False

    def stop(self) -> None:
        self._stopped = True

    def run(self) -> None:
        lines = [f"=== DNS Query: {self._domain} ({self._rtype}) ==="]
        dig_bin = shutil.which("dig")
        if dig_bin:
            try:
                res = subprocess.run(
                    [dig_bin, "+noall", "+answer", "+comments", self._domain, self._rtype],
                    capture_output=True, text=True, timeout=6
                )
                if res.stdout.strip():
                    lines.append(res.stdout.strip())
                if res.stderr.strip():
                    lines.append(res.stderr.strip())
            except Exception as exc:
                lines.append(f"dig failed: {exc}")
        else:
            lines.append("[dig not installed — using Python socket resolver]")
            try:
                infos = socket.getaddrinfo(self._domain, None)
                seen = set()
                for fam, _st, _pr, _cn, sockaddr in infos:
                    ip = sockaddr[0]
                    if ip not in seen:
                        seen.add(ip)
                        kind = "AAAA" if fam == socket.AF_INET6 else "A"
                        lines.append(f"{self._domain}\t{kind}\t{ip}")
            except socket.gaierror as exc:
                lines.append(f"Resolution failed: {exc}")

        if not self._stopped:
            self.lookup_done.emit("\n".join(lines))


class NetInspectWorker(QThread):
    """Collects local interface, routing, and socket statistics off the UI thread."""
    inspect_done = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._stopped = False

    def stop(self) -> None:
        self._stopped = True

    def _run_cmd(self, cmd: list) -> str:
        if not shutil.which(cmd[0]):
            return f"[{cmd[0]} not available]"
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            out = res.stdout.strip() or res.stderr.strip()
            return out or "(no output)"
        except Exception as exc:
            return f"Error running {' '.join(cmd)}: {exc}"

    def run(self) -> None:
        sections = []
        if shutil.which("ip"):
            sections.append("=== Network Interfaces (ip -br addr) ===\n" + self._run_cmd(["ip", "-br", "addr"]))
            sections.append("=== Routing Table (ip route) ===\n" + self._run_cmd(["ip", "route"]))
        else:
            sections.append(f"=== Hostname ===\n{socket.gethostname()}")

        if shutil.which("ss"):
            sections.append("=== Active Listening & Open Sockets (ss -tuln) ===\n" + self._run_cmd(["ss", "-tuln"]))
        elif shutil.which("netstat"):
            sections.append("=== Active Sockets (netstat -an) ===\n" + self._run_cmd(["netstat", "-an"]))

        if os.path.isfile("/etc/resolv.conf"):
            try:
                with open("/etc/resolv.conf", "r", encoding="utf-8", errors="ignore") as fp:
                    sections.append("=== /etc/resolv.conf ===\n" + fp.read().strip())
            except OSError:
                pass

        if not self._stopped:
            self.inspect_done.emit("\n\n".join(sections))


class LeonidaNetRadarApp(QMainWindow):
    """Main window for Leonida Net Radar."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Leonida Net Radar — Vice OS")
        self.resize(920, 640)
        self.setMinimumSize(760, 520)
        icon = _load_app_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)

        self._ping_proc = None
        self._workers = []

        self._init_ui()
        self._refresh_interfaces()

    def _init_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("RootWidget")
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.setSpacing(12)

        # Header + Radar Scope
        banner = QFrame(root)
        banner.setObjectName("RadarBanner")
        bh = QHBoxLayout(banner)
        bh.setContentsMargins(16, 10, 16, 10)
        bh.setSpacing(14)

        self._radar = RadarScopeWidget(banner)
        bh.addWidget(self._radar)

        title_col = QVBoxLayout()
        title_lbl = QLabel("LEONIDA NET RADAR · TELEMETRY & PROBE", banner)
        title_lbl.setStyleSheet("color: #ffd166; font-size: 19px; font-weight: bold; background: transparent;")
        title_col.addWidget(title_lbl)

        self._summary_lbl = QLabel("Standing by. Ready for Ping, TCP Port Probe, DNS, and Interface inspection.", banner)
        self._summary_lbl.setStyleSheet("color: #cfc6e6; font-size: 12px; background: transparent;")
        self._summary_lbl.setWordWrap(True)
        title_col.addWidget(self._summary_lbl)
        bh.addLayout(title_col, 1)

        layout.addWidget(banner)

        # Tabs
        tabs = QTabWidget(root)
        tabs.addTab(self._build_ping_tab(), "Ping Monitor")
        tabs.addTab(self._build_port_tab(), "TCP Port Probe")
        tabs.addTab(self._build_dns_tab(), "DNS Lookup")
        tabs.addTab(self._build_iface_tab(), "Interfaces & Routing")
        layout.addWidget(tabs, 1)

    def _build_ping_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(10)

        row = QHBoxLayout()
        self._ping_host = QLineEdit("1.1.1.1")
        self._ping_host.setPlaceholderText("Hostname or IP (e.g. 1.1.1.1, 192.168.1.1)")
        self._ping_host.returnPressed.connect(self._start_ping)
        row.addWidget(self._ping_host, 1)

        row.addWidget(QLabel("Count:"))
        self._ping_count = QSpinBox()
        self._ping_count.setRange(1, 50)
        self._ping_count.setValue(4)
        row.addWidget(self._ping_count)

        self._ping_btn = QPushButton("Ping")
        self._ping_btn.clicked.connect(self._start_ping)
        row.addWidget(self._ping_btn)

        self._ping_stop_btn = QPushButton("Stop")
        self._ping_stop_btn.setObjectName("StopBtn")
        self._ping_stop_btn.setEnabled(False)
        self._ping_stop_btn.clicked.connect(self._stop_ping)
        row.addWidget(self._ping_stop_btn)
        v.addLayout(row)

        presets = QHBoxLayout()
        for label, target in [("Cloudflare (1.1.1.1)", "1.1.1.1"), ("Google (8.8.8.8)", "8.8.8.8"),
                              ("Gateway (192.168.1.1)", "192.168.1.1"), ("Loopback", "127.0.0.1")]:
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, t=target: self._ping_host.setText(t))
            presets.addWidget(b)
        presets.addStretch(1)
        v.addLayout(presets)

        self._ping_out = QPlainTextEdit()
        self._ping_out.setReadOnly(True)
        v.addWidget(self._ping_out, 1)
        return w

    def _build_port_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(10)

        row = QHBoxLayout()
        self._port_host = QLineEdit("127.0.0.1")
        self._port_host.setPlaceholderText("Target host or IP")
        row.addWidget(self._port_host, 1)

        self._ports_edit = QLineEdit("22,53,80,443,631,3306,5432,8080,8443")
        self._ports_edit.setPlaceholderText("Ports (e.g. 22,80,443,8000-8010)")
        row.addWidget(self._ports_edit, 1)

        self._scan_btn = QPushButton("Probe Ports")
        self._scan_btn.clicked.connect(self._start_port_probe)
        row.addWidget(self._scan_btn)
        v.addLayout(row)

        self._port_table = QTableWidget(0, 4)
        self._port_table.setHorizontalHeaderLabels(["Port", "Service", "Status", "Latency"])
        self._port_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._port_table.setEditTriggers(QTableWidget.NoEditTriggers)
        v.addWidget(self._port_table, 1)
        return w

    def _build_dns_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(10)

        row = QHBoxLayout()
        self._dns_domain = QLineEdit("debian.org")
        self._dns_domain.setPlaceholderText("Domain or IP for reverse lookup")
        self._dns_domain.returnPressed.connect(self._start_dns_lookup)
        row.addWidget(self._dns_domain, 1)

        self._dns_type = QComboBox()
        self._dns_type.addItems(["A", "AAAA", "MX", "TXT", "NS", "CNAME", "PTR", "ANY"])
        row.addWidget(self._dns_type)

        self._dns_btn = QPushButton("Lookup")
        self._dns_btn.clicked.connect(self._start_dns_lookup)
        row.addWidget(self._dns_btn)
        v.addLayout(row)

        self._dns_out = QPlainTextEdit()
        self._dns_out.setReadOnly(True)
        v.addWidget(self._dns_out, 1)
        return w

    def _build_iface_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(10)

        row = QHBoxLayout()
        row.addWidget(QLabel("Live Network Interfaces, Routes, and Sockets (ip / ss):"))
        row.addStretch(1)
        ref_btn = QPushButton("Refresh")
        ref_btn.clicked.connect(self._refresh_interfaces)
        row.addWidget(ref_btn)
        v.addLayout(row)

        self._iface_out = QPlainTextEdit()
        self._iface_out.setReadOnly(True)
        v.addWidget(self._iface_out, 1)
        return w

    def _start_ping(self) -> None:
        target = self._ping_host.text().strip()
        if not target:
            return
        self._stop_ping()
        self._ping_out.clear()

        ping_bin = shutil.which("ping")
        if not ping_bin:
            self._ping_out.setPlainText("ping binary not found on system.")
            return

        count = str(self._ping_count.value())
        args = ["-n", count, target] if os.name == "nt" else ["-c", count, target]

        self._ping_proc = QProcess(self)
        self._ping_proc.setProcessChannelMode(QProcess.MergedChannels)
        self._ping_proc.readyReadStandardOutput.connect(self._read_ping_output)
        self._ping_proc.finished.connect(self._on_ping_finished)

        self._ping_btn.setEnabled(False)
        self._ping_stop_btn.setEnabled(True)
        self._radar.set_active(True)
        self._summary_lbl.setText(f"Pinging {target} ({count} packets)...")
        self._ping_proc.start(ping_bin, args)

    def _read_ping_output(self) -> None:
        if self._ping_proc is None:
            return
        chunk = bytes(self._ping_proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        if chunk:
            self._ping_out.moveCursor(self._ping_out.textCursor().End)
            self._ping_out.insertPlainText(chunk)

    def _on_ping_finished(self, exit_code: int, _status) -> None:
        self._ping_btn.setEnabled(True)
        self._ping_stop_btn.setEnabled(False)
        self._radar.set_active(False)
        text = self._ping_out.toPlainText()
        rtt_match = re.search(r"rtt [^=]+=\s*([\d./]+)\s*ms", text)
        loss_match = re.search(r"(\d+% packet loss)", text)
        summary = f"Ping finished (exit {exit_code})"
        if loss_match:
            summary += f" · {loss_match.group(1)}"
        if rtt_match:
            summary += f" · RTT min/avg/max/mdev: {rtt_match.group(1)} ms"
        self._summary_lbl.setText(summary)

    def _stop_ping(self) -> None:
        if self._ping_proc is not None and self._ping_proc.state() != QProcess.NotRunning:
            self._ping_proc.terminate()
            if not self._ping_proc.waitForFinished(800):
                self._ping_proc.kill()
                self._ping_proc.waitForFinished(500)
        self._ping_btn.setEnabled(True)
        self._ping_stop_btn.setEnabled(False)
        self._radar.set_active(False)

    def _track_worker(self, worker: QThread) -> None:
        self._workers = [w for w in self._workers if w.isRunning()]
        self._workers.append(worker)

    def _start_port_probe(self) -> None:
        host = self._port_host.text().strip()
        ports = parse_port_spec(self._ports_edit.text())
        if not host or not ports:
            self._summary_lbl.setText("Enter a valid host and port list (e.g. 22,80,443).")
            return
        self._port_table.setRowCount(0)
        self._scan_btn.setEnabled(False)
        self._radar.set_active(True)
        self._radar.set_blips(0)
        self._summary_lbl.setText(f"Probing {len(ports)} TCP ports on {host}...")

        worker = PortProbeWorker(host, ports, 0.7)
        worker.port_result.connect(self._on_port_row)
        worker.scan_done.connect(self._on_port_scan_done)
        self._track_worker(worker)
        worker.start()

    def _on_port_row(self, port: int, service: str, state: str, latency: str) -> None:
        row = self._port_table.rowCount()
        self._port_table.insertRow(row)
        items = [
            QTableWidgetItem(str(port)),
            QTableWidgetItem(service),
            QTableWidgetItem(state),
            QTableWidgetItem(latency),
        ]
        color = QColor("#64ffda") if state == "OPEN" else QColor("#cfc6e6")
        for col, item in enumerate(items):
            item.setForeground(color)
            self._port_table.setItem(row, col, item)

    def _on_port_scan_done(self, open_count: int, total: int) -> None:
        self._scan_btn.setEnabled(True)
        self._radar.set_active(False)
        self._radar.set_blips(open_count)
        self._summary_lbl.setText(f"TCP Probe complete: {open_count} open out of {total} scanned.")

    def _start_dns_lookup(self) -> None:
        domain = self._dns_domain.text().strip()
        if not domain:
            return
        rtype = self._dns_type.currentText()
        self._dns_btn.setEnabled(False)
        self._radar.set_active(True)
        self._dns_out.setPlainText(f"Resolving {domain} ({rtype})...")

        worker = DnsLookupWorker(domain, rtype)
        worker.lookup_done.connect(self._on_dns_done)
        self._track_worker(worker)
        worker.start()

    def _on_dns_done(self, text: str) -> None:
        self._dns_btn.setEnabled(True)
        self._radar.set_active(False)
        self._dns_out.setPlainText(text)
        self._summary_lbl.setText("DNS lookup complete.")

    def _refresh_interfaces(self) -> None:
        worker = NetInspectWorker()
        worker.inspect_done.connect(self._iface_out.setPlainText)
        self._track_worker(worker)
        worker.start()

    def closeEvent(self, event) -> None:
        self._stop_ping()
        self._radar.set_active(False)
        for worker in self._workers:
            if hasattr(worker, "stop"):
                worker.stop()
            if worker.isRunning():
                worker.wait(1500)
        log_info("Leonida Net Radar shut down cleanly.")
        event.accept()


def main() -> None:
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    _configure_cjk_fonts(app)
    app.setStyleSheet(STYLE)
    win = LeonidaNetRadarApp()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
