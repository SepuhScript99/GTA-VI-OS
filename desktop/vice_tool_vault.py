#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) — Vice Vault.
Real OpenSSL AES-256-CBC (-pbkdf2) file encryptor/decryptor combined with a
cryptographically secure (secrets) password and passphrase generator with
combinatorial entropy meter and clipboard auto-clear.
Styled via vice_theme (Noto Sans CJK fallback).
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
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar,
    QRadioButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget
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
)

try:
    from python.vice_utils import log_error, log_info  # noqa: E402
except ImportError:
    def log_info(msg: str) -> None:
        print(f"[INFO] {msg}")

    def log_error(msg: str) -> None:
        print(f"[ERROR] {msg}", file=sys.stderr)


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
        self.setWindowTitle("Vice Vault — Vice OS")
        self.resize(840, 580)
        self.setMinimumSize(680, 480)
        icon = load_tool_icon("vice-tool-vault", "security-high")
        if not icon.isNull():
            self.setWindowIcon(icon)

        self._worker = None
        self._pw_len_cache = 20
        self._phrase_words_cache = 6
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

        header = make_header(
            title="Vice Vault",
            subtitle="OpenSSL AES-256-CBC PBKDF2 file encryption & CSPRNG secrets generator",
            icon_name="vice-tool-vault",
            badge_text="AES-256-CBC",
            badge_variant="gold",
            parent=root,
        )
        layout.addWidget(header)

        tabs = QTabWidget(root)
        tabs.addTab(self._build_crypto_tab(), "File Encrypt / Decrypt")
        tabs.addTab(self._build_gen_tab(), "Password && Passphrase Lab")
        layout.addWidget(tabs, 1)

    def _build_crypto_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(12)

        mode_card = make_card(title="Operation Mode", parent=w)
        mode_row = QHBoxLayout()
        self._enc_radio = QRadioButton("Encrypt File (AES-256-CBC + PBKDF2)")
        self._enc_radio.setChecked(True)
        self._dec_radio = QRadioButton("Decrypt File (.enc)")
        self._enc_radio.toggled.connect(self._on_mode_changed)
        mode_row.addWidget(self._enc_radio)
        mode_row.addWidget(self._dec_radio)
        mode_row.addStretch(1)
        mode_card.body_layout.addLayout(mode_row)
        v.addWidget(mode_card)

        files_card = make_card(title="Files & Passphrase", parent=w)
        in_row = QHBoxLayout()
        in_row.setSpacing(8)
        self._in_edit = QLineEdit()
        self._in_edit.setPlaceholderText("Select input file...")
        in_row.addWidget(self._in_edit, 1)
        in_btn = make_button("Browse Input...", variant="secondary")
        in_btn.clicked.connect(self._browse_input)
        in_row.addWidget(in_btn)
        files_card.body_layout.addLayout(in_row)

        out_row = QHBoxLayout()
        out_row.setSpacing(8)
        self._out_edit = QLineEdit()
        self._out_edit.setPlaceholderText("Output file path...")
        out_row.addWidget(self._out_edit, 1)
        out_btn = make_button("Save As...", variant="secondary")
        out_btn.clicked.connect(self._browse_output)
        out_row.addWidget(out_btn)
        files_card.body_layout.addLayout(out_row)

        pw_row = QHBoxLayout()
        pw_row.setSpacing(8)
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
        files_card.body_layout.addLayout(pw_row)
        v.addWidget(files_card)

        act_row = QHBoxLayout()
        self._run_crypto_btn = make_button("Encrypt File Now", variant="primary")
        self._run_crypto_btn.clicked.connect(self._run_crypto)
        act_row.addWidget(self._run_crypto_btn)
        act_row.addStretch(1)
        v.addLayout(act_row)

        self._crypto_status = QLabel("Ready. Passphrases are passed via environment variable, never CLI args.")
        self._crypto_status.setWordWrap(True)
        self._crypto_status.setObjectName("MutedLabel")
        v.addWidget(self._crypto_status)
        v.addStretch(1)
        return w

    def _build_gen_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(12)

        opts_card = make_card(title="Generator Options", parent=w)
        mode_row = QHBoxLayout()
        self._pw_mode = QRadioButton("Random Password")
        self._pw_mode.setChecked(True)
        self._phrase_mode = QRadioButton("Diceware Passphrase")
        self._pw_mode.toggled.connect(self._on_gen_mode_toggled)
        mode_row.addWidget(self._pw_mode)
        mode_row.addWidget(self._phrase_mode)
        mode_row.addStretch(1)
        opts_card.body_layout.addLayout(mode_row)

        opts_row = QHBoxLayout()
        opts_row.setSpacing(8)
        self._len_title = QLabel("Length:")
        opts_row.addWidget(self._len_title)
        self._len_spin = QSpinBox()
        self._len_spin.setRange(8, 64)
        self._len_spin.setValue(self._pw_len_cache)
        self._len_spin.valueChanged.connect(self._on_spin_changed)
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

        self._sep_lbl = QLabel("Sep:")
        self._sep_combo = QComboBox()
        self._sep_combo.addItems(["-", "_", ".", " "])
        self._sep_combo.currentIndexChanged.connect(self._generate_secret)
        self._sep_lbl.setVisible(False)
        self._sep_combo.setVisible(False)
        opts_row.addWidget(self._sep_lbl)
        opts_row.addWidget(self._sep_combo)
        opts_row.addStretch(1)
        opts_card.body_layout.addLayout(opts_row)
        v.addWidget(opts_card)

        out_card = make_card(title="Generated Credential", parent=w)
        out_row = QHBoxLayout()
        out_row.setSpacing(8)
        self._gen_output = QLineEdit()
        self._gen_output.setReadOnly(True)
        self._gen_output.setStyleSheet(
            f"font-family: {MONO_STACK}; font-size: 15px; color: {COLORS['accent_aqua']}; "
            f"font-weight: bold; padding: 10px;"
        )
        out_row.addWidget(self._gen_output, 1)

        regen_btn = make_button("Regenerate", variant="secondary")
        regen_btn.clicked.connect(self._generate_secret)
        out_row.addWidget(regen_btn)

        copy_btn = make_button("Copy (30s Clear)", variant="primary")
        copy_btn.clicked.connect(self._copy_generated)
        out_row.addWidget(copy_btn)
        out_card.body_layout.addLayout(out_row)

        self._entropy_bar = QProgressBar()
        self._entropy_bar.setRange(0, 160)
        self._entropy_bar.setFormat("Entropy: %v bits")
        out_card.body_layout.addWidget(self._entropy_bar)

        self._entropy_lbl = QLabel("")
        self._entropy_lbl.setStyleSheet(f"color: {COLORS['accent_gold']}; font-weight: bold;")
        out_card.body_layout.addWidget(self._entropy_lbl)
        v.addWidget(out_card)
        v.addStretch(1)
        return w

    def _on_gen_mode_toggled(self) -> None:
        is_phrase = self._phrase_mode.isChecked()
        for chk in (self._chk_upper, self._chk_lower, self._chk_digits, self._chk_symbols, self._chk_no_ambig):
            chk.setVisible(not is_phrase)
        self._sep_lbl.setVisible(is_phrase)
        self._sep_combo.setVisible(is_phrase)

        self._len_spin.blockSignals(True)
        if is_phrase:
            self._len_title.setText("Words:")
            self._len_spin.setRange(3, 12)
            self._len_spin.setValue(self._phrase_words_cache)
        else:
            self._len_title.setText("Length:")
            self._len_spin.setRange(8, 64)
            self._len_spin.setValue(self._pw_len_cache)
        self._len_spin.blockSignals(False)
        self._generate_secret()

    def _on_spin_changed(self, value: int) -> None:
        if self._phrase_mode.isChecked():
            self._phrase_words_cache = value
        else:
            self._pw_len_cache = value
        self._generate_secret()

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
        self._crypto_status.setStyleSheet(f"color: {COLORS['text_secondary']};")
        self._crypto_status.setText("Processing with OpenSSL AES-256-CBC (-pbkdf2)...")
        self._worker = VaultCryptoWorker(encrypt, in_path, out_path, pw)
        self._worker.finished_ok.connect(self._on_crypto_done)
        self._worker.start()

    def _on_crypto_done(self, ok: bool, msg: str) -> None:
        self._run_crypto_btn.setEnabled(True)
        color = COLORS["success"] if ok else COLORS["danger"]
        self._crypto_status.setStyleSheet(f"color: {color}; font-weight: bold;")
        self._crypto_status.setText(msg)
        if ok:
            log_info(msg)
        else:
            log_error(msg)

    def _generate_secret(self) -> None:
        if self._phrase_mode.isChecked():
            words_n = max(3, min(12, self._len_spin.value()))
            sep = self._sep_combo.currentText()
            chosen = [secrets.choice(WORDLIST).capitalize() for _ in range(words_n)]
            num = str(secrets.randbelow(90) + 10)
            secret_val = sep.join(chosen) + sep + num
            bits = words_n * math.log2(len(WORDLIST)) + math.log2(90)
        else:
            length = max(8, self._len_spin.value())
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
            tier = "Fortress"
        elif bits_int >= 75:
            tier = "Strong"
        elif bits_int >= 50:
            tier = "Moderate"
        else:
            tier = "Weak"
        self._entropy_lbl.setText(f"Estimated Entropy: {bits_int} bits · Rating: {tier}")

    def _copy_generated(self) -> None:
        text = self._gen_output.text()
        if not text:
            return
        QApplication.clipboard().setText(text)
        self._clip_timer.start(30000)
        base = self._entropy_lbl.text().split(" (Copied")[0]
        self._entropy_lbl.setText(base + " (Copied — clears in 30s)")

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
    apply_app_theme(app)
    win = ViceVaultApp()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
