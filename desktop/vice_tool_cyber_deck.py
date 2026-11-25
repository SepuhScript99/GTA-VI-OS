#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) — Vice Cyber Audit Deck.
Refined security & ethical recon workbench wrapping verified Debian Bookworm
tools (nmap, sslscan, testssl.sh, whatweb, wafw00f, dnsrecon, dnsenum, whois,
lynis, chkrootkit, rkhunter, arp-scan, exiftool, binwalk, yara, dirb, gobuster)
with strict target validation, zero shell injection (list-based QProcess),
safe preset scans, live streaming output, and Markdown/Text export.
Styled via vice_theme (Noto Sans CJK fallback).
"""

from datetime import datetime
import os
import re
import shutil
import signal
import sys

from PyQt5.QtCore import Qt, QProcess
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit,
    QVBoxLayout, QWidget
)

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in ("/opt/vice-os", _HERE, "/opt/vice-os/lib"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from vice_theme import (  # noqa: E402
    COLORS,
    MONO_STACK,
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


_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
_HOST_RE = re.compile(r"^[A-Za-z0-9._:/-]{1,253}$")
_DOMAIN_RE = re.compile(r"^[A-Za-z0-9.-]{1,253}$")
_URL_RE = re.compile(r"^https?://[A-Za-z0-9._:/?=&%-]{1,512}$")

CATEGORIES = [
    "All",
    "Network & Recon",
    "TLS & Web",
    "Host Hardening",
    "Forensics",
]

PRESETS = [
    {
        "id": "nmap_fast",
        "title": "Nmap Quick TCP Scan (-F)",
        "category": "Network & Recon",
        "bin": "nmap",
        "input_kind": "host",
        "default_target": "127.0.0.1",
        "placeholder": "Host, IP, or CIDR (e.g. 127.0.0.1, 192.168.1.0/24)",
        "note": "Unprivileged TCP connect scan of the top 100 common ports.",
        "pkexec": False,
        "args": lambda t, _e: ["-sT", "-F", "-T4", t],
    },
    {
        "id": "nmap_sv",
        "title": "Nmap Service & Version Probe",
        "category": "Network & Recon",
        "bin": "nmap",
        "input_kind": "host",
        "default_target": "127.0.0.1",
        "placeholder": "Host or IP (e.g. 127.0.0.1)",
        "note": "Detects listening service banners on the top 50 ports.",
        "pkexec": False,
        "args": lambda t, _e: ["-sT", "-sV", "--top-ports", "50", t],
    },
    {
        "id": "arp_scan",
        "title": "ARP-Scan Local Subnet",
        "category": "Network & Recon",
        "bin": "arp-scan",
        "input_kind": "none",
        "default_target": "",
        "placeholder": "No target required — discovers local Ethernet/Wi-Fi LAN hosts",
        "note": "Sends ARP discovery probes across the active local subnet (requires pkexec).",
        "pkexec": True,
        "args": lambda _t, _e: ["--localnet"],
    },
    {
        "id": "whois_lookup",
        "title": "WHOIS Domain / IP Ownership",
        "category": "Network & Recon",
        "bin": "whois",
        "input_kind": "host",
        "default_target": "debian.org",
        "placeholder": "Domain or IPv4/IPv6 address (e.g. debian.org)",
        "note": "Queries public registrar and ASN allocation records.",
        "pkexec": False,
        "args": lambda t, _e: [t],
    },
    {
        "id": "dnsrecon_std",
        "title": "DNSRecon Standard Audit",
        "category": "Network & Recon",
        "bin": "dnsrecon",
        "input_kind": "domain",
        "default_target": "debian.org",
        "placeholder": "Domain name (e.g. debian.org)",
        "note": "Enumerates NS, MX, SOA, TXT, and A/AAAA DNS records.",
        "pkexec": False,
        "args": lambda t, _e: ["-d", t, "-t", "std"],
    },
    {
        "id": "dnsenum_audit",
        "title": "DNSEnum Zone & Subdomain Check",
        "category": "Network & Recon",
        "bin": "dnsenum",
        "input_kind": "domain",
        "default_target": "debian.org",
        "placeholder": "Domain name (e.g. debian.org)",
        "note": "Queries host, NS, and MX records without slow reverse sweeps.",
        "pkexec": False,
        "args": lambda t, _e: ["--noreverse", t],
    },
    {
        "id": "sslscan_check",
        "title": "SSLScan TLS Ciphers & Certs",
        "category": "TLS & Web",
        "bin": "sslscan",
        "input_kind": "host",
        "default_target": "debian.org:443",
        "placeholder": "Host or host:port (e.g. debian.org:443)",
        "note": "Inspects supported TLS protocols, cipher suites, and certificate chain.",
        "pkexec": False,
        "args": lambda t, _e: ["--no-colour", t],
    },
    {
        "id": "testssl_fast",
        "title": "testssl TLS Server Audit",
        "category": "TLS & Web",
        "bin": "testssl",
        "alt_bins": ["testssl.sh"],
        "input_kind": "host",
        "default_target": "debian.org:443",
        "placeholder": "Host or host:port (e.g. example.com:443)",
        "note": "Checks TLS protocols, HSTS headers, and known TLS vulnerabilities.",
        "pkexec": False,
        "args": lambda t, _e: ["--color", "0", "--fast", t],
    },
    {
        "id": "whatweb_fp",
        "title": "WhatWeb Technology Fingerprint",
        "category": "TLS & Web",
        "bin": "whatweb",
        "input_kind": "url",
        "default_target": "https://debian.org",
        "placeholder": "Target URL (https://... or http://...)",
        "note": "Identifies web servers, frameworks, and HTTP headers passively.",
        "pkexec": False,
        "args": lambda t, _e: ["--color=never", t],
    },
    {
        "id": "wafw00f_detect",
        "title": "WAFW00F Firewall Detector",
        "category": "TLS & Web",
        "bin": "wafw00f",
        "input_kind": "url",
        "default_target": "https://debian.org",
        "placeholder": "Target URL (https://... or http://...)",
        "note": "Detects Web Application Firewalls fronting the target HTTP endpoint.",
        "pkexec": False,
        "args": lambda t, _e: [t],
    },
    {
        "id": "dirb_scan",
        "title": "Dirb Web Path Scanner",
        "category": "TLS & Web",
        "bin": "dirb",
        "input_kind": "url",
        "default_target": "http://127.0.0.1",
        "placeholder": "Authorized target URL (e.g. http://127.0.0.1)",
        "note": "Silent-mode common path discovery against authorized web services.",
        "pkexec": False,
        "args": lambda t, _e: [t, "-S"],
    },
    {
        "id": "lynis_audit",
        "title": "Lynis Local Security Audit",
        "category": "Host Hardening",
        "bin": "lynis",
        "input_kind": "none",
        "default_target": "",
        "placeholder": "Audits the local Vice OS / Debian system",
        "note": "Runs non-interactive Lynis system hardening and compliance audit.",
        "pkexec": True,
        "args": lambda _t, _e: ["audit", "system", "--quick", "--no-colors"],
    },
    {
        "id": "chkrootkit_scan",
        "title": "chkrootkit Rootkit Scanner",
        "category": "Host Hardening",
        "bin": "chkrootkit",
        "input_kind": "none",
        "default_target": "",
        "placeholder": "Audits local binaries and kernel hooks",
        "note": "Scans the local system for known rootkits in quiet mode.",
        "pkexec": True,
        "args": lambda _t, _e: ["-q"],
    },
    {
        "id": "rkhunter_check",
        "title": "rkhunter Integrity Check",
        "category": "Host Hardening",
        "bin": "rkhunter",
        "input_kind": "none",
        "default_target": "",
        "placeholder": "Audits local system files and rootkit signatures",
        "note": "Runs rkhunter non-interactively without pausing for keypresses.",
        "pkexec": True,
        "args": lambda _t, _e: ["--check", "--sk", "--nocolors"],
    },
    {
        "id": "exiftool_inspect",
        "title": "ExifTool Metadata Inspector",
        "category": "Forensics",
        "bin": "exiftool",
        "input_kind": "file",
        "default_target": "",
        "placeholder": "Path to image, PDF, audio, or document file",
        "note": "Extracts embedded EXIF, GPS coordinates, author, and software metadata.",
        "pkexec": False,
        "args": lambda t, _e: [t],
    },
    {
        "id": "binwalk_inspect",
        "title": "Binwalk Binary / Firmware Analysis",
        "category": "Forensics",
        "bin": "binwalk",
        "input_kind": "file",
        "default_target": "",
        "placeholder": "Path to firmware image or binary file",
        "note": "Scans binary blobs for embedded filesystems, archives, and headers.",
        "pkexec": False,
        "args": lambda t, _e: [t],
    },
    {
        "id": "yara_scan",
        "title": "YARA Rule Scanner",
        "category": "Forensics",
        "bin": "yara",
        "input_kind": "yara",
        "default_target": "",
        "placeholder": "Target file or directory to scan",
        "note": "Matches compiled or text YARA rule files against target binaries.",
        "pkexec": False,
        "args": lambda t, e: [e, t],
    },
]


def _validate_input(kind: str, target: str, extra: str = "") -> tuple:
    t = target.strip()
    e = extra.strip()
    if kind == "none":
        return True, ""
    if not t:
        return False, "Target input is required."
    if kind == "host":
        if t.startswith("-") or not _HOST_RE.match(t):
            return False, "Host/IP must contain only letters, digits, '.', '_', ':', '/', '-'."
    elif kind == "domain":
        if t.startswith("-") or not _DOMAIN_RE.match(t):
            return False, "Domain must contain only letters, digits, '.', and '-'."
    elif kind == "url":
        if not _URL_RE.match(t):
            return False, "URL must start with http:// or https:// without shell characters."
    elif kind == "file":
        if not os.path.isfile(t):
            return False, "Select an existing file path."
    elif kind == "yara":
        if not e or not os.path.isfile(e):
            return False, "Select an existing YARA rule (.yar) file."
        if not os.path.exists(t):
            return False, "Select an existing target file or directory."
    return True, ""


class ViceCyberDeckApp(QMainWindow):
    """Main window for Vice Cyber Audit Deck."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice Cyber Audit Deck — Vice OS")
        self.resize(1020, 680)
        self.setMinimumSize(820, 540)
        icon = load_tool_icon("vice-tool-cyber-deck", "security-high")
        if not icon.isNull():
            self.setWindowIcon(icon)

        self._proc = None
        self._current_preset = PRESETS[0]
        self._init_ui()
        self._populate_presets()

    def _init_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("RootWidget")
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.setSpacing(12)

        self._header = make_header(
            title="Vice Cyber Audit Deck",
            subtitle="Authorized security recon, TLS/DNS audit, rootkit checks, and file forensics",
            icon_name="vice-tool-cyber-deck",
            badge_text="IDLE",
            badge_variant="neutral",
            parent=root,
        )
        layout.addWidget(self._header)

        body = QHBoxLayout()
        body.setSpacing(12)

        # Left column: Category filter + Preset list
        left_card = make_card(title="Audit Presets", margins=(12, 12, 12, 12), spacing=8, parent=root)
        left_card.setFixedWidth(310)

        self._cat_combo = QComboBox(left_card)
        for cat in CATEGORIES:
            self._cat_combo.addItem(cat.replace("&", "&&"), cat)
        self._cat_combo.currentIndexChanged.connect(self._populate_presets)
        left_card.body_layout.addWidget(self._cat_combo)

        self._preset_list = QListWidget(left_card)
        self._preset_list.currentItemChanged.connect(self._on_preset_changed)
        left_card.body_layout.addWidget(self._preset_list, 1)
        body.addWidget(left_card)

        # Right column: Target controls + Streaming output
        right_col = QVBoxLayout()
        right_col.setSpacing(10)

        ctrl_card = make_card(parent=root, margins=(14, 12, 14, 12), spacing=8)
        title_row = QHBoxLayout()
        self._preset_title = QLabel("Select a preset", ctrl_card)
        self._preset_title.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 16px; font-weight: bold;"
        )
        title_row.addWidget(self._preset_title, 1)

        self._bin_status = QLabel("", ctrl_card)
        title_row.addWidget(self._bin_status)
        ctrl_card.body_layout.addLayout(title_row)

        self._preset_note = QLabel("", ctrl_card)
        self._preset_note.setObjectName("MutedLabel")
        self._preset_note.setWordWrap(True)
        ctrl_card.body_layout.addWidget(self._preset_note)

        # Target row
        t_row = QHBoxLayout()
        t_row.setSpacing(8)
        self._target_edit = QLineEdit(ctrl_card)
        self._target_edit.textChanged.connect(self._update_preview)
        self._target_edit.returnPressed.connect(self._run_audit)
        t_row.addWidget(self._target_edit, 1)

        self._browse_btn = make_button("Browse...", variant="secondary", parent=ctrl_card)
        self._browse_btn.clicked.connect(self._browse_target)
        t_row.addWidget(self._browse_btn)
        ctrl_card.body_layout.addLayout(t_row)

        # YARA Rule row (shown only for YARA preset)
        self._yara_row_widget = QWidget(ctrl_card)
        self._yara_row_widget.setStyleSheet("background: transparent;")
        y_row = QHBoxLayout(self._yara_row_widget)
        y_row.setContentsMargins(0, 0, 0, 0)
        y_row.setSpacing(8)
        self._yara_rule_edit = QLineEdit(self._yara_row_widget)
        self._yara_rule_edit.setPlaceholderText("Path to YARA rule (.yar / .yara)...")
        self._yara_rule_edit.textChanged.connect(self._update_preview)
        y_row.addWidget(self._yara_rule_edit, 1)
        y_btn = make_button("Rule File...", variant="secondary", parent=self._yara_row_widget)
        y_btn.clicked.connect(self._browse_yara_rule)
        y_row.addWidget(y_btn)
        ctrl_card.body_layout.addWidget(self._yara_row_widget)

        self._cmd_preview = QLabel("", ctrl_card)
        self._cmd_preview.setStyleSheet(
            f"color: {COLORS['accent_aqua']}; font-family: {MONO_STACK}; font-size: 11px;"
        )
        self._cmd_preview.setWordWrap(True)
        ctrl_card.body_layout.addWidget(self._cmd_preview)

        act_row = QHBoxLayout()
        act_row.setSpacing(8)
        self._run_btn = make_button("Run Audit", variant="primary", parent=ctrl_card)
        self._run_btn.clicked.connect(self._run_audit)
        act_row.addWidget(self._run_btn)

        self._stop_btn = make_button("Stop", variant="danger", parent=ctrl_card)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_audit)
        act_row.addWidget(self._stop_btn)

        clr_btn = make_button("Clear", variant="secondary", parent=ctrl_card)
        clr_btn.clicked.connect(lambda: self._output.clear())
        act_row.addWidget(clr_btn)

        act_row.addStretch(1)

        exp_md = make_button("Export Markdown...", variant="secondary", parent=ctrl_card)
        exp_md.clicked.connect(lambda: self._export_output("md"))
        act_row.addWidget(exp_md)

        exp_txt = make_button("Export Text...", variant="secondary", parent=ctrl_card)
        exp_txt.clicked.connect(lambda: self._export_output("txt"))
        act_row.addWidget(exp_txt)
        ctrl_card.body_layout.addLayout(act_row)

        right_col.addWidget(ctrl_card)

        self._output = QPlainTextEdit(root)
        self._output.setReadOnly(True)
        self._output.setPlainText("Select an authorized audit preset and click Run Audit.")
        right_col.addWidget(self._output, 1)

        body.addLayout(right_col, 1)
        layout.addLayout(body, 1)

    @staticmethod
    def _resolve_preset_bin(preset: dict) -> str:
        sbin_path = os.pathsep.join([
            os.environ.get("PATH", ""),
            "/usr/local/sbin",
            "/usr/sbin",
            "/sbin",
        ])
        for cand in [preset["bin"]] + list(preset.get("alt_bins", [])):
            found = shutil.which(cand) or shutil.which(cand, path=sbin_path)
            if found:
                return found
        return ""

    def _populate_presets(self) -> None:
        cat = self._cat_combo.currentData() or "All"
        self._preset_list.clear()
        for preset in PRESETS:
            if cat != "All" and preset["category"] != cat:
                continue
            avail = bool(self._resolve_preset_bin(preset))
            tag = "READY" if avail else "MISSING"
            item = QListWidgetItem(f"{preset['title']}\n  {preset['bin']} · {tag}")
            item.setData(Qt.UserRole, preset)
            self._preset_list.addItem(item)
        if self._preset_list.count() > 0:
            self._preset_list.setCurrentRow(0)

    def _on_preset_changed(self, current: QListWidgetItem, _prev) -> None:
        if current is None:
            return
        preset = current.data(Qt.UserRole)
        if not preset:
            return
        self._current_preset = preset
        self._preset_title.setText(preset["title"])
        self._preset_note.setText(preset["note"])

        avail = bool(self._resolve_preset_bin(preset))
        if avail:
            self._bin_status.setText(f"{preset['bin']} installed")
            self._bin_status.setStyleSheet(f"color: {COLORS['success']}; font-weight: bold; font-size: 12px;")
        else:
            self._bin_status.setText(f"{preset['bin']} missing")
            self._bin_status.setStyleSheet(f"color: {COLORS['danger']}; font-weight: bold; font-size: 12px;")

        kind = preset["input_kind"]
        self._target_edit.setEnabled(kind != "none")
        self._target_edit.setPlaceholderText(preset["placeholder"])
        self._target_edit.setText(preset["default_target"])
        self._browse_btn.setVisible(kind in ("file", "yara"))
        self._yara_row_widget.setVisible(kind == "yara")
        self._update_preview()

    def _build_command(self) -> tuple:
        p = self._current_preset
        prog_path = self._resolve_preset_bin(p)
        if not prog_path:
            return "", [], f"Binary '{p['bin']}' is not installed."

        ok, err = _validate_input(
            p["input_kind"], self._target_edit.text(), self._yara_rule_edit.text()
        )
        if not ok:
            return "", [], err

        args = p["args"](self._target_edit.text().strip(), self._yara_rule_edit.text().strip())
        if p["pkexec"]:
            pk = shutil.which("pkexec")
            if pk:
                return pk, [prog_path] + args, ""
        return prog_path, args, ""

    def _update_preview(self) -> None:
        prog, args, err = self._build_command()
        if prog:
            self._cmd_preview.setText("Command: " + " ".join([os.path.basename(prog)] + args))
        else:
            p = self._current_preset
            self._cmd_preview.setText(f"Tool: {p['bin']}  ({err})")

    def _browse_target(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select Target File", os.path.expanduser("~"))
        if path:
            self._target_edit.setText(path)

    def _browse_yara_rule(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select YARA Rule File", os.path.expanduser("~"), "YARA Rules (*.yar *.yara);;All Files (*)"
        )
        if path:
            self._yara_rule_edit.setText(path)

    def _run_audit(self) -> None:
        if self._proc is not None and self._proc.state() != QProcess.NotRunning:
            return
        prog, args, err = self._build_command()
        if not prog:
            QMessageBox.warning(self, "Cannot Run Audit", err)
            return

        self._output.clear()
        self._output.appendPlainText(
            f"# {self._current_preset['title']}\n$ {prog} {' '.join(args)}\n"
        )
        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(QProcess.MergedChannels)
        self._proc.readyReadStandardOutput.connect(self._on_output)
        self._proc.finished.connect(self._on_finished)
        self._proc.errorOccurred.connect(self._on_proc_error)

        self._run_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._header.set_badge("SCANNING", "aqua")
        log_info(f"Vice Cyber Audit Deck running {self._current_preset['id']}")
        self._proc.start(prog, args)

    def _on_proc_error(self, _err) -> None:
        self._run_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._header.set_badge("ERROR", "danger")
        msg = self._proc.errorString() if self._proc is not None else "Process failed to start"
        self._output.appendPlainText(f"\n[ERROR] {msg}\n")

    def _on_output(self) -> None:
        if self._proc is None:
            return
        raw = bytes(self._proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        clean = _ANSI_RE.sub("", raw)
        if clean:
            self._output.moveCursor(self._output.textCursor().End)
            self._output.insertPlainText(clean)

    def _on_finished(self, exit_code: int, _status) -> None:
        self._run_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._header.set_badge("COMPLETE" if exit_code == 0 else f"EXIT {exit_code}", "success" if exit_code == 0 else "gold")
        self._output.appendPlainText(f"\n[FINISHED] Exit code: {exit_code}\n")

    def _stop_audit(self) -> None:
        if self._proc is not None and self._proc.state() != QProcess.NotRunning:
            self._proc.terminate()
            if not self._proc.waitForFinished(800):
                self._proc.kill()
                self._proc.waitForFinished(500)
        self._run_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._header.set_badge("STOPPED", "neutral")

    def _export_output(self, fmt: str) -> None:
        content = self._output.toPlainText().strip()
        if not content:
            QMessageBox.information(self, "Empty Output", "Run an audit first before exporting.")
            return
        default_path = os.path.expanduser(f"~/vice-cyber-audit.{fmt}")
        flt = "Markdown (*.md)" if fmt == "md" else "Text (*.txt)"
        path, _ = QFileDialog.getSaveFileName(self, "Export Audit Report", default_path, flt)
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="\n") as fp:
                if fmt == "md":
                    fp.write(f"# Vice Cyber Audit Report — {self._current_preset['title']}\n\n")
                    fp.write(f"- Generated: {datetime.now().isoformat()}\n")
                    fp.write(f"- Tool: `{self._current_preset['bin']}`\n\n```text\n{content}\n```\n")
                else:
                    fp.write(f"Vice Cyber Audit Report ({datetime.now().isoformat()})\n")
                    fp.write(f"Preset: {self._current_preset['title']}\n\n{content}\n")
            QMessageBox.information(self, "Exported", f"Report saved to:\n{path}")
        except OSError as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))

    def closeEvent(self, event) -> None:
        self._stop_audit()
        event.accept()


def main() -> None:
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    apply_app_theme(app)
    win = ViceCyberDeckApp()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
