#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) — Vice Vault.
Real OpenSSL AES-256-CBC (-pbkdf2) file encryptor/decryptor combined with a
cryptographically secure (secrets) password and passphrase generator with
combinatorial entropy meter and clipboard copy.
"""

import math
import os
import secrets
import shutil
import signal
import string
import subprocess
import sys

from PyQt5.QtCore import QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QIcon, QPixmap
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QRadioButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget
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

WORDLIST = (
    "anchor", "atlas", "aurora", "badge", "bayfront", "beacon", "breeze", "bridge",
    "canyon", "carbon", "casino", "cipher", "circuit", "cobalt", "comet", "coral",
    "cosmos", "courier", "crescent", "crimson", "crown", "cruise", "crystal", "cyber",
    "dagger", "delta", "desert", "diamond", "dolphin", "drift", "dune", "eclipse",
    "emerald", "ember", "empire", "enigma", "falcon", "fathom", "flamingo", "flash",
    "flint", "fortress", "fusion", "galaxy", "glacier", "gold", "granite", "harbor",
    "haven", "hawk", "horizon", "hunter", "ignite", "island", "jade", "jaguar",
    "jetstream", "keywest", "kinetic", "lagoon", "laser", "leonida", "liberty", "lunar",
    "magnet", "mamba", "mango", "marina", "matrix", "mercury", "meteor", "mirage",
    "monsoon", "neon", "nexus", "night", "nova", "oasis", "obsidian", "ocean",
    "onyx", "orbit", "orchid", "outrun", "palm", "panther", "paradox", "pearl",
    "phantom", "phoenix", "pier", "pilot", "prism", "pulse", "python", "quantum",
    "quartz", "radar", "radiant", "ranger", "raven", "reef", "retro", "ridge",
    "ripple", "rocket", "ruby", "safari", "sapphire", "saturn", "scarlet", "sector",
    "shadow", "shield", "signal", "silver", "siren", "skyline", "solar", "sonic",
    "spark", "spectrum", "sphinx", "starfish", "stealth", "storm", "summit", "sunset",
    "surge", "synth", "tango", "tempest", "thunder", "tiger", "titan", "torque",
    "tropic", "turbo", "ultra", "vapor", "vector", "velvet", "vertex", "vortex",
)

STYLE = """
QMainWindow, QWidget#RootWidget {
    background-color: #120e1e;
    color: #f4f1fa;
    font-family: "Noto Sans", "Noto Sans CJK JP", "Noto Sans CJK SC", "Noto Sans CJK TC", "Noto Sans CJK KR", "DejaVu Sans", sans-serif;
    font-size: 13px;
}
QFrame#Banner {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #221338, stop:0.6 #331338, stop:1 #152138);
    border: 1px solid #ffd166;
    border-radius: 12px;
}
QTabWidget::pane {
    border: 1px solid #3c2e5e;
    border-radius: 10px;
    background-color: #161126;
}
QTabBar::tab {
    background-color: #1b152e;
    color: #cfc6e6;
    border: 1px solid #322650;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 8px 16px;
    margin-right: 4px;
    font-weight: bold;
}
QTabBar::tab:selected {
    background-color: #321d46;
    color: #ffd166;
    border-color: #ff4da6;
}
QLineEdit, QComboBox, QSpinBox {
    background-color: #1b152e;
    color: #f4f1fa;
    border: 1px solid #3c2e5e;
    border-radius: 8px;
    padding: 8px 10px;
}
QLineEdit:focus {
    border-color: #ffd166;
}
QPushButton {
    background-color: #1f1836;
    color: #ffd166;
    border: 1px solid #ff8a5b;
    border-radius: 8px;
    padding: 8px 14px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #ff8a5b;
    color: #120e1e;
}
QPushButton#PrimaryBtn {
    color: #00e5ff;
    border-color: #00e5ff;
}
QPushButton#PrimaryBtn:hover {
    background-color: #00e5ff;
    color: #120e1e;
}
QProgressBar {
    background-color: #161028;
    border: 1px solid #43346b;
    border-radius: 7px;
    height: 16px;
    text-align: center;
    color: #ffffff;
    font-weight: bold;
}
QProgressBar::chunk {
    border-radius: 6px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #ff4da6, stop:0.5 #ffd166, stop:1 #64ffda);
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
        "/usr/share/icons/hicolor/64x64/apps/vice-tool-vault.png",
        "/usr/share/pixmaps/vice-tool-vault.png",
    ):
        if os.path.isfile(path):
            pm = QPixmap(path)
            if not pm.isNull():
                return QIcon(pm)
    return QIcon.fromTheme("security-high")


