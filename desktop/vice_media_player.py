#!/usr/bin/env python3
"""Vice OS — Media Player. mpv frontend with playlist, seek, volume controls."""

import sys
import os
import subprocess
import glob

sys.path.insert(0, '/opt/vice-os/lib')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QSlider, QListWidget, QListWidgetItem, QSplitter, QFileDialog,
    QMessageBox, QProgressBar, QFrame
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont

from python.vice_utils import log_info, log_error

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 620

STYLE = """
QWidget { background-color: #0a0a0a; color: #00ffff; font-family: "Noto Sans Mono CJK JP", "Noto Sans CJK JP", "Noto Sans CJK SC", monospace; }
QPushButton { background: #1a1a1a; color: #00ffff; border: 1px solid #00ffff; padding: 6px 12px; }
QPushButton:hover { background: #00ffff; color: #0a0a0a; }
QPushButton:disabled { color: #444; border-color: #444; }
QSlider::groove:horizontal { background: #1a1a1a; height: 6px; border: 1px solid #00ffff; }
QSlider::handle:horizontal { background: #00ffff; width: 14px; height: 14px; margin: -4px 0; border-radius: 7px; }
QSlider::sub-page:horizontal { background: #003333; }
QListWidget { background: #0d0d0d; color: #00ffff; border: 1px solid #00ffff; font-size: 11px; }
QListWidget::item:selected { background: #00ffff; color: #0a0a0a; }
QLabel { color: #00ffff; }
QSplitter::handle { background: #00ffff; width: 1px; }
QProgressBar { border: 1px solid #00ffff; background: #1a1a1a; }
QProgressBar::chunk { background: #00ffff; }
"""

MEDIA_EXTS = ["*.mp3", "*.flac", "*.ogg", "*.wav", "*.m4a",
              "*.mp4", "*.mkv", "*.avi", "*.webm", "*.mov"]
SOCKET = "/tmp/vice_mpv_socket"


def fmt_time(seconds):
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def mpv_query(property_name):
    """Query a property from the running mpv via IPC socket."""
    try:
        import socket as sock
        s = sock.socket(sock.AF_UNIX, sock.SOCK_STREAM)
        s.settimeout(0.2)
        s.connect(SOCKET)
        s.send(f'{{ "command": ["get_property", "{property_name}"] }}\n'.encode())
        data = s.recv(65536).decode()
        s.close()
        import json
        resp = json.loads(data.strip().splitlines()[0])
        if resp.get("error") == "success":
            return resp.get("data")
    except Exception:
        pass
    return None


class MpvPlayer(QThread):
    """Wrapper for launching mpv in windowed slave mode with IPC."""
    started = pyqtSignal()
    finished = pyqtSignal()

    def __init__(self, path, volume=80):
        super().__init__()
        self._path = path
        self._volume = volume

    def run(self):
        if os.path.exists(SOCKET):
            try:
                os.unlink(SOCKET)
            except Exception:
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
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            proc.wait()
        except FileNotFoundError:
            log_error("mpv not installed")
        except Exception as e:
            log_error(f"mpv launch failed: {e}")
        self.finished.emit()


