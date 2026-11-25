#!/usr/bin/env python3
"""
Vice OS Settings Center — Live Inline Control Panels.
Every settings category renders genuine Linux controls wired directly to system
utilities (xrandr, wpctl/pactl, nmcli, bluetoothctl, ufw, vice-timesync, udisksctl,
libfm/xfconf, apt/fwupd, upower/cpufreq, cups, gsettings, xinput, crontab, etc.)
with lazy background QThread loading and clean cancellation on close.
"""

import configparser
from datetime import datetime
import glob
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

try:
    from zoneinfo import ZoneInfo, available_timezones
except ImportError:
    ZoneInfo = None
    available_timezones = None

from PyQt5.QtCore import QSize, Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QIcon, QPixmap
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

sys.path.insert(0, "/opt/vice-os/lib")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from python.vice_utils import log_error, log_info  # noqa: E402
from vice_theme import COLORS, MONO_STACK, make_badge, resolve_icon, style_badge  # noqa: E402

APP_DIR = os.path.dirname(os.path.abspath(__file__))


def _is_root() -> bool:
    return hasattr(os, "geteuid") and os.geteuid() == 0


def _priv_cmd(cmd: list) -> list:
    if _is_root():
        return list(cmd)
    if shutil.which("pkexec"):
        return ["pkexec"] + list(cmd)
    if shutil.which("sudo"):
        return ["sudo", "-n"] + list(cmd)
    return list(cmd)


