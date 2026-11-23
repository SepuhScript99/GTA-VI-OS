#!/usr/bin/env python3
"""Vice OS — Screen Recorder. ffmpeg-based fullscreen/window capture with audio."""

import datetime
import os
import re
import subprocess
import sys

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPlainTextEdit, QProgressBar, QSpinBox,
    QVBoxLayout, QWidget,
)

sys.path.insert(0, '/opt/vice-os/lib')

from python.vice_utils import log_info  # noqa: E402
import vice_theme as vt  # noqa: E402

WINDOW_WIDTH = 720
WINDOW_HEIGHT = 560
SAVE_DIR = os.path.expanduser("~/Videos/Recordings")


def get_display_size():
    """Query display size via xdpyinfo or xrandr; fallback 1920x1080."""
    try:
        out = subprocess.check_output(["xdpyinfo"], text=True, timeout=3)
        for line in out.splitlines():
            if line.startswith("dimensions:"):
                dims = line.split()[1]
                return dims.split("x")[0], dims.split("x")[1]
    except Exception:
        pass
    try:
        out = subprocess.check_output(["xrandr", "--current"], text=True, timeout=3)
        for line in out.splitlines():
            if "*" in line:
                res = line.strip().split()[0]
                if "x" in res:
                    w, h = res.split("x", 1)
                    return w, h
    except Exception:
        pass
    return "1920", "1080"


def get_active_window_geometry():
    """Return (x, y, w, h) of focused X11 window via xdotool, or None."""
    try:
        wid = subprocess.check_output(["xdotool", "getactivewindow"], text=True, timeout=2).strip()
        geo = subprocess.check_output(["xdotool", "getwindowgeometry", wid], text=True, timeout=2)
        pos_m = re.search(r"Position:\s*(-?\d+),(-?\d+)", geo)
        geo_m = re.search(r"Geometry:\s*(\d+)x(\d+)", geo)
        if pos_m and geo_m:
            w = max(2, int(geo_m.group(1)) & ~1)
            h = max(2, int(geo_m.group(2)) & ~1)
            x = max(0, int(pos_m.group(1)))
            y = max(0, int(pos_m.group(2)))
            return x, y, w, h
    except Exception:
        pass
    return None


def get_audio_source():
    """Detect PulseAudio/PipeWire monitor source name for desktop audio capture."""
    try:
        r = subprocess.run(["pactl", "get-default-sink"], capture_output=True, text=True, timeout=3)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip() + ".monitor"
    except Exception:
        pass
    return None