class MediaPlayer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice OS — Media Player")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        self._playlist = []
        self._current = -1
        self._player = None
        self._duration = 0
        self._seeking = False
        self._init_ui()
        self._poll = QTimer()
        self._poll.setInterval(1000)
        self._poll.timeout.connect(self._update_progress)
        self._poll.start()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Vice OS — Media Player")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("monospace", 13, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; margin: 4px;")
        root.addWidget(title)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        # Left: playlist
        playlist_panel = QWidget()
        pl = QVBoxLayout(playlist_panel)
        pl.setContentsMargins(0, 0, 0, 0)

        pl.addWidget(QLabel("Playlist:"))
        self._list = QListWidget()
        self._list.doubleClicked.connect(self._play_index)
        pl.addWidget(self._list)

        pl_btns = QHBoxLayout()
        add_btn = QPushButton("+ Add Files")
        add_btn.clicked.connect(self._add_files)
        pl_btns.addWidget(add_btn)
        add_dir_btn = QPushButton("+ Add Folder")
        add_dir_btn.clicked.connect(self._add_folder)
        pl_btns.addWidget(add_dir_btn)
        rm_btn = QPushButton("Remove")
        rm_btn.setStyleSheet("QPushButton { border-color: #ff4444; color: #ff4444; } QPushButton:hover { background: #ff4444; color: #0a0a0a; }")
        rm_btn.clicked.connect(self._remove_selected)
        pl_btns.addWidget(rm_btn)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_playlist)
        pl_btns.addWidget(clear_btn)
        pl.addLayout(pl_btns)
        splitter.addWidget(playlist_panel)

        # Right: controls
        control_panel = QWidget()
        cr = QVBoxLayout(control_panel)
        cr.setContentsMargins(8, 0, 0, 0)

        self._now_playing = QLabel("Nothing playing")
        self._now_playing.setAlignment(Qt.AlignCenter)
        self._now_playing.setFont(QFont("monospace", 12, QFont.Bold))
        self._now_playing.setStyleSheet("color: #00ffff; margin: 8px;")
        self._now_playing.setWordWrap(True)
        cr.addWidget(self._now_playing)

        # Seek bar
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

        # Transport buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        for label, slot, big in [
            ("⏮ Prev", self._prev, False),
            ("⏪ -10s", lambda: self._seek_relative(-10), False),
            ("▶ Play", self._play_current, True),
            ("⏸ Pause", self._toggle_pause, False),
            ("⏹ Stop", self._stop, False),
            ("⏩ +10s", lambda: self._seek_relative(10), False),
            ("⏭ Next", self._next, False),
        ]:
            btn = QPushButton(label)
            if big:
                btn.setStyleSheet("QPushButton { border-color: #ff00ff; color: #ff00ff; } QPushButton:hover { background: #ff00ff; color: #0a0a0a; }")
            btn.clicked.connect(slot)
            btn_row.addWidget(btn)
        btn_row.addStretch()
        cr.addLayout(btn_row)

        # Volume
        vol_row = QHBoxLayout()
        vol_row.addWidget(QLabel("🔊"))
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
        cr.addLayout(vol_row)

        # Repeat toggle
        self._repeat_btn = QPushButton("Repeat: OFF")
        self._repeat_btn.setCheckable(True)
        self._repeat_btn.toggled.connect(self._toggle_repeat)
        vol_row.addWidget(self._repeat_btn)

        cr.addStretch()
        splitter.addWidget(control_panel)
        splitter.setSizes([380, 600])

        self._status = QLabel("Ready — add media files to the playlist")
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self._status)

    # --- Playlist management ---

    def _add_files(self):
        exts = " ".join(e.replace("*", "*") for e in MEDIA_EXTS)
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add Media Files", os.path.expanduser("~"),
            f"Media ({' '.join(MEDIA_EXTS)});;All files (*)"
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
        for ext in MEDIA_EXTS:
            for f in glob.glob(os.path.join(path, "**", ext), recursive=True):
                self._playlist.append(f)
                self._list.addItem(QListWidgetItem(os.path.basename(f)))
                count += 1
        self._status.setText(f"Added {count} file(s) — {len(self._playlist)} total")

    def _remove_selected(self):
        row = self._list.currentRow()
        if row < 0:
            return
        self._playlist.pop(row)
        self._list.takeItem(row)

    def _clear_playlist(self):
        self._playlist.clear()
        self._list.clear()
        self._status.setText("Playlist cleared")

    # --- Playback ---

    def _play_index(self, index):
        row = index.row() if hasattr(index, "row") else index
        if 0 <= row < len(self._playlist):
            self._current = row
            self._launch(self._playlist[row])

    def _play_current(self):
        if not self._playlist:
            QMessageBox.information(self, "Empty Playlist", "Add media files first.")
            return
        if self._current < 0:
            self._current = 0
        self._list.setCurrentRow(self._current)
        self._launch(self._playlist[self._current])

    def _launch(self, path):
        self._stop_player()
        self._now_playing.setText(os.path.basename(path))
        self._status.setText(f"Playing: {os.path.basename(path)}")
        log_info(f"Playing: {path}")
        self._player = MpvPlayer(path, self._volume.value())
        self._player.finished.connect(self._on_playback_end)
        self._player.start()

    def _on_playback_end(self):
        if self._repeat_btn.isChecked():
            self._play_current()
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
        try:
            if os.path.exists(SOCKET):
                import socket as sock
                s = sock.socket(sock.AF_UNIX, sock.SOCK_STREAM)
                s.settimeout(0.3)
                s.connect(SOCKET)
                s.send(b'{ "command": ["quit"] }\n')
                s.close()
        except Exception:
            pass

    def _stop(self):
        self._stop_player()
        self._now_playing.setText("Stopped")

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
        try:
            import socket as sock
            import json
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


def main():
    app = QApplication(sys.argv)
    win = MediaPlayer()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()