class VaultCryptoWorker(QThread):
    """Runs OpenSSL AES-256-CBC (-pbkdf2) off the UI thread cleanly."""
    finished_ok = pyqtSignal(bool, str)

    def __init__(self, encrypt: bool, in_path: str, out_path: str, passphrase: str):
        super().__init__()
        self._encrypt = encrypt
        self._in_path = in_path
        self._out_path = out_path
        self._passphrase = passphrase
        self._proc = None
        self._stopped = False

    def stop(self) -> None:
        self._stopped = True
        if self._proc is not None and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass

    def run(self) -> None:
        openssl_bin = shutil.which("openssl")
        if not openssl_bin:
            self.finished_ok.emit(False, "openssl binary not found. Install package 'openssl'.")
            return

        cmd = [openssl_bin, "enc"]
        if not self._encrypt:
            cmd.append("-d")
        cmd.extend([
            "-aes-256-cbc",
            "-pbkdf2",
            "-iter", "100000",
            "-salt",
            "-in", self._in_path,
            "-out", self._out_path,
            "-pass", "env:VICE_VAULT_PASS",
        ])

        env = os.environ.copy()
        env["VICE_VAULT_PASS"] = self._passphrase

        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            _out, err = self._proc.communicate()
            rc = self._proc.returncode
            if self._stopped:
                if os.path.exists(self._out_path):
                    try:
                        os.unlink(self._out_path)
                    except OSError:
                        pass
                self.finished_ok.emit(False, "Operation cancelled.")
                return
            if rc == 0:
                action = "Encrypted" if self._encrypt else "Decrypted"
                self.finished_ok.emit(True, f"{action} successfully -> {self._out_path}")
            else:
                if os.path.exists(self._out_path):
                    try:
                        os.unlink(self._out_path)
                    except OSError:
                        pass
                err_msg = err.decode("utf-8", errors="replace").strip() or "OpenSSL error (wrong passphrase?)"
                self.finished_ok.emit(False, err_msg)
        except Exception as exc:
            self.finished_ok.emit(False, str(exc))