def _run_sync(cmd: list, timeout: int = 8, input_data: str = None) -> tuple:
    """Run a command synchronously (use inside QThread workers or fast actions)."""
    if not cmd:
        return False, "Empty command"
    try:
        res = subprocess.run(
            cmd,
            input=input_data,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = (res.stdout or "").strip() or (res.stderr or "").strip()
        return res.returncode == 0, out
    except FileNotFoundError:
        return False, f"Command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return False, f"Timed out: {' '.join(cmd)}"
    except Exception as exc:
        return False, str(exc)


def _btn_text(label: str) -> str:
    """Escape literal '&' for QPushButton mnemonics."""
    return label.replace("&", "&&")


def _make_btn(label: str, variant: str = "secondary", parent=None) -> QPushButton:
    btn = QPushButton(_btn_text(label), parent)
    if variant == "primary":
        btn.setObjectName("PrimaryButton")
    elif variant == "danger":
        btn.setObjectName("DangerButton")
    btn.setFocusPolicy(Qt.NoFocus)
    return btn


class _FnWorker(QThread):
    """Run any callable off the UI thread and emit its result."""

    finished_data = pyqtSignal(object)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn
        self._stopped = False

    def stop(self):
        self._stopped = True

    def run(self):
        try:
            result = self._fn()
        except Exception as exc:
            result = ("__error__", str(exc))
        if not self._stopped:
            self.finished_data.emit(result)


class _StreamWorker(QThread):
    """Run a subprocess streaming stdout/stderr lines and emit completion."""

    line_out = pyqtSignal(str)
    done = pyqtSignal(bool, str)

    def __init__(self, cmd: list, timeout: int = 60, input_data: str = None, parent=None):
        super().__init__(parent)
        self._cmd = list(cmd)
        self._timeout = timeout
        self._input_data = input_data
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

    def run(self):
        try:
            self._proc = subprocess.Popen(
                self._cmd,
                stdin=subprocess.PIPE if self._input_data is not None else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            if self._input_data is not None and self._proc.stdin:
                try:
                    self._proc.stdin.write(self._input_data)
                    self._proc.stdin.close()
                except Exception:
                    pass
            lines = []
            if self._proc.stdout:
                for raw in self._proc.stdout:
                    if self._stopped:
                        break
                    line = raw.rstrip("\r\n")
                    lines.append(line)
                    self.line_out.emit(line)
            rc = self._proc.wait(timeout=self._timeout)
            if not self._stopped:
                self.done.emit(rc == 0, "\n".join(lines[-20:]))
        except Exception as exc:
            if not self._stopped:
                self.line_out.emit(f"Error: {exc}")
                self.done.emit(False, str(exc))
        finally:
            self._proc = None


class BaseSettingsPage(QWidget):
    """Base class providing consistent header, scrollable body, lazy QThread load, and cleanup."""

    def __init__(self, title: str, subtitle: str, badge_text: str = "", badge_variant: str = "aqua"):
        super().__init__()
        self._workers = []
        self._timers = []
        self._activated_once = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(10)

        # Page header
        hdr = QFrame(self)
        hdr.setObjectName("Card")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(14, 10, 14, 10)
        hl.setSpacing(10)

        tcol = QVBoxLayout()
        tcol.setSpacing(2)
        t_lbl = QLabel(title, hdr)
        t_lbl.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 16px; font-weight: bold;")
        tcol.addWidget(t_lbl)
        s_lbl = QLabel(subtitle, hdr)
        s_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        s_lbl.setWordWrap(True)
        tcol.addWidget(s_lbl)
        hl.addLayout(tcol, 1)

        self._hdr_right = QHBoxLayout()
        self._hdr_right.setSpacing(6)
        if badge_text:
            self._badge = make_badge(badge_text, badge_variant, hdr)
            self._hdr_right.addWidget(self._badge)
        else:
            self._badge = None
        self._refresh_btn = _make_btn("Refresh", "secondary", hdr)
        self._refresh_btn.clicked.connect(self.refresh_page)
        self._hdr_right.addWidget(self._refresh_btn)
        hl.addLayout(self._hdr_right)
        outer.addWidget(hdr)

        # Scrollable content area
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body_host = QWidget()
        body_host.setStyleSheet("background: transparent;")
        self.body = QVBoxLayout(body_host)
        self.body.setContentsMargins(2, 2, 6, 2)
        self.body.setSpacing(10)
        scroll.setWidget(body_host)
        outer.addWidget(scroll, 1)

        # Footer status
        foot = QHBoxLayout()
        self._progress = QProgressBar(self)
        self._progress.setRange(0, 0)
        self._progress.setFixedWidth(120)
        self._progress.setFixedHeight(10)
        self._progress.setVisible(False)
        foot.addWidget(self._progress)
        self._status = QLabel("Ready", self)
        self._status.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        self._status.setWordWrap(True)
        foot.addWidget(self._status, 1)
        outer.addLayout(foot)

    def set_status(self, msg: str, tone: str = "muted"):
        color_map = {
            "ok": COLORS["success"],
            "err": COLORS["danger"],
            "warn": COLORS["warning"],
            "muted": COLORS["text_secondary"],
        }
        self._status.setStyleSheet(f"color: {color_map.get(tone, COLORS['text_secondary'])}; font-size: 11px;")
        self._status.setText(msg)

    def on_activated(self):
        if not self._activated_once:
            self._activated_once = True
            self.refresh_page()

    def refresh_page(self):
        """Override in subclasses to load live system state."""

    def _run_bg(self, fn, on_done, busy_msg: str = "Loading..."):
        self._progress.setVisible(True)
        self.set_status(busy_msg)
        w = _FnWorker(fn, parent=self)

        def _handle(res):
            self._progress.setVisible(False)
            if isinstance(res, tuple) and len(res) == 2 and res[0] == "__error__":
                self.set_status(f"Error: {res[1]}", "err")
                return
            on_done(res)

        w.finished_data.connect(_handle)
        self._workers = [wk for wk in self._workers if wk.isRunning()]
        self._workers.append(w)
        w.start()
        return w

    def _run_cmd_bg(self, cmd: list, on_done, busy_msg: str = "Running...", timeout: int = 30, input_data: str = None):
        self._progress.setVisible(True)
        self.set_status(busy_msg)
        w = _StreamWorker(cmd, timeout=timeout, input_data=input_data, parent=self)

        def _handle(ok: bool, out: str):
            self._progress.setVisible(False)
            on_done(ok, out)

        w.done.connect(_handle)
        self._workers = [wk for wk in self._workers if wk.isRunning()]
        self._workers.append(w)
        w.start()
        return w

    def _make_table(self, headers: list, stretch_col: int = 0) -> QTableWidget:
        tbl = QTableWidget(self)
        tbl.setColumnCount(len(headers))
        tbl.setHorizontalHeaderLabels(headers)
        for i in range(len(headers)):
            mode = QHeaderView.Stretch if i == stretch_col else QHeaderView.ResizeToContents
            tbl.horizontalHeader().setSectionResizeMode(i, mode)
        tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        tbl.setAlternatingRowColors(True)
        tbl.verticalHeader().setVisible(False)
        return tbl

    def stop_workers(self):
        for t in self._timers:
            try:
                t.stop()
            except Exception:
                pass
        for w in self._workers:
            if w is not None:
                if hasattr(w, "stop"):
                    w.stop()
                if w.isRunning():
                    w.wait(2000)


# ==============================================================================
# 1. DISPLAY
# ==============================================================================


def _parse_xrandr_outputs(out: str) -> dict:
    displays = {}
    cur = None
    for line in (out or "").splitlines():
        m = re.match(r"^(\S+)\s+(connected|disconnected)", line)
        if m:
            cur = m.group(1)
            connected = m.group(2) == "connected"
            geo = re.search(r"(\d+x\d+)\+(\d+)\+(\d+)", line)
            displays[cur] = {
                "connected": connected,
                "active": geo is not None,
                "current_res": geo.group(1) if geo else "",
                "primary": " primary " in line,
                "modes": [],
                "current_rate": "",
            }
        elif cur and re.match(r"^\s+\d+x\d+", line):
            parts = line.split()
            res = parts[0]
            rates = []
            for p in parts[1:]:
                clean = p.replace("*", "").replace("+", "")
                try:
                    rates.append(round(float(clean), 2))
                except ValueError:
                    pass
            is_cur = "*" in line
            if is_cur:
                rm = re.search(r"(\d+\.\d+)\*", line)
                if rm:
                    displays[cur]["current_rate"] = f"{float(rm.group(1)):.2f}"
            displays[cur]["modes"].append({"res": res, "rates": rates, "current": is_cur})
    return displays


class DisplayPage(BaseSettingsPage):
    def __init__(self):
        super().__init__(
            "Display & Monitors",
            "Live xrandr outputs, resolution, refresh rate, rotation, and brightness",
            "XRANDR", "coral",
        )
        self._outputs = {}

        box = QGroupBox("Monitor Configuration")
        form = QFormLayout(box)

        self._out_combo = QComboBox()
        self._out_combo.currentTextChanged.connect(self._on_output_changed)
        form.addRow("Output:", self._out_combo)

        self._res_combo = QComboBox()
        self._res_combo.currentTextChanged.connect(self._on_res_changed)
        form.addRow("Resolution:", self._res_combo)

        self._rate_combo = QComboBox()
        form.addRow("Refresh Rate:", self._rate_combo)

        self._rot_combo = QComboBox()
        self._rot_combo.addItems(["normal", "left", "right", "inverted"])
        form.addRow("Orientation:", self._rot_combo)

        self._primary_cb = QCheckBox("Set as primary display")
        form.addRow("", self._primary_cb)
        self.body.addWidget(box)

        bright_box = QGroupBox("Screen Brightness")
        bl = QHBoxLayout(bright_box)
        self._bright_slider = QSlider(Qt.Horizontal)
        self._bright_slider.setRange(25, 100)
        self._bright_slider.setValue(100)
        self._bright_lbl = QLabel("100%")
        self._bright_lbl.setFixedWidth(44)
        self._bright_slider.valueChanged.connect(lambda v: self._bright_lbl.setText(f"{v}%"))
        self._bright_slider.sliderReleased.connect(self._apply_brightness)
        bl.addWidget(QLabel("Dim"))
        bl.addWidget(self._bright_slider, 1)
        bl.addWidget(QLabel("Bright"))
        bl.addWidget(self._bright_lbl)
        self.body.addWidget(bright_box)

        act = QHBoxLayout()
        self._apply_btn = _make_btn("Apply Display Settings", "primary", self)
        self._apply_btn.clicked.connect(self._apply_display)
        act.addWidget(self._apply_btn)
        act.addStretch(1)
        self.body.addLayout(act)
        self.body.addStretch(1)

    def refresh_page(self):
        def _probe():
            ok, out = _run_sync(["xrandr", "--query"], timeout=5)
            outputs = _parse_xrandr_outputs(out) if ok else {}
            bright = 100
            for bp in (
                "/sys/class/backlight/intel_backlight",
                "/sys/class/backlight/acpi_video0",
                "/sys/class/backlight/amdgpu_bl0",
            ):
                if os.path.isdir(bp):
                    try:
                        with open(os.path.join(bp, "brightness"), encoding="utf-8") as f:
                            cur = int(f.read().strip())
                        with open(os.path.join(bp, "max_brightness"), encoding="utf-8") as f:
                            mx = max(1, int(f.read().strip()))
                        bright = max(25, min(100, int(round(cur * 100 / mx))))
                        break
                    except Exception:
                        pass
            return {"outputs": outputs, "bright": bright, "xrandr_ok": ok, "err": out if not ok else ""}

        self._run_bg(_probe, self._populate, "Querying xrandr outputs...")

    def _populate(self, data):
        self._outputs = {k: v for k, v in data["outputs"].items() if v["connected"]}
        self._out_combo.blockSignals(True)
        self._out_combo.clear()
        for name in self._outputs:
            self._out_combo.addItem(name)
        self._out_combo.blockSignals(False)
        self._bright_slider.blockSignals(True)
        self._bright_slider.setValue(data["bright"])
        self._bright_lbl.setText(f"{data['bright']}%")
        self._bright_slider.blockSignals(False)
        if self._outputs:
            self._on_output_changed(self._out_combo.currentText())
            self.set_status(f"Detected {len(self._outputs)} connected output(s)", "ok")
        else:
            self.set_status(data.get("err") or "xrandr unavailable (no X11 display)", "warn")

    def _on_output_changed(self, name: str):
        info = self._outputs.get(name)
        if not info:
            return
        self._res_combo.blockSignals(True)
        self._res_combo.clear()
        seen = set()
        for m in info["modes"]:
            if m["res"] not in seen:
                seen.add(m["res"])
                self._res_combo.addItem(m["res"])
        if info["current_res"]:
            idx = self._res_combo.findText(info["current_res"])
            if idx >= 0:
                self._res_combo.setCurrentIndex(idx)
        self._res_combo.blockSignals(False)
        self._primary_cb.setChecked(bool(info.get("primary")))
        self._on_res_changed(self._res_combo.currentText())
        if info.get("current_rate"):
            ridx = self._rate_combo.findText(f"{info['current_rate']} Hz")
            if ridx >= 0:
                self._rate_combo.setCurrentIndex(ridx)

    def _on_res_changed(self, res: str):
        self._rate_combo.clear()
        info = self._outputs.get(self._out_combo.currentText(), {})
        for m in info.get("modes", []):
            if m["res"] == res:
                for rate in m["rates"]:
                    self._rate_combo.addItem(f"{rate:.2f} Hz")
                break

    def _apply_brightness(self):
        pct = self._bright_slider.value()
        ratio = max(0.25, min(1.0, pct / 100.0))
        out_name = self._out_combo.currentText().strip()

        def _do():
            if shutil.which("brightnessctl"):
                ok, msg = _run_sync(["brightnessctl", "set", f"{pct}%"], timeout=4)
                if ok:
                    return True, f"Brightness set to {pct}%"
            if out_name and shutil.which("xrandr"):
                return _run_sync(["xrandr", "--output", out_name, "--brightness", f"{ratio:.2f}"], timeout=4)
            return False, "No backlight or xrandr output available"

        self._run_bg(_do, lambda r: self.set_status(r[1] or f"Brightness {pct}%", "ok" if r[0] else "err"), "Applying brightness...")

    def _apply_display(self):
        out_name = self._out_combo.currentText().strip()
        if not out_name:
            QMessageBox.warning(self, "No Output", "No connected display output detected.")
            return
        cmd = ["xrandr", "--output", out_name]
        res = self._res_combo.currentText().strip()
        cmd += ["--mode", res] if res else ["--auto"]
        rate = self._rate_combo.currentText().replace(" Hz", "").strip()
        if rate:
            cmd += ["--rate", rate]
        cmd += ["--rotate", self._rot_combo.currentText()]
        if self._primary_cb.isChecked():
            cmd.append("--primary")

        def _done(ok: bool, msg: str):
            if ok:
                self.set_status(f"Applied {res} on {out_name}", "ok")
                self.refresh_page()
            else:
                self.set_status(msg or "xrandr failed", "err")
                QMessageBox.warning(self, "Display Error", msg or "Failed to apply display settings.")

        self._run_cmd_bg(cmd, _done, "Applying xrandr settings...")


# ==============================================================================
# 2. SOUND (Strictly 0..100% Volume Cap!)
# ==============================================================================


class SoundPage(BaseSettingsPage):
    def __init__(self):
        super().__init__(
            "Sound & PipeWire Audio",
            "Live PipeWire/WirePlumber output sink selector, 0–100% volume cap, mute, and test",
            "PIPEWIRE", "aqua",
        )
        self._sinks = []
        self._updating_slider = False

        adv_btn = _make_btn("Advanced Mixer", "secondary", self)
        adv_btn.clicked.connect(self._open_mixer)
        self._hdr_right.insertWidget(0, adv_btn)

        out_box = QGroupBox("Output Device (Sink)")
        ol = QVBoxLayout(out_box)

        sink_row = QHBoxLayout()
        sink_row.addWidget(QLabel("Output Sink:"))
        self._sink_combo = QComboBox()
        sink_row.addWidget(self._sink_combo, 1)
        set_def_btn = _make_btn("Set Default", "secondary", out_box)
        set_def_btn.clicked.connect(self._set_default_sink)
        sink_row.addWidget(set_def_btn)
        ol.addLayout(sink_row)

        vol_row = QHBoxLayout()
        vol_row.addWidget(QLabel("Master Volume:"))
        self._vol_slider = QSlider(Qt.Horizontal)
        self._vol_slider.setRange(0, 100)
        self._vol_slider.setValue(75)
        self._vol_slider.valueChanged.connect(self._on_volume_changed)
        vol_row.addWidget(self._vol_slider, 1)
        self._vol_lbl = QLabel("75%")
        self._vol_lbl.setFixedWidth(44)
        vol_row.addWidget(self._vol_lbl)

        self._mute_btn = _make_btn("Mute", "secondary", out_box)
        self._mute_btn.setCheckable(True)
        self._mute_btn.clicked.connect(self._toggle_mute)
        vol_row.addWidget(self._mute_btn)
        ol.addLayout(vol_row)

        act_row = QHBoxLayout()
        test_btn = _make_btn("Test Sound", "primary", out_box)
        test_btn.clicked.connect(self._test_sound)
        act_row.addWidget(test_btn)
        act_row.addStretch(1)
        ol.addLayout(act_row)
        self.body.addWidget(out_box)

        status_box = QGroupBox("PipeWire / WirePlumber Status")
        sl = QVBoxLayout(status_box)
        self._wp_out = QPlainTextEdit()
        self._wp_out.setReadOnly(True)
        self._wp_out.setMinimumHeight(180)
        sl.addWidget(self._wp_out)
        self.body.addWidget(status_box, 1)

    def _open_mixer(self):
        mixer = os.path.join(APP_DIR, "vice_audio_manager.py")
        if os.path.isfile(mixer):
            subprocess.Popen([sys.executable, mixer], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif shutil.which("pavucontrol"):
            subprocess.Popen(["pavucontrol"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def refresh_page(self):
        def _probe():
            sinks = []
            default_sink = ""
            cur_vol = 75
            muted = False
            wp_txt = ""

            if shutil.which("pactl"):
                _, def_out = _run_sync(["pactl", "get-default-sink"], timeout=4)
                default_sink = def_out.strip()
                ok, sinks_out = _run_sync(["pactl", "list", "sinks"], timeout=5)
                if ok:
                    cur = {}
                    for line in sinks_out.splitlines():
                        m = re.match(r"^Sink #(\d+)", line)
                        if m:
                            if cur:
                                sinks.append(cur)
                            cur = {"index": m.group(1), "name": "", "desc": "", "vol": 75, "muted": False}
                        elif cur:
                            if "Name:" in line:
                                cur["name"] = line.split("Name:", 1)[1].strip()
                            elif "Description:" in line:
                                cur["desc"] = line.split("Description:", 1)[1].strip()
                            elif "Volume:" in line and "%" in line:
                                vm = re.search(r"(\d+)%", line)
                                if vm:
                                    cur["vol"] = max(0, min(100, int(vm.group(1))))
                            elif "Mute:" in line:
                                cur["muted"] = "yes" in line.lower()
                    if cur:
                        sinks.append(cur)
                for s in sinks:
                    if s["name"] == default_sink or not default_sink:
                        cur_vol = s["vol"]
                        muted = s["muted"]
                        break

            if shutil.which("wpctl"):
                ok_w, w_out = _run_sync(["wpctl", "status"], timeout=4)
                if ok_w:
                    wp_txt = w_out
                if not sinks:
                    ok_g, g_out = _run_sync(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"], timeout=4)
                    if ok_g:
                        m = re.search(r"([0-9.]+)", g_out)
                        if m:
                            cur_vol = max(0, min(100, int(round(float(m.group(1)) * 100))))
                        muted = "MUTED" in g_out

            return {
                "sinks": sinks, "default": default_sink, "vol": cur_vol,
                "muted": muted, "wpctl": wp_txt or "wpctl status unavailable",
            }

        self._run_bg(_probe, self._populate, "Querying PipeWire audio...")

    def _populate(self, data):
        self._sinks = data["sinks"]
        self._sink_combo.clear()
        sel_idx = 0
        for i, s in enumerate(self._sinks):
            label = s["desc"] or s["name"]
            self._sink_combo.addItem(label, s["name"])
            if s["name"] == data["default"]:
                sel_idx = i
        if self._sinks:
            self._sink_combo.setCurrentIndex(sel_idx)
        else:
            self._sink_combo.addItem("Default Audio Sink", "@DEFAULT_SINK@")

        self._updating_slider = True
        vol = max(0, min(100, int(data["vol"])))
        self._vol_slider.setValue(vol)
        self._vol_lbl.setText(f"{vol}%")
        self._mute_btn.setChecked(bool(data["muted"]))
        self._mute_btn.setText("Unmute" if data["muted"] else "Mute")
        self._updating_slider = False
        self._wp_out.setPlainText(data["wpctl"])
        self.set_status(f"Volume: {vol}% ({'Muted' if data['muted'] else 'Active'})", "ok")

    def _on_volume_changed(self, value: int):
        value = max(0, min(100, int(value)))
        self._vol_lbl.setText(f"{value}%")
        if self._updating_slider:
            return
        if shutil.which("pactl"):
            subprocess.Popen(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{value}%"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif shutil.which("wpctl"):
            subprocess.Popen(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{value / 100.0:.2f}"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.set_status(f"Volume set to {value}%", "ok")

    def _toggle_mute(self):
        def _do():
            if shutil.which("pactl"):
                return _run_sync(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"], timeout=4)
            if shutil.which("wpctl"):
                return _run_sync(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"], timeout=4)
            return False, "No audio backend (pactl/wpctl)"

        self._run_bg(_do, lambda r: (self.refresh_page() if r[0] else QMessageBox.warning(self, "Mute Failed", r[1])), "Toggling mute...")

    def _set_default_sink(self):
        sink_name = self._sink_combo.currentData()
        if not sink_name or sink_name == "@DEFAULT_SINK@":
            return

        def _do():
            if shutil.which("pactl"):
                return _run_sync(["pactl", "set-default-sink", sink_name], timeout=4)
            return False, "pactl not installed"

        self._run_bg(_do, lambda r: (self.set_status(f"Default sink: {sink_name}", "ok") if r[0] else QMessageBox.warning(self, "Error", r[1])), "Switching output sink...")

    def _test_sound(self):
        def _do():
            test_oga = "/usr/share/sounds/freedesktop/stereo/audio-volume-change.oga"
            if shutil.which("paplay") and os.path.isfile(test_oga):
                return _run_sync(["paplay", test_oga], timeout=6)
            if shutil.which("canberra-gtk-play"):
                return _run_sync(["canberra-gtk-play", "-i", "audio-volume-change"], timeout=6)
            if shutil.which("speaker-test"):
                return _run_sync(["speaker-test", "-t", "wav", "-c", "2", "-l", "1"], timeout=8)
            return False, "No test sound player (paplay/speaker-test) installed"

        self._run_bg(_do, lambda r: (self.set_status("Test sound played", "ok") if r[0] else QMessageBox.warning(self, "Test Sound Failed", r[1])), "Playing test sound...")


# ==============================================================================
# 3. NETWORK (Live nmcli Active Connections + Wi-Fi Scan & Connect + DHCP)
# ==============================================================================


class _WifiPasswordDialog(QDialog):
    def __init__(self, ssid: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Connect to {ssid}")
        self.setMinimumWidth(360)
        form = QFormLayout(self)
        self._pw = QLineEdit(self)
        self._pw.setEchoMode(QLineEdit.Password)
        self._pw.setPlaceholderText("Enter Wi-Fi passphrase (leave empty if open)")
        form.addRow("Password:", self._pw)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    def password(self) -> str:
        return self._pw.text()


class NetworkPage(BaseSettingsPage):
    def __init__(self):
        super().__init__(
            "Network & Wi-Fi",
            "Live NetworkManager interfaces (IP, Gateway, DNS, MAC, Speed) and Wi-Fi scan/connect",
            "NMCLI", "aqua",
        )
        self._active_dev = ""
        self._active_con = ""

        conn_box = QGroupBox("Active Connections & Interface Details")
        cl = QVBoxLayout(conn_box)
        self._dev_table = self._make_table(["Device", "Type", "State", "Connection", "IPv4 / Gateway / DNS", "MAC / Speed"], stretch_col=4)
        self._dev_table.setMinimumHeight(140)
        cl.addWidget(self._dev_table)

        c_act = QHBoxLayout()
        self._dhcp_btn = _make_btn("Reconnect Wired / DHCP", "primary", conn_box)
        self._dhcp_btn.clicked.connect(self._reconnect_dhcp)
        c_act.addWidget(self._dhcp_btn)

        self._wifi_toggle_btn = _make_btn("Toggle Wi-Fi Radio", "secondary", conn_box)
        self._wifi_toggle_btn.clicked.connect(self._toggle_wifi)
        c_act.addWidget(self._wifi_toggle_btn)

        self._wifi_badge = make_badge("Wi-Fi: --", "neutral", conn_box)
        c_act.addWidget(self._wifi_badge)
        c_act.addStretch(1)
        cl.addLayout(c_act)
        self.body.addWidget(conn_box)

        wifi_box = QGroupBox("Nearby Wi-Fi Networks")
        wl = QVBoxLayout(wifi_box)
        self._wifi_table = self._make_table(["SSID", "Signal", "Security", "In Use"], stretch_col=0)
        self._wifi_table.setMinimumHeight(170)
        wl.addWidget(self._wifi_table)

        w_act = QHBoxLayout()
        scan_btn = _make_btn("Scan Wi-Fi", "secondary", wifi_box)
        scan_btn.clicked.connect(self._scan_wifi)
        w_act.addWidget(scan_btn)
        conn_btn = _make_btn("Connect Selected Wi-Fi", "primary", wifi_box)
        conn_btn.clicked.connect(self._connect_wifi)
        w_act.addWidget(conn_btn)
        w_act.addStretch(1)
        wl.addLayout(w_act)
        self.body.addWidget(wifi_box, 1)

    def refresh_page(self):
        def _probe():
            if not shutil.which("nmcli"):
                return {"ok": False, "err": "nmcli not installed"}
            ok, devs_raw = _run_sync(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"], timeout=6)
            rows = []
            for line in devs_raw.splitlines() if ok else []:
                parts = line.split(":")
                if len(parts) < 4:
                    continue
                dev, dtype, state, con = parts[0], parts[1], parts[2], ":".join(parts[3:])
                if dtype == "loopback":
                    continue
                ok_d, dshow = _run_sync(["nmcli", "-t", "-f", "IP4.ADDRESS,IP4.GATEWAY,IP4.DNS,GENERAL.HWADDR", "device", "show", dev], timeout=4)
                ips, gw, dns, mac = [], "", [], ""
                for dl in dshow.splitlines() if ok_d else []:
                    if dl.startswith("IP4.ADDRESS"):
                        ips.append(dl.split(":", 1)[1].strip())
                    elif dl.startswith("IP4.GATEWAY"):
                        gw = dl.split(":", 1)[1].strip()
                    elif dl.startswith("IP4.DNS"):
                        dns.append(dl.split(":", 1)[1].strip())
                    elif dl.startswith("GENERAL.HWADDR"):
                        mac = dl.split(":", 1)[1].strip()
                speed = ""
                sp_file = f"/sys/class/net/{dev}/speed"
                if os.path.isfile(sp_file):
                    try:
                        with open(sp_file, encoding="utf-8") as fp:
                            sp_val = fp.read().strip()
                        if sp_val.isdigit() and int(sp_val) > 0:
                            speed = f"{sp_val} Mb/s"
                    except OSError:
                        pass
                net_info = f"IP: {', '.join(ips) or '—'} | GW: {gw or '—'} | DNS: {', '.join(dns) or '—'}"
                hw_info = f"{mac or '—'}" + (f" ({speed})" if speed else "")
                rows.append((dev, dtype, state, con or "—", net_info, hw_info))

            _, wifi_state = _run_sync(["nmcli", "radio", "wifi"], timeout=4)
            _, wifi_list = _run_sync(["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY,IN-USE", "device", "wifi", "list"], timeout=6)
            aps = []
            seen = set()
            for wl in wifi_list.splitlines():
                p = [x.replace("\\:", ":") for x in re.split(r"(?<!\\):", wl)]
                if len(p) >= 4 and p[0] and p[0] not in seen:
                    seen.add(p[0])
                    aps.append((p[0], f"{p[1]}%", p[2] or "Open", "Connected" if p[3] == "*" else ""))
            return {"ok": ok, "rows": rows, "wifi_on": "enabled" in wifi_state.lower(), "aps": aps}

        self._run_bg(_probe, self._populate, "Inspecting NetworkManager...")

    def _populate(self, data):
        if not data.get("ok"):
            self.set_status(data.get("err") or "nmcli unavailable", "err")
            return
        self._dev_table.setRowCount(0)
        self._active_dev = ""
        self._active_con = ""
        for rdata in data["rows"]:
            r = self._dev_table.rowCount()
            self._dev_table.insertRow(r)
            for c, val in enumerate(rdata):
                it = QTableWidgetItem(val)
                if c == 2:
                    it.setForeground(QBrush(QColor(COLORS["success"] if "connected" in val.lower() and "dis" not in val.lower() else COLORS["warning"])))
                self._dev_table.setItem(r, c, it)
            if rdata[1] == "ethernet" and not self._active_dev:
                self._active_dev = rdata[0]
                self._active_con = "" if rdata[3] == "—" else rdata[3]

        w_on = data["wifi_on"]
        self._wifi_badge.setText("Wi-Fi: ON" if w_on else "Wi-Fi: OFF")
        style_badge(self._wifi_badge, "success" if w_on else "neutral")

        self._wifi_table.setRowCount(0)
        for ap in data["aps"]:
            r = self._wifi_table.rowCount()
            self._wifi_table.insertRow(r)
            for c, val in enumerate(ap):
                it = QTableWidgetItem(val)
                if c == 3 and val:
                    it.setForeground(QBrush(QColor(COLORS["success"])))
                self._wifi_table.setItem(r, c, it)
        self.set_status(f"Loaded {len(data['rows'])} interface(s) and {len(data['aps'])} Wi-Fi network(s)", "ok")

    def _reconnect_dhcp(self):
        row = self._dev_table.currentRow()
        dev = self._dev_table.item(row, 0).text() if row >= 0 else self._active_dev
        con = self._dev_table.item(row, 3).text() if row >= 0 else self._active_con
        if not dev:
            QMessageBox.information(self, "No Interface", "No wired/network interface found.")
            return
        cmd = ["nmcli", "device", "reapply", dev] if not con or con == "—" else ["nmcli", "con", "up", con]
        self._run_cmd_bg(cmd, lambda ok, out: (self.refresh_page() if ok else QMessageBox.warning(self, "DHCP Failed", out)), f"Reconnecting {dev}...")

    def _toggle_wifi(self):
        target = "off" if "ON" in self._wifi_badge.text() else "on"
        self._run_cmd_bg(["nmcli", "radio", "wifi", target], lambda ok, out: (self.refresh_page() if ok else QMessageBox.warning(self, "Wi-Fi Toggle Failed", out)), f"Turning Wi-Fi {target}...")

    def _scan_wifi(self):
        self._run_cmd_bg(["nmcli", "device", "wifi", "rescan"], lambda _ok, _out: self.refresh_page(), "Scanning Wi-Fi access points...", timeout=15)

    def _connect_wifi(self):
        row = self._wifi_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Select Network", "Select a Wi-Fi SSID first.")
            return
        ssid = self._wifi_table.item(row, 0).text()
        sec = self._wifi_table.item(row, 2).text()
        cmd = ["nmcli", "device", "wifi", "connect", ssid]
        if sec.lower() != "open":
            dlg = _WifiPasswordDialog(ssid, self)
            if dlg.exec_() != QDialog.Accepted:
                return
            pw = dlg.password()
            if pw:
                cmd += ["password", pw]
        self._run_cmd_bg(cmd, lambda ok, out: (self.refresh_page() if ok else QMessageBox.warning(self, "Wi-Fi Connect Failed", out)), f"Connecting to {ssid}...", timeout=25)


# ==============================================================================
# 4. VPN & PRIVACY SHIELD
# ==============================================================================


class VPNPage(BaseSettingsPage):
    def __init__(self):
        super().__init__(
            "VPN, Tor && Encrypted DNS",
            "Live WireGuard/OpenVPN NM tunnels, Tor/Privoxy/Stubby status, and DNS presets",
            "SHIELD", "aqua",
        )
        self._svc_badges = {}

        svc_box = QGroupBox("Privacy & Tunnel Services")
        sl = QGridLayout(svc_box)
        for idx, (svc, label) in enumerate([("tor", "Tor Daemon"), ("privoxy", "Privoxy HTTP Proxy"), ("stubby", "Stubby DNS-over-TLS"), ("unbound", "Unbound Resolver")]):
            sl.addWidget(QLabel(label), idx, 0)
            b = make_badge("checking", "neutral", svc_box)
            self._svc_badges[svc] = b
            sl.addWidget(b, idx, 1)
            start_b = _make_btn("Start", "primary", svc_box)
            start_b.clicked.connect(lambda _c=False, s=svc: self._svc_action(s, "start"))
            sl.addWidget(start_b, idx, 2)
            stop_b = _make_btn("Stop", "danger", svc_box)
            stop_b.clicked.connect(lambda _c=False, s=svc: self._svc_action(s, "stop"))
            sl.addWidget(stop_b, idx, 3)
        self.body.addWidget(svc_box)

        vpn_box = QGroupBox("NetworkManager VPN / WireGuard Profiles")
        vl = QVBoxLayout(vpn_box)
        self._vpn_table = self._make_table(["Profile Name", "Type", "State"], stretch_col=0)
        self._vpn_table.setMinimumHeight(130)
        vl.addWidget(self._vpn_table)
        vr = QHBoxLayout()
        up_b = _make_btn("Connect Profile", "primary", vpn_box)
        up_b.clicked.connect(lambda: self._vpn_toggle(True))
        vr.addWidget(up_b)
        dn_b = _make_btn("Disconnect Profile", "danger", vpn_box)
        dn_b.clicked.connect(lambda: self._vpn_toggle(False))
        vr.addWidget(dn_b)
        shield_b = _make_btn("Launch Vice Net Shield", "secondary", vpn_box)
        shield_b.clicked.connect(self._open_net_shield)
        vr.addWidget(shield_b)
        vr.addStretch(1)
        vl.addLayout(vr)
        self.body.addWidget(vpn_box, 1)

        dns_box = QGroupBox("Current DNS (/etc/resolv.conf)")
        dl = QVBoxLayout(dns_box)
        self._dns_lbl = QLabel("Checking /etc/resolv.conf...")
        self._dns_lbl.setStyleSheet(f"font-family: {MONO_STACK}; color: {COLORS['accent_aqua']};")
        self._dns_lbl.setWordWrap(True)
        dl.addWidget(self._dns_lbl)
        self.body.addWidget(dns_box)

    def _open_net_shield(self):
        p = os.path.join(APP_DIR, "vice_tool_net_shield.py")
        if os.path.isfile(p):
            subprocess.Popen([sys.executable, p], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def refresh_page(self):
        def _probe():
            svcs = {}
            for s in ("tor", "privoxy", "stubby", "unbound"):
                ok, out = _run_sync(["systemctl", "is-active", s], timeout=3)
                svcs[s] = out.strip() or ("active" if ok else "inactive")
            vpns = []
            if shutil.which("nmcli"):
                ok_v, v_out = _run_sync(["nmcli", "-t", "-f", "NAME,TYPE,STATE", "con", "show"], timeout=4)
                for line in v_out.splitlines() if ok_v else []:
                    p = line.split(":")
                    if len(p) >= 3 and p[1] in ("vpn", "wireguard", "tun"):
                        vpns.append((p[0], p[1], p[2] or "inactive"))
            ns = []
            if os.path.isfile("/etc/resolv.conf"):
                try:
                    with open("/etc/resolv.conf", encoding="utf-8", errors="replace") as fp:
                        for line in fp:
                            if line.strip().startswith("nameserver"):
                                ns.append(line.strip())
                except OSError:
                    pass
            return {"svcs": svcs, "vpns": vpns, "dns": "\n".join(ns) or "(no nameservers in /etc/resolv.conf)"}

        self._run_bg(_probe, self._populate, "Checking VPN & privacy services...")

    def _populate(self, data):
        for s, st in data["svcs"].items():
            b = self._svc_badges[s]
            b.setText(st.upper())
            style_badge(b, "success" if st == "active" else "neutral")
        self._vpn_table.setRowCount(0)
        for row_vals in data["vpns"]:
            r = self._vpn_table.rowCount()
            self._vpn_table.insertRow(r)
            for c, val in enumerate(row_vals):
                self._vpn_table.setItem(r, c, QTableWidgetItem(val))
        self._dns_lbl.setText(data["dns"])
        self.set_status("Privacy & VPN status updated", "ok")

    def _svc_action(self, svc: str, action: str):
        self._run_cmd_bg(_priv_cmd(["systemctl", action, svc]), lambda ok, out: (self.refresh_page() if ok else QMessageBox.warning(self, "Service Error", out)), f"{action.title()}ing {svc}...")

    def _vpn_toggle(self, up: bool):
        row = self._vpn_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "No Profile", "Select a VPN/WireGuard profile first (or use Vice Net Shield to import .ovpn/.conf).")
            return
        name = self._vpn_table.item(row, 0).text()
        self._run_cmd_bg(["nmcli", "con", "up" if up else "down", name], lambda ok, out: (self.refresh_page() if ok else QMessageBox.warning(self, "VPN Error", out)), f"{'Connecting' if up else 'Disconnecting'} {name}...")


# ==============================================================================
# 5. BLUETOOTH
# ==============================================================================


class BluetoothPage(BaseSettingsPage):
    def __init__(self):
        super().__init__(
            "Bluetooth Peripherals",
            "Live adapter power toggle, nearby scan, and device pairing/connection",
            "BLUETOOTH", "aqua",
        )
        ctrl = QHBoxLayout()
        self._pwr_badge = make_badge("Adapter: --", "neutral", self)
        ctrl.addWidget(self._pwr_badge)
        self._pwr_btn = _make_btn("Toggle Power", "secondary", self)
        self._pwr_btn.clicked.connect(self._toggle_power)
        ctrl.addWidget(self._pwr_btn)
        scan_btn = _make_btn("Scan Nearby (8s)", "primary", self)
        scan_btn.clicked.connect(self._scan_devices)
        ctrl.addWidget(scan_btn)
        ctrl.addStretch(1)
        self.body.addLayout(ctrl)

        self._table = self._make_table(["MAC Address", "Name", "Paired", "Connected"], stretch_col=1)
        self._table.setMinimumHeight(240)
        self.body.addWidget(self._table, 1)

        acts = QHBoxLayout()
        for lbl, act, var in (
            ("Pair", "pair", "secondary"),
            ("Connect", "connect", "primary"),
            ("Disconnect", "disconnect", "secondary"),
            ("Remove", "remove", "danger"),
        ):
            b = _make_btn(lbl, var, self)
            b.clicked.connect(lambda _c=False, a=act: self._bt_action(a))
            acts.addWidget(b)
        acts.addStretch(1)
        self.body.addLayout(acts)

    def refresh_page(self):
        def _probe():
            if not shutil.which("bluetoothctl"):
                return {"ok": False, "err": "bluetoothctl not installed"}
            ok, show = _run_sync(["bluetoothctl", "show"], timeout=4)
            powered = "Powered: yes" in show
            _, paired = _run_sync(["bluetoothctl", "devices", "Paired"], timeout=4)
            _, conn = _run_sync(["bluetoothctl", "devices", "Connected"], timeout=4)
            conn_macs = {line.split()[1] for line in conn.splitlines() if len(line.split()) >= 2}
            devs = []
            for line in paired.splitlines():
                parts = line.split(None, 2)
                if len(parts) >= 3:
                    mac, name = parts[1], parts[2]
                    devs.append((mac, name, "Yes", "Yes" if mac in conn_macs else "No"))
            return {"ok": True, "powered": powered, "devs": devs, "has_ctrl": ok and bool(show)}

        self._run_bg(_probe, self._populate, "Querying Bluetooth adapter...")

    def _populate(self, data):
        if not data.get("ok"):
            self.set_status(data.get("err") or "Bluetooth unavailable", "warn")
            return
        pwr = data["powered"]
        self._pwr_badge.setText("POWER: ON" if pwr else ("POWER: OFF" if data["has_ctrl"] else "NO ADAPTER"))
        style_badge(self._pwr_badge, "success" if pwr else "neutral")
        self._pwr_btn.setText("Turn Off" if pwr else "Turn On")
        self._table.setRowCount(0)
        for mac, name, paired, conn in data["devs"]:
            self._add_dev_row(mac, name, paired, conn)
        self.set_status(f"{len(data['devs'])} paired device(s)", "ok")

    def _add_dev_row(self, mac, name, paired, conn):
        for r in range(self._table.rowCount()):
            if self._table.item(r, 0).text() == mac:
                return
        r = self._table.rowCount()
        self._table.insertRow(r)
        self._table.setItem(r, 0, QTableWidgetItem(mac))
        self._table.setItem(r, 1, QTableWidgetItem(name))
        self._table.setItem(r, 2, QTableWidgetItem(paired))
        self._table.setItem(r, 3, QTableWidgetItem(conn))

    def _toggle_power(self):
        on = "ON" not in self._pwr_badge.text()

        def _do():
            if on and shutil.which("rfkill"):
                _run_sync(["rfkill", "unblock", "bluetooth"], timeout=3)
            return _run_sync(["bluetoothctl", "power", "on" if on else "off"], timeout=5)

        self._run_bg(_do, lambda r: (self.refresh_page() if r[0] else QMessageBox.warning(self, "Bluetooth Error", r[1])), "Toggling Bluetooth power...")

    def _scan_devices(self):
        def _do():
            _run_sync(["bluetoothctl", "power", "on"], timeout=4)
            ok, out = _run_sync(["bluetoothctl", "--timeout", "8", "scan", "on"], timeout=12)
            found = []
            for line in out.splitlines():
                m = re.search(r"Device ([0-9A-F:]{17}) (.+)", line)
                if m:
                    found.append((m.group(1), m.group(2).strip()))
            return ok, found, out

        def _done(res):
            ok, found, out = res
            for mac, name in found:
                self._add_dev_row(mac, name, "No", "No")
            self.set_status(f"Scan finished ({len(found)} device(s) seen)", "ok" if ok or found else "warn")

        self._run_bg(_do, _done, "Scanning Bluetooth devices (8s)...")

    def _bt_action(self, action: str):
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select a Bluetooth device first.")
            return
        mac = self._table.item(row, 0).text()
        self._run_cmd_bg(["bluetoothctl", action, mac], lambda ok, out: (self.refresh_page() if ok else QMessageBox.warning(self, f"Bluetooth {action}", out)), f"Running bluetoothctl {action} {mac}...")


# ==============================================================================
# 6. FIREWALL (UFW)
# ==============================================================================


class FirewallPage(BaseSettingsPage):
    def __init__(self):
        super().__init__(
            "Firewall (UFW)",
            "Inspect live UFW numbered rules, toggle firewall state, and add/delete port rules",
            "UFW", "aqua",
        )
        top = QHBoxLayout()
        self._fw_badge = make_badge("UFW: --", "neutral", self)
        top.addWidget(self._fw_badge)
        top.addStretch(1)
        self._en_btn = _make_btn("Enable UFW", "primary", self)
        self._en_btn.clicked.connect(lambda: self._run_ufw(["--force", "enable"], "Enabling UFW..."))
        top.addWidget(self._en_btn)
        self._dis_btn = _make_btn("Disable UFW", "danger", self)
        self._dis_btn.clicked.connect(self._confirm_disable)
        top.addWidget(self._dis_btn)
        ins_btn = _make_btn("Inspect Live Rules (pkexec)", "secondary", self)
        ins_btn.clicked.connect(self._inspect_live)
        top.addWidget(ins_btn)
        self.body.addLayout(top)

        self._table = self._make_table(["#", "To", "Action", "From"], stretch_col=1)
        self._table.setMinimumHeight(200)
        self.body.addWidget(self._table, 1)

        add_box = QGroupBox("Add Port / Service Rule")
        al = QHBoxLayout(add_box)
        self._act_cb = QComboBox()
        self._act_cb.addItems(["allow", "deny", "limit"])
        al.addWidget(self._act_cb)
        self._dir_cb = QComboBox()
        self._dir_cb.addItems(["in", "out"])
        al.addWidget(self._dir_cb)
        self._proto_cb = QComboBox()
        self._proto_cb.addItems(["any", "tcp", "udp"])
        al.addWidget(self._proto_cb)
        self._port_ed = QLineEdit()
        self._port_ed.setPlaceholderText("Port/Service (e.g. 22, 443, ssh)")
        al.addWidget(self._port_ed, 1)
        add_btn = _make_btn("Add Rule", "primary", add_box)
        add_btn.clicked.connect(self._add_rule)
        al.addWidget(add_btn)
        del_btn = _make_btn("Delete Selected Rule", "danger", add_box)
        del_btn.clicked.connect(self._delete_rule)
        al.addWidget(del_btn)
        self.body.addWidget(add_box)

    def refresh_page(self):
        def _probe():
            conf = "/etc/ufw/ufw.conf"
            enabled = None
            if os.path.isfile(conf):
                try:
                    with open(conf, encoding="utf-8", errors="replace") as fp:
                        for line in fp:
                            if line.strip().startswith("ENABLED="):
                                enabled = "yes" in line.split("=", 1)[1].lower()
                                break
                except OSError:
                    pass
            live_out = ""
            if _is_root() and shutil.which("ufw"):
                _, live_out = _run_sync(["ufw", "status", "numbered"], timeout=6)
            return {"enabled": enabled, "live": live_out, "has_ufw": bool(shutil.which("ufw") or os.path.isfile("/usr/sbin/ufw"))}

        self._run_bg(_probe, self._populate, "Reading UFW configuration...")

    def _populate(self, data):
        if not data["has_ufw"]:
            self._fw_badge.setText("UFW NOT INSTALLED")
            style_badge(self._fw_badge, "danger")
            self.set_status("ufw binary not found", "warn")
            return
        if data["live"]:
            self._apply_live_output(data["live"])
            return
        if data["enabled"] is True:
            self._fw_badge.setText("CONFIGURED: ACTIVE")
            style_badge(self._fw_badge, "success")
        elif data["enabled"] is False:
            self._fw_badge.setText("CONFIGURED: INACTIVE")
            style_badge(self._fw_badge, "danger")
        else:
            self._fw_badge.setText("UFW READY")
            style_badge(self._fw_badge, "neutral")
        self.set_status("Click 'Inspect Live Rules (pkexec)' to query active kernel rules", "muted")

    def _inspect_live(self):
        ufw_bin = shutil.which("ufw") or "/usr/sbin/ufw"
        self._run_cmd_bg(_priv_cmd([ufw_bin, "status", "numbered"]), lambda ok, out: (self._apply_live_output(out) if ok else QMessageBox.warning(self, "UFW Inspect Failed", out)), "Querying live UFW rules...")

    def _apply_live_output(self, out: str):
        inactive = "inactive" in out.lower()
        self._fw_badge.setText("STATUS: INACTIVE" if inactive else "STATUS: ACTIVE")
        style_badge(self._fw_badge, "danger" if inactive else "success")
        self._table.setRowCount(0)
        for line in out.splitlines():
            m = re.match(r"^\[\s*(\d+)\]\s+(.+?)\s+(ALLOW IN|DENY IN|REJECT IN|LIMIT IN|ALLOW OUT|DENY OUT|ALLOW|DENY|REJECT|LIMIT)\s+(.*)$", line.strip(), re.I)
            if m:
                r = self._table.rowCount()
                self._table.insertRow(r)
                self._table.setItem(r, 0, QTableWidgetItem(m.group(1)))
                self._table.setItem(r, 1, QTableWidgetItem(m.group(2).strip()))
                act_it = QTableWidgetItem(m.group(3).upper())
                act_it.setForeground(QBrush(QColor(COLORS["success"] if "ALLOW" in m.group(3).upper() else COLORS["danger"])))
                self._table.setItem(r, 2, act_it)
                self._table.setItem(r, 3, QTableWidgetItem(m.group(4).strip() or "Anywhere"))
        self.set_status(f"Loaded {self._table.rowCount()} live UFW rule(s)", "ok")

    def _run_ufw(self, args: list, msg: str):
        ufw_bin = shutil.which("ufw") or "/usr/sbin/ufw"
        self._run_cmd_bg(_priv_cmd([ufw_bin] + args), lambda ok, out: (self._inspect_live() if ok else QMessageBox.warning(self, "UFW Error", out)), msg)

    def _confirm_disable(self):
        if QMessageBox.question(self, "Disable UFW", "Disable host firewall protection?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self._run_ufw(["disable"], "Disabling UFW...")

    def _add_rule(self):
        port = self._port_ed.text().strip()
        if not port or not re.match(r"^[A-Za-z0-9:_-]+$", port):
            QMessageBox.warning(self, "Invalid Port", "Enter a valid port number, range (8000:8010), or service name (ssh).")
            return
        args = [self._act_cb.currentText(), self._dir_cb.currentText()]
        proto = self._proto_cb.currentText()
        if proto != "any":
            args += ["proto", proto]
        args += ["to", "any", "port", port]
        self._run_ufw(args, f"Adding rule for {port}...")

    def _delete_rule(self):
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Inspect rules and select a rule number first.")
            return
        num = self._table.item(row, 0).text()
        if QMessageBox.question(self, "Delete Rule", f"Delete UFW rule #{num}?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self._run_ufw(["--force", "delete", num], f"Deleting rule #{num}...")


# ==============================================================================
# 7. DATE & TIME
# ==============================================================================


class DateTimePage(BaseSettingsPage):
    def __init__(self):
        super().__init__(
            "Date, Time && Timezone",
            "Live local clock, host/NTP sync via vice-timesync, searchable IANA selector, Chrony status",
            "UTC", "aqua",
        )
        self._zones = []
        self._timesync_bin = self._find_timesync()

        clock_box = QGroupBox("Local Clock & Host Sync")
        cl = QHBoxLayout(clock_box)
        left = QVBoxLayout()
        self._clock_lbl = QLabel("--:--:--")
        self._clock_lbl.setStyleSheet(f"color: {COLORS['text_primary']}; font-family: {MONO_STACK}; font-size: 32px; font-weight: bold;")
        left.addWidget(self._clock_lbl)
        self._date_lbl = QLabel("Loading...")
        self._date_lbl.setStyleSheet(f"color: {COLORS['accent_peach']}; font-size: 13px; font-weight: 600;")
        left.addWidget(self._date_lbl)
        cl.addLayout(left, 1)

        sync_btn = _make_btn("Sync With Host && Internet", "primary", clock_box)
        sync_btn.clicked.connect(lambda: self._run_timesync(["--auto", "--force"], "Syncing clock & timezone..."))
        cl.addWidget(sync_btn)
        self.body.addWidget(clock_box)

        tz_box = QGroupBox("IANA Timezone Selector")
        tl = QVBoxLayout(tz_box)
        self._tz_search = QLineEdit()
        self._tz_search.setPlaceholderText("Filter IANA timezones (e.g. Asia/Jakarta, America/New_York)...")
        self._tz_search.setClearButtonEnabled(True)
        self._tz_search.textChanged.connect(self._filter_tz)
        tl.addWidget(self._tz_search)
        self._tz_list = QListWidget()
        self._tz_list.setMinimumHeight(140)
        self._tz_list.itemDoubleClicked.connect(lambda _i: self._set_selected_tz())
        tl.addWidget(self._tz_list)
        set_tz_btn = _make_btn("Set Timezone", "secondary", tz_box)
        set_tz_btn.clicked.connect(self._set_selected_tz)
        tl.addWidget(set_tz_btn, 0, Qt.AlignLeft)
        self.body.addWidget(tz_box)

        chrony_box = QGroupBox("Chrony & timedatectl Status")
        chl = QVBoxLayout(chrony_box)
        self._chrony_out = QPlainTextEdit()
        self._chrony_out.setReadOnly(True)
        self._chrony_out.setMaximumHeight(130)
        chl.addWidget(self._chrony_out)
        self.body.addWidget(chrony_box)

        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(1000)
        self._tick_timer.timeout.connect(self._tick)
        self._timers.append(self._tick_timer)

    @staticmethod
    def _find_timesync() -> str:
        if shutil.which("vice-timesync"):
            return shutil.which("vice-timesync")
        for c in ("/usr/local/bin/vice-timesync", os.path.join(APP_DIR, "..", "system_scripts", "vice-timesync.sh")):
            if os.path.isfile(c):
                return c
        return "/usr/local/bin/vice-timesync"

    @staticmethod
    def _active_tz() -> str:
        try:
            tgt = os.path.realpath("/etc/localtime")
            if "/usr/share/zoneinfo/" in tgt:
                return tgt.split("/usr/share/zoneinfo/", 1)[1]
        except OSError:
            pass
        return time.tzname[0] or "UTC"

    def _tick(self):
        if hasattr(time, "tzset"):
            try:
                time.tzset()
            except Exception:
                pass
        now = datetime.now().astimezone()
        self._clock_lbl.setText(now.strftime("%H:%M:%S"))
        tz = self._active_tz()
        self._date_lbl.setText(f"{now.strftime('%A, %d %B %Y')} · {tz}")
        if self._badge is not None:
            self._badge.setText(tz)

    def refresh_page(self):
        if not self._tick_timer.isActive():
            self._tick_timer.start()
        self._tick()

        def _probe():
            zones = set()
            tab = "/usr/share/zoneinfo/zone1970.tab"
            if os.path.isfile(tab):
                try:
                    with open(tab, encoding="utf-8", errors="replace") as fp:
                        for line in fp:
                            line = line.strip()
                            if line and not line.startswith("#"):
                                cols = line.split("\t")
                                if len(cols) >= 3:
                                    zones.add(cols[2].strip())
                except OSError:
                    pass
            if not zones and available_timezones is not None:
                zones = {z for z in available_timezones() if "/" in z}
            zones.add("UTC")

            lines = []
            if shutil.which("timedatectl"):
                _, td = _run_sync(["timedatectl"], timeout=4)
                lines.append("=== timedatectl ===\n" + td)
            if shutil.which("chronyc"):
                _, ch = _run_sync(["chronyc", "tracking"], timeout=4)
                lines.append("=== chronyc tracking ===\n" + ch)
            return {"zones": sorted(zones), "diag": "\n\n".join(lines) or "timedatectl/chronyc unavailable"}

        self._run_bg(_probe, self._populate, "Loading timezones & Chrony status...")

    def _populate(self, data):
        self._zones = data["zones"]
        self._filter_tz()
        self._chrony_out.setPlainText(data["diag"])
        self.set_status(f"Active timezone: {self._active_tz()}", "ok")

    def _filter_tz(self):
        q = self._tz_search.text().strip().lower()
        active = self._active_tz()
        self._tz_list.clear()
        for z in self._zones:
            if not q or q in z.lower():
                it = QListWidgetItem(z)
                self._tz_list.addItem(it)
                if z == active:
                    self._tz_list.setCurrentItem(it)

    def _set_selected_tz(self):
        it = self._tz_list.currentItem()
        if not it:
            QMessageBox.information(self, "Select Timezone", "Select an IANA timezone from the list first.")
            return
        self._run_timesync(["--set", it.text()], f"Setting timezone to {it.text()}...")

    def _run_timesync(self, args: list, msg: str):
        ts = self._timesync_bin
        if os.path.isfile(ts) or shutil.which(ts):
            cmd = _priv_cmd((["bash", ts] if ts.endswith(".sh") else [ts]) + args)
        elif args[0] == "--set" and shutil.which("timedatectl"):
            cmd = _priv_cmd(["timedatectl", "set-timezone", args[1]])
        else:
            QMessageBox.warning(self, "Missing Tool", "vice-timesync / timedatectl not found.")
            return
        self._run_cmd_bg(cmd, lambda ok, out: (self.refresh_page() if ok else QMessageBox.warning(self, "TimeSync Failed", out)), msg)


# ==============================================================================
# 8 & 9. STORAGE & USB (Shared Native Auto-Mount & Auto-Play Config Helpers)
# ==============================================================================

LIBFM_CONF = os.path.expanduser("~/.config/libfm/libfm.conf")


def _read_native_automount() -> dict:
    """Read libfm.conf [volume] and xfconf-query thunar-volman settings."""
    state = {"mount_on_startup": True, "mount_removable": True, "autorun": True, "autobrowse": True, "autoplay_audio": True}
    if os.path.isfile(LIBFM_CONF):
        cp = configparser.ConfigParser(interpolation=None)
        try:
            cp.read(LIBFM_CONF, encoding="utf-8")
            if cp.has_section("volume"):
                vol = cp["volume"]
                state["mount_on_startup"] = vol.get("mount_on_startup", "1").strip() == "1"
                state["mount_removable"] = vol.get("mount_removable", "1").strip() == "1"
                state["autorun"] = vol.get("autorun", "1").strip() == "1"
        except Exception:
            pass
    if shutil.which("xfconf-query"):
        for key, prop in (("autobrowse", "/autobrowse/enabled"), ("autoplay_audio", "/autoplay-audio-cds/enabled")):
            ok, out = _run_sync(["xfconf-query", "-c", "thunar-volman", "-p", prop], timeout=3)
            if ok and out.strip().lower() in ("true", "false"):
                state[key] = out.strip().lower() == "true"
    return state


def _write_native_automount(mount_startup: bool, mount_removable: bool, autorun: bool, autobrowse: bool, autoplay_audio: bool) -> tuple:
    """Persist native Linux auto-mount/auto-play settings to libfm.conf and thunar-volman xfconf."""
    cp = configparser.ConfigParser(interpolation=None)
    cp.optionxform = str
    if os.path.isfile(LIBFM_CONF):
        try:
            cp.read(LIBFM_CONF, encoding="utf-8")
        except Exception:
            pass
    if not cp.has_section("volume"):
        cp.add_section("volume")
    cp.set("volume", "mount_on_startup", "1" if mount_startup else "0")
    cp.set("volume", "mount_removable", "1" if mount_removable else "0")
    cp.set("volume", "autorun", "1" if autorun else "0")
    try:
        os.makedirs(os.path.dirname(LIBFM_CONF), exist_ok=True)
        with open(LIBFM_CONF, "w", encoding="utf-8", newline="\n") as fp:
            cp.write(fp, space_around_delimiters=False)
    except OSError as exc:
        return False, f"Failed writing {LIBFM_CONF}: {exc}"

    if shutil.which("xfconf-query"):
        pairs = (
            ("/automount-drives/enabled", "true" if mount_removable else "false"),
            ("/automount-media/enabled", "true" if mount_removable else "false"),
            ("/autobrowse/enabled", "true" if autobrowse else "false"),
            ("/autoplay-audio-cds/enabled", "true" if autoplay_audio else "false"),
            ("/autoplay-video-cds/enabled", "true" if autorun else "false"),
        )
        for prop, val in pairs:
            _run_sync(["xfconf-query", "-c", "thunar-volman", "-p", prop, "-n", "-t", "bool", "-s", val], timeout=3)
    return True, "Saved native auto-mount & auto-play preferences"


def _flatten_lsblk(nodes: list, parent_tran: str = "", usb_only: bool = False) -> list:
    rows = []
    for dev in nodes or []:
        tran = dev.get("tran") or parent_tran
        children = dev.get("children") or []
        dtype = dev.get("type") or ""
        if (not usb_only or tran == "usb") and (dtype in ("part", "disk", "rom") or dev.get("fstype")):
            if not (usb_only and children and dtype == "disk"):
                rows.append({
                    "name": dev.get("name", ""),
                    "type": dtype,
                    "fstype": dev.get("fstype") or "—",
                    "size": dev.get("size") or "",
                    "label": dev.get("label") or "",
                    "mountpoint": dev.get("mountpoint") or "",
                    "tran": tran or "local",
                })
        if children:
            rows.extend(_flatten_lsblk(children, tran, usb_only=usb_only))
    return rows


class _BaseBlockStoragePage(BaseSettingsPage):
    def __init__(self, title: str, subtitle: str, badge: str, usb_only: bool):
        super().__init__(title, subtitle, badge, "peach")
        self._usb_only = usb_only

        self._table = self._make_table(["Device", "Type", "FS", "Size", "Label", "Bus", "Mountpoint"], stretch_col=6)
        self._table.setMinimumHeight(180)
        self.body.addWidget(self._table, 1)

        act = QHBoxLayout()
        m_btn = _make_btn("Mount", "primary", self)
        m_btn.clicked.connect(lambda: self._udisks("mount"))
        act.addWidget(m_btn)
        u_btn = _make_btn("Unmount", "secondary", self)
        u_btn.clicked.connect(lambda: self._udisks("unmount"))
        act.addWidget(u_btn)
        e_btn = _make_btn("Safely Eject", "danger", self)
        e_btn.clicked.connect(lambda: self._udisks("power-off"))
        act.addWidget(e_btn)
        act.addStretch(1)
        self.body.addLayout(act)

        auto_box = QGroupBox("Native Auto-Mount && Auto-Play (libfm + thunar-volman)")
        al = QVBoxLayout(auto_box)
        self._cb_startup = QCheckBox("Mount available volumes on session startup (mount_on_startup)")
        self._cb_removable = QCheckBox("Auto-mount removable USB/media drives when plugged in (mount_removable)")
        self._cb_autorun = QCheckBox("Enable auto-run / media auto-play actions (autorun)")
        self._cb_autobrowse = QCheckBox("Open file manager automatically on removable mount (autobrowse)")
        self._cb_audio = QCheckBox("Auto-play Audio CDs / media with MPV (autoplay-audio-cds)")
        for cb in (self._cb_startup, self._cb_removable, self._cb_autorun, self._cb_autobrowse, self._cb_audio):
            al.addWidget(cb)
        save_auto = _make_btn("Save Auto-Mount && Auto-Play Settings", "secondary", auto_box)
        save_auto.clicked.connect(self._save_automount)
        al.addWidget(save_auto, 0, Qt.AlignLeft)
        self.body.addWidget(auto_box)

    def refresh_page(self):
        def _probe():
            rows = []
            if shutil.which("lsblk"):
                ok, out = _run_sync(["lsblk", "-J", "-o", "NAME,TYPE,FSTYPE,SIZE,LABEL,MOUNTPOINT,TRAN"], timeout=6)
                if ok and out:
                    data = json.loads(out)
                    rows = _flatten_lsblk(data.get("blockdevices", []), usb_only=self._usb_only)
            df_txt = ""
            if not self._usb_only and shutil.which("df"):
                _, df_txt = _run_sync(["df", "-h", "-x", "tmpfs", "-x", "devtmpfs"], timeout=4)
            auto = _read_native_automount()
            return {"rows": rows, "auto": auto, "df": df_txt}

        self._run_bg(_probe, self._populate, "Scanning block devices...")

    def _populate(self, data):
        self._table.setRowCount(0)
        for d in data["rows"]:
            r = self._table.rowCount()
            self._table.insertRow(r)
            vals = (f"/dev/{d['name']}", d["type"], d["fstype"], d["size"], d["label"], d["tran"], d["mountpoint"] or "Unmounted")
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if c == 6:
                    it.setForeground(QBrush(QColor(COLORS["success"] if d["mountpoint"] else COLORS["text_muted"])))
                self._table.setItem(r, c, it)
        auto = data["auto"]
        self._cb_startup.setChecked(auto["mount_on_startup"])
        self._cb_removable.setChecked(auto["mount_removable"])
        self._cb_autorun.setChecked(auto["autorun"])
        self._cb_autobrowse.setChecked(auto["autobrowse"])
        self._cb_audio.setChecked(auto["autoplay_audio"])
        self.set_status(f"Found {len(data['rows'])} device/partition(s)", "ok")

    def _udisks(self, op: str):
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select a drive or partition first.")
            return
        dev = self._table.item(row, 0).text()
        if not shutil.which("udisksctl"):
            QMessageBox.warning(self, "Missing Tool", "udisksctl not installed.")
            return
        self._run_cmd_bg(["udisksctl", op, "-b", dev], lambda ok, out: (self.refresh_page() if ok else QMessageBox.warning(self, f"udisksctl {op}", out)), f"Running udisksctl {op} {dev}...")

    def _save_automount(self):
        ok, msg = _write_native_automount(
            self._cb_startup.isChecked(),
            self._cb_removable.isChecked(),
            self._cb_autorun.isChecked(),
            self._cb_autobrowse.isChecked(),
            self._cb_audio.isChecked(),
        )
        if ok:
            self.set_status(msg, "ok")
        else:
            QMessageBox.warning(self, "Save Failed", msg)


class StoragePage(_BaseBlockStoragePage):
    def __init__(self):
        super().__init__(
            "Storage, Disks && Auto-Mount",
            "Live lsblk/df partitions, udisksctl mount/eject, and native libfm/thunar-volman auto-mount",
            "STORAGE", False,
        )


class USBPage(_BaseBlockStoragePage):
    def __init__(self):
        super().__init__(
            "USB Drives && Auto-Play",
            "Removable USB storage mount/eject plus native USB auto-mount & media auto-play controls",
            "USB", True,
        )
        usb_box = QGroupBox("Connected USB Bus Devices (lsusb)")
        ul = QVBoxLayout(usb_box)
        self._lsusb_txt = QPlainTextEdit()
        self._lsusb_txt.setReadOnly(True)
        self._lsusb_txt.setMaximumHeight(110)
        ul.addWidget(self._lsusb_txt)
        self.body.addWidget(usb_box)

    def refresh_page(self):
        super().refresh_page()
        if shutil.which("lsusb"):
            self._run_bg(lambda: _run_sync(["lsusb"], timeout=4)[1], lambda txt: self._lsusb_txt.setPlainText(txt or "No USB devices"), "Listing USB bus...")


# ==============================================================================
# 10. UPDATES (APT + Bookworm-Backports + Unattended Upgrades + fwupd)
# ==============================================================================


class UpdatesPage(BaseSettingsPage):
    def __init__(self):
        super().__init__(
            "System Updates, Kernel Pin && Firmware",
            "Live Debian APT upgrades, bookworm-backports kernel pin, unattended-upgrades, and fwupd",
            "APT + FWUPD", "aqua",
        )
        info_box = QGroupBox("Update Posture")
        il = QGridLayout(info_box)
        self._kern_lbl = QLabel("Kernel: --")
        self._bpo_lbl = QLabel("Backports Pin: --")
        self._unatt_lbl = QLabel("Unattended Upgrades: --")
        self._fw_lbl = QLabel("Firmware (fwupd): --")
        il.addWidget(self._kern_lbl, 0, 0)
        il.addWidget(self._bpo_lbl, 0, 1)
        il.addWidget(self._unatt_lbl, 1, 0)
        il.addWidget(self._fw_lbl, 1, 1)

        self._unatt_btn = _make_btn("Toggle Unattended Security Upgrades", "secondary", info_box)
        self._unatt_btn.clicked.connect(self._toggle_unattended)
        il.addWidget(self._unatt_btn, 2, 0)

        fw_btn = _make_btn("Check Firmware Updates (fwupdmgr)", "secondary", info_box)
        fw_btn.clicked.connect(self._check_fwupd)
        il.addWidget(fw_btn, 2, 1)
        self.body.addWidget(info_box)

        self._table = self._make_table(["Package", "Current Version", "Candidate Version", "Arch"], stretch_col=0)
        self._table.setMinimumHeight(180)
        self.body.addWidget(self._table, 1)

        acts = QHBoxLayout()
        chk_btn = _make_btn("Check APT Updates (pkexec)", "secondary", self)
        chk_btn.clicked.connect(self._apt_update)
        acts.addWidget(chk_btn)
        inst_btn = _make_btn("Install APT Updates (pkexec)", "primary", self)
        inst_btn.clicked.connect(self._apt_upgrade)
        acts.addWidget(inst_btn)
        acts.addStretch(1)
        self.body.addLayout(acts)

    def refresh_page(self):
        def _probe():
            _, kver = _run_sync(["uname", "-r"], timeout=3)
            bpo_pin = os.path.isfile("/etc/apt/preferences.d/90-vice-backports-kernel")
            bpo_src = False
            if os.path.isfile("/etc/apt/sources.list"):
                try:
                    with open("/etc/apt/sources.list", encoding="utf-8", errors="replace") as fp:
                        bpo_src = "bookworm-backports" in fp.read()
                except OSError:
                    pass
            unatt_active = False
            if shutil.which("systemctl"):
                ok_u, u_out = _run_sync(["systemctl", "is-active", "unattended-upgrades"], timeout=3)
                unatt_active = ok_u and u_out.strip() == "active"

            pkgs = []
            if shutil.which("apt"):
                _, apt_out = _run_sync(["apt", "list", "--upgradable", "--quiet=2"], timeout=12)
                for line in apt_out.splitlines():
                    if "/" in line:
                        p = line.split()
                        name = p[0].split("/")[0]
                        new_v = p[1] if len(p) > 1 else ""
                        arch = p[2] if len(p) > 2 else ""
                        old_v = ""
                        for i, tok in enumerate(p):
                            if tok.startswith("[upgradable") and i + 2 < len(p):
                                old_v = p[i + 2].rstrip("]")
                                break
                        pkgs.append((name, old_v, new_v, arch))
            return {"kver": kver, "bpo_pin": bpo_pin, "bpo_src": bpo_src, "unatt": unatt_active, "pkgs": pkgs}

        self._run_bg(_probe, self._populate, "Checking APT & backports kernel status...")

    def _populate(self, data):
        self._kern_lbl.setText(f"Running Kernel: {data['kver']}")
        bpo_txt = "Active (bookworm-backports pinned)" if (data["bpo_pin"] and data["bpo_src"]) else ("Configured" if data["bpo_src"] else "Standard Bookworm")
        self._bpo_lbl.setText(f"Backports Pin: {bpo_txt}")
        self._unatt_lbl.setText(f"Unattended Upgrades: {'ENABLED' if data['unatt'] else 'Disabled / Not Installed'}")
        self._fw_lbl.setText("Firmware (fwupd): Ready" if shutil.which("fwupdmgr") else "Firmware: fwupd not installed")
        self._table.setRowCount(0)
        for p in data["pkgs"]:
            r = self._table.rowCount()
            self._table.insertRow(r)
            for c, val in enumerate(p):
                self._table.setItem(r, c, QTableWidgetItem(val))
        self.set_status(f"{len(data['pkgs'])} upgradable package(s) cached", "ok")

    def _apt_update(self):
        self._run_cmd_bg(_priv_cmd(["apt-get", "update", "-qq"]), lambda ok, out: (self.refresh_page() if ok else QMessageBox.warning(self, "APT Update Failed", out)), "Updating APT package lists...", timeout=90)

    def _apt_upgrade(self):
        if QMessageBox.question(self, "Install Updates", "Run system upgrade (apt-get upgrade -y)?", QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self._run_cmd_bg(_priv_cmd(["env", "DEBIAN_FRONTEND=noninteractive", "apt-get", "upgrade", "-y"]), lambda ok, out: (self.refresh_page() if ok else QMessageBox.warning(self, "Upgrade Failed", out)), "Installing APT upgrades...", timeout=300)

    def _toggle_unattended(self):
        enable = "Disabled" in self._unatt_lbl.text()
        action = "enable" if enable else "disable"
        cmd = _priv_cmd(["systemctl", action, "--now", "unattended-upgrades"])
        self._run_cmd_bg(cmd, lambda ok, out: (self.refresh_page() if ok else QMessageBox.warning(self, "Unattended Upgrades", out)), f"Running systemctl {action} unattended-upgrades...")

    def _check_fwupd(self):
        if not shutil.which("fwupdmgr"):
            QMessageBox.information(self, "fwupd Missing", "Install fwupd to inspect firmware updates.")
            return
        self._run_cmd_bg(["fwupdmgr", "get-updates"], lambda _ok, out: (self._fw_lbl.setText(f"Firmware: {out.splitlines()[0][:55]}" if out else "Firmware: Up to date"), self.set_status(out or "Firmware check complete", "ok")), "Checking firmware updates...")


# ==============================================================================
# 11. KERNEL & SYSCTL
# ==============================================================================


class KernelPage(BaseSettingsPage):
    def __init__(self):
        super().__init__(
            "Kernel, Modules && Sysctl",
            "Live kernel release, bookworm-backports policy, loaded modules, and sysctl tuning",
            "KERNEL", "coral",
        )
        top = QGroupBox("Kernel Summary")
        tl = QVBoxLayout(top)
        self._kern_info = QLabel("Loading...")
        self._kern_info.setWordWrap(True)
        self._kern_info.setStyleSheet(f"font-family: {MONO_STACK}; color: {COLORS['accent_aqua']};")
        tl.addWidget(self._kern_info)
        self.body.addWidget(top)

        sys_box = QGroupBox("Live Sysctl Network & VM Parameters")
        sl = QHBoxLayout(sys_box)
        self._sys_key = QComboBox()
        self._sys_key.addItems([
            "net.ipv4.tcp_congestion_control",
            "net.core.default_qdisc",
            "net.ipv4.tcp_mtu_probing",
            "vm.swappiness",
            "fs.inotify.max_user_watches",
        ])
        sl.addWidget(self._sys_key, 1)
        self._sys_val = QLineEdit()
        self._sys_val.setPlaceholderText("New value")
        sl.addWidget(self._sys_val)
        apply_s = _make_btn("Apply Sysctl (pkexec)", "primary", sys_box)
        apply_s.clicked.connect(self._apply_sysctl)
        sl.addWidget(apply_s)
        self.body.addWidget(sys_box)

        self._mod_table = self._make_table(["Module", "Size", "Used By"], stretch_col=2)
        self._mod_table.setMinimumHeight(200)
        self.body.addWidget(self._mod_table, 1)

    def refresh_page(self):
        def _probe():
            _, uname = _run_sync(["uname", "-srm"], timeout=3)
            _, cc = _run_sync(["sysctl", "-n", "net.ipv4.tcp_congestion_control"], timeout=3)
            _, qd = _run_sync(["sysctl", "-n", "net.core.default_qdisc"], timeout=3)
            _, policy = _run_sync(["apt-cache", "policy", "linux-image-amd64"], timeout=5)
            cand = ""
            for line in policy.splitlines():
                if "Candidate:" in line:
                    cand = line.split(":", 1)[1].strip()
                    break
            mods = []
            _, lsmod = _run_sync(["lsmod"], timeout=4)
            for line in lsmod.splitlines()[1:80]:
                p = line.split()
                if len(p) >= 3:
                    mods.append((p[0], p[1], " ".join(p[2:])))
            return {"uname": uname, "cc": cc, "qd": qd, "cand": cand or "—", "mods": mods}

        self._run_bg(_probe, self._populate, "Inspecting kernel & modules...")

    def _populate(self, data):
        self._kern_info.setText(
            f"Running: {data['uname']}  |  Backports/APT Candidate: {data['cand']}\n"
            f"TCP Congestion Control: {data['cc']}  |  Default Qdisc: {data['qd']}"
        )
        self._mod_table.setRowCount(0)
        for m in data["mods"]:
            r = self._mod_table.rowCount()
            self._mod_table.insertRow(r)
            for c, v in enumerate(m):
                self._mod_table.setItem(r, c, QTableWidgetItem(v))
        self.set_status(f"Loaded {len(data['mods'])} kernel module(s)", "ok")

    def _apply_sysctl(self):
        k = self._sys_key.currentText()
        v = self._sys_val.text().strip()
        if not v:
            QMessageBox.warning(self, "Empty Value", f"Enter a value for {k}.")
            return
        self._run_cmd_bg(_priv_cmd(["sysctl", "-w", f"{k}={v}"]), lambda ok, out: (self.refresh_page() if ok else QMessageBox.warning(self, "Sysctl Failed", out)), f"Setting {k}={v}...")


# ==============================================================================
# 12. POWER
# ==============================================================================


class PowerPage(BaseSettingsPage):
    def __init__(self):
        super().__init__(
            "Power, CPU Governor && Session",
            "Live AC/Battery telemetry, CPU scaling governor, DPMS screen blanking, and power actions",
            "POWER", "aqua",
        )
        bat_box = QGroupBox("Battery & Power Supply")
        bl = QVBoxLayout(bat_box)
        self._bat_bar = QProgressBar()
        self._bat_bar.setRange(0, 100)
        bl.addWidget(self._bat_bar)
        self._bat_lbl = QLabel("Checking power supply...")
        bl.addWidget(self._bat_lbl)
        self.body.addWidget(bat_box)

        gov_box = QGroupBox("CPU Scaling Governor & Screen Blanking")
        gl = QFormLayout(gov_box)
        gov_row = QHBoxLayout()
        self._gov_combo = QComboBox()
        gov_row.addWidget(self._gov_combo, 1)
        gov_btn = _make_btn("Apply Governor (pkexec)", "primary", gov_box)
        gov_btn.clicked.connect(self._apply_governor)
        gov_row.addWidget(gov_btn)
        gl.addRow("CPU Governor:", gov_row)

        dpms_row = QHBoxLayout()
        self._dpms_combo = QComboBox()
        self._dpms_combo.addItem("Never (Disable Blanking)", 0)
        self._dpms_combo.addItem("5 Minutes", 300)
        self._dpms_combo.addItem("10 Minutes", 600)
        self._dpms_combo.addItem("30 Minutes", 1800)
        dpms_row.addWidget(self._dpms_combo, 1)
        dpms_btn = _make_btn("Apply Blanking", "secondary", gov_box)
        dpms_btn.clicked.connect(self._apply_dpms)
        dpms_row.addWidget(dpms_btn)
        gl.addRow("Screen Blank / DPMS:", dpms_row)
        self.body.addWidget(gov_box)

        act_box = QGroupBox("Session Power Actions")
        al = QHBoxLayout(act_box)
        for lbl, cmd, var in (
            ("Suspend", ["systemctl", "suspend"], "secondary"),
            ("Reboot", ["systemctl", "reboot"], "secondary"),
            ("Shutdown", ["systemctl", "poweroff"], "danger"),
        ):
            b = _make_btn(lbl, var, act_box)
            b.clicked.connect(lambda _c=False, c=cmd, lb=lbl: self._power_cmd(c, lb))
            al.addWidget(b)
        al.addStretch(1)
        self.body.addWidget(act_box)
        self.body.addStretch(1)

    def refresh_page(self):
        def _probe():
            bat = None
            for bp in ("/sys/class/power_supply/BAT0", "/sys/class/power_supply/BAT1"):
                if os.path.isdir(bp):
                    try:
                        cap = open(os.path.join(bp, "capacity"), encoding="utf-8").read().strip()
                        st = open(os.path.join(bp, "status"), encoding="utf-8").read().strip()
                        bat = (int(cap) if cap.isdigit() else 100, st)
                        break
                    except OSError:
                        pass
            avail_govs, cur_gov = [], ""
            g_avail = "/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors"
            g_cur = "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"
            if os.path.isfile(g_avail):
                avail_govs = open(g_avail, encoding="utf-8").read().strip().split()
            if os.path.isfile(g_cur):
                cur_gov = open(g_cur, encoding="utf-8").read().strip()
            return {"bat": bat, "govs": avail_govs, "cur_gov": cur_gov}

        self._run_bg(_probe, self._populate, "Reading battery & CPU governor...")

    def _populate(self, data):
        if data["bat"]:
            pct, st = data["bat"]
            self._bat_bar.setValue(pct)
            self._bat_lbl.setText(f"{pct}% — {st}")
        else:
            self._bat_bar.setValue(100)
            self._bat_lbl.setText("AC Power / Virtual Machine (no battery cell)")
        self._gov_combo.clear()
        for g in (data["govs"] or ["performance", "powersave", "schedutil"]):
            self._gov_combo.addItem(g)
        if data["cur_gov"]:
            idx = self._gov_combo.findText(data["cur_gov"])
            if idx >= 0:
                self._gov_combo.setCurrentIndex(idx)
        self.set_status(f"CPU governor: {data['cur_gov'] or 'default'}", "ok")

    def _apply_governor(self):
        gov = self._gov_combo.currentText()
        paths = sorted(glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor"))
        if not paths:
            QMessageBox.information(self, "Unavailable", "CPU frequency scaling is not exposed on this VM/hardware.")
            return
        script = f"for f in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo {shlex.quote(gov)} > \"$f\"; done"
        self._run_cmd_bg(_priv_cmd(["bash", "-c", script]), lambda ok, out: (self.refresh_page() if ok else QMessageBox.warning(self, "Governor Error", out)), f"Setting governor {gov}...")

    def _apply_dpms(self):
        sec = int(self._dpms_combo.currentData() or 0)
        if not shutil.which("xset"):
            QMessageBox.warning(self, "Missing xset", "xset command not available.")
            return
        cmd = ["bash", "-c", "xset s off -dpms" if sec == 0 else f"xset s {sec} +dpms && xset dpms {sec} {sec} {sec}"]
        self._run_cmd_bg(cmd, lambda ok, out: self.set_status("Updated X11 screen blanking" if ok else out, "ok" if ok else "err"), "Applying DPMS...")

    def _power_cmd(self, cmd: list, label: str):
        if QMessageBox.question(self, label, f"{label} the system now?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ==============================================================================
# 13. USERS
# ==============================================================================


class UsersPage(BaseSettingsPage):
    def __init__(self):
        super().__init__(
            "User Accounts && Groups",
            "Local Linux accounts (/etc/passwd UID >= 1000), group memberships, password & user creation",
            "USERS", "coral",
        )
        self._table = self._make_table(["Username", "UID", "Shell", "Home", "Groups"], stretch_col=4)
        self._table.setMinimumHeight(200)
        self.body.addWidget(self._table, 1)

        acts = QHBoxLayout()
        pw_btn = _make_btn("Change Password", "primary", self)
        pw_btn.clicked.connect(self._change_password)
        acts.addWidget(pw_btn)
        add_btn = _make_btn("Create User", "secondary", self)
        add_btn.clicked.connect(self._create_user)
        acts.addWidget(add_btn)
        acts.addStretch(1)
        self.body.addLayout(acts)

    def refresh_page(self):
        def _probe():
            users = []
            with open("/etc/passwd", encoding="utf-8", errors="replace") as fp:
                for line in fp:
                    parts = line.strip().split(":")
                    if len(parts) < 7:
                        continue
                    uid = int(parts[2]) if parts[2].isdigit() else 0
                    if uid >= 1000 and parts[0] != "nobody":
                        _, grps = _run_sync(["id", "-Gn", parts[0]], timeout=3)
                        users.append((parts[0], parts[2], parts[6], parts[5], grps))
            return users

        self._run_bg(_probe, self._populate, "Reading local users...")

    def _populate(self, users):
        self._table.setRowCount(0)
        for u in users:
            r = self._table.rowCount()
            self._table.insertRow(r)
            for c, val in enumerate(u):
                self._table.setItem(r, c, QTableWidgetItem(val))
        self.set_status(f"Found {len(users)} local user account(s)", "ok")

    def _change_password(self):
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select a user first.")
            return
        uname = self._table.item(row, 0).text()
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Change Password: {uname}")
        fl = QFormLayout(dlg)
        pw1 = QLineEdit(dlg)
        pw1.setEchoMode(QLineEdit.Password)
        pw2 = QLineEdit(dlg)
        pw2.setEchoMode(QLineEdit.Password)
        fl.addRow("New Password:", pw1)
        fl.addRow("Confirm Password:", pw2)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        fl.addRow(btns)
        if dlg.exec_() != QDialog.Accepted:
            return
        if not pw1.text() or pw1.text() != pw2.text():
            QMessageBox.warning(self, "Mismatch", "Passwords are empty or do not match.")
            return
        self._run_cmd_bg(_priv_cmd(["chpasswd"]), lambda ok, out: (self.set_status(f"Password updated for {uname}", "ok") if ok else QMessageBox.warning(self, "Failed", out)), f"Updating password for {uname}...", input_data=f"{uname}:{pw1.text()}\n")

    def _create_user(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Create Local User")
        fl = QFormLayout(dlg)
        un = QLineEdit(dlg)
        un.setPlaceholderText("lowercase username")
        pw = QLineEdit(dlg)
        pw.setEchoMode(QLineEdit.Password)
        sudo_cb = QCheckBox("Grant sudo administrator access", dlg)
        fl.addRow("Username:", un)
        fl.addRow("Password:", pw)
        fl.addRow("", sudo_cb)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        fl.addRow(btns)
        if dlg.exec_() != QDialog.Accepted:
            return
        uname = un.text().strip()
        if not re.match(r"^[a-z_][a-z0-9_-]{0,31}$", uname):
            QMessageBox.warning(self, "Invalid Username", "Use lowercase letters, digits, '-' or '_'.")
            return
        script = f"useradd -m -s /bin/bash {shlex.quote(uname)}"
        if sudo_cb.isChecked():
            script += f" && usermod -aG sudo {shlex.quote(uname)}"
        if pw.text():
            script += f" && printf '%s:%s\\n' {shlex.quote(uname)} {shlex.quote(pw.text())} | chpasswd"
        self._run_cmd_bg(_priv_cmd(["bash", "-c", script]), lambda ok, out: (self.refresh_page() if ok else QMessageBox.warning(self, "Create User Failed", out)), f"Creating user {uname}...")


# ==============================================================================
# 14. PRINTERS (CUPS)
# ==============================================================================


class PrintersPage(BaseSettingsPage):
    def __init__(self):
        super().__init__(
            "Printers && CUPS Queues",
            "Live CUPS service status, configured printers, active print jobs, and test page",
            "CUPS", "aqua",
        )
        top = QHBoxLayout()
        self._cups_badge = make_badge("CUPS: --", "neutral", self)
        top.addWidget(self._cups_badge)
        self._cups_btn = _make_btn("Toggle CUPS Service", "secondary", self)
        self._cups_btn.clicked.connect(self._toggle_cups)
        top.addWidget(self._cups_btn)
        top.addStretch(1)
        self.body.addLayout(top)

        self._printers_tbl = self._make_table(["Printer", "State", "Default", "Details"], stretch_col=3)
        self._printers_tbl.setMinimumHeight(140)
        self.body.addWidget(self._printers_tbl)

        p_acts = QHBoxLayout()
        def_b = _make_btn("Set Default", "secondary", self)
        def_b.clicked.connect(self._set_default)
        p_acts.addWidget(def_b)
        tst_b = _make_btn("Print Test Page", "primary", self)
        tst_b.clicked.connect(self._test_page)
        p_acts.addWidget(tst_b)
        gui_b = _make_btn("Add / Configure Printer", "secondary", self)
        gui_b.clicked.connect(self._open_printer_mgr)
        p_acts.addWidget(gui_b)
        p_acts.addStretch(1)
        self.body.addLayout(p_acts)

        self._jobs_tbl = self._make_table(["Job ID", "Details"], stretch_col=1)
        self._jobs_tbl.setMaximumHeight(140)
        self.body.addWidget(self._jobs_tbl)

    def _open_printer_mgr(self):
        p = os.path.join(APP_DIR, "vice_printer_manager.py")
        if os.path.isfile(p):
            subprocess.Popen([sys.executable, p], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def refresh_page(self):
        def _probe():
            ok_c, st_c = _run_sync(["systemctl", "is-active", "cups"], timeout=3)
            cups_on = ok_c and st_c.strip() == "active"
            printers, jobs = [], []
            def_name = ""
            if shutil.which("lpstat"):
                ok_p, out_p = _run_sync(["lpstat", "-p", "-d"], timeout=5)
                for line in out_p.splitlines() if ok_p else []:
                    if line.startswith("system default destination:"):
                        def_name = line.split(":", 1)[1].strip()
                    elif line.startswith("printer "):
                        parts = line.split(None, 3)
                        if len(parts) >= 3:
                            printers.append((parts[1], parts[2].rstrip("."), "", parts[3] if len(parts) > 3 else ""))
                ok_j, out_j = _run_sync(["lpstat", "-o"], timeout=4)
                for line in out_j.splitlines() if ok_j else []:
                    p = line.split(None, 1)
                    if p:
                        jobs.append((p[0], p[1] if len(p) > 1 else ""))
            return {"cups_on": cups_on, "printers": printers, "default": def_name, "jobs": jobs}

        self._run_bg(_probe, self._populate, "Querying CUPS printers...")

    def _populate(self, data):
        on = data["cups_on"]
        self._cups_badge.setText("CUPS: ACTIVE" if on else "CUPS: INACTIVE")
        style_badge(self._cups_badge, "success" if on else "neutral")
        self._printers_tbl.setRowCount(0)
        for name, st, _, det in data["printers"]:
            r = self._printers_tbl.rowCount()
            self._printers_tbl.insertRow(r)
            self._printers_tbl.setItem(r, 0, QTableWidgetItem(name))
            self._printers_tbl.setItem(r, 1, QTableWidgetItem(st))
            self._printers_tbl.setItem(r, 2, QTableWidgetItem("Yes" if name == data["default"] else "No"))
            self._printers_tbl.setItem(r, 3, QTableWidgetItem(det))
        self._jobs_tbl.setRowCount(0)
        for jid, det in data["jobs"]:
            r = self._jobs_tbl.rowCount()
            self._jobs_tbl.insertRow(r)
            self._jobs_tbl.setItem(r, 0, QTableWidgetItem(jid))
            self._jobs_tbl.setItem(r, 1, QTableWidgetItem(det))
        self.set_status(f"{len(data['printers'])} printer(s), {len(data['jobs'])} job(s)", "ok")

    def _toggle_cups(self):
        act = "stop" if "ACTIVE" in self._cups_badge.text() and "INACTIVE" not in self._cups_badge.text() else "start"
        self._run_cmd_bg(_priv_cmd(["systemctl", act, "cups"]), lambda ok, out: (self.refresh_page() if ok else QMessageBox.warning(self, "CUPS Error", out)), f"{act.title()}ing CUPS...")

    def _set_default(self):
        row = self._printers_tbl.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Printer", "Select a printer first.")
            return
        name = self._printers_tbl.item(row, 0).text()
        self._run_cmd_bg(_priv_cmd(["lpoptions", "-d", name]), lambda ok, out: (self.refresh_page() if ok else QMessageBox.warning(self, "Failed", out)), f"Setting default {name}...")

    def _test_page(self):
        row = self._printers_tbl.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Printer", "Select a printer first.")
            return
        name = self._printers_tbl.item(row, 0).text()
        self._run_cmd_bg(["lp", "-d", name, "/usr/share/cups/data/testprint"], lambda ok, out: (self.refresh_page() if ok else QMessageBox.warning(self, "Test Print Failed", out)), f"Printing test page to {name}...")


# ==============================================================================
# 15. THEME, 16. WALLPAPER, 17. KEYBOARD, 18. MOUSE, 19. ACCESSIBILITY
# ==============================================================================


class ThemePage(BaseSettingsPage):
    def __init__(self):
        super().__init__(
            "Theme && Appearance",
            "Live GTK3 theme, icon theme, font settings, and Openbox window decoration",
            "LEONIDA DUSK", "coral",
        )
        box = QGroupBox("Desktop Styling")
        fl = QFormLayout(box)
        self._gtk_cb = QComboBox()
        self._gtk_cb.setEditable(True)
        self._gtk_cb.addItems(["Arc-Dark", "Adwaita-dark", "Adwaita"])
        fl.addRow("GTK Theme:", self._gtk_cb)

        self._icon_cb = QComboBox()
        self._icon_cb.setEditable(True)
        self._icon_cb.addItems(["Papirus-Dark", "Papirus", "Adwaita"])
        fl.addRow("Icon Theme:", self._icon_cb)

        self._font_ed = QLineEdit("Noto Sans 10")
        fl.addRow("Interface Font:", self._font_ed)

        self._ob_lbl = QLabel("--")
        fl.addRow("Openbox Theme:", self._ob_lbl)
        self.body.addWidget(box)

        acts = QHBoxLayout()
        ap = _make_btn("Apply Appearance", "primary", self)
        ap.clicked.connect(self._apply)
        acts.addWidget(ap)
        mgr = _make_btn("Open Palette Studio", "secondary", self)
        mgr.clicked.connect(lambda: subprocess.Popen([sys.executable, os.path.join(APP_DIR, "vice_theme_manager.py")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        acts.addWidget(mgr)
        acts.addStretch(1)
        self.body.addLayout(acts)
        self.body.addStretch(1)

    def refresh_page(self):
        def _probe():
            gtk_t, icon_t, font_n, ob_t = "Arc-Dark", "Papirus-Dark", "Noto Sans 10", "Vice-Dark"
            if shutil.which("gsettings"):
                ok, o = _run_sync(["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"], timeout=3)
                if ok and o:
                    gtk_t = o.strip("'")
                ok, o = _run_sync(["gsettings", "get", "org.gnome.desktop.interface", "icon-theme"], timeout=3)
                if ok and o:
                    icon_t = o.strip("'")
                ok, o = _run_sync(["gsettings", "get", "org.gnome.desktop.interface", "font-name"], timeout=3)
                if ok and o:
                    font_n = o.strip("'")
            rc = os.path.expanduser("~/.config/openbox/rc.xml")
            if os.path.isfile(rc):
                try:
                    tree = ET.parse(rc)
                    el = tree.getroot().find(".//{http://openbox.org/3.4/rc}theme/{http://openbox.org/3.4/rc}name")
                    if el is not None and el.text:
                        ob_t = el.text.strip()
                except Exception:
                    pass
            return {"gtk": gtk_t, "icon": icon_t, "font": font_n, "ob": ob_t}

        self._run_bg(_probe, self._populate, "Reading GTK & Openbox theme...")

    def _populate(self, data):
        self._gtk_cb.setCurrentText(data["gtk"])
        self._icon_cb.setCurrentText(data["icon"])
        self._font_ed.setText(data["font"])
        self._ob_lbl.setText(data["ob"])
        self.set_status("Theme settings loaded", "ok")

    def _apply(self):
        gtk_t = self._gtk_cb.currentText().strip()
        icon_t = self._icon_cb.currentText().strip()
        font_n = self._font_ed.text().strip()

        def _do():
            if shutil.which("gsettings"):
                _run_sync(["gsettings", "set", "org.gnome.desktop.interface", "gtk-theme", gtk_t], timeout=3)
                _run_sync(["gsettings", "set", "org.gnome.desktop.interface", "icon-theme", icon_t], timeout=3)
                _run_sync(["gsettings", "set", "org.gnome.desktop.interface", "font-name", font_n], timeout=3)
            ini = os.path.expanduser("~/.config/gtk-3.0/settings.ini")
            cp = configparser.ConfigParser(interpolation=None)
            cp.optionxform = str
            if os.path.isfile(ini):
                cp.read(ini, encoding="utf-8")
            if not cp.has_section("Settings"):
                cp.add_section("Settings")
            cp.set("Settings", "gtk-theme-name", gtk_t)
            cp.set("Settings", "gtk-icon-theme-name", icon_t)
            cp.set("Settings", "gtk-font-name", font_n)
            cp.set("Settings", "gtk-application-prefer-dark-theme", "1")
            os.makedirs(os.path.dirname(ini), exist_ok=True)
            with open(ini, "w", encoding="utf-8", newline="\n") as fp:
                cp.write(fp, space_around_delimiters=False)
            if shutil.which("openbox"):
                _run_sync(["openbox", "--reconfigure"], timeout=3)
            return True, "Applied GTK3 & Openbox theme"

        self._run_bg(_do, lambda r: self.set_status(r[1], "ok" if r[0] else "err"), "Applying theme...")


class WallpaperPage(BaseSettingsPage):
    def __init__(self):
        super().__init__(
            "Desktop Wallpaper",
            "Select and apply Leonida coastal dusk backgrounds across PCManFM / nitrogen / feh",
            "WALLPAPER", "peach",
        )
        self._list = QListWidget()
        self._list.setIconSize(QSize(128, 76))
        self._list.setViewMode(QListWidget.IconMode)
        self._list.setResizeMode(QListWidget.Adjust)
        self._list.setSpacing(10)
        self._list.setMinimumHeight(250)
        self._list.itemDoubleClicked.connect(lambda _i: self._apply())
        self.body.addWidget(self._list, 1)

        acts = QHBoxLayout()
        ap = _make_btn("Apply Selected Wallpaper", "primary", self)
        ap.clicked.connect(self._apply)
        acts.addWidget(ap)
        br = _make_btn("Browse Image...", "secondary", self)
        br.clicked.connect(self._browse)
        acts.addWidget(br)
        acts.addStretch(1)
        self.body.addLayout(acts)

    def refresh_page(self):
        def _probe():
            dirs = [
                "/opt/vice-os/wallpapers",
                "/usr/share/backgrounds",
                "/usr/share/wallpapers",
                os.path.expanduser("~/Pictures/Wallpapers"),
                os.path.expanduser("~/Pictures"),
            ]
            imgs = []
            seen = set()
            for d in dirs:
                if not os.path.isdir(d):
                    continue
                for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
                    for p in sorted(glob.glob(os.path.join(d, ext))):
                        if p not in seen:
                            seen.add(p)
                            imgs.append(p)
            return imgs[:60]

        self._run_bg(_probe, self._populate, "Discovering wallpapers...")

    def _populate(self, imgs):
        self._list.clear()
        for p in imgs:
            pm = QPixmap(p)
            ic = QIcon(pm.scaled(128, 76, Qt.KeepAspectRatio, Qt.SmoothTransformation)) if not pm.isNull() else resolve_icon("image-x-generic")
            it = QListWidgetItem(ic, os.path.basename(p))
            it.setData(Qt.UserRole, p)
            it.setToolTip(p)
            self._list.addItem(it)
        self.set_status(f"Found {len(imgs)} wallpaper(s)", "ok")

    def _browse(self):
        p, _ = QFileDialog.getOpenFileName(self, "Choose Wallpaper", os.path.expanduser("~"), "Images (*.png *.jpg *.jpeg *.webp)")
        if p:
            self._apply_path(p)

    def _apply(self):
        it = self._list.currentItem()
        if not it:
            QMessageBox.warning(self, "No Selection", "Select a wallpaper first.")
            return
        self._apply_path(it.data(Qt.UserRole))

    def _apply_path(self, path: str):
        def _do():
            applied = False
            if shutil.which("pcmanfm"):
                ok, _ = _run_sync(["pcmanfm", "--set-wallpaper", path, "--wallpaper-mode=crop"], timeout=4)
                applied = applied or ok
            if shutil.which("nitrogen"):
                ok, _ = _run_sync(["nitrogen", "--set-zoom-fill", "--save", path], timeout=4)
                applied = applied or ok
            if shutil.which("feh"):
                ok, _ = _run_sync(["feh", "--bg-fill", path], timeout=4)
                applied = applied or ok
            return applied, f"Applied {os.path.basename(path)}" if applied else "No wallpaper backend (pcmanfm/nitrogen/feh) active"

        self._run_bg(_do, lambda r: (self.set_status(r[1], "ok" if r[0] else "warn")), "Applying wallpaper...")


class KeyboardPage(BaseSettingsPage):
    def __init__(self):
        super().__init__(
            "Keyboard Layout && Shortcuts",
            "Live X11 keymap layout (setxkbmap), repeat rate (xset), and Openbox shortcuts",
            "XKB", "coral",
        )
        box = QGroupBox("Keyboard Layout & Repeat Rate")
        fl = QFormLayout(box)
        self._layout_cb = QComboBox()
        self._layout_cb.setEditable(True)
        self._layout_cb.addItems(["us", "gb", "id", "de", "fr", "es", "jp", "kr"])
        fl.addRow("Keymap Layout:", self._layout_cb)

        self._delay_spin = QSpinBox()
        self._delay_spin.setRange(150, 1000)
        self._delay_spin.setValue(300)
        self._delay_spin.setSuffix(" ms")
        fl.addRow("Repeat Delay:", self._delay_spin)

        self._rate_spin = QSpinBox()
        self._rate_spin.setRange(10, 80)
        self._rate_spin.setValue(30)
        self._rate_spin.setSuffix(" cps")
        fl.addRow("Repeat Rate:", self._rate_spin)
        self.body.addWidget(box)

        acts = QHBoxLayout()
        ap = _make_btn("Apply Keyboard Settings", "primary", self)
        ap.clicked.connect(self._apply)
        acts.addWidget(ap)
        sc = _make_btn("Edit Shortcuts...", "secondary", self)
        sc.clicked.connect(lambda: subprocess.Popen([sys.executable, os.path.join(APP_DIR, "vice_keyboard_shortcuts.py")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        acts.addWidget(sc)
        acts.addStretch(1)
        self.body.addLayout(acts)

        self._kb_info = QPlainTextEdit()
        self._kb_info.setReadOnly(True)
        self.body.addWidget(self._kb_info, 1)

    def refresh_page(self):
        def _probe():
            layout = "us"
            q_out = ""
            if shutil.which("setxkbmap"):
                ok, q_out = _run_sync(["setxkbmap", "-query"], timeout=3)
                for line in q_out.splitlines() if ok else []:
                    if line.startswith("layout:"):
                        layout = line.split(":", 1)[1].strip()
            return {"layout": layout, "query": q_out or "setxkbmap unavailable"}

        self._run_bg(_probe, self._populate, "Reading XKB keymap...")

    def _populate(self, data):
        self._layout_cb.setCurrentText(data["layout"])
        self._kb_info.setPlainText(data["query"])
        self.set_status(f"Active layout: {data['layout']}", "ok")

    def _apply(self):
        lay = self._layout_cb.currentText().strip()
        d, r = self._delay_spin.value(), self._rate_spin.value()

        def _do():
            ok1 = True
            if shutil.which("setxkbmap") and lay:
                ok1, msg = _run_sync(["setxkbmap", lay], timeout=4)
                if not ok1:
                    return False, msg
            if shutil.which("xset"):
                _run_sync(["xset", "r", "rate", str(d), str(r)], timeout=4)
            return True, f"Applied layout '{lay}' ({d}ms / {r}cps)"

        self._run_bg(_do, lambda res: (self.refresh_page() if res[0] else QMessageBox.warning(self, "Keyboard Error", res[1])), "Applying keyboard settings...")


class MousePage(BaseSettingsPage):
    def __init__(self):
        super().__init__(
            "Mouse && Touchpad",
            "Live libinput/xinput pointer speed, natural scrolling, tap-to-click, and cursor size",
            "XINPUT", "aqua",
        )
        self._devs = []
        box = QGroupBox("Pointer & Touchpad Controls")
        fl = QFormLayout(box)

        self._dev_cb = QComboBox()
        fl.addRow("Input Device:", self._dev_cb)

        sp_row = QHBoxLayout()
        self._speed = QSlider(Qt.Horizontal)
        self._speed.setRange(-10, 10)
        self._speed.setValue(0)
        self._speed_lbl = QLabel("0.0")
        self._speed.valueChanged.connect(lambda v: self._speed_lbl.setText(f"{v / 10.0:.1f}"))
        sp_row.addWidget(self._speed, 1)
        sp_row.addWidget(self._speed_lbl)
        fl.addRow("Acceleration Speed:", sp_row)

        self._tap_cb = QCheckBox("Enable tap-to-click (touchpads)")
        self._nat_cb = QCheckBox("Enable natural scrolling")
        self._left_cb = QCheckBox("Left-handed primary button swap")
        fl.addRow("", self._tap_cb)
        fl.addRow("", self._nat_cb)
        fl.addRow("", self._left_cb)
        self.body.addWidget(box)

        ap = _make_btn("Apply Pointer Settings", "primary", self)
        ap.clicked.connect(self._apply)
        self.body.addWidget(ap, 0, Qt.AlignLeft)
        self.body.addStretch(1)

    def refresh_page(self):
        def _probe():
            devs = []
            if shutil.which("xinput"):
                ok, out = _run_sync(["xinput", "list", "--name-only"], timeout=4)
                for line in out.splitlines() if ok else []:
                    n = line.strip()
                    if n and "virtual core" not in n.lower():
                        devs.append(n)
            return devs

        self._run_bg(_probe, self._populate, "Detecting xinput pointers...")

    def _populate(self, devs):
        self._devs = devs
        self._dev_cb.clear()
        for d in devs:
            self._dev_cb.addItem(d)
        self.set_status(f"Found {len(devs)} xinput device(s)", "ok")

    def _apply(self):
        dev = self._dev_cb.currentText()
        spd = self._speed.value() / 10.0
        tap = 1 if self._tap_cb.isChecked() else 0
        nat = 1 if self._nat_cb.isChecked() else 0
        left = self._left_cb.isChecked()

        def _do():
            if dev and shutil.which("xinput"):
                _run_sync(["xinput", "set-prop", dev, "libinput Accel Speed", str(spd)], timeout=3)
                _run_sync(["xinput", "set-prop", dev, "libinput Tapping Enabled", str(tap)], timeout=3)
                _run_sync(["xinput", "set-prop", dev, "libinput Natural Scrolling Enabled", str(nat)], timeout=3)
                _run_sync(["xinput", "set-button-map", dev] + (["3", "2", "1"] if left else ["1", "2", "3"]), timeout=3)
            if shutil.which("gsettings"):
                _run_sync(["gsettings", "set", "org.gnome.desktop.peripherals.touchpad", "tap-to-click", "true" if tap else "false"], timeout=3)
                _run_sync(["gsettings", "set", "org.gnome.desktop.peripherals.touchpad", "natural-scroll", "true" if nat else "false"], timeout=3)
            return True, f"Applied pointer settings to {dev or 'gsettings'}"

        self._run_bg(_do, lambda r: self.set_status(r[1], "ok" if r[0] else "err"), "Applying pointer settings...")


class AccessibilityPage(BaseSettingsPage):
    def __init__(self):
        super().__init__(
            "Accessibility",
            "Text scaling factor, cursor size, and sticky/slow/bounce keyboard assist",
            "A11Y", "aqua",
        )
        box = QGroupBox("Visual & Keyboard Accessibility")
        fl = QFormLayout(box)
        self._scale_cb = QComboBox()
        for label, val in (("100% (1.0x)", 1.0), ("115% (1.15x)", 1.15), ("125% (1.25x)", 1.25), ("150% (1.5x)", 1.5)):
            self._scale_cb.addItem(label, val)
        fl.addRow("Text Scaling:", self._scale_cb)

        self._cursor_cb = QComboBox()
        for sz in (24, 32, 48, 64):
            self._cursor_cb.addItem(f"{sz} px", sz)
        fl.addRow("Cursor Size:", self._cursor_cb)

        self._sticky_cb = QCheckBox("Enable Sticky Keys")
        self._slow_cb = QCheckBox("Enable Slow Keys")
        self._bounce_cb = QCheckBox("Enable Bounce Keys")
        fl.addRow("", self._sticky_cb)
        fl.addRow("", self._slow_cb)
        fl.addRow("", self._bounce_cb)
        self.body.addWidget(box)

        ap = _make_btn("Apply Accessibility Settings", "primary", self)
        ap.clicked.connect(self._apply)
        self.body.addWidget(ap, 0, Qt.AlignLeft)
        self.body.addStretch(1)

    def refresh_page(self):
        def _probe():
            scale, csize = 1.0, 24
            sticky = slow = bounce = False
            if shutil.which("gsettings"):
                ok, o = _run_sync(["gsettings", "get", "org.gnome.desktop.interface", "text-scaling-factor"], timeout=3)
                if ok:
                    try:
                        scale = float(o.strip())
                    except ValueError:
                        pass
                ok, o = _run_sync(["gsettings", "get", "org.gnome.desktop.interface", "cursor-size"], timeout=3)
                if ok and o.strip().isdigit():
                    csize = int(o.strip())
                sticky = _run_sync(["gsettings", "get", "org.gnome.desktop.a11y.keyboard", "stickykeys-enable"], timeout=3)[1].strip() == "true"
                slow = _run_sync(["gsettings", "get", "org.gnome.desktop.a11y.keyboard", "slowkeys-enable"], timeout=3)[1].strip() == "true"
                bounce = _run_sync(["gsettings", "get", "org.gnome.desktop.a11y.keyboard", "bouncekeys-enable"], timeout=3)[1].strip() == "true"
            return {"scale": scale, "csize": csize, "sticky": sticky, "slow": slow, "bounce": bounce}

        self._run_bg(_probe, self._populate, "Reading accessibility settings...")

    def _populate(self, data):
        idx = self._scale_cb.findData(data["scale"])
        if idx >= 0:
            self._scale_cb.setCurrentIndex(idx)
        cidx = self._cursor_cb.findData(data["csize"])
        if cidx >= 0:
            self._cursor_cb.setCurrentIndex(cidx)
        self._sticky_cb.setChecked(data["sticky"])
        self._slow_cb.setChecked(data["slow"])
        self._bounce_cb.setChecked(data["bounce"])
        self.set_status("Accessibility settings loaded", "ok")

    def _apply(self):
        scale = str(self._scale_cb.currentData())
        csize = str(self._cursor_cb.currentData())
        sticky = "true" if self._sticky_cb.isChecked() else "false"
        slow = "true" if self._slow_cb.isChecked() else "false"
        bounce = "true" if self._bounce_cb.isChecked() else "false"

        def _do():
            if shutil.which("gsettings"):
                _run_sync(["gsettings", "set", "org.gnome.desktop.interface", "text-scaling-factor", scale], timeout=3)
                _run_sync(["gsettings", "set", "org.gnome.desktop.interface", "cursor-size", csize], timeout=3)
                _run_sync(["gsettings", "set", "org.gnome.desktop.a11y.keyboard", "stickykeys-enable", sticky], timeout=3)
                _run_sync(["gsettings", "set", "org.gnome.desktop.a11y.keyboard", "slowkeys-enable", slow], timeout=3)
                _run_sync(["gsettings", "set", "org.gnome.desktop.a11y.keyboard", "bouncekeys-enable", bounce], timeout=3)
            return True, f"Applied scaling {scale}x, cursor {csize}px"

        self._run_bg(_do, lambda r: self.set_status(r[1], "ok"), "Applying accessibility...")


# ==============================================================================
# 20. SECURITY, 21. STARTUP, 22. CLEANUP, 23. SSH, 24. SHARES, 25. CRON, 26. BACKUP
# ==============================================================================


class SecurityPage(BaseSettingsPage):
    def __init__(self):
        super().__init__(
            "System Security && Hardening",
            "Live listening sockets (ss), UFW/AppArmor/chkrootkit posture, and kernel sysctl audit",
            "AUDIT", "coral",
        )
        self._summary = QLabel("Scanning security posture...")
        self._summary.setStyleSheet(f"font-family: {MONO_STACK}; color: {COLORS['accent_aqua']};")
        self._summary.setWordWrap(True)
        self.body.addWidget(self._summary)

        self._ports_tbl = self._make_table(["Proto", "State", "Local Address", "Process"], stretch_col=3)
        self._ports_tbl.setMinimumHeight(200)
        self.body.addWidget(self._ports_tbl, 1)

        acts = QHBoxLayout()
        deck = _make_btn("Open Vice Cyber Deck", "primary", self)
        deck.clicked.connect(lambda: subprocess.Popen([sys.executable, os.path.join(APP_DIR, "vice_tool_cyber_deck.py")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        acts.addWidget(deck)
        acts.addStretch(1)
        self.body.addLayout(acts)

    def refresh_page(self):
        def _probe():
            _, kptr = _run_sync(["sysctl", "-n", "kernel.kptr_restrict"], timeout=3)
            _, dmesg = _run_sync(["sysctl", "-n", "kernel.dmesg_restrict"], timeout=3)
            _, rpf = _run_sync(["sysctl", "-n", "net.ipv4.conf.all.rp_filter"], timeout=3)
            _, chk = _run_sync(["systemctl", "is-active", "chkrootkit.timer"], timeout=3)
            ports = []
            if shutil.which("ss"):
                ok, out = _run_sync(["ss", "-tulnp"], timeout=4)
                for line in out.splitlines()[1:] if ok else []:
                    p = line.split()
                    if len(p) >= 5:
                        ports.append((p[0], p[1], p[4], " ".join(p[6:]) if len(p) > 6 else ""))
            return {"kptr": kptr, "dmesg": dmesg, "rpf": rpf, "chk": chk, "ports": ports}

        self._run_bg(_probe, self._populate, "Auditing listening ports & hardening...")

    def _populate(self, data):
        self._summary.setText(
            f"kptr_restrict={data['kptr']}  |  dmesg_restrict={data['dmesg']}  |  "
            f"rp_filter={data['rpf']}  |  chkrootkit.timer={data['chk']}"
        )
        self._ports_tbl.setRowCount(0)
        for row_v in data["ports"]:
            r = self._ports_tbl.rowCount()
            self._ports_tbl.insertRow(r)
            for c, val in enumerate(row_v):
                self._ports_tbl.setItem(r, c, QTableWidgetItem(val))
        self.set_status(f"Detected {len(data['ports'])} listening socket(s)", "ok")


class StartupPage(BaseSettingsPage):
    USER_DIR = os.path.expanduser("~/.config/autostart")
    SYS_DIR = "/etc/xdg/autostart"

    def __init__(self):
        super().__init__(
            "Startup Applications",
            "Live XDG autostart entries (~/.config/autostart & /etc/xdg/autostart)",
            "AUTOSTART", "aqua",
        )
        self._entries = []
        self._table = self._make_table(["Enabled", "Name", "Command", "Source"], stretch_col=2)
        self._table.setMinimumHeight(240)
        self.body.addWidget(self._table, 1)

        acts = QHBoxLayout()
        add_b = _make_btn("+ Add Startup App", "primary", self)
        add_b.clicked.connect(self._add_entry)
        acts.addWidget(add_b)
        del_b = _make_btn("Delete User Entry", "danger", self)
        del_b.clicked.connect(self._delete_entry)
        acts.addWidget(del_b)
        acts.addStretch(1)
        self.body.addLayout(acts)

    def refresh_page(self):
        def _probe():
            seen = set()
            entries = []
            for d in (self.USER_DIR, self.SYS_DIR):
                if not os.path.isdir(d):
                    continue
                is_sys = os.path.abspath(d) == os.path.abspath(self.SYS_DIR)
                for p in sorted(glob.glob(os.path.join(d, "*.desktop"))):
                    fn = os.path.basename(p)
                    if fn in seen:
                        continue
                    seen.add(fn)
                    name, cmd, enabled = fn[:-8], "", True
                    try:
                        with open(p, encoding="utf-8", errors="replace") as fp:
                            for line in fp:
                                ls = line.strip()
                                if ls.startswith("Name="):
                                    name = ls.split("=", 1)[1]
                                elif ls.startswith("Exec="):
                                    cmd = ls.split("=", 1)[1]
                                elif ls.startswith("X-GNOME-Autostart-enabled="):
                                    enabled = ls.split("=", 1)[1].strip().lower() == "true"
                                elif ls.startswith("Hidden=") and ls.split("=", 1)[1].strip().lower() == "true":
                                    enabled = False
                    except OSError:
                        pass
                    entries.append((p, name, cmd, enabled, "System" if is_sys else "User"))
            return entries

        self._run_bg(_probe, self._populate, "Scanning XDG autostart entries...")

    def _populate(self, entries):
        self._entries = entries
        self._table.setRowCount(0)
        for path, name, cmd, enabled, src in entries:
            r = self._table.rowCount()
            self._table.insertRow(r)
            host = QWidget()
            hl = QHBoxLayout(host)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setAlignment(Qt.AlignCenter)
            cb = QCheckBox()
            cb.setChecked(enabled)
            cb.toggled.connect(lambda on, p=path: self._toggle_entry(p, on))
            hl.addWidget(cb)
            self._table.setCellWidget(r, 0, host)
            self._table.setItem(r, 1, QTableWidgetItem(name))
            self._table.setItem(r, 2, QTableWidgetItem(cmd))
            self._table.setItem(r, 3, QTableWidgetItem(src))
        self.set_status(f"{len(entries)} autostart item(s)", "ok")

    def _toggle_entry(self, path: str, enabled: bool):
        target = path
        if os.path.dirname(os.path.abspath(path)) == os.path.abspath(self.SYS_DIR):
            os.makedirs(self.USER_DIR, exist_ok=True)
            target = os.path.join(self.USER_DIR, os.path.basename(path))
            if not os.path.exists(target):
                shutil.copy2(path, target)
        try:
            lines = open(target, encoding="utf-8", errors="replace").readlines()
            out_lines, found = [], False
            for ln in lines:
                if ln.strip().startswith("X-GNOME-Autostart-enabled="):
                    out_lines.append(f"X-GNOME-Autostart-enabled={'true' if enabled else 'false'}\n")
                    found = True
                elif ln.strip().startswith("Hidden="):
                    out_lines.append(f"Hidden={'false' if enabled else 'true'}\n")
                else:
                    out_lines.append(ln)
            if not found:
                out_lines.append(f"X-GNOME-Autostart-enabled={'true' if enabled else 'false'}\n")
            with open(target, "w", encoding="utf-8", newline="\n") as fp:
                fp.writelines(out_lines)
            self.set_status(f"{'Enabled' if enabled else 'Disabled'} {os.path.basename(target)}", "ok")
        except OSError as exc:
            QMessageBox.warning(self, "Error", str(exc))

    def _add_entry(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Add Startup App")
        fl = QFormLayout(dlg)
        nm = QLineEdit(dlg)
        cmd = QLineEdit(dlg)
        fl.addRow("Name:", nm)
        fl.addRow("Command:", cmd)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        fl.addRow(btns)
        if dlg.exec_() != QDialog.Accepted or not nm.text().strip() or not cmd.text().strip():
            return
        slug = re.sub(r"[^a-z0-9_-]+", "-", nm.text().strip().lower()).strip("-") or "custom"
        os.makedirs(self.USER_DIR, exist_ok=True)
        dest = os.path.join(self.USER_DIR, f"{slug}.desktop")
        with open(dest, "w", encoding="utf-8", newline="\n") as fp:
            fp.write(f"[Desktop Entry]\nType=Application\nName={nm.text().strip()}\nExec={cmd.text().strip()}\nX-GNOME-Autostart-enabled=true\n")
        self.refresh_page()

    def _delete_entry(self):
        row = self._table.currentRow()
        if row < 0 or row >= len(self._entries):
            return
        path, name, _, _, src = self._entries[row]
        if src == "System" and not path.startswith(self.USER_DIR):
            QMessageBox.information(self, "System Entry", "Uncheck system entries to disable them via user override.")
            return
        if os.path.isfile(path):
            os.remove(path)
            self.refresh_page()


class CleanupPage(BaseSettingsPage):
    def __init__(self):
        super().__init__(
            "System Cleanup",
            "Inspect and reclaim disk space from APT archives, systemd journal, thumbnails, and Trash",
            "CLEANUP", "peach",
        )
        self._cbs = {}
        box = QGroupBox("Cleanup Targets")
        bl = QVBoxLayout(box)
        for key, label in (
            ("thumbs", "Thumbnail Cache (~/.cache/thumbnails)"),
            ("trash", "User Trash (~/.local/share/Trash)"),
            ("apt", "APT Package Cache (/var/cache/apt/archives — pkexec)"),
            ("journal", "Systemd Journal Logs >7 days (journalctl --vacuum-time=7d — pkexec)"),
        ):
            cb = QCheckBox(label)
            cb.setChecked(key in ("thumbs", "trash"))
            self._cbs[key] = cb
            bl.addWidget(cb)
        self.body.addWidget(box)

        self._info = QPlainTextEdit()
        self._info.setReadOnly(True)
        self.body.addWidget(self._info, 1)

        btn = _make_btn("Clean Selected Targets", "primary", self)
        btn.clicked.connect(self._clean)
        self.body.addWidget(btn, 0, Qt.AlignLeft)

    @staticmethod
    def _dir_size_mb(path: str) -> float:
        total = 0
        if not os.path.isdir(path):
            return 0.0
        for root, _dirs, files in os.walk(path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
        return total / (1024 * 1024)

    def refresh_page(self):
        def _probe():
            th = self._dir_size_mb(os.path.expanduser("~/.cache/thumbnails"))
            tr = self._dir_size_mb(os.path.expanduser("~/.local/share/Trash"))
            ap = self._dir_size_mb("/var/cache/apt/archives")
            _, jr = _run_sync(["journalctl", "--disk-usage"], timeout=4)
            return f"Thumbnails: {th:.1f} MB\nTrash: {tr:.1f} MB\nAPT Archives: {ap:.1f} MB\nJournal: {jr or 'N/A'}"

        self._run_bg(_probe, lambda txt: (self._info.setPlainText(txt), self.set_status("Disk reclaim report updated", "ok")), "Calculating cache sizes...")

    def _clean(self):
        selected = [k for k, cb in self._cbs.items() if cb.isChecked()]
        if not selected:
            return

        def _do():
            log = []
            if "thumbs" in selected:
                p = os.path.expanduser("~/.cache/thumbnails")
                if os.path.isdir(p):
                    shutil.rmtree(p, ignore_errors=True)
                    os.makedirs(p, exist_ok=True)
                    log.append("Cleared thumbnails")
            if "trash" in selected:
                for sub in ("files", "info"):
                    p = os.path.expanduser(f"~/.local/share/Trash/{sub}")
                    if os.path.isdir(p):
                        shutil.rmtree(p, ignore_errors=True)
                        os.makedirs(p, exist_ok=True)
                log.append("Emptied Trash")
            if "apt" in selected:
                ok, out = _run_sync(_priv_cmd(["apt-get", "clean"]), timeout=20)
                log.append(f"apt-get clean: {'OK' if ok else out}")
            if "journal" in selected:
                ok, out = _run_sync(_priv_cmd(["journalctl", "--vacuum-time=7d"]), timeout=20)
                log.append(f"journal vacuum: {'OK' if ok else out}")
            return "\n".join(log)

        self._run_bg(_do, lambda txt: (self._info.appendPlainText("\n--- Cleanup ---\n" + txt), self.refresh_page()), "Cleaning selected targets...")


class SSHPage(BaseSettingsPage):
    def __init__(self):
        super().__init__(
            "OpenSSH Server && Keys",
            "Live sshd service toggle, ~/.ssh public key management, and Ed25519 key generation",
            "SSH", "aqua",
        )
        top = QHBoxLayout()
        self._svc_badge = make_badge("SSH: --", "neutral", self)
        top.addWidget(self._svc_badge)
        self._svc_btn = _make_btn("Toggle SSH Server", "secondary", self)
        self._svc_btn.clicked.connect(self._toggle_ssh)
        top.addWidget(self._svc_btn)
        gen_b = _make_btn("Generate Ed25519 Key", "primary", self)
        gen_b.clicked.connect(self._gen_key)
        top.addWidget(gen_b)
        top.addStretch(1)
        self.body.addLayout(top)

        self._keys_list = QListWidget()
        self._keys_list.currentTextChanged.connect(self._show_pub)
        self.body.addWidget(self._keys_list)

        self._pub_view = QPlainTextEdit()
        self._pub_view.setReadOnly(True)
        self._pub_view.setMaximumHeight(120)
        self.body.addWidget(self._pub_view, 1)

    def refresh_page(self):
        def _probe():
            ok, out = _run_sync(["systemctl", "is-active", "ssh"], timeout=3)
            if not ok:
                ok, out = _run_sync(["systemctl", "is-active", "sshd"], timeout=3)
            keys = sorted(glob.glob(os.path.expanduser("~/.ssh/*.pub")))
            return {"active": ok and out.strip() == "active", "keys": keys}

        self._run_bg(_probe, self._populate, "Checking SSH service & keys...")

    def _populate(self, data):
        act = data["active"]
        self._svc_badge.setText("SSH SERVER: ACTIVE" if act else "SSH SERVER: INACTIVE")
        style_badge(self._svc_badge, "success" if act else "neutral")
        self._keys_list.clear()
        for k in data["keys"]:
            self._keys_list.addItem(k)
        self.set_status(f"Found {len(data['keys'])} SSH public key(s)", "ok")

    def _show_pub(self, path: str):
        if path and os.path.isfile(path):
            try:
                self._pub_view.setPlainText(open(path, encoding="utf-8", errors="replace").read().strip())
            except OSError:
                pass

    def _toggle_ssh(self):
        act = "stop" if "ACTIVE" in self._svc_badge.text() and "INACTIVE" not in self._svc_badge.text() else "start"
        self._run_cmd_bg(_priv_cmd(["systemctl", act, "ssh"]), lambda ok, out: (self.refresh_page() if ok else QMessageBox.warning(self, "SSH Error", out)), f"{act.title()}ing ssh.service...")

    def _gen_key(self):
        ssh_dir = os.path.expanduser("~/.ssh")
        os.makedirs(ssh_dir, mode=0o700, exist_ok=True)
        dest = os.path.join(ssh_dir, "id_ed25519")
        if os.path.exists(dest):
            QMessageBox.information(self, "Key Exists", f"{dest} already exists.")
            return
        self._run_cmd_bg(["ssh-keygen", "-t", "ed25519", "-f", dest, "-N", "", "-q"], lambda ok, out: (self.refresh_page() if ok else QMessageBox.warning(self, "ssh-keygen Failed", out)), "Generating Ed25519 key...")


class NetworkSharesPage(BaseSettingsPage):
    def __init__(self):
        super().__init__(
            "Network Shares (SMB / NFS)",
            "View mounted SMB/CIFS & NFS shares and mount/unmount remote folders",
            "CIFS / NFS", "peach",
        )
        self._table = self._make_table(["Source Share", "Mountpoint", "Type", "Options"], stretch_col=0)
        self._table.setMinimumHeight(180)
        self.body.addWidget(self._table, 1)

        form_box = QGroupBox("Mount Remote Share")
        fl = QHBoxLayout(form_box)
        self._type_cb = QComboBox()
        self._type_cb.addItems(["cifs", "nfs"])
        fl.addWidget(self._type_cb)
        self._src_ed = QLineEdit()
        self._src_ed.setPlaceholderText("//server/share or server:/export")
        fl.addWidget(self._src_ed, 1)
        self._mp_ed = QLineEdit()
        self._mp_ed.setPlaceholderText("/mnt/shares/myshare")
        fl.addWidget(self._mp_ed, 1)
        m_b = _make_btn("Mount (pkexec)", "primary", form_box)
        m_b.clicked.connect(self._mount)
        fl.addWidget(m_b)
        u_b = _make_btn("Unmount Selected", "danger", form_box)
        u_b.clicked.connect(self._unmount)
        fl.addWidget(u_b)
        self.body.addWidget(form_box)

    def refresh_page(self):
        def _probe():
            ok, out = _run_sync(["mount", "-t", "cifs,nfs,nfs4"], timeout=4)
            rows = []
            for line in out.splitlines() if ok else []:
                m = re.match(r"^(\S+)\s+on\s+(\S+)\s+type\s+(\S+)\s+\(([^)]+)\)", line)
                if m:
                    rows.append((m.group(1), m.group(2), m.group(3), m.group(4)))
            return rows

        self._run_bg(_probe, self._populate, "Listing mounted SMB/NFS shares...")

    def _populate(self, rows):
        self._table.setRowCount(0)
        for vals in rows:
            r = self._table.rowCount()
            self._table.insertRow(r)
            for c, v in enumerate(vals):
                self._table.setItem(r, c, QTableWidgetItem(v))
        self.set_status(f"{len(rows)} mounted network share(s)", "ok")

    def _mount(self):
        src = self._src_ed.text().strip()
        mp = self._mp_ed.text().strip() or "/mnt/shares/share"
        fstype = self._type_cb.currentText()
        if not src:
            QMessageBox.warning(self, "Missing Source", "Enter //host/share or host:/path.")
            return
        cmd = _priv_cmd(["bash", "-c", f"mkdir -p {shlex.quote(mp)} && mount -t {fstype} {shlex.quote(src)} {shlex.quote(mp)}"])
        self._run_cmd_bg(cmd, lambda ok, out: (self.refresh_page() if ok else QMessageBox.warning(self, "Mount Failed", out)), f"Mounting {src}...")

    def _unmount(self):
        row = self._table.currentRow()
        if row < 0:
            return
        mp = self._table.item(row, 1).text()
        self._run_cmd_bg(_priv_cmd(["umount", mp]), lambda ok, out: (self.refresh_page() if ok else QMessageBox.warning(self, "Unmount Failed", out)), f"Unmounting {mp}...")


class CronPage(BaseSettingsPage):
    def __init__(self):
        super().__init__(
            "Scheduled Cron Jobs",
            "Live user crontab editor (crontab -l / crontab -) with visual schedule add/delete",
            "CRON", "coral",
        )
        self._table = self._make_table(["Schedule", "Command"], stretch_col=1)
        self._table.setMinimumHeight(180)
        self.body.addWidget(self._table, 1)

        add_box = QGroupBox("Add User Cron Job")
        al = QHBoxLayout(add_box)
        self._sched_ed = QLineEdit("0 * * * *")
        self._sched_ed.setFixedWidth(130)
        al.addWidget(self._sched_ed)
        self._cmd_ed = QLineEdit()
        self._cmd_ed.setPlaceholderText("Command (e.g. /usr/local/bin/backup.sh)")
        al.addWidget(self._cmd_ed, 1)
        add_b = _make_btn("Add Job", "primary", add_box)
        add_b.clicked.connect(self._add_job)
        al.addWidget(add_b)
        del_b = _make_btn("Delete Selected", "danger", add_box)
        del_b.clicked.connect(self._del_job)
        al.addWidget(del_b)
        self.body.addWidget(add_box)

    def refresh_page(self):
        def _probe():
            if not shutil.which("crontab"):
                return {"ok": False, "jobs": [], "err": "crontab not installed"}
            ok, out = _run_sync(["crontab", "-l"], timeout=4)
            jobs = []
            for line in out.splitlines():
                ls = line.strip()
                if not ls or ls.startswith("#"):
                    continue
                if ls.startswith("@"):
                    p = ls.split(None, 1)
                    if len(p) == 2:
                        jobs.append((p[0], p[1]))
                else:
                    p = ls.split(None, 5)
                    if len(p) == 6:
                        jobs.append((" ".join(p[:5]), p[5]))
            return {"ok": True, "jobs": jobs}

        self._run_bg(_probe, self._populate, "Reading user crontab...")

    def _populate(self, data):
        self._table.setRowCount(0)
        for sched, cmd in data["jobs"]:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setItem(r, 0, QTableWidgetItem(sched))
            self._table.setItem(r, 1, QTableWidgetItem(cmd))
        self.set_status(f"{len(data['jobs'])} cron job(s) active", "ok")

    def _save_table(self):
        lines = []
        for r in range(self._table.rowCount()):
            lines.append(f"{self._table.item(r, 0).text()} {self._table.item(r, 1).text()}")
        payload = ("\n".join(lines) + "\n") if lines else ""
        ok, err = _run_sync(["crontab", "-"], timeout=4, input_data=payload)
        if ok:
            self.set_status("Crontab updated", "ok")
        else:
            QMessageBox.warning(self, "Crontab Error", err)

    def _add_job(self):
        sched = self._sched_ed.text().strip()
        cmd = self._cmd_ed.text().strip()
        if not sched or not cmd:
            return
        r = self._table.rowCount()
        self._table.insertRow(r)
        self._table.setItem(r, 0, QTableWidgetItem(sched))
        self._table.setItem(r, 1, QTableWidgetItem(cmd))
        self._cmd_ed.clear()
        self._save_table()

    def _del_job(self):
        row = self._table.currentRow()
        if row >= 0:
            self._table.removeRow(row)
            self._save_table()


class BackupPage(BaseSettingsPage):
    def __init__(self):
        super().__init__(
            "Backup && Snapshots",
            "Create compressed tar archives of home directories and manage Timeshift snapshots",
            "BACKUP", "aqua",
        )
        box = QGroupBox("Quick Archive Backup (tar.gz)")
        fl = QFormLayout(box)
        self._src_ed = QLineEdit(os.path.expanduser("~/Documents"))
        self._dst_ed = QLineEdit(os.path.expanduser("~/backups"))
        fl.addRow("Source Folder:", self._src_ed)
        fl.addRow("Backup Destination:", self._dst_ed)
        self.body.addWidget(box)

        acts = QHBoxLayout()
        run_b = _make_btn("Create Archive Now", "primary", self)
        run_b.clicked.connect(self._run_backup)
        acts.addWidget(run_b)
        ts_b = _make_btn("Create Timeshift Snapshot (pkexec)", "secondary", self)
        ts_b.clicked.connect(self._run_timeshift)
        acts.addWidget(ts_b)
        acts.addStretch(1)
        self.body.addLayout(acts)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self.body.addWidget(self._log, 1)

    def refresh_page(self):
        def _probe():
            bdir = os.path.expanduser("~/backups")
            archives = sorted(glob.glob(os.path.join(bdir, "*.tar.gz"))) if os.path.isdir(bdir) else []
            ts = "Timeshift not installed"
            if shutil.which("timeshift"):
                _, ts = _run_sync(["timeshift", "--list"], timeout=6)
            return f"Local archives in {bdir}: {len(archives)}\n" + "\n".join(archives[-8:]) + f"\n\n=== Timeshift ===\n{ts}"

        self._run_bg(_probe, lambda txt: (self._log.setPlainText(txt), self.set_status("Backup inventory loaded", "ok")), "Checking backups & Timeshift...")

    def _run_backup(self):
        src = os.path.expanduser(self._src_ed.text().strip())
        dst = os.path.expanduser(self._dst_ed.text().strip())
        if not os.path.isdir(src):
            QMessageBox.warning(self, "Missing Source", f"Folder not found: {src}")
            return
        os.makedirs(dst, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        out_tgz = os.path.join(dst, f"vice-backup-{stamp}.tar.gz")
        self._run_cmd_bg(["tar", "-czf", out_tgz, "-C", os.path.dirname(src), os.path.basename(src)], lambda ok, out: (self.refresh_page() if ok else QMessageBox.warning(self, "Backup Failed", out)), f"Archiving {src}...", timeout=120)

    def _run_timeshift(self):
        if not shutil.which("timeshift"):
            QMessageBox.information(self, "Timeshift Unavailable", "Timeshift is not installed; use tar archive backup above.")
            return
        self._run_cmd_bg(_priv_cmd(["timeshift", "--create", "--comments", "Vice OS Settings Snapshot"]), lambda ok, out: (self.refresh_page() if ok else QMessageBox.warning(self, "Timeshift Failed", out)), "Creating Timeshift snapshot...", timeout=180)


INLINE_PAGE_CLASSES = {
    "Display": DisplayPage,
    "Sound": SoundPage,
    "Network": NetworkPage,
    "Users": UsersPage,
    "Power": PowerPage,
    "Firewall": FirewallPage,
    "Printers": PrintersPage,
    "Date & Time": DateTimePage,
    "Accessibility": AccessibilityPage,
    "Storage": StoragePage,
    "Updates": UpdatesPage,
    "Bluetooth": BluetoothPage,
    "Security": SecurityPage,
    "Theme": ThemePage,
    "Keyboard": KeyboardPage,
    "Mouse": MousePage,
    "Wallpaper": WallpaperPage,
    "Startup": StartupPage,
    "Cleanup": CleanupPage,
    "Kernel": KernelPage,
    "VPN": VPNPage,
    "SSH": SSHPage,
    "Network Shares": NetworkSharesPage,
    "Cron": CronPage,
    "Backup": BackupPage,
    "USB": USBPage,
}
