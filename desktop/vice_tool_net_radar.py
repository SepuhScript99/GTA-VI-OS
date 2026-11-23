#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) — Leonida Net Radar.
Live LAN/host ping monitor, TCP port probe, DNS lookup (dig/socket),
and local network interface & routing inspector (ip/ss) styled via
vice_theme (Noto Sans CJK fallback).
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
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMainWindow, QPlainTextEdit, QSpinBox,
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget
)

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
    qcolor,
)

try:
    from python.vice_utils import log_info  # noqa: E402
except ImportError:
    def log_info(msg: str) -> None:
        print(f"[INFO] {msg}")


_HOST_RE = re.compile(r"^[A-Za-z0-9._:-]{1,253}$")


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


def _valid_host(host: str) -> bool:
    clean = host.strip()
    return bool(clean and not clean.startswith("-") and _HOST_RE.match(clean))


class RadarScopeWidget(QWidget):
    """Subtle slate telemetry radar scope widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(82, 82)
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
        max_r = min(cx, cy) - 5.0

        painter.setBrush(QColor(COLORS["bg_canvas"]))
        painter.setPen(QPen(QColor(COLORS["border_strong"]), 1.4))
        painter.drawEllipse(int(cx - max_r), int(cy - max_r), int(max_r * 2), int(max_r * 2))

        painter.setPen(QPen(QColor(COLORS["border"]), 1))
        for factor in (0.33, 0.66):
            r = max_r * factor
            painter.drawEllipse(int(cx - r), int(cy - r), int(r * 2), int(r * 2))
        painter.drawLine(int(cx - max_r), int(cy), int(cx + max_r), int(cy))
        painter.drawLine(int(cx), int(cy - max_r), int(cx), int(cy + max_r))

        if self._active:
            painter.setPen(QPen(QColor(COLORS["accent_aqua"]), 2.0))
            ex = cx + math.cos(self._angle) * max_r
            ey = cy + math.sin(self._angle) * max_r
            painter.drawLine(int(cx), int(cy), int(ex), int(ey))

        painter.setBrush(QColor(COLORS["accent_coral"]))
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
        self.resize(940, 650)
        self.setMinimumSize(760, 520)
        icon = load_tool_icon("vice-tool-net-radar", "network-wired")
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

        self._header = make_header(
            title="Leonida Net Radar",
            subtitle="Ping telemetry, TCP port probe, DNS lookup, and routing inspector",
            icon_name="vice-tool-net-radar",
            badge_text="IDLE",
            badge_variant="neutral",
            parent=root,
        )
        self._radar = RadarScopeWidget(self._header)
        self._header.right_layout.addWidget(self._radar)
        layout.addWidget(self._header)

        tabs = QTabWidget(root)
        tabs.addTab(self._build_ping_tab(), "Ping Monitor")
        tabs.addTab(self._build_port_tab(), "TCP Port Probe")
        tabs.addTab(self._build_dns_tab(), "DNS Lookup")
        tabs.addTab(self._build_iface_tab(), "Interfaces && Routing")
        layout.addWidget(tabs, 1)

        self._summary_lbl = QLabel("Standing by. Ready for Ping, TCP Port Probe, DNS, and Interface inspection.", root)
        self._summary_lbl.setObjectName("MutedLabel")
        self._summary_lbl.setWordWrap(True)
        layout.addWidget(self._summary_lbl)

    def _build_ping_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(10)

        row = QHBoxLayout()
        row.setSpacing(8)
        self._ping_host = QLineEdit("1.1.1.1")
        self._ping_host.setPlaceholderText("Hostname or IP (e.g. 1.1.1.1, 192.168.1.1)")
        self._ping_host.returnPressed.connect(self._start_ping)
        row.addWidget(self._ping_host, 1)

        row.addWidget(QLabel("Count:"))
        self._ping_count = QSpinBox()
        self._ping_count.setRange(1, 50)
        self._ping_count.setValue(4)
        row.addWidget(self._ping_count)

        self._ping_btn = make_button("Ping", variant="primary")
        self._ping_btn.clicked.connect(self._start_ping)
        row.addWidget(self._ping_btn)

        self._ping_stop_btn = make_button("Stop", variant="danger")
        self._ping_stop_btn.setEnabled(False)
        self._ping_stop_btn.clicked.connect(self._stop_ping)
        row.addWidget(self._ping_stop_btn)
        v.addLayout(row)

        presets = QHBoxLayout()
        presets.setSpacing(6)
        for label, target in (
            ("Cloudflare 1.1.1.1", "1.1.1.1"),
            ("Google 8.8.8.8", "8.8.8.8"),
            ("Quad9 9.9.9.9", "9.9.9.9"),
            ("Loopback 127.0.0.1", "127.0.0.1"),
        ):
            b = make_button(label, variant="secondary")
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
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(10)

        row = QHBoxLayout()
        row.setSpacing(8)
        self._port_host = QLineEdit("127.0.0.1")
        self._port_host.setPlaceholderText("Target host or IP")
        row.addWidget(self._port_host, 1)

        self._ports_edit = QLineEdit("22,53,80,443,631,3306,5432,8080,8443")
        self._ports_edit.setPlaceholderText("Ports (e.g. 22,80,443,8000-8010)")
        row.addWidget(self._ports_edit, 1)

        self._scan_btn = make_button("Probe Ports", variant="primary")
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
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(10)

        row = QHBoxLayout()
        row.setSpacing(8)
        self._dns_domain = QLineEdit("debian.org")
        self._dns_domain.setPlaceholderText("Domain or IP for reverse lookup")
        self._dns_domain.returnPressed.connect(self._start_dns_lookup)
        row.addWidget(self._dns_domain, 1)

        self._dns_type = QComboBox()
        self._dns_type.addItems(["A", "AAAA", "MX", "TXT", "NS", "CNAME", "PTR", "ANY"])
        row.addWidget(self._dns_type)

        self._dns_btn = make_button("Lookup", variant="primary")
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
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(10)

        row = QHBoxLayout()
        hdr_lbl = QLabel("Live Network Interfaces, Routes, and Sockets (ip / ss)")
        hdr_lbl.setObjectName("SectionTitle")
        row.addWidget(hdr_lbl)
        row.addStretch(1)
        ref_btn = make_button("Refresh", variant="secondary", icon_name="view-refresh")
        ref_btn.clicked.connect(self._refresh_interfaces)
        row.addWidget(ref_btn)
        v.addLayout(row)

        self._iface_out = QPlainTextEdit()
        self._iface_out.setReadOnly(True)
        v.addWidget(self._iface_out, 1)
        return w

    def _start_ping(self) -> None:
        target = self._ping_host.text().strip()
        if not _valid_host(target):
            self._summary_lbl.setText("Enter a valid hostname or IP address.")
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
        self._header.set_badge("PINGING", "aqua")
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
        self._header.set_badge("COMPLETE" if exit_code == 0 else "IDLE", "success" if exit_code == 0 else "neutral")
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
        self._header.set_badge("IDLE", "neutral")

    def _track_worker(self, worker: QThread) -> None:
        self._workers = [w for w in self._workers if w.isRunning()]
        self._workers.append(worker)

    def _start_port_probe(self) -> None:
        host = self._port_host.text().strip()
        ports = parse_port_spec(self._ports_edit.text())
        if not _valid_host(host) or not ports:
            self._summary_lbl.setText("Enter a valid host and port list (e.g. 22,80,443).")
            return
        self._port_table.setRowCount(0)
        self._scan_btn.setEnabled(False)
        self._radar.set_active(True)
        self._radar.set_blips(0)
        self._header.set_badge("SCANNING", "aqua")
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
        color = qcolor("success") if state == "OPEN" else qcolor("text_secondary")
        for col, item in enumerate(items):
            item.setForeground(color)
            self._port_table.setItem(row, col, item)

    def _on_port_scan_done(self, open_count: int, total: int) -> None:
        self._scan_btn.setEnabled(True)
        self._radar.set_active(False)
        self._radar.set_blips(open_count)
        self._header.set_badge(f"{open_count} OPEN", "coral" if open_count else "neutral")
        self._summary_lbl.setText(f"TCP Probe complete: {open_count} open out of {total} scanned.")

    def _start_dns_lookup(self) -> None:
        domain = self._dns_domain.text().strip()
        if not _valid_host(domain):
            self._summary_lbl.setText("Enter a valid domain name or IP address.")
            return
        rtype = self._dns_type.currentText()
        self._dns_btn.setEnabled(False)
        self._radar.set_active(True)
        self._header.set_badge("RESOLVING", "aqua")
        self._dns_out.setPlainText(f"Resolving {domain} ({rtype})...")

        worker = DnsLookupWorker(domain, rtype)
        worker.lookup_done.connect(self._on_dns_done)
        self._track_worker(worker)
        worker.start()

    def _on_dns_done(self, text: str) -> None:
        self._dns_btn.setEnabled(True)
        self._radar.set_active(False)
        self._header.set_badge("READY", "neutral")
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
    apply_app_theme(app)
    win = LeonidaNetRadarApp()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
