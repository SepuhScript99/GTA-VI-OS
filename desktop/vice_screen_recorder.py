#!/usr/bin/env python3
"""Vice OS — Screen Recorder. ffmpeg-based fullscreen/window capture with audio."""

import sys
import os
import subprocess
import datetime

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QComboBox, QSpinBox, QLineEdit, QGroupBox, QFileDialog, QMessageBox,
    QProgressBar, QPlainTextEdit, QCheckBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 720
WINDOW_HEIGHT = 560
SAVE_DIR = os.path.expanduser("~/Videos/Recordings")

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 6px 16px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QPushButton#recBtn { border-color: #ff4444; color: #ff4444; font-weight: bold; }
QPushButton#recBtn:hover { background: #ff4444; color: #0a0a0a; }
QComboBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 4px; }
QSpinBox { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 3px; }
QLineEdit { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 5px; }
QGroupBox { border: 1px solid #00ffff; margin-top: 10px; padding: 8px; }
QGroupBox::title { color: #ff00ff; subcontrol-origin: margin; left: 8px; }
QCheckBox { color: #00ffff; }
QCheckBox::indicator { width: 14px; height: 14px; background: #1a1a1a; border: 1px solid #00ffff; }
QCheckBox::indicator:checked { background: #00ffff; }
QPlainTextEdit { background: #0d0d0d; color: #aaffff; border: 1px solid #1a4a4a; font-size: 11px; }
QProgressBar { border: 1px solid #00ffff; background: #1a1a1a; text-align: center; color: #00ffff; }
QProgressBar::chunk { background: #ff4444; }
QLabel { color: #00ffff; }
"""


def get_display_size():
    """Query display size via xdotool/xdpyinfo; fallback 1920x1080."""
    try:
        out = subprocess.check_output(["xdpyinfo"], text=True, timeout=3)
        for line in out.splitlines():
            if line.startswith("dimensions:"):
                dims = line.split()[1]
                return dims.split("x")[0], dims.split("x")[1]
    except Exception:
        pass
    return "1920", "1080"


def get_audio_source():
    """Detect PulseAudio source name for capture."""
    try:
        r = subprocess.run(["pactl", "get-default-source"], capture_output=True, text=True, timeout=3)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip() + ".monitor"
    except Exception:
        pass
    return None


class RecordWorker(QThread):
    line = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self, cmd):
        super().__init__()
        self._cmd = cmd
        self._proc = None

    def run(self):
        self._proc = subprocess.Popen(
            self._cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        for line in self._proc.stdout:
            self.line.emit(line.rstrip())
        self._proc.wait()
        self.finished.emit(self._proc.returncode == 0)

    def stop(self):
        if self._proc and self._proc.poll() is None:
            # Send 'q' to stdin for clean ffmpeg shutdown (finalizes container)
            try:
                self._proc.stdin.write("q")
                self._proc.stdin.flush()
            except Exception:
                self._proc.terminate()


class ScreenRecorder(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Screen Recorder")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._worker = None
        self._recording = False
        self._output_path = None
        os.makedirs(SAVE_DIR, exist_ok=True)
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Screen Recorder")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 14, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 6px;")
        root.addWidget(title)

        # Source settings
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
        sl.addWidget(self._region_edit)
        root.addWidget(src_box)

        # Output settings
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

        # Quality settings
        qual_box = QGroupBox("Quality")
        ql = QHBoxLayout(qual_box)
        ql.addWidget(QLabel("Preset:"))
        self._preset_combo = QComboBox()
        self._preset_combo.addItems(["ultrafast", "superfast", "veryfast", "fast", "medium"])
        self._preset_combo.setCurrentText("veryfast")
        ql.addWidget(self._preset_combo)
        ql.addStretch()
        root.addWidget(qual_box)

        # Record button + status
        rec_row = QHBoxLayout()
        self._rec_btn = QPushButton("● Start Recording")
        self._rec_btn.setObjectName("recBtn")
        self._rec_btn.clicked.connect(self._toggle_recording)
        rec_row.addWidget(self._rec_btn)

        open_dir_btn = QPushButton("Open Save Folder")
        open_dir_btn.clicked.connect(lambda: subprocess.Popen(["xdg-open", SAVE_DIR]))
        rec_row.addWidget(open_dir_btn)
        rec_row.addStretch()

        self._rec_label = QLabel("IDLE")
        self._rec_label.setFont(QFont("monospace", 12, QFont.Bold))
        rec_row.addWidget(self._rec_label)
        root.addLayout(rec_row)

        # Progress (indeterminate while recording)
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        # Log
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        root.addWidget(self._log)

        self._status = QLabel(f"Output directory: {SAVE_DIR}")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
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

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self._output_path = os.path.join(SAVE_DIR, f"vice_rec_{ts}.{fmt}")

        video_codec = "libx264" if fmt != "webm" else "libvpx"
        audio_codec = "aac" if fmt != "webm" else "libvorbis"

        cmd = ["ffmpeg", "-y", "-f", "x11grab",
               "-framerate", str(fps)]

        if source.startswith("Fullscreen"):
            w, h = get_display_size()
            cmd += ["-video_size", f"{w}x{h}", "-i", os.environ.get("DISPLAY", ":0")]
        elif source.startswith("Window"):
            cmd += ["-i", os.environ.get("DISPLAY", ":0") + "+0,0"]
        else:  # Region
            try:
                x, y, w, h = [int(v.strip()) for v in self._region_edit.text().split(",")]
            except ValueError:
                raise ValueError("Region must be x,y,width,height (integers)")
            cmd += ["-video_size", f"{w}x{h}", "-i",
                    f"{os.environ.get('DISPLAY', ':0')}+{x},{y}"]

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
        self._rec_btn.setText("■ Stop Recording")
        self._rec_label.setText("● RECORDING")
        self._rec_label.setStyleSheet("color: #ff4444;")
        self._progress.setVisible(True)
        self._source_combo.setEnabled(False)
        self._format_combo.setEnabled(False)

        self._worker = RecordWorker(cmd)
        self._worker.line.connect(self._log.appendPlainText)
        self._worker.finished.connect(self._rec_done)
        self._worker.start()
        log_info(f"Recording started: {self._output_path}")

    def _stop_recording(self):
        if self._worker:
            self._worker.stop()
        self._rec_btn.setText("Stopping...")
        self._rec_btn.setEnabled(False)

    def _rec_done(self, ok):
        self._recording = False
        self._rec_btn.setText("● Start Recording")
        self._rec_btn.setEnabled(True)
        self._rec_label.setText("IDLE")
        self._rec_label.setStyleSheet("color: #00ffff;")
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


def main():
    app = QApplication(sys.argv)
    win = ScreenRecorder()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()