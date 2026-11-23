#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) — Vice Media Studio.
Real FFmpeg + ImageMagick (convert) GUI converter supporting Video -> MP4/WebM/GIF,
audio extraction (MP3/WAV/FLAC), and Image convert/resize (PNG/JPG/WebP)
using non-blocking QProcess execution with live log and progress tracking.
Styled via vice_theme (Noto Sans CJK fallback).
"""

import os
import re
import shutil
import signal
import sys

from PyQt5.QtCore import Qt, QProcess
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar,
    QSpinBox, QTabWidget, QVBoxLayout, QWidget
)

try:
    from PIL import Image
except ImportError:
    Image = None

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


VIDEO_PRESETS = [
    ("Video -> MP4 (H.264 / AAC)", ".mp4", "video", ["-c:v", "libx264", "-preset", "fast", "-crf", "22", "-c:a", "aac", "-b:a", "192k"]),
    ("Video -> WebM (VP9 / Opus)", ".webm", "video", ["-c:v", "libvpx-vp9", "-crf", "30", "-b:v", "0", "-c:a", "libopus"]),
    ("Video -> Animated GIF (15fps)", ".gif", "gif", ["-vf", "fps=15,scale=640:-1:flags=lanczos", "-loop", "0"]),
    ("Extract Audio -> MP3 (192k)", ".mp3", "audio", ["-vn", "-c:a", "libmp3lame", "-b:a", "192k"]),
    ("Extract Audio -> WAV (PCM)", ".wav", "audio", ["-vn", "-c:a", "pcm_s16le"]),
    ("Extract Audio -> FLAC (Lossless)", ".flac", "audio", ["-vn", "-c:a", "flac"]),
]


def _parse_hms(ts: str) -> float:
    parts = ts.split(":")
    if len(parts) != 3:
        return 0.0
    try:
        return int(parts[0]) * 3600.0 + int(parts[1]) * 60.0 + float(parts[2])
    except ValueError:
        return 0.0


class ViceMediaStudioApp(QMainWindow):
    """Main window for Vice Media Studio."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice Media Studio — Vice OS")
        self.resize(900, 660)
        self.setMinimumSize(720, 520)
        icon = load_tool_icon("vice-tool-media-studio", "applications-multimedia")
        if not icon.isNull():
            self.setWindowIcon(icon)

        self._proc = None
        self._duration_sec = 0.0
        self._init_ui()

    def _init_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("RootWidget")
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.setSpacing(12)

        self._header = make_header(
            title="Vice Media Studio",
            subtitle="Transcode MP4/WebM/GIF, extract audio, and convert/resize images",
            icon_name="vice-tool-media-studio",
            badge_text="READY",
            badge_variant="neutral",
            parent=root,
        )
        layout.addWidget(self._header)

        tabs = QTabWidget(root)
        tabs.addTab(self._build_av_tab(), "Video && Audio (FFmpeg)")
        tabs.addTab(self._build_img_tab(), "Image Studio (convert)")
        layout.addWidget(tabs, 1)

        self._progress = QProgressBar(root)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        layout.addWidget(self._progress)

        self._log_box = QPlainTextEdit(root)
        self._log_box.setReadOnly(True)
        self._log_box.setMaximumHeight(160)
        layout.addWidget(self._log_box)

    def _build_av_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(10)

        card = make_card(title="FFmpeg Media Pipeline", parent=w)
        in_row = QHBoxLayout()
        in_row.setSpacing(8)
        self._av_in = QLineEdit()
        self._av_in.setPlaceholderText("Input video or audio file...")
        in_row.addWidget(self._av_in, 1)
        in_btn = make_button("Browse Media...", variant="secondary")
        in_btn.clicked.connect(self._browse_av_input)
        in_row.addWidget(in_btn)
        card.body_layout.addLayout(in_row)

        opt_row = QHBoxLayout()
        opt_row.setSpacing(8)
        opt_row.addWidget(QLabel("Preset:"))
        self._preset_combo = QComboBox()
        for label, _ext, _kind, _flags in VIDEO_PRESETS:
            self._preset_combo.addItem(label)
        self._preset_combo.currentIndexChanged.connect(self._suggest_av_out)
        opt_row.addWidget(self._preset_combo, 1)

        opt_row.addWidget(QLabel("Scale:"))
        self._scale_combo = QComboBox()
        self._scale_combo.addItems(["Original", "1920x1080", "1280x720", "854x480"])
        opt_row.addWidget(self._scale_combo)
        card.body_layout.addLayout(opt_row)

        out_row = QHBoxLayout()
        out_row.setSpacing(8)
        self._av_out = QLineEdit()
        self._av_out.setPlaceholderText("Output media path...")
        out_row.addWidget(self._av_out, 1)
        out_btn = make_button("Save As...", variant="secondary")
        out_btn.clicked.connect(self._browse_av_out)
        out_row.addWidget(out_btn)
        card.body_layout.addLayout(out_row)

        act_row = QHBoxLayout()
        act_row.setSpacing(8)
        self._av_run_btn = make_button("Start Conversion", variant="primary")
        self._av_run_btn.clicked.connect(self._run_ffmpeg)
        act_row.addWidget(self._av_run_btn)

        self._av_cancel_btn = make_button("Cancel", variant="danger")
        self._av_cancel_btn.setEnabled(False)
        self._av_cancel_btn.clicked.connect(self._cancel_process)
        act_row.addWidget(self._av_cancel_btn)
        act_row.addStretch(1)
        card.body_layout.addLayout(act_row)

        v.addWidget(card)
        v.addStretch(1)
        return w

    def _build_img_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(10)

        in_row = QHBoxLayout()
        in_row.setSpacing(8)
        self._img_in = QLineEdit()
        self._img_in.setPlaceholderText("Input image file (PNG, JPG, WebP, BMP, TIFF)...")
        in_row.addWidget(self._img_in, 1)
        in_btn = make_button("Browse Image...", variant="secondary")
        in_btn.clicked.connect(self._browse_img_input)
        in_row.addWidget(in_btn)
        v.addLayout(in_row)

        opt_row = QHBoxLayout()
        opt_row.setSpacing(8)
        opt_row.addWidget(QLabel("Format:"))
        self._img_fmt = QComboBox()
        self._img_fmt.addItems(["png", "jpg", "webp"])
        self._img_fmt.currentIndexChanged.connect(self._suggest_img_out)
        opt_row.addWidget(self._img_fmt)

        opt_row.addWidget(QLabel("Resize:"))
        self._img_resize = QComboBox()
        self._img_resize.addItems(["Original", "Max Width (px)", "Exact W x H"])
        opt_row.addWidget(self._img_resize)

        self._img_w = QSpinBox()
        self._img_w.setRange(16, 8192)
        self._img_w.setValue(1280)
        opt_row.addWidget(QLabel("W:"))
        opt_row.addWidget(self._img_w)

        self._img_h = QSpinBox()
        self._img_h.setRange(16, 8192)
        self._img_h.setValue(720)
        opt_row.addWidget(QLabel("H:"))
        opt_row.addWidget(self._img_h)

        self._img_q = QSpinBox()
        self._img_q.setRange(10, 100)
        self._img_q.setValue(90)
        opt_row.addWidget(QLabel("Quality:"))
        opt_row.addWidget(self._img_q)
        v.addLayout(opt_row)

        out_row = QHBoxLayout()
        out_row.setSpacing(8)
        self._img_out = QLineEdit()
        self._img_out.setPlaceholderText("Output image path...")
        out_row.addWidget(self._img_out, 1)
        out_btn = make_button("Save As...", variant="secondary")
        out_btn.clicked.connect(self._browse_img_out)
        out_row.addWidget(out_btn)
        v.addLayout(out_row)

        mid_row = QHBoxLayout()
        mid_row.setSpacing(12)
        self._img_preview = QLabel("No image loaded")
        self._img_preview.setFixedSize(220, 140)
        self._img_preview.setAlignment(Qt.AlignCenter)
        self._img_preview.setStyleSheet(
            f"border: 1px solid {COLORS['border']}; border-radius: 8px; "
            f"background: {COLORS['bg_canvas']}; color: {COLORS['text_muted']};"
        )
        mid_row.addWidget(self._img_preview)

        col_btns = QVBoxLayout()
        col_btns.setSpacing(8)
        self._img_run_btn = make_button("Convert / Resize Image", variant="primary")
        self._img_run_btn.clicked.connect(self._run_image_convert)
        col_btns.addWidget(self._img_run_btn)
        self._img_meta = QLabel("Uses ImageMagick 'convert' with Pillow fallback.")
        self._img_meta.setObjectName("MutedLabel")
        self._img_meta.setWordWrap(True)
        col_btns.addWidget(self._img_meta)
        col_btns.addStretch(1)
        mid_row.addLayout(col_btns, 1)
        v.addLayout(mid_row)
        return w

    def _browse_av_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Video or Audio", os.path.expanduser("~"),
            "Media Files (*.mp4 *.mkv *.webm *.avi *.mov *.mp3 *.wav *.flac *.ogg *.m4a);;All Files (*)"
        )
        if path:
            self._av_in.setText(path)
            self._suggest_av_out()

    def _suggest_av_out(self) -> None:
        src = self._av_in.text().strip()
        if not src:
            return
        idx = self._preset_combo.currentIndex()
        ext = VIDEO_PRESETS[idx][1]
        base, _old = os.path.splitext(src)
        self._av_out.setText(f"{base}_vice{ext}")

    def _browse_av_out(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save Media As", self._av_out.text() or os.path.expanduser("~"))
        if path:
            self._av_out.setText(path)

    def _browse_img_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Image", os.path.expanduser("~/Pictures"),
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.tiff);;All Files (*)"
        )
        if path:
            self._img_in.setText(path)
            pm = QPixmap(path)
            if not pm.isNull():
                self._img_preview.setPixmap(pm.scaled(214, 134, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                self._img_meta.setText(f"Source dimensions: {pm.width()} x {pm.height()} px")
            self._suggest_img_out()

    def _suggest_img_out(self) -> None:
        src = self._img_in.text().strip()
        if not src:
            return
        ext = self._img_fmt.currentText()
        base, _old = os.path.splitext(src)
        self._img_out.setText(f"{base}_vice.{ext}")

    def _browse_img_out(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save Image As", self._img_out.text() or os.path.expanduser("~"))
        if path:
            self._img_out.setText(path)

    def _append_log(self, text: str) -> None:
        self._log_box.moveCursor(self._log_box.textCursor().End)
        self._log_box.insertPlainText(text)

    def _is_busy(self) -> bool:
        return self._proc is not None and self._proc.state() != QProcess.NotRunning

    def _set_busy(self, busy: bool) -> None:
        self._av_run_btn.setEnabled(not busy)
        self._img_run_btn.setEnabled(not busy)
        self._av_cancel_btn.setEnabled(busy)
        self._header.set_badge("RUNNING" if busy else "READY", "aqua" if busy else "neutral")

    def _run_ffmpeg(self) -> None:
        if self._is_busy():
            return
        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            QMessageBox.warning(self, "FFmpeg Missing", "ffmpeg binary is not installed.")
            return
        src = self._av_in.text().strip()
        dst = self._av_out.text().strip()
        if not src or not os.path.isfile(src):
            QMessageBox.warning(self, "Input Error", "Select an existing media file.")
            return
        if not dst or os.path.abspath(src) == os.path.abspath(dst):
            QMessageBox.warning(self, "Output Error", "Specify a distinct output file path.")
            return

        _label, _ext, kind, base_flags = VIDEO_PRESETS[self._preset_combo.currentIndex()]
        args = ["-y", "-i", src]
        scale = self._scale_combo.currentText()
        if kind == "video" and scale != "Original":
            w, h = scale.split("x")
            args.extend(["-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease"])
        args.extend(base_flags)
        args.append(dst)

        self._duration_sec = 0.0
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._log_box.clear()
        self._append_log(f"$ {ffmpeg_bin} {' '.join(args)}\n")

        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(QProcess.MergedChannels)
        self._proc.readyReadStandardOutput.connect(self._on_proc_output)
        self._proc.finished.connect(self._on_proc_finished)
        self._proc.errorOccurred.connect(self._on_proc_error)
        self._set_busy(True)
        self._proc.start(ffmpeg_bin, args)
        log_info(f"Vice Media Studio started ffmpeg -> {dst}")

    def _run_image_convert(self) -> None:
        if self._is_busy():
            return
        src = self._img_in.text().strip()
        dst = self._img_out.text().strip()
        if not src or not os.path.isfile(src):
            QMessageBox.warning(self, "Input Error", "Select an existing image file.")
            return
        if not dst or os.path.abspath(src) == os.path.abspath(dst):
            QMessageBox.warning(self, "Output Error", "Specify a distinct output image path.")
            return

        convert_bin = shutil.which("convert")
        resize_mode = self._img_resize.currentText()
        w = self._img_w.value()
        h = self._img_h.value()
        q = self._img_q.value()

        if convert_bin:
            args = [src]
            if resize_mode == "Max Width (px)":
                args.extend(["-resize", f"{w}x>"])
            elif resize_mode == "Exact W x H":
                args.extend(["-resize", f"{w}x{h}!"])
            args.extend(["-quality", str(q), dst])

            self._duration_sec = 0.0
            self._progress.setRange(0, 0)
            self._log_box.clear()
            self._append_log(f"$ {convert_bin} {' '.join(args)}\n")

            self._proc = QProcess(self)
            self._proc.setProcessChannelMode(QProcess.MergedChannels)
            self._proc.readyReadStandardOutput.connect(self._on_proc_output)
            self._proc.finished.connect(self._on_proc_finished)
            self._proc.errorOccurred.connect(self._on_proc_error)
            self._set_busy(True)
            self._proc.start(convert_bin, args)
            return

        if Image is not None:
            try:
                im = Image.open(src)
                if resize_mode == "Max Width (px)" and im.width > w:
                    new_h = max(1, int(im.height * (w / im.width)))
                    im = im.resize((w, new_h), Image.LANCZOS)
                elif resize_mode == "Exact W x H":
                    im = im.resize((w, h), Image.LANCZOS)
                fmt = self._img_fmt.currentText().upper()
                if fmt == "JPG":
                    fmt = "JPEG"
                    im = im.convert("RGB")
                im.save(dst, fmt, quality=q)
                self._progress.setRange(0, 100)
                self._progress.setValue(100)
                self._append_log(f"[Pillow fallback] Converted image -> {dst}\n")
                self._header.set_badge("DONE", "success")
                return
            except Exception as exc:
                QMessageBox.critical(self, "Convert Error", str(exc))
                return

        QMessageBox.warning(self, "ImageMagick Missing", "Install package 'imagemagick' ('convert').")

    def _on_proc_output(self) -> None:
        if self._proc is None:
            return
        text = bytes(self._proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        if not text:
            return
        self._append_log(text)
        dur_m = re.search(r"Duration:\s*(\d+:\d+:\d+(?:\.\d+)?)", text)
        if dur_m:
            self._duration_sec = max(0.1, _parse_hms(dur_m.group(1)))
        time_matches = re.findall(r"time=(\d+:\d+:\d+(?:\.\d+)?)", text)
        if time_matches and self._duration_sec > 0.0:
            cur = _parse_hms(time_matches[-1])
            pct = max(0, min(99, int(round((cur / self._duration_sec) * 100))))
            self._progress.setRange(0, 100)
            self._progress.setValue(pct)

    def _on_proc_finished(self, exit_code: int, _status) -> None:
        self._set_busy(False)
        self._progress.setRange(0, 100)
        if exit_code == 0:
            self._progress.setValue(100)
            self._header.set_badge("DONE", "success")
            self._append_log("\n[SUCCESS] Conversion completed cleanly.\n")
        else:
            self._header.set_badge("ERROR", "danger")
            self._append_log(f"\n[ERROR] Process exited with code {exit_code}.\n")

    def _on_proc_error(self, _err) -> None:
        self._set_busy(False)
        self._progress.setRange(0, 100)
        self._header.set_badge("ERROR", "danger")
        msg = self._proc.errorString() if self._proc is not None else "Process failed to start"
        self._append_log(f"\n[ERROR] Failed to start process: {msg}\n")

    def _cancel_process(self) -> None:
        if self._is_busy():
            self._proc.terminate()
            if not self._proc.waitForFinished(1000):
                self._proc.kill()
                self._proc.waitForFinished(500)
        self._set_busy(False)
        self._progress.setRange(0, 100)
        self._append_log("\n[CANCELLED] Process terminated by user.\n")

    def closeEvent(self, event) -> None:
        self._cancel_process()
        event.accept()


def main() -> None:
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    apply_app_theme(app)
    win = ViceMediaStudioApp()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
