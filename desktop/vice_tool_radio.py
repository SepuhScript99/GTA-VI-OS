#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) — Leonida FM Radio.
Real PipeWire/mpv-backed audio & internet radio player featuring GTA-inspired
Leonida FM stations, custom stream URLs, local audio playback, live track
metadata via mpv IPC, volume control, and clean process shutdown on close.
"""

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QIcon, QPixmap
from PyQt5.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton,
    QSlider, QVBoxLayout, QWidget
)

sys.path.insert(0, "/opt/vice-os/lib")

try:
    from python.vice_utils import log_error, log_info  # noqa: E402
except ImportError:
    def log_info(msg: str) -> None:
        print(f"[INFO] {msg}")

    def log_error(msg: str) -> None:
        print(f"[ERROR] {msg}", file=sys.stderr)


CJK_FONTS = [
    "Noto Sans",
    "Noto Sans CJK JP",
    "Noto Sans CJK SC",
    "Noto Sans CJK TC",
    "Noto Sans CJK KR",
    "DejaVu Sans",
]

STATIONS = [
    {
        "name": "Vice Sunset 104.5 FM",
        "genre": "Synthwave · Neon Highway",
        "url": "https://stream.nightride.fm/nightride.mp3",
    },
    {
        "name": "Leonida Wave 98.3 FM",
        "genre": "Chillwave · Coastal Drive",
        "url": "https://stream.nightride.fm/chillsynth.mp3",
    },
    {
        "name": "Ocean Beach Lo-Fi",
        "genre": "Lo-Fi · Downtempo Beats",
        "url": "https://ice2.somafm.com/groovesalad-128-mp3",
    },
    {
        "name": "Starfish Vapor 101.7",
        "genre": "Chillwave · Vapor Sunset",
        "url": "https://ice2.somafm.com/vaporwaves-128-mp3",
    },
    {
        "name": "Vice Dark Retrowave",
        "genre": "Retrowave · Midnight Run",
        "url": "https://stream.nightride.fm/darksynth.mp3",
    },
    {
        "name": "Key West Midnight Jazz",
        "genre": "Jazz · Lounge Noir",
        "url": "https://ice2.somafm.com/secretagent-128-mp3",
    },
]

STYLE = """
QMainWindow, QWidget#RootWidget {
    background-color: #120e1e;
    color: #f4f1fa;
    font-family: "Noto Sans", "Noto Sans CJK JP", "Noto Sans CJK SC", "Noto Sans CJK TC", "Noto Sans CJK KR", "DejaVu Sans", sans-serif;
    font-size: 13px;
}
QFrame#TunerCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #211438, stop:0.6 #2e153d, stop:1 #16223c);
    border: 1px solid #ff4da6;
    border-radius: 14px;
}
QLabel#StationTitle {
    color: #ffd166;
    font-size: 20px;
    font-weight: bold;
    background: transparent;
}
QLabel#TrackTitle {
    color: #00e5ff;
    font-size: 14px;
    font-weight: bold;
    background: transparent;
}
QLabel#StatusPill {
    color: #ff8a5b;
    font-size: 12px;
    font-weight: bold;
    background: transparent;
}
QListWidget#StationList {
    background-color: #181229;
    color: #f4f1fa;
    border: 1px solid #382b57;
    border-radius: 10px;
    padding: 6px;
    outline: none;
}
QListWidget#StationList::item {
    padding: 10px 12px;
    margin: 2px 0;
    border-radius: 8px;
}
QListWidget#StationList::item:selected {
    background-color: #362049;
    color: #ffd166;
    border: 1px solid #ff4da6;
}
QListWidget#StationList::item:hover {
    background-color: #241b3d;
}
QLineEdit {
    background-color: #1b152e;
    color: #f4f1fa;
    border: 1px solid #3c2e5e;
    border-radius: 8px;
    padding: 8px 12px;
}
QLineEdit:focus {
    border-color: #ff4da6;
}
QPushButton {
    background-color: #1e1733;
    color: #f4f1fa;
    border: 1px solid #43346b;
    border-radius: 8px;
    padding: 8px 14px;
    font-weight: bold;
}
QPushButton:hover {
    border-color: #ff8a5b;
    background-color: #2c2047;
}
QPushButton#PlayBtn {
    background-color: #351b42;
    color: #ffd166;
    border: 1px solid #ff4da6;
}
QPushButton#PlayBtn:hover {
    background-color: #ff4da6;
    color: #120e1e;
}
QPushButton#StopBtn {
    color: #ff6b8b;
    border-color: #ff6b8b;
}
QPushButton#StopBtn:hover {
    background-color: #ff6b8b;
    color: #120e1e;
}
QSlider::groove:horizontal {
    background: #1d1633;
    height: 8px;
    border: 1px solid #403166;
    border-radius: 4px;
}
QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff4da6, stop:1 #00e5ff);
    border-radius: 4px;
}
QSlider::handle:horizontal {
    background: #ffd166;
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
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
        "/usr/share/icons/hicolor/64x64/apps/vice-tool-radio.png",
        "/usr/share/pixmaps/vice-tool-radio.png",
        "/usr/share/pixmaps/vice-app.png",
    ):
        if os.path.isfile(path):
            pm = QPixmap(path)
            if not pm.isNull():
                return QIcon(pm)
    return QIcon.fromTheme("multimedia-player")


