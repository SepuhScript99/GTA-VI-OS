#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) — Leonida FM Radio.
Real PipeWire/mpv-backed audio & internet radio player featuring Leonida FM
stations, custom stream URLs, local audio playback, live track metadata via
mpv IPC, volume control, and clean process shutdown on close.
Styled via vice_theme (Noto Sans CJK fallback).
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
from PyQt5.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QSlider,
    QVBoxLayout, QWidget
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
)

try:
    from python.vice_utils import log_error, log_info  # noqa: E402
except ImportError:
    def log_info(msg: str) -> None:
        print(f"[INFO] {msg}")

    def log_error(msg: str) -> None:
        print(f"[ERROR] {msg}", file=sys.stderr)


STATIONS = [
    {
        "name": "Vice Sunset 104.5 FM",
        "genre": "Synthwave · Coastal Highway",
        "url": "https://stream.nightride.fm/nightride.mp3",
    },
    {
        "name": "Leonida Wave 98.3 FM",
        "genre": "Chillwave · Dusk Drive",
        "url": "https://stream.nightride.fm/chillsynth.mp3",
    },
    {
        "name": "Ocean Beach Lo-Fi",
        "genre": "Lo-Fi · Downtempo Beats",
        "url": "https://ice2.somafm.com/groovesalad-128-mp3",
    },
    {
        "name": "Starfish Vapor 101.7",
        "genre": "Chillwave · Sunset Horizon",
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


class LeonidaRadioApp(QMainWindow):
    """Main window for Leonida FM Radio backed by mpv + PipeWire."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Leonida FM Radio — Vice OS")
        self.resize(780, 580)
        self.setMinimumSize(640, 480)
        icon = load_tool_icon("vice-tool-radio", "multimedia-player")
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

        self._header = make_header(
            title="Leonida FM Radio",
            subtitle="PipeWire & mpv Audio Streamer",
            icon_name="vice-tool-radio",
            badge_text="OFF AIR",
            badge_variant="neutral",
            parent=root,
        )
        layout.addWidget(self._header)

        # Now Playing Card
        tuner = make_card(parent=root, margins=(16, 14, 16, 14), spacing=6)
        self._station_lbl = QLabel(self._current_station, tuner)
        self._station_lbl.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 19px; font-weight: bold;"
        )
        tuner.body_layout.addWidget(self._station_lbl)

        self._track_lbl = QLabel(self._current_genre, tuner)
        self._track_lbl.setObjectName("ValueReadout")
        self._track_lbl.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 13px; font-weight: normal;"
        )
        self._track_lbl.setWordWrap(True)
        tuner.body_layout.addWidget(self._track_lbl)
        layout.addWidget(tuner)

        # Station Presets Card
        presets_card = make_card(
            title="Station Presets",
            subtitle="Double-click a station or press Tune In to start playback",
            parent=root,
        )
        self._station_list = QListWidget(presets_card)
        for idx, st in enumerate(STATIONS):
            item = QListWidgetItem(f"{st['name']}   —   {st['genre']}")
            item.setData(Qt.UserRole, idx)
            self._station_list.addItem(item)
        self._station_list.setCurrentRow(0)
        self._station_list.itemDoubleClicked.connect(lambda _item: self._play_selected())
        presets_card.body_layout.addWidget(self._station_list, 1)
        layout.addWidget(presets_card, 1)

        # Custom Stream & Local File Row
        custom_row = QHBoxLayout()
        custom_row.setSpacing(8)
        self._url_input = QLineEdit(root)
        self._url_input.setPlaceholderText("Custom stream URL (https://... or icecast stream)...")
        self._url_input.returnPressed.connect(self._play_custom_url)
        custom_row.addWidget(self._url_input, 1)

        url_btn = make_button("Play URL", variant="secondary", parent=root)
        url_btn.clicked.connect(self._play_custom_url)
        custom_row.addWidget(url_btn)

        file_btn = make_button("Local File...", variant="secondary", parent=root)
        file_btn.clicked.connect(self._pick_local_file)
        custom_row.addWidget(file_btn)
        layout.addLayout(custom_row)

        # Playback + Volume Controls Card
        ctrl_card = make_card(parent=root, margins=(14, 10, 14, 10), spacing=0)
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(8)

        self._play_btn = make_button("Tune In", variant="primary", parent=ctrl_card)
        self._play_btn.clicked.connect(self._play_selected)
        ctrl_row.addWidget(self._play_btn)

        self._pause_btn = make_button("Pause", variant="secondary", parent=ctrl_card)
        self._pause_btn.clicked.connect(self._toggle_pause)
        self._pause_btn.setEnabled(False)
        ctrl_row.addWidget(self._pause_btn)

        self._stop_btn = make_button("Stop", variant="danger", parent=ctrl_card)
        self._stop_btn.clicked.connect(self._stop_playback)
        self._stop_btn.setEnabled(False)
        ctrl_row.addWidget(self._stop_btn)

        ctrl_row.addStretch(1)

        self._mute_btn = make_button("Mute", variant="secondary", parent=ctrl_card)
        self._mute_btn.setCheckable(True)
        self._mute_btn.clicked.connect(self._toggle_mute)
        ctrl_row.addWidget(self._mute_btn)

        vol_title = QLabel("Volume", ctrl_card)
        vol_title.setObjectName("MutedLabel")
        ctrl_row.addWidget(vol_title)

        self._vol_slider = QSlider(Qt.Horizontal, ctrl_card)
        self._vol_slider.setRange(0, 100)
        self._vol_slider.setValue(80)
        self._vol_slider.setFixedWidth(150)
        self._vol_slider.valueChanged.connect(self._on_volume_changed)
        ctrl_row.addWidget(self._vol_slider)

        self._vol_lbl = QLabel("80%", ctrl_card)
        self._vol_lbl.setFixedWidth(38)
        self._vol_lbl.setStyleSheet(f"color: {COLORS['accent_aqua']}; font-weight: bold;")
        ctrl_row.addWidget(self._vol_lbl)

        ctrl_card.body_layout.addLayout(ctrl_row)
        layout.addWidget(ctrl_card)

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
        self._header.set_badge("OFF AIR", "neutral")

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
        self._track_lbl.setStyleSheet(
            f"color: {COLORS['accent_aqua']}; font-size: 13px; font-weight: 600;"
        )
        self._header.set_badge("LIVE", "aqua")
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
        self._header.set_badge("PAUSED" if self._paused else "LIVE", "gold" if self._paused else "aqua")

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
            self._track_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px;")
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
    apply_app_theme(app)
    win = LeonidaRadioApp()
    app.aboutToQuit.connect(win._stop_playback)
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
