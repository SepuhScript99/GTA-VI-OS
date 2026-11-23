#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) — Vice Privacy & Identity Cloak.
Inspects and spoofs/restores network interface MAC addresses (macchanger / ip link
via pkexec), watches live connections and listening ports (ss -tunap), inspects
and strips EXIF/file metadata (mat2 / exiftool), and wipes selected shell/browser
history traces safely on user confirmation. Styled via vice_theme (Noto Sans CJK fallback).
"""

import glob
import os
import re
import shutil
import signal
import subprocess
import sys

from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QFileDialog, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPlainTextEdit, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout,
    QWidget
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
    qcolor,
)

try:
    from python.vice_utils import log_info  # noqa: E402
except ImportError:
    def log_info(msg: str) -> None:
        print(f"[INFO] {msg}")


_IFACE_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,32}$")
_MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")

TRACE_TARGETS = [
    ("bash_history", "Bash Command History (~/.bash_history)", ["~/.bash_history"]),
    ("zsh_history", "Zsh Command History (~/.zsh_history)", ["~/.zsh_history"]),
    ("lesshst", "Less Pager History (~/.lesshst)", ["~/.lesshst"]),
    ("recent_xbel", "Recent Files List (recently-used.xbel)", ["~/.local/share/recently-used.xbel"]),
    ("thumbs", "Thumbnail Cache (~/.cache/thumbnails)", ["~/.cache/thumbnails"]),
    ("ff_cache", "Firefox Cache (~/.cache/mozilla/firefox)", ["~/.cache/mozilla/firefox"]),
    ("ff_history", "Firefox History DB (places.sqlite — close Firefox first)", ["~/.mozilla/firefox/*/places.sqlite"]),
]


def _human_size(num_bytes: int) -> str:
    val = float(num_bytes)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if val < 1024.0:
            return f"{val:.1f} {unit}" if unit != "B" else f"{int(val)} B"
        val /= 1024.0
    return f"{val:.1f} TiB"


def _path_size(path: str) -> int:
    if os.path.isfile(path):
        try:
            return os.path.getsize(path)
        except OSError:
            return 0
    if os.path.isdir(path):
        total = 0
        for root_dir, _dirs, files in os.walk(path):
            for fname in files:
                try:
                    total += os.path.getsize(os.path.join(root_dir, fname))
                except OSError:
                    pass
        return total
    return 0


class CloakWorker(QThread):
    """Runs passive inspection or privileged MAC/metadata commands off the UI thread."""
    result_ready = pyqtSignal(str, bool, object)

    def __init__(self, task: str, payload=None):
        super().__init__()
        self._task = task
        self._payload = payload

    def run(self) -> None:
        if self._task == "ifaces":
            self.result_ready.emit("ifaces", True, self._read_ifaces())
        elif self._task == "sockets":
            self.result_ready.emit("sockets", True, self._read_sockets())
        elif self._task == "mac_cmd":
            cmd, ok_msg = self._payload
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
                if res.returncode == 0:
                    self.result_ready.emit("mac_cmd", True, res.stdout.strip() or ok_msg)
                else:
                    err = res.stderr.strip() or res.stdout.strip() or f"Exit {res.returncode}"
                    self.result_ready.emit("mac_cmd", False, err)
            except Exception as exc:
                self.result_ready.emit("mac_cmd", False, str(exc))
        elif self._task == "meta_inspect":
            self.result_ready.emit("meta_inspect", True, self._inspect_meta(self._payload))
        elif self._task == "meta_clean":
            files, inplace = self._payload
            ok, msg = self._clean_meta(files, inplace)
            self.result_ready.emit("meta_clean", ok, msg)

    def _read_ifaces(self) -> list:
        rows = []
        net_dir = "/sys/class/net"
        if not os.path.isdir(net_dir):
            return rows
        macchanger_bin = shutil.which("macchanger")
        for iface in sorted(os.listdir(net_dir)):
            if iface == "lo" or not _IFACE_RE.match(iface):
                continue
            cur_mac = ""
            state = "unknown"
            perm_mac = "-"
            try:
                with open(f"{net_dir}/{iface}/address", "r", encoding="utf-8") as fp:
                    cur_mac = fp.read().strip()
            except OSError:
                pass
            try:
                with open(f"{net_dir}/{iface}/operstate", "r", encoding="utf-8") as fp:
                    state = fp.read().strip()
            except OSError:
                pass
            if macchanger_bin:
                try:
                    res = subprocess.run([macchanger_bin, "-s", iface], capture_output=True, text=True, timeout=3)
                    for line in res.stdout.splitlines():
                        if line.lower().startswith("permanent mac:"):
                            perm_mac = line.split(":", 1)[1].strip()
                except Exception:
                    pass
            rows.append({"iface": iface, "mac": cur_mac, "perm": perm_mac, "state": state})
        return rows

    def _read_sockets(self) -> list:
        rows = []
        ss_bin = shutil.which("ss")
        if not ss_bin:
            return rows
        try:
            res = subprocess.run([ss_bin, "-tunap"], capture_output=True, text=True, timeout=4)
            for line in res.stdout.splitlines()[1:]:
                parts = line.split(None, 6)
                if len(parts) >= 6:
                    rows.append((
                        parts[0],
                        parts[1],
                        parts[4],
                        parts[5],
                        parts[6] if len(parts) > 6 else "-",
                    ))
        except Exception:
            pass
        return rows

    def _inspect_meta(self, files: list) -> str:
        exif_bin = shutil.which("exiftool")
        mat2_bin = shutil.which("mat2")
        out_parts = []
        for path in files:
            if exif_bin:
                res = subprocess.run([exif_bin, path], capture_output=True, text=True, timeout=10)
                out_parts.append(f"=== {os.path.basename(path)} (exiftool) ===\n{res.stdout.strip() or res.stderr.strip()}")
            elif mat2_bin:
                res = subprocess.run([mat2_bin, "--show", path], capture_output=True, text=True, timeout=10)
                out_parts.append(f"=== {os.path.basename(path)} (mat2) ===\n{res.stdout.strip() or res.stderr.strip()}")
            else:
                out_parts.append(f"[{os.path.basename(path)}] Install 'mat2' or 'libimage-exiftool-perl'.")
        return "\n\n".join(out_parts)

    def _clean_meta(self, files: list, inplace: bool) -> tuple:
        mat2_bin = shutil.which("mat2")
        exif_bin = shutil.which("exiftool")
        logs = []
        ok_all = True
        for path in files:
            if mat2_bin and not inplace:
                res = subprocess.run([mat2_bin, path], capture_output=True, text=True, timeout=20)
                ok_all = ok_all and (res.returncode == 0)
                logs.append(f"[mat2] {os.path.basename(path)}: {'cleaned copy created' if res.returncode == 0 else res.stderr.strip()}")
            elif exif_bin:
                cmd = [exif_bin, "-all="]
                if inplace:
                    cmd.append("-overwrite_original")
                cmd.append(path)
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
                ok_all = ok_all and (res.returncode == 0)
                logs.append(f"[exiftool] {os.path.basename(path)}: {res.stdout.strip() or res.stderr.strip()}")
            elif mat2_bin:
                res = subprocess.run([mat2_bin, "--inplace", path], capture_output=True, text=True, timeout=20)
                ok_all = ok_all and (res.returncode == 0)
                logs.append(f"[mat2 --inplace] {os.path.basename(path)}: {res.returncode}")
            else:
                return False, "Neither 'mat2' nor 'exiftool' is installed."
        return ok_all, "\n".join(logs)


class VicePrivacyCloakApp(QMainWindow):
    """Main window for Vice Privacy & Identity Cloak."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice Privacy & Identity Cloak — Vice OS")
        self.resize(960, 660)
        self.setMinimumSize(760, 520)
        icon = load_tool_icon("vice-tool-mac-cloak", "preferences-system-privacy")
        if not icon.isNull():
            self.setWindowIcon(icon)

        self._workers = []
        self._socket_rows = []
        self._meta_files = []
        self._trace_checks = {}

        self._init_ui()
        self._refresh_ifaces()
        self._refresh_sockets()
        self._refresh_traces()

        self._sock_timer = QTimer(self)
        self._sock_timer.setInterval(4000)
        self._sock_timer.timeout.connect(self._refresh_sockets)

    def _init_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("RootWidget")
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.setSpacing(12)

        self._header = make_header(
            title="Vice Privacy & Identity Cloak",
            subtitle="MAC spoofing, socket watchdog, EXIF/metadata cleaner, and trace eraser",
            icon_name="vice-tool-mac-cloak",
            badge_text="PRIVACY DECK",
            badge_variant="gold",
            parent=root,
        )
        layout.addWidget(self._header)

        tabs = QTabWidget(root)
        tabs.addTab(self._build_mac_tab(), "MAC Cloak")
        tabs.addTab(self._build_socket_tab(), "Connections && Ports")
        tabs.addTab(self._build_meta_tab(), "Metadata Cleaner")
        tabs.addTab(self._build_trace_tab(), "History && Trace Wipe")
        layout.addWidget(tabs, 1)

        self._status_lbl = QLabel("Ready.", root)
        self._status_lbl.setObjectName("MutedLabel")
        layout.addWidget(self._status_lbl)

    def _build_mac_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(10)

        top = QHBoxLayout()
        lbl = QLabel("Network Interfaces (MAC Address Inspector & Spoofer)")
        lbl.setObjectName("SectionTitle")
        top.addWidget(lbl)
        top.addStretch(1)
        ref = make_button("Refresh", variant="secondary", icon_name="view-refresh")
        ref.clicked.connect(self._refresh_ifaces)
        top.addWidget(ref)
        v.addLayout(top)

        self._iface_table = QTableWidget(0, 4)
        self._iface_table.setHorizontalHeaderLabels(["Interface", "Current MAC", "Permanent MAC", "Link State"])
        self._iface_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._iface_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._iface_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._iface_table.setEditTriggers(QTableWidget.NoEditTriggers)
        v.addWidget(self._iface_table, 1)

        act_card = make_card(title="Spoof or Restore Selected Interface (via pkexec)", parent=w)
        row1 = QHBoxLayout()
        row1.setSpacing(8)
        rand_btn = make_button("Randomize MAC", variant="primary", parent=act_card)
        rand_btn.clicked.connect(self._randomize_mac)
        row1.addWidget(rand_btn)

        rest_btn = make_button("Restore Permanent MAC", variant="secondary", parent=act_card)
        rest_btn.clicked.connect(self._restore_mac)
        row1.addWidget(rest_btn)

        self._custom_mac = QLineEdit(act_card)
        self._custom_mac.setPlaceholderText("Custom MAC (e.g. 02:11:22:33:44:55)")
        self._custom_mac.setStyleSheet(f"font-family: {MONO_STACK};")
        row1.addWidget(self._custom_mac, 1)

        set_btn = make_button("Apply Custom", variant="secondary", parent=act_card)
        set_btn.clicked.connect(self._set_custom_mac)
        row1.addWidget(set_btn)
        act_card.body_layout.addLayout(row1)
        v.addWidget(act_card)
        return w

    def _build_socket_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(8)
        self._sock_filter = QLineEdit()
        self._sock_filter.setPlaceholderText("Filter by port, address, state, or process...")
        self._sock_filter.setClearButtonEnabled(True)
        self._sock_filter.textChanged.connect(self._render_sockets)
        top.addWidget(self._sock_filter, 1)

        self._listen_only = QCheckBox("LISTEN only")
        self._listen_only.toggled.connect(self._render_sockets)
        top.addWidget(self._listen_only)

        self._auto_sock = QCheckBox("Auto-refresh (4s)")
        self._auto_sock.toggled.connect(self._toggle_sock_timer)
        top.addWidget(self._auto_sock)

        ref = make_button("Refresh", variant="secondary", icon_name="view-refresh")
        ref.clicked.connect(self._refresh_sockets)
        top.addWidget(ref)
        v.addLayout(top)

        self._sock_table = QTableWidget(0, 5)
        self._sock_table.setHorizontalHeaderLabels(["Proto", "State", "Local Address", "Peer Address", "Process"])
        self._sock_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._sock_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._sock_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._sock_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._sock_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self._sock_table.setEditTriggers(QTableWidget.NoEditTriggers)
        v.addWidget(self._sock_table, 1)
        return w

    def _build_meta_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(8)
        pick_btn = make_button("Select Files...", variant="secondary")
        pick_btn.clicked.connect(self._pick_meta_files)
        top.addWidget(pick_btn)

        self._meta_inplace = QCheckBox("Overwrite original files in-place")
        top.addWidget(self._meta_inplace)
        top.addStretch(1)

        clean_btn = make_button("Strip All Metadata", variant="primary")
        clean_btn.clicked.connect(self._clean_meta)
        top.addWidget(clean_btn)
        v.addLayout(top)

        self._meta_out = QPlainTextEdit()
        self._meta_out.setReadOnly(True)
        self._meta_out.setPlainText("Select images, PDFs, or office documents to inspect and strip embedded EXIF/GPS/author tags.")
        v.addWidget(self._meta_out, 1)
        return w

    def _build_trace_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(10)

        card = make_card(
            title="Shell & Browser Trace Wipe Helper",
            subtitle="Inspect local history/cache sizes and wipe only the items you explicitly select",
            parent=w,
        )
        for key, label, _patterns in TRACE_TARGETS:
            chk = QCheckBox(f"{label}  —  checking...", card)
            self._trace_checks[key] = chk
            card.body_layout.addWidget(chk)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        ref = make_button("Refresh Sizes", variant="secondary", parent=card)
        ref.clicked.connect(self._refresh_traces)
        btn_row.addWidget(ref)

        wipe_btn = make_button("Wipe Selected Traces", variant="danger", parent=card)
        wipe_btn.clicked.connect(self._wipe_traces)
        btn_row.addWidget(wipe_btn)
        btn_row.addStretch(1)
        card.body_layout.addLayout(btn_row)
        v.addWidget(card)
        v.addStretch(1)
        return w

    def _start_worker(self, task: str, payload=None) -> None:
        self._workers = [w for w in self._workers if w.isRunning()]
        worker = CloakWorker(task, payload)
        worker.result_ready.connect(self._on_worker_result)
        self._workers.append(worker)
        worker.start()

    def _on_worker_result(self, task: str, ok: bool, data) -> None:
        if task == "ifaces":
            self._iface_table.setRowCount(0)
            for row_data in data:
                r = self._iface_table.rowCount()
                self._iface_table.insertRow(r)
                self._iface_table.setItem(r, 0, QTableWidgetItem(row_data["iface"]))
                self._iface_table.setItem(r, 1, QTableWidgetItem(row_data["mac"]))
                self._iface_table.setItem(r, 2, QTableWidgetItem(row_data["perm"]))
                st = QTableWidgetItem(row_data["state"])
                st.setForeground(qcolor("success") if row_data["state"] == "up" else qcolor("text_secondary"))
                self._iface_table.setItem(r, 3, st)
            if self._iface_table.rowCount() > 0 and self._iface_table.currentRow() < 0:
                self._iface_table.selectRow(0)
        elif task == "sockets":
            self._socket_rows = data
            self._render_sockets()
        elif task == "mac_cmd":
            color = COLORS["success"] if ok else COLORS["danger"]
            self._status_lbl.setStyleSheet(f"color: {color}; font-weight: 600;")
            self._status_lbl.setText(str(data))
            self._refresh_ifaces()
        elif task == "meta_inspect":
            self._meta_out.setPlainText(str(data))
        elif task == "meta_clean":
            self._meta_out.appendPlainText("\n--- CLEAN RESULT ---\n" + str(data))
            self._status_lbl.setStyleSheet(
                f"color: {COLORS['success'] if ok else COLORS['danger']}; font-weight: 600;"
            )
            self._status_lbl.setText("Metadata clean finished." if ok else "Metadata clean had errors.")

    def _refresh_ifaces(self) -> None:
        self._start_worker("ifaces")

    def _selected_iface(self) -> str:
        row = self._iface_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Select Interface", "Select a network interface first.")
            return ""
        iface = self._iface_table.item(row, 0).text().strip()
        if not _IFACE_RE.match(iface):
            return ""
        return iface

    def _randomize_mac(self) -> None:
        iface = self._selected_iface()
        if not iface:
            return
        if shutil.which("macchanger"):
            script = 'ip link set dev "$1" down && macchanger -r "$1" && ip link set dev "$1" up'
            self._start_worker("mac_cmd", (["pkexec", "bash", "-c", script, "vice-mac", iface], f"Randomized MAC on {iface}"))
        else:
            QMessageBox.warning(self, "Missing macchanger", "Install package 'macchanger' for automatic MAC randomization.")

    def _restore_mac(self) -> None:
        iface = self._selected_iface()
        if not iface:
            return
        if not shutil.which("macchanger"):
            QMessageBox.warning(self, "Missing macchanger", "Install package 'macchanger'.")
            return
        script = 'ip link set dev "$1" down && macchanger -p "$1" && ip link set dev "$1" up'
        self._start_worker("mac_cmd", (["pkexec", "bash", "-c", script, "vice-mac", iface], f"Restored permanent MAC on {iface}"))

    def _set_custom_mac(self) -> None:
        iface = self._selected_iface()
        if not iface:
            return
        mac = self._custom_mac.text().strip()
        if not _MAC_RE.match(mac):
            QMessageBox.warning(self, "Invalid MAC", "Enter a valid MAC address like 02:11:22:33:44:55.")
            return
        if shutil.which("macchanger"):
            script = 'ip link set dev "$1" down && macchanger -m "$2" "$1" && ip link set dev "$1" up'
        else:
            script = 'ip link set dev "$1" down && ip link set dev "$1" address "$2" && ip link set dev "$1" up'
        self._start_worker("mac_cmd", (["pkexec", "bash", "-c", script, "vice-mac", iface, mac], f"Set MAC {mac} on {iface}"))

    def _refresh_sockets(self) -> None:
        self._start_worker("sockets")

    def _toggle_sock_timer(self, enabled: bool) -> None:
        if enabled:
            self._sock_timer.start()
        else:
            self._sock_timer.stop()

    def _render_sockets(self) -> None:
        query = self._sock_filter.text().strip().lower()
        only_listen = self._listen_only.isChecked()
        self._sock_table.setRowCount(0)
        listen_n = 0
        estab_n = 0
        for proto, state, local, peer, proc in self._socket_rows:
            if state == "LISTEN":
                listen_n += 1
            elif state == "ESTAB":
                estab_n += 1
            if only_listen and state != "LISTEN":
                continue
            if query and query not in f"{proto} {state} {local} {peer} {proc}".lower():
                continue
            r = self._sock_table.rowCount()
            self._sock_table.insertRow(r)
            for c, val in enumerate((proto, state, local, peer, proc)):
                it = QTableWidgetItem(val)
                if c == 1:
                    it.setForeground(qcolor("accent_aqua") if state == "LISTEN" else qcolor("text_primary"))
                self._sock_table.setItem(r, c, it)
        self._header.set_badge(f"{listen_n} LISTEN · {estab_n} ESTAB", "aqua" if listen_n else "neutral")

    def _pick_meta_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Files to Inspect / Clean", os.path.expanduser("~")
        )
        if not paths:
            return
        self._meta_files = paths
        self._meta_out.setPlainText(f"Inspecting metadata in {len(paths)} file(s)...")
        self._start_worker("meta_inspect", paths)

    def _clean_meta(self) -> None:
        if not self._meta_files:
            QMessageBox.information(self, "No Files", "Select one or more files first.")
            return
        self._start_worker("meta_clean", (self._meta_files, self._meta_inplace.isChecked()))

    def _refresh_traces(self) -> None:
        for key, label, patterns in TRACE_TARGETS:
            total = 0
            for pat in patterns:
                for match in glob.glob(os.path.expanduser(pat)):
                    total += _path_size(match)
            self._trace_checks[key].setText(f"{label}  —  {_human_size(total)}")

    def _wipe_traces(self) -> None:
        selected = [spec for spec in TRACE_TARGETS if self._trace_checks[spec[0]].isChecked()]
        if not selected:
            QMessageBox.information(self, "Nothing Selected", "Check one or more trace items to wipe.")
            return
        if QMessageBox.question(
            self, "Confirm Trace Wipe",
            f"Permanently delete {len(selected)} selected history/cache item(s)?"
        ) != QMessageBox.Yes:
            return

        wiped = 0
        for _key, _label, patterns in selected:
            for pat in patterns:
                for match in glob.glob(os.path.expanduser(pat)):
                    try:
                        if os.path.isdir(match):
                            shutil.rmtree(match, ignore_errors=True)
                        elif os.path.isfile(match):
                            os.unlink(match)
                        wiped += 1
                    except OSError:
                        pass
        self._status_lbl.setStyleSheet(f"color: {COLORS['success']}; font-weight: 600;")
        self._status_lbl.setText(f"Wiped {wiped} trace target(s).")
        log_info(f"Vice Privacy Cloak wiped {wiped} trace target(s)")
        self._refresh_traces()

    def closeEvent(self, event) -> None:
        self._sock_timer.stop()
        for w in self._workers:
            if w.isRunning():
                w.wait(1500)
        event.accept()


def main() -> None:
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    apply_app_theme(app)
    win = VicePrivacyCloakApp()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