class LeonidaRadioApp(QMainWindow):
    """Main window for Leonida FM Radio backed by mpv + PipeWire."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Leonida FM Radio — Vice OS")
        self.resize(760, 560)
        self.setMinimumSize(640, 480)
        icon = _load_app_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)

        self._proc = None
        self._socket_path = os.path.join(
            tempfile.gettempdir(), f"vice_radio_ipc_{os.getpid()}.sock"
        )
        self._current_station = "Off Air"
        self._current_genre = "Select a Leonida FM station, stream URL, or local audio file"
        self._paused = False
        self._muted = False

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(1200)
        self._poll_timer.timeout.connect(self._poll_mpv)

        self._init_ui()

    def _init_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("RootWidget")
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.setSpacing(12)

        # Now Playing Tuner Banner
        tuner = QFrame(root)
        tuner.setObjectName("TunerCard")
        tuner_layout = QVBoxLayout(tuner)
        tuner_layout.setContentsMargins(18, 14, 18, 14)
        tuner_layout.setSpacing(6)

        hdr = QHBoxLayout()
        brand = QLabel("LEONIDA FM RADIO · PIPEWIRE AUDIO", tuner)
        brand.setStyleSheet("color: #ff8a5b; font-size: 11px; font-weight: bold; letter-spacing: 1px; background: transparent;")
        hdr.addWidget(brand)
        hdr.addStretch(1)
        self._status_lbl = QLabel("● OFF AIR", tuner)
        self._status_lbl.setObjectName("StatusPill")
        hdr.addWidget(self._status_lbl)
        tuner_layout.addLayout(hdr)

        self._station_lbl = QLabel(self._current_station, tuner)
        self._station_lbl.setObjectName("StationTitle")
        tuner_layout.addWidget(self._station_lbl)

        self._track_lbl = QLabel(self._current_genre, tuner)
        self._track_lbl.setObjectName("TrackTitle")
        self._track_lbl.setWordWrap(True)
        tuner_layout.addWidget(self._track_lbl)

        layout.addWidget(tuner)

        # Station Presets List
        presets_lbl = QLabel("Leonida Station Presets (double-click or press Tune In):", root)
        presets_lbl.setStyleSheet("color: #cfc6e6; font-weight: bold;")
        layout.addWidget(presets_lbl)

        self._station_list = QListWidget(root)
        self._station_list.setObjectName("StationList")
        for idx, st in enumerate(STATIONS):
            item = QListWidgetItem(f"{st['name']}   —   {st['genre']}")
            item.setData(Qt.UserRole, idx)
            self._station_list.addItem(item)
        self._station_list.setCurrentRow(0)
        self._station_list.itemDoubleClicked.connect(lambda _item: self._play_selected())
        layout.addWidget(self._station_list, 1)

        # Custom URL + Local File Row
        custom_row = QHBoxLayout()
        custom_row.setSpacing(8)
        self._url_input = QLineEdit(root)
        self._url_input.setPlaceholderText("Custom radio stream URL (https://... or icecast stream)...")
        self._url_input.returnPressed.connect(self._play_custom_url)
        custom_row.addWidget(self._url_input, 1)

        url_btn = QPushButton("Play URL", root)
        url_btn.clicked.connect(self._play_custom_url)
        custom_row.addWidget(url_btn)

        file_btn = QPushButton("Local File...", root)
        file_btn.clicked.connect(self._pick_local_file)
        custom_row.addWidget(file_btn)
        layout.addLayout(custom_row)

        # Playback + Volume Controls
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(10)

        self._play_btn = QPushButton("Tune In", root)
        self._play_btn.setObjectName("PlayBtn")
        self._play_btn.clicked.connect(self._play_selected)
        ctrl_row.addWidget(self._play_btn)

        self._pause_btn = QPushButton("Pause", root)
        self._pause_btn.clicked.connect(self._toggle_pause)
        self._pause_btn.setEnabled(False)
        ctrl_row.addWidget(self._pause_btn)

        self._stop_btn = QPushButton("Stop", root)
        self._stop_btn.setObjectName("StopBtn")
        self._stop_btn.clicked.connect(self._stop_playback)
        self._stop_btn.setEnabled(False)
        ctrl_row.addWidget(self._stop_btn)

        ctrl_row.addSpacing(12)

        self._mute_btn = QPushButton("Mute", root)
        self._mute_btn.setCheckable(True)
        self._mute_btn.clicked.connect(self._toggle_mute)
        ctrl_row.addWidget(self._mute_btn)

        vol_title = QLabel("Vol:", root)
        vol_title.setStyleSheet("color: #cfc6e6; font-weight: bold;")
        ctrl_row.addWidget(vol_title)

        self._vol_slider = QSlider(Qt.Horizontal, root)
        self._vol_slider.setRange(0, 100)
        self._vol_slider.setValue(80)
        self._vol_slider.setFixedWidth(150)
        self._vol_slider.valueChanged.connect(self._on_volume_changed)
        ctrl_row.addWidget(self._vol_slider)

        self._vol_lbl = QLabel("80%", root)
        self._vol_lbl.setFixedWidth(38)
        self._vol_lbl.setStyleSheet("color: #00e5ff; font-weight: bold;")
        ctrl_row.addWidget(self._vol_lbl)

        layout.addLayout(ctrl_row)

    def _ipc_command(self, cmd_list: list):
        if not hasattr(socket, "AF_UNIX") or not os.path.exists(self._socket_path):
            return None
        sock = None
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(0.25)
            sock.connect(self._socket_path)
            payload = (json.dumps({"command": cmd_list}) + "\n").encode("utf-8")
            sock.sendall(payload)
            data = sock.recv(4096).decode("utf-8", errors="replace").splitlines()
            if data:
                resp = json.loads(data[0])
                if resp.get("error") == "success":
                    return resp.get("data")
        except Exception:
            return None
        finally:
            if sock is not None:
                try:
                    sock.close()
                except Exception:
                    pass
        return None

    def _cleanup_socket(self) -> None:
        if os.path.exists(self._socket_path):
            try:
                os.unlink(self._socket_path)
            except OSError:
                pass

    def _stop_playback(self) -> None:
        self._poll_timer.stop()
        if self._proc is not None:
            if self._proc.poll() is None:
                self._ipc_command(["quit"])
                try:
                    self._proc.terminate()
                    self._proc.wait(timeout=1.2)
                except Exception:
                    try:
                        self._proc.kill()
                        self._proc.wait(timeout=0.8)
                    except Exception:
                        pass
            self._proc = None
        self._cleanup_socket()
        self._paused = False
        self._pause_btn.setText("Pause")
        self._pause_btn.setEnabled(False)
        self._stop_btn.setEnabled(False)
        self._status_lbl.setText("● OFF AIR")
        self._status_lbl.setStyleSheet("color: #ff8a5b; font-size: 12px; font-weight: bold; background: transparent;")

    def _start_stream(self, target: str, title: str, subtitle: str) -> None:
        if not shutil.which("mpv"):
            QMessageBox.warning(
                self,
                "mpv Missing",
                "mpv is required for Leonida FM Radio playback. Install package 'mpv'."
            )
            return

        self._stop_playback()
        self._cleanup_socket()

        vol = self._vol_slider.value()
        cmd = [
            "mpv",
            "--no-video",
            "--no-terminal",
            "--ao=pipewire,pulse,alsa",
            f"--volume={vol}",
            "--ytdl=no",
            target,
        ]
        if hasattr(socket, "AF_UNIX"):
            cmd.insert(3, f"--input-ipc-server={self._socket_path}")
        if self._muted:
            cmd.insert(3, "--mute=yes")

        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            log_error(f"Leonida FM failed launching mpv: {exc}")
            QMessageBox.critical(self, "Playback Error", f"Failed to start mpv:\n{exc}")
            return

        self._current_station = title
        self._current_genre = subtitle
        self._paused = False
        self._station_lbl.setText(title)
        self._track_lbl.setText(f"Connecting · {subtitle}")
        self._status_lbl.setText("● LIVE")
        self._status_lbl.setStyleSheet("color: #00e5ff; font-size: 12px; font-weight: bold; background: transparent;")
        self._pause_btn.setText("Pause")
        self._pause_btn.setEnabled(True)
        self._stop_btn.setEnabled(True)
        self._poll_timer.start()
        log_info(f"Leonida FM tuned to {title}")

    def _play_selected(self) -> None:
        row = self._station_list.currentRow()
        if row < 0 or row >= len(STATIONS):
            row = 0
        st = STATIONS[row]
        self._start_stream(st["url"], st["name"], st["genre"])

    def _play_custom_url(self) -> None:
        url = self._url_input.text().strip()
        if not url:
            QMessageBox.information(self, "Stream URL", "Enter a valid http:// or https:// audio stream URL.")
            return
        if not url.startswith(("http://", "https://", "rtsp://")):
            QMessageBox.warning(self, "Invalid URL", "Stream URL must start with http://, https://, or rtsp://.")
            return
        self._start_stream(url, "Custom Stream", url)

    def _pick_local_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Local Audio File",
            os.path.expanduser("~/Music"),
            "Audio Files (*.mp3 *.flac *.ogg *.wav *.m4a *.opus *.aac);;All Files (*)",
        )
        if path:
            self._start_stream(path, os.path.basename(path), os.path.dirname(path))

    def _toggle_pause(self) -> None:
        if self._proc is None or self._proc.poll() is not None:
            return
        self._paused = not self._paused
        self._ipc_command(["set_property", "pause", self._paused])
        self._pause_btn.setText("Resume" if self._paused else "Pause")
        self._status_lbl.setText("● PAUSED" if self._paused else "● LIVE")

    def _toggle_mute(self) -> None:
        self._muted = self._mute_btn.isChecked()
        self._mute_btn.setText("Unmute" if self._muted else "Mute")
        if self._proc is not None and self._proc.poll() is None:
            self._ipc_command(["set_property", "mute", self._muted])

    def _on_volume_changed(self, value: int) -> None:
        self._vol_lbl.setText(f"{value}%")
        if self._proc is not None and self._proc.poll() is None:
            self._ipc_command(["set_property", "volume", value])

    def _poll_mpv(self) -> None:
        if self._proc is None:
            self._poll_timer.stop()
            return
        rc = self._proc.poll()
        if rc is not None:
            self._stop_playback()
            self._track_lbl.setText(f"Stream stopped (mpv exited with code {rc}).")
            return

        title = self._ipc_command(["get_property", "media-title"])
        if isinstance(title, str) and title.strip() and not title.startswith("http"):
            self._track_lbl.setText(f"Now Playing: {title.strip()}")
        else:
            self._track_lbl.setText(self._current_genre)

    def closeEvent(self, event) -> None:
        self._stop_playback()
        event.accept()


def main() -> None:
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    _configure_cjk_fonts(app)
    app.setStyleSheet(STYLE)
    win = LeonidaRadioApp()
    app.aboutToQuit.connect(win._stop_playback)
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