class RecordWorker(QThread):
    line = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self, cmd, parent=None):
        super().__init__(parent)
        self._cmd = list(cmd)
        self._proc = None

    def run(self):
        try:
            self._proc = subprocess.Popen(
                self._cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            if self._proc.stdout:
                for line in self._proc.stdout:
                    self.line.emit(line.rstrip())
            rc = self._proc.wait()
            self.finished.emit(rc == 0)
        except Exception as e:
            self.line.emit(f"Error: {e}")
            self.finished.emit(False)

    def stop(self):
        if self._proc is not None and self._proc.poll() is None:
            try:
                if self._proc.stdin:
                    self._proc.stdin.write("q")
                    self._proc.stdin.flush()
            except Exception:
                try:
                    self._proc.terminate()
                except OSError:
                    pass


class ScreenRecorder(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Screen Recorder")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(640, 480)
        vt.apply_app_theme(self)
        self._worker = None
        self._recording = False
        self._output_path = None
        os.makedirs(SAVE_DIR, exist_ok=True)
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)

        root.addWidget(vt.make_header(
            "Screen Recorder",
            "Record fullscreen, active window or custom region via ffmpeg + PipeWire",
            icon_name="media-record",
            badge_text="REC",
            badge_variant="coral",
            parent=self,
        ))

        src_box = QGroupBox("Capture Source")
        sl = QHBoxLayout(src_box)

        sl.addWidget(QLabel("Source:"))
        self._source_combo = QComboBox()
        self._source_combo.addItems(["Fullscreen", "Window (active)", "Region (manual x,y,w,h)"])
        self._source_combo.currentTextChanged.connect(self._source_changed)
        sl.addWidget(self._source_combo)

        sl.addWidget(QLabel("Region:"))
        self._region_edit = QLineEdit("0,0,1920,1080")
        self._region_edit.setToolTip("x,y,width,height — used in Region mode")
        self._region_edit.setFixedWidth(150)
        self._region_edit.setEnabled(False)
        sl.addWidget(self._region_edit)
        root.addWidget(src_box)

        out_box = QGroupBox("Output")
        ol = QHBoxLayout(out_box)

        ol.addWidget(QLabel("Format:"))
        self._format_combo = QComboBox()
        self._format_combo.addItems(["mkv", "mp4", "webm"])
        ol.addWidget(self._format_combo)

        ol.addWidget(QLabel("FPS:"))
        self._fps_spin = QSpinBox()
        self._fps_spin.setRange(10, 60)
        self._fps_spin.setValue(30)
        ol.addWidget(self._fps_spin)

        self._audio_cb = QCheckBox("Record audio")
        self._audio_cb.setChecked(True)
        ol.addWidget(self._audio_cb)
        root.addWidget(out_box)

        qual_box = QGroupBox("Quality")
        ql = QHBoxLayout(qual_box)
        ql.addWidget(QLabel("Preset:"))
        self._preset_combo = QComboBox()
        self._preset_combo.addItems(["ultrafast", "superfast", "veryfast", "fast", "medium"])
        self._preset_combo.setCurrentText("veryfast")
        ql.addWidget(self._preset_combo)
        ql.addStretch()
        root.addWidget(qual_box)

        rec_row = QHBoxLayout()
        self._rec_btn = vt.make_button("Start Recording", "danger", parent=self)
        self._rec_btn.clicked.connect(self._toggle_recording)
        rec_row.addWidget(self._rec_btn)

        open_dir_btn = vt.make_button("Open Save Folder", "secondary", parent=self)
        open_dir_btn.clicked.connect(
            lambda: subprocess.Popen(["xdg-open", SAVE_DIR], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        )
        rec_row.addWidget(open_dir_btn)
        rec_row.addStretch()

        self._rec_label = QLabel("IDLE")
        self._rec_label.setFont(QFont("monospace", 12, QFont.Bold))
        self._rec_label.setStyleSheet(f"color: {vt.COLORS['accent_aqua']};")
        rec_row.addWidget(self._rec_label)
        root.addLayout(rec_row)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        root.addWidget(self._log)

        self._status = QLabel(f"Output directory: {SAVE_DIR}")
        self._status.setStyleSheet(f"color: {vt.COLORS['text_secondary']}; font-size: 11px;")
        root.addWidget(self._status)

    def _source_changed(self, source):
        if source.startswith("Region"):
            w, h = get_display_size()
            self._region_edit.setText(f"0,0,{w},{h}")
            self._region_edit.setEnabled(True)
        else:
            self._region_edit.setEnabled(False)

    def _build_cmd(self):
        fmt = self._format_combo.currentText()
        fps = self._fps_spin.value()
        preset = self._preset_combo.currentText()
        source = self._source_combo.currentText()
        with_audio = self._audio_cb.isChecked()

        os.makedirs(SAVE_DIR, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self._output_path = os.path.join(SAVE_DIR, f"vice_rec_{ts}.{fmt}")

        video_codec = "libx264" if fmt != "webm" else "libvpx"
        audio_codec = "aac" if fmt != "webm" else "libvorbis"

        cmd = ["ffmpeg", "-y", "-f", "x11grab", "-framerate", str(fps)]
        disp = os.environ.get("DISPLAY", ":0")

        if source.startswith("Fullscreen"):
            w, h = get_display_size()
            cmd += ["-video_size", f"{w}x{h}", "-i", disp]
        elif source.startswith("Window"):
            geom = get_active_window_geometry()
            if geom:
                x, y, w, h = geom
                cmd += ["-video_size", f"{w}x{h}", "-i", f"{disp}+{x},{y}"]
            else:
                w, h = get_display_size()
                cmd += ["-video_size", f"{w}x{h}", "-i", disp]
        else:
            try:
                x, y, w, h = [int(v.strip()) for v in self._region_edit.text().split(",")]
            except ValueError as e:
                raise ValueError("Region must be x,y,width,height (integers)") from e
            cmd += ["-video_size", f"{w}x{h}", "-i", f"{disp}+{x},{y}"]

        if with_audio:
            audio_src = get_audio_source() or "default"
            cmd += ["-f", "pulse", "-i", audio_src]

        cmd += ["-c:v", video_codec, "-preset", preset, "-pix_fmt", "yuv420p"]
        if with_audio:
            cmd += ["-c:a", audio_codec]
        cmd += [self._output_path]
        return cmd

    def _toggle_recording(self):
        if self._recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        try:
            cmd = self._build_cmd()
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Settings", str(e))
            return

        self._log.clear()
        self._log.appendPlainText("$ " + " ".join(cmd))
        self._recording = True
        self._rec_btn.setText("Stop Recording")
        self._rec_label.setText("RECORDING")
        self._rec_label.setStyleSheet(f"color: {vt.COLORS['danger']};")
        self._progress.setVisible(True)
        self._source_combo.setEnabled(False)
        self._format_combo.setEnabled(False)

        self._worker = RecordWorker(cmd, parent=self)
        self._worker.line.connect(self._log.appendPlainText)
        self._worker.finished.connect(self._rec_done)
        self._worker.start()
        log_info(f"Recording started: {self._output_path}")

    def _stop_recording(self):
        if self._worker is not None:
            self._worker.stop()
        self._rec_btn.setText("Stopping...")
        self._rec_btn.setEnabled(False)

    def _rec_done(self, ok):
        self._recording = False
        self._rec_btn.setText("Start Recording")
        self._rec_btn.setEnabled(True)
        self._rec_label.setText("IDLE")
        self._rec_label.setStyleSheet(f"color: {vt.COLORS['accent_aqua']};")
        self._progress.setVisible(False)
        self._source_combo.setEnabled(True)
        self._format_combo.setEnabled(True)

        if ok and self._output_path and os.path.exists(self._output_path):
            size = os.path.getsize(self._output_path) // (1024 * 1024)
            self._log.appendPlainText(f"[OK] Saved: {self._output_path} ({size} MB)")
            self._status.setText(f"Saved: {self._output_path} ({size} MB)")
            log_info(f"Recording saved: {self._output_path}")
        else:
            self._log.appendPlainText("[WARN] ffmpeg exited non-zero; file may be incomplete")
            self._status.setText("Recording stopped (check log)")

    def closeEvent(self, event):
        if self._worker is not None and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(3000)
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    win = ScreenRecorder()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