class ViceVaultApp(QMainWindow):
    """Main window for Vice Vault."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice Vault — AES-256 & Secrets Generator")
        self.resize(820, 560)
        self.setMinimumSize(680, 480)
        icon = _load_app_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)

        self._worker = None
        self._clip_timer = QTimer(self)
        self._clip_timer.setSingleShot(True)
        self._clip_timer.timeout.connect(self._clear_clipboard)

        self._init_ui()
        self._generate_secret()

    def _init_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("RootWidget")
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.setSpacing(12)

        banner = QFrame(root)
        banner.setObjectName("Banner")
        bl = QVBoxLayout(banner)
        bl.setContentsMargins(16, 12, 16, 12)
        title = QLabel("VICE VAULT · AES-256-CBC PBKDF2 & SECRETS LAB", banner)
        title.setStyleSheet("color: #ffd166; font-size: 18px; font-weight: bold; background: transparent;")
        bl.addWidget(title)
        sub = QLabel("OpenSSL file encryption (env-passed key, zero CLI leak) + CSPRNG credential forge", banner)
        sub.setStyleSheet("color: #cfc6e6; font-size: 12px; background: transparent;")
        bl.addWidget(sub)
        layout.addWidget(banner)

        tabs = QTabWidget(root)
        tabs.addTab(self._build_crypto_tab(), "File Encrypt / Decrypt")
        tabs.addTab(self._build_gen_tab(), "Password & Passphrase Lab")
        layout.addWidget(tabs, 1)

    def _build_crypto_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(12)

        mode_row = QHBoxLayout()
        self._enc_radio = QRadioButton("Encrypt File (AES-256-CBC + PBKDF2)")
        self._enc_radio.setChecked(True)
        self._dec_radio = QRadioButton("Decrypt File (.enc)")
        self._enc_radio.toggled.connect(self._on_mode_changed)
        mode_row.addWidget(self._enc_radio)
        mode_row.addWidget(self._dec_radio)
        mode_row.addStretch(1)
        v.addLayout(mode_row)

        in_row = QHBoxLayout()
        self._in_edit = QLineEdit()
        self._in_edit.setPlaceholderText("Select input file...")
        in_row.addWidget(self._in_edit, 1)
        in_btn = QPushButton("Browse Input...")
        in_btn.clicked.connect(self._browse_input)
        in_row.addWidget(in_btn)
        v.addLayout(in_row)

        out_row = QHBoxLayout()
        self._out_edit = QLineEdit()
        self._out_edit.setPlaceholderText("Output file path...")
        out_row.addWidget(self._out_edit, 1)
        out_btn = QPushButton("Save As...")
        out_btn.clicked.connect(self._browse_output)
        out_row.addWidget(out_btn)
        v.addLayout(out_row)

        pw_row = QHBoxLayout()
        self._pass_edit = QLineEdit()
        self._pass_edit.setEchoMode(QLineEdit.Password)
        self._pass_edit.setPlaceholderText("Vault passphrase...")
        pw_row.addWidget(self._pass_edit, 1)

        self._confirm_edit = QLineEdit()
        self._confirm_edit.setEchoMode(QLineEdit.Password)
        self._confirm_edit.setPlaceholderText("Confirm passphrase (for encryption)...")
        pw_row.addWidget(self._confirm_edit, 1)

        self._show_pw_chk = QCheckBox("Show")
        self._show_pw_chk.toggled.connect(self._toggle_pw_visibility)
        pw_row.addWidget(self._show_pw_chk)
        v.addLayout(pw_row)

        act_row = QHBoxLayout()
        self._run_crypto_btn = QPushButton("Encrypt File Now")
        self._run_crypto_btn.setObjectName("PrimaryBtn")
        self._run_crypto_btn.clicked.connect(self._run_crypto)
        act_row.addWidget(self._run_crypto_btn)
        act_row.addStretch(1)
        v.addLayout(act_row)

        self._crypto_status = QLabel("Ready. Passphrases are never passed on command-line arguments.")
        self._crypto_status.setWordWrap(True)
        self._crypto_status.setStyleSheet("color: #cfc6e6;")
        v.addWidget(self._crypto_status)
        v.addStretch(1)
        return w

    def _build_gen_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(12)

        mode_row = QHBoxLayout()
        self._pw_mode = QRadioButton("Random Password")
        self._pw_mode.setChecked(True)
        self._phrase_mode = QRadioButton("Diceware Passphrase")
        self._pw_mode.toggled.connect(self._generate_secret)
        mode_row.addWidget(self._pw_mode)
        mode_row.addWidget(self._phrase_mode)
        mode_row.addStretch(1)
        v.addLayout(mode_row)

        opts_row = QHBoxLayout()
        opts_row.addWidget(QLabel("Length / Words:"))
        self._len_spin = QSpinBox()
        self._len_spin.setRange(4, 64)
        self._len_spin.setValue(20)
        self._len_spin.valueChanged.connect(self._generate_secret)
        opts_row.addWidget(self._len_spin)

        self._chk_upper = QCheckBox("A-Z")
        self._chk_upper.setChecked(True)
        self._chk_lower = QCheckBox("a-z")
        self._chk_lower.setChecked(True)
        self._chk_digits = QCheckBox("0-9")
        self._chk_digits.setChecked(True)
        self._chk_symbols = QCheckBox("!@#$%")
        self._chk_symbols.setChecked(True)
        self._chk_no_ambig = QCheckBox("No 0O1lI")

        for chk in (self._chk_upper, self._chk_lower, self._chk_digits, self._chk_symbols, self._chk_no_ambig):
            chk.toggled.connect(self._generate_secret)
            opts_row.addWidget(chk)

        self._sep_combo = QComboBox()
        self._sep_combo.addItems(["-", "_", ".", " "])
        self._sep_combo.currentIndexChanged.connect(self._generate_secret)
        opts_row.addWidget(QLabel("Sep:"))
        opts_row.addWidget(self._sep_combo)
        opts_row.addStretch(1)
        v.addLayout(opts_row)

        out_row = QHBoxLayout()
        self._gen_output = QLineEdit()
        self._gen_output.setReadOnly(True)
        self._gen_output.setStyleSheet(
            "font-family: 'Noto Sans Mono CJK JP', 'DejaVu Sans Mono', monospace; "
            "font-size: 15px; color: #00e5ff; font-weight: bold; padding: 10px;"
        )
        out_row.addWidget(self._gen_output, 1)

        regen_btn = QPushButton("Regenerate")
        regen_btn.clicked.connect(self._generate_secret)
        out_row.addWidget(regen_btn)

        copy_btn = QPushButton("Copy (30s Clear)")
        copy_btn.setObjectName("PrimaryBtn")
        copy_btn.clicked.connect(self._copy_generated)
        out_row.addWidget(copy_btn)
        v.addLayout(out_row)

        self._entropy_bar = QProgressBar()
        self._entropy_bar.setRange(0, 160)
        self._entropy_bar.setFormat("Entropy: %v bits")
        v.addWidget(self._entropy_bar)

        self._entropy_lbl = QLabel("")
        self._entropy_lbl.setStyleSheet("color: #ffd166; font-weight: bold;")
        v.addWidget(self._entropy_lbl)
        v.addStretch(1)
        return w

    def _on_mode_changed(self) -> None:
        enc = self._enc_radio.isChecked()
        self._confirm_edit.setEnabled(enc)
        self._run_crypto_btn.setText("Encrypt File Now" if enc else "Decrypt File Now")
        self._suggest_output_path()

    def _suggest_output_path(self) -> None:
        in_path = self._in_edit.text().strip()
        if not in_path:
            return
        if self._enc_radio.isChecked():
            if not in_path.endswith(".enc"):
                self._out_edit.setText(in_path + ".enc")
        else:
            if in_path.endswith(".enc"):
                self._out_edit.setText(in_path[:-4])
            else:
                self._out_edit.setText(in_path + ".dec")

    def _browse_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select File", os.path.expanduser("~"))
        if path:
            self._in_edit.setText(path)
            self._suggest_output_path()

    def _browse_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Output File", self._out_edit.text() or os.path.expanduser("~"))
        if path:
            self._out_edit.setText(path)

    def _toggle_pw_visibility(self, show: bool) -> None:
        mode = QLineEdit.Normal if show else QLineEdit.Password
        self._pass_edit.setEchoMode(mode)
        self._confirm_edit.setEchoMode(mode)

    def _run_crypto(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        encrypt = self._enc_radio.isChecked()
        in_path = self._in_edit.text().strip()
        out_path = self._out_edit.text().strip()
        pw = self._pass_edit.text()

        if not in_path or not os.path.isfile(in_path):
            QMessageBox.warning(self, "Input Error", "Select an existing input file.")
            return
        if not out_path:
            QMessageBox.warning(self, "Output Error", "Specify an output file path.")
            return
        if os.path.abspath(in_path) == os.path.abspath(out_path):
            QMessageBox.warning(self, "Path Error", "Input and output paths must be different.")
            return
        if not pw:
            QMessageBox.warning(self, "Passphrase Required", "Enter a vault passphrase.")
            return
        if encrypt and pw != self._confirm_edit.text():
            QMessageBox.warning(self, "Mismatch", "Passphrases do not match.")
            return

        self._run_crypto_btn.setEnabled(False)
        self._crypto_status.setText("Processing with OpenSSL AES-256-CBC (-pbkdf2)...")
        self._worker = VaultCryptoWorker(encrypt, in_path, out_path, pw)
        self._worker.finished_ok.connect(self._on_crypto_done)
        self._worker.start()

    def _on_crypto_done(self, ok: bool, msg: str) -> None:
        self._run_crypto_btn.setEnabled(True)
        color = "#64ffda" if ok else "#ff6b8b"
        self._crypto_status.setStyleSheet(f"color: {color}; font-weight: bold;")
        self._crypto_status.setText(msg)
        if ok:
            log_info(msg)
        else:
            log_error(msg)

    def _generate_secret(self) -> None:
        if self._phrase_mode.isChecked():
            words_n = max(3, min(12, self._len_spin.value()))
            if self._len_spin.value() > 12:
                self._len_spin.blockSignals(True)
                self._len_spin.setValue(6)
                self._len_spin.blockSignals(False)
                words_n = 6
            sep = self._sep_combo.currentText()
            chosen = [secrets.choice(WORDLIST).capitalize() for _ in range(words_n)]
            num = str(secrets.randbelow(90) + 10)
            secret_val = sep.join(chosen) + sep + num
            bits = words_n * math.log2(len(WORDLIST)) + math.log2(90)
        else:
            length = max(8, self._len_spin.value())
            if self._len_spin.value() < 8:
                self._len_spin.blockSignals(True)
                self._len_spin.setValue(16)
                self._len_spin.blockSignals(False)
                length = 16

            ambig = set("0O1lI") if self._chk_no_ambig.isChecked() else set()
            groups = []
            if self._chk_upper.isChecked():
                groups.append("".join(c for c in string.ascii_uppercase if c not in ambig))
            if self._chk_lower.isChecked():
                groups.append("".join(c for c in string.ascii_lowercase if c not in ambig))
            if self._chk_digits.isChecked():
                groups.append("".join(c for c in string.digits if c not in ambig))
            if self._chk_symbols.isChecked():
                groups.append("!@#$%^&*()-_=+[]{}?")

            groups = [g for g in groups if g]
            if not groups:
                groups = [string.ascii_lowercase]
            pool = "".join(groups)
            chars = [secrets.choice(g) for g in groups[:length]]
            while len(chars) < length:
                chars.append(secrets.choice(pool))
            secrets.SystemRandom().shuffle(chars)
            secret_val = "".join(chars)
            bits = length * math.log2(len(set(pool)))

        bits_int = int(round(bits))
        self._gen_output.setText(secret_val)
        self._entropy_bar.setValue(min(160, bits_int))
        if bits_int >= 110:
            tier = "Leonida Fort Knox"
        elif bits_int >= 75:
            tier = "Strong"
        elif bits_int >= 50:
            tier = "Moderate"
        else:
            tier = "Weak"
        self._entropy_lbl.setText(f"Estimated Entropy: {bits_int} bits — Rating: {tier}")

    def _copy_generated(self) -> None:
        text = self._gen_output.text()
        if not text:
            return
        QApplication.clipboard().setText(text)
        self._clip_timer.start(30000)
        self._entropy_lbl.setText(self._entropy_lbl.text().split(" (Copied")[0] + " (Copied — auto-clears in 30s)")

    def _clear_clipboard(self) -> None:
        cb = QApplication.clipboard()
        if cb.text() == self._gen_output.text():
            cb.clear()

    def closeEvent(self, event) -> None:
        self._clip_timer.stop()
        if self._worker is not None:
            self._worker.stop()
            if self._worker.isRunning():
                self._worker.wait(2000)
        event.accept()


def main() -> None:
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    _configure_cjk_fonts(app)
    app.setStyleSheet(STYLE)
    win = ViceVaultApp()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
