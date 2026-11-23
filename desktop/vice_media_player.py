#!/usr/bin/env python3
"""Vice OS — Media Player. mpv frontend with playlist, seek, volume controls."""

import json
import os
import socket as sock
import subprocess
import sys
import tempfile

from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QSlider, QSplitter,
    QVBoxLayout, QWidget,
)

sys.path.insert(0, '/opt/vice-os/lib')

from python.vice_utils import log_error, log_info  # noqa: E402
import vice_theme as vt  # noqa: E402

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 620

MEDIA_EXTS = ("*.mp3", "*.flac", "*.ogg", "*.wav", "*.m4a", "*.mp4", "*.mkv", "*.avi", "*.webm", "*.mov")
MEDIA_SUFFIXES = (".mp3", ".flac", ".ogg", ".wav", ".m4a", ".mp4", ".mkv", ".avi", ".webm", ".mov")


def _ipc_socket_path():
    base = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
    return os.path.join(base, f"vice_mpv_{os.getpid()}.sock")


SOCKET = _ipc_socket_path()


def fmt_time(seconds):
    seconds = int(float(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def mpv_query(property_name):
    """Query a property from the running mpv via IPC socket."""
    if not os.path.exists(SOCKET):
        return None
    try:
        s = sock.socket(sock.AF_UNIX, sock.SOCK_STREAM)
        s.settimeout(0.2)
        s.connect(SOCKET)
        s.send(json.dumps({"command": ["get_property", property_name]}).encode() + b"\n")
        data = s.recv(65536).decode("utf-8", errors="replace")
        s.close()
        resp = json.loads(data.strip().splitlines()[0])
        if resp.get("error") == "success":
            return resp.get("data")
    except Exception:
        pass
    return None


class MpvPlayer(QThread):
    """Wrapper for launching mpv in windowed mode with IPC."""

    started = pyqtSignal()
    finished = pyqtSignal()

    def __init__(self, path, volume=80, parent=None):
        super().__init__(parent)
        self._path = path
        self._volume = volume
        self._proc = None
        self._cancelled = False

    def stop(self):
        self._cancelled = True
        if self._proc is not None and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except OSError:
                pass

    def run(self):
        if os.path.exists(SOCKET):
            try:
                os.unlink(SOCKET)
            except OSError:
                pass
        cmd = [
            "mpv",
            f"--input-ipc-server={SOCKET}",
            f"--volume={self._volume}",
            "--force-window=yes",
            "--keep-open=yes",
            "--no-terminal",
            self._path,
        ]
        try:
            self.started.emit()
            self._proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._proc.wait()
        except FileNotFoundError:
            log_error("mpv not installed")
        except Exception as e:
            log_error(f"mpv launch failed: {e}")
        if not self._cancelled:
            self.finished.emit()


class MediaPlayer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Media Player")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(780, 480)
        vt.apply_app_theme(self)
        self._playlist = []
        self._current = -1
        self._player = None
        self._duration = 0
        self._seeking = False
        self._manual_stop = False
        self._init_ui()
        self._poll = QTimer(self)
        self._poll.setInterval(1000)
        self._poll.timeout.connect(self._update_progress)
        self._poll.start()

    def _init_ui(self):
        root = QVBoxLayout(self)

        root.addWidget(vt.make_header(
            "Media Player",
            "Play audio & video files with playlist queue, seek and mpv IPC controls",
            icon_name="multimedia-player",
            badge_text="MPV",
            badge_variant="coral",
            parent=self,
        ))

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        playlist_panel = QWidget()
        pl = QVBoxLayout(playlist_panel)
        pl.setContentsMargins(0, 0, 0, 0)

        pl.addWidget(QLabel("Playlist:"))
        self._list = QListWidget()
        self._list.doubleClicked.connect(self._play_index)
        pl.addWidget(self._list)

        pl_btns = QHBoxLayout()
        add_btn = vt.make_button("+ Add Files", "primary", parent=playlist_panel)
        add_btn.clicked.connect(self._add_files)
        pl_btns.addWidget(add_btn)
        add_dir_btn = vt.make_button("+ Add Folder", "secondary", parent=playlist_panel)
        add_dir_btn.clicked.connect(self._add_folder)
        pl_btns.addWidget(add_dir_btn)
        rm_btn = vt.make_button("Remove", "danger", parent=playlist_panel)
        rm_btn.clicked.connect(self._remove_selected)
        pl_btns.addWidget(rm_btn)
        clear_btn = vt.make_button("Clear", "secondary", parent=playlist_panel)
        clear_btn.clicked.connect(self._clear_playlist)
        pl_btns.addWidget(clear_btn)
        pl.addLayout(pl_btns)
        splitter.addWidget(playlist_panel)

        control_panel = QWidget()
        cr = QVBoxLayout(control_panel)
        cr.setContentsMargins(8, 0, 0, 0)

        self._now_playing = QLabel("Nothing playing")
        self._now_playing.setAlignment(Qt.AlignCenter)
        self._now_playing.setFont(QFont("monospace", 12, QFont.Bold))
        self._now_playing.setStyleSheet(f"color: {vt.COLORS['accent_aqua']}; margin: 8px;")
        self._now_playing.setWordWrap(True)
        cr.addWidget(self._now_playing)

        seek_row = QHBoxLayout()
        self._time_label = QLabel("0:00")
        self._time_label.setFixedWidth(50)
        seek_row.addWidget(self._time_label)
        self._seek = QSlider(Qt.Horizontal)
        self._seek.setRange(0, 1000)
        self._seek.sliderPressed.connect(lambda: setattr(self, "_seeking", True))
        self._seek.sliderReleased.connect(self._seek_released)
        seek_row.addWidget(self._seek, 1)
        self._dur_label = QLabel("0:00")
        self._dur_label.setFixedWidth(50)
        seek_row.addWidget(self._dur_label)
        cr.addLayout(seek_row)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        for label, slot, variant in (
            ("Prev", self._prev, "secondary"),
            ("-10s", lambda: self._seek_relative(-10), "secondary"),
            ("Play", self._play_current, "primary"),
            ("Pause", self._toggle_pause, "secondary"),
            ("Stop", self._stop, "danger"),
            ("+10s", lambda: self._seek_relative(10), "secondary"),
            ("Next", self._next, "secondary"),
        ):
            btn = vt.make_button(label, variant, parent=control_panel)
            btn.clicked.connect(slot)
            btn_row.addWidget(btn)
        btn_row.addStretch()
        cr.addLayout(btn_row)

        vol_row = QHBoxLayout()
        vol_row.addWidget(QLabel("Volume:"))
        self._volume = QSlider(Qt.Horizontal)
        self._volume.setRange(0, 100)
        self._volume.setValue(80)
        self._volume.setFixedWidth(200)
        self._volume.valueChanged.connect(self._set_volume)
        vol_row.addWidget(self._volume)
        self._vol_label = QLabel("80%")
        self._vol_label.setFixedWidth(40)
        vol_row.addWidget(self._vol_label)
        vol_row.addStretch()
        self._repeat_btn = QPushButton("Repeat: OFF")
        self._repeat_btn.setCheckable(True)
        self._repeat_btn.toggled.connect(self._toggle_repeat)
        vol_row.addWidget(self._repeat_btn)
        cr.addLayout(vol_row)

        cr.addStretch()
        splitter.addWidget(control_panel)
        splitter.setSizes([380, 600])

        self._status = QLabel("Ready — add media files to the playlist")
        self._status.setStyleSheet(f"color: {vt.COLORS['text_secondary']}; font-size: 11px;")
        root.addWidget(self._status)

    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add Media Files", os.path.expanduser("~"),
            f"Media ({' '.join(MEDIA_EXTS)});;All files (*)",
        )
        for p in paths:
            self._playlist.append(p)
            self._list.addItem(QListWidgetItem(os.path.basename(p)))
        self._status.setText(f"{len(self._playlist)} item(s) in playlist")

    def _add_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Add Folder", os.path.expanduser("~"))
        if not path:
            return
        count = 0
        for dirpath, _dirnames, filenames in os.walk(path):
            for fname in sorted(filenames):
                if fname.lower().endswith(MEDIA_SUFFIXES):
                    full = os.path.join(dirpath, fname)
                    self._playlist.append(full)
                    self._list.addItem(QListWidgetItem(fname))
                    count += 1
        self._status.setText(f"Added {count} file(s) — {len(self._playlist)} total")

    def _remove_selected(self):
        row = self._list.currentRow()
        if row < 0:
            return
        self._playlist.pop(row)
        self._list.takeItem(row)
        if row == self._current:
            self._current = -1
        elif row < self._current:
            self._current -= 1

    def _clear_playlist(self):
        self._playlist.clear()
        self._list.clear()
        self._current = -1
        self._status.setText("Playlist cleared")

    def _play_index(self, index):
        row = index.row() if hasattr(index, "row") else index
        if 0 <= row < len(self._playlist):
            self._current = row
            self._launch(self._playlist[row])

    def _play_current(self):
        if not self._playlist:
            QMessageBox.information(self, "Empty Playlist", "Add media files first.")
            return
        if self._current < 0 or self._current >= len(self._playlist):
            self._current = 0
        self._list.setCurrentRow(self._current)
        self._launch(self._playlist[self._current])

    def _launch(self, path):
        self._stop_player()
        self._manual_stop = False
        self._duration = 0
        self._seek.setValue(0)
        self._time_label.setText("0:00")
        self._dur_label.setText("0:00")
        self._now_playing.setText(os.path.basename(path))
        self._status.setText(f"Playing: {os.path.basename(path)}")
        log_info(f"Playing: {path}")
        self._player = MpvPlayer(path, self._volume.value(), parent=self)
        self._player.finished.connect(self._on_playback_end)
        self._player.start()

    def _on_playback_end(self):
        if self._manual_stop:
            return
        if self._repeat_btn.isChecked() and 0 <= self._current < len(self._playlist):
            self._launch(self._playlist[self._current])
        elif self._current + 1 < len(self._playlist):
            self._current += 1
            self._list.setCurrentRow(self._current)
            self._launch(self._playlist[self._current])
        else:
            self._now_playing.setText("Nothing playing")
            self._status.setText("End of playlist")

    def _prev(self):
        if self._current > 0:
            self._current -= 1
            self._list.setCurrentRow(self._current)
            self._launch(self._playlist[self._current])

    def _next(self):
        if self._current + 1 < len(self._playlist):
            self._current += 1
            self._list.setCurrentRow(self._current)
            self._launch(self._playlist[self._current])

    def _stop_player(self):
        self._manual_stop = True
        self._mpv_command(["quit"])
        if self._player is not None and self._player.isRunning():
            self._player.stop()
            self._player.wait(1500)
        if os.path.exists(SOCKET):
            try:
                os.unlink(SOCKET)
            except OSError:
                pass

    def _stop(self):
        self._stop_player()
        self._now_playing.setText("Stopped")
        self._status.setText("Stopped")

    def _toggle_pause(self):
        self._mpv_command(["cycle", "pause"])

    def _seek_relative(self, seconds):
        self._mpv_command(["seek", str(seconds), "relative"])

    def _seek_released(self):
        if self._duration:
            pos = self._seek.value() / 1000 * self._duration
            self._mpv_command(["seek", str(pos), "absolute"])
        self._seeking = False

    def _set_volume(self, value):
        self._vol_label.setText(f"{value}%")
        self._mpv_command(["set_property", "volume", value])

    def _toggle_repeat(self, on):
        self._repeat_btn.setText("Repeat: ON" if on else "Repeat: OFF")

    def _mpv_command(self, command):
        if not os.path.exists(SOCKET):
            return
        try:
            s = sock.socket(sock.AF_UNIX, sock.SOCK_STREAM)
            s.settimeout(0.2)
            s.connect(SOCKET)
            s.send(json.dumps({"command": command}).encode() + b"\n")
            s.close()
        except Exception:
            pass

    def _update_progress(self):
        if self._seeking:
            return
        pos = mpv_query("time-pos")
        dur = mpv_query("duration")
        if dur:
            self._duration = float(dur)
            self._dur_label.setText(fmt_time(dur))
        if pos is not None and self._duration:
            self._time_label.setText(fmt_time(pos))
            self._seek.setValue(int(pos / self._duration * 1000))

    def closeEvent(self, event):
        self._poll.stop()
        self._stop_player()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    win = MediaPlayer()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
