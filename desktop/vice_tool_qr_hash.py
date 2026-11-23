#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) — Vice QR & Dev Lab.
Real QR code generator (qrencode with pure-Python + Pillow fallback),
SHA256/SHA512/MD5/SHA1 text and file hash verifier, Base64/URL/Hex
encoder-decoder, and JSON formatter & validator.
"""

import base64
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import urllib.parse

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QIcon, QPixmap
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar,
    QPushButton, QTabWidget, QVBoxLayout, QWidget
)

try:
    from PIL import Image
except ImportError:
    Image = None

sys.path.insert(0, "/opt/vice-os/lib")

try:
    from python.vice_utils import log_info  # noqa: E402
except ImportError:
    def log_info(msg: str) -> None:
        print(f"[INFO] {msg}")


CJK_FONTS = [
    "Noto Sans",
    "Noto Sans CJK JP",
    "Noto Sans CJK SC",
    "Noto Sans CJK TC",
    "Noto Sans CJK KR",
    "DejaVu Sans",
]

# Single-block Level-L Byte-mode capacity table: (version, size, data_cw, ec_cw, align_pos)
_QR_VER_SPECS = [
    (1, 21, 19, 7, []),
    (2, 25, 34, 10, [6, 18]),
    (3, 29, 55, 15, [6, 22]),
    (4, 33, 80, 20, [6, 26]),
]
# Precomputed BCH(15,5) format string for Level L (01), Mask 0 (000) -> 0x77c4 (MSB first)
_QR_FORMAT_L_M0 = 0b111011111000100

STYLE = """
QMainWindow, QWidget#RootWidget {
    background-color: #120e1e;
    color: #f4f1fa;
    font-family: "Noto Sans", "Noto Sans CJK JP", "Noto Sans CJK SC", "Noto Sans CJK TC", "Noto Sans CJK KR", "DejaVu Sans", sans-serif;
    font-size: 13px;
}
QFrame#Banner {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #1d1433, stop:0.6 #2e153d, stop:1 #14243b);
    border: 1px solid #00e5ff;
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
    padding: 8px 14px;
    margin-right: 4px;
    font-weight: bold;
}
QTabBar::tab:selected {
    background-color: #2f1d45;
    color: #00e5ff;
    border-color: #ff4da6;
}
QLineEdit, QComboBox {
    background-color: #1b152e;
    color: #f4f1fa;
    border: 1px solid #3c2e5e;
    border-radius: 8px;
    padding: 7px 10px;
}
QPlainTextEdit {
    background-color: #0d0a18;
    color: #e4ddfa;
    border: 1px solid #382b57;
    border-radius: 8px;
    font-family: "Noto Sans Mono CJK JP", "Noto Sans Mono CJK SC", "DejaVu Sans Mono", monospace;
    font-size: 12px;
    padding: 8px;
}
QPushButton {
    background-color: #1f1836;
    color: #00e5ff;
    border: 1px solid #00e5ff;
    border-radius: 8px;
    padding: 7px 12px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #00e5ff;
    color: #120e1e;
}
QPushButton#AccentBtn {
    color: #ffd166;
    border-color: #ff4da6;
}
QPushButton#AccentBtn:hover {
    background-color: #ff4da6;
    color: #120e1e;
}
QProgressBar {
    background-color: #151026;
    border: 1px solid #43346b;
    border-radius: 6px;
    height: 14px;
    text-align: center;
    color: #ffffff;
    font-weight: bold;
}
QProgressBar::chunk {
    border-radius: 5px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff4da6, stop:1 #00e5ff);
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
        "/usr/share/icons/hicolor/64x64/apps/vice-tool-qr-hash.png",
        "/usr/share/pixmaps/vice-tool-qr-hash.png",
    ):
        if os.path.isfile(path):
            pm = QPixmap(path)
            if not pm.isNull():
                return QIcon(pm)
    return QIcon.fromTheme("accessories-calculator")


def _gf_mul(a: int, b: int) -> int:
    res = 0
    while b:
        if b & 1:
            res ^= a
        a <<= 1
        if a & 0x100:
            a ^= 0x11D
        b >>= 1
    return res


def _rs_ec_bytes(data: list, ec_count: int) -> list:
    gen = [1]
    for i in range(ec_count):
        alpha = 1
        for _ in range(i):
            alpha = _gf_mul(alpha, 2)
        nxt = [0] * (len(gen) + 1)
        for j, coef in enumerate(gen):
            nxt[j] ^= coef
            nxt[j + 1] ^= _gf_mul(coef, alpha)
        gen = nxt
    rem = list(data) + [0] * ec_count
    for i in range(len(data)):
        factor = rem[i]
        if factor:
            for j in range(1, len(gen)):
                rem[i + j] ^= _gf_mul(gen[j], factor)
    return rem[len(data):]


def build_qr_matrix(payload: str) -> list:
    """Pure-Python ISO-18004 Level-L Byte-mode QR matrix (Version 1-4, <=78 bytes)."""
    raw = payload.encode("utf-8")
    spec = None
    for ver, size, data_cw, ec_cw, aligns in _QR_VER_SPECS:
        if len(raw) + 2 <= data_cw:
            spec = (ver, size, data_cw, ec_cw, aligns)
            break
    if spec is None:
        raise ValueError("Payload exceeds pure-Python QR fallback limit (78 bytes); install qrencode.")

    _ver, size, data_cw, ec_cw, aligns = spec
    bits = []

    def push_bits(val: int, width: int) -> None:
        for shift in range(width - 1, -1, -1):
            bits.append((val >> shift) & 1)

    push_bits(0b0100, 4)  # Byte mode
    push_bits(len(raw), 8)
    for b in raw:
        push_bits(b, 8)
    max_bits = data_cw * 8
    push_bits(0, min(4, max_bits - len(bits)))
    while len(bits) % 8:
        bits.append(0)
    codewords = [
        int("".join(str(b) for b in bits[i:i + 8]), 2)
        for i in range(0, len(bits), 8)
    ]
    pad_bytes = (0xEC, 0x11)
    idx = 0
    while len(codewords) < data_cw:
        codewords.append(pad_bytes[idx % 2])
        idx += 1

    all_cw = codewords + _rs_ec_bytes(codewords, ec_cw)
    all_bits = []
    for cw in all_cw:
        for shift in range(7, -1, -1):
            all_bits.append((cw >> shift) & 1)

    grid = [[None] * size for _ in range(size)]
    func = [[False] * size for _ in range(size)]

    def set_mod(r: int, c: int, val: int, is_func: bool = True) -> None:
        grid[r][c] = val
        if is_func:
            func[r][c] = True

    def place_finder(r0: int, c0: int) -> None:
        for dr in range(-1, 8):
            for dc in range(-1, 8):
                rr, cc = r0 + dr, c0 + dc
                if 0 <= rr < size and 0 <= cc < size:
                    in_outer = 0 <= dr <= 6 and 0 <= dc <= 6
                    on_border = dr in (0, 6) or dc in (0, 6)
                    in_core = 2 <= dr <= 4 and 2 <= dc <= 4
                    set_mod(rr, cc, 1 if (in_outer and (on_border or in_core)) else 0)

    place_finder(0, 0)
    place_finder(0, size - 7)
    place_finder(size - 7, 0)

    if aligns:
        for ar in aligns:
            for ac in aligns:
                if func[ar][ac]:
                    continue
                for dr in range(-2, 3):
                    for dc in range(-2, 3):
                        val = 1 if (max(abs(dr), abs(dc)) == 2 or (dr == 0 and dc == 0)) else 0
                        set_mod(ar + dr, ac + dc, val)

    for i in range(8, size - 8):
        if not func[6][i]:
            set_mod(6, i, 1 if i % 2 == 0 else 0)
        if not func[i][6]:
            set_mod(i, 6, 1 if i % 2 == 0 else 0)

    set_mod(size - 8, 8, 1)  # Dark module

    # Reserve format info cells
    for i in range(9):
        if i != 6:
            func[8][i] = True
            func[i][8] = True
    for i in range(size - 8, size):
        func[8][i] = True
    for i in range(size - 7, size):
        func[i][8] = True

    # Place data bits in standard upward/downward zig-zag
    bit_i = 0
    col = size - 1
    up = True
    while col > 0:
        if col == 6:
            col -= 1
        rows = range(size - 1, -1, -1) if up else range(size)
        for r in rows:
            for dc in (0, -1):
                c = col + dc
                if not func[r][c]:
                    b = all_bits[bit_i] if bit_i < len(all_bits) else 0
                    bit_i += 1
                    # Mask 0: (r + c) % 2 == 0
                    if (r + c) % 2 == 0:
                        b ^= 1
                    grid[r][c] = b
        up = not up
        col -= 2

    # Write format info (Level L, Mask 0)
    for i in range(15):
        bit = (_QR_FORMAT_L_M0 >> i) & 1
        if i < 6:
            grid[i][8] = bit
        elif i < 8:
            grid[i + 1][8] = bit
        else:
            grid[size - 15 + i][8] = bit

        if i < 8:
            grid[8][size - 1 - i] = bit
        elif i < 9:
            grid[8][15 - i] = bit
        else:
            grid[8][14 - i] = bit

    return grid


class FileHashWorker(QThread):
    """Computes MD5, SHA1, SHA256, SHA512 of a file in chunks off the UI thread."""
    progress = pyqtSignal(int)
    done = pyqtSignal(dict, str)

    def __init__(self, path: str):
        super().__init__()
        self._path = path
        self._stopped = False

    def stop(self) -> None:
        self._stopped = True

    def run(self) -> None:
        try:
            total = os.path.getsize(self._path)
            algos = {
                "md5": hashlib.md5(),
                "sha1": hashlib.sha1(),
                "sha256": hashlib.sha256(),
                "sha512": hashlib.sha512(),
            }
            done_bytes = 0
            with open(self._path, "rb") as fp:
                while not self._stopped:
                    chunk = fp.read(1048576)
                    if not chunk:
                        break
                    for h in algos.values():
                        h.update(chunk)
                    done_bytes += len(chunk)
                    if total > 0:
                        self.progress.emit(int((done_bytes / total) * 100))
            if self._stopped:
                return
            digests = {k: h.hexdigest() for k, h in algos.items()}
            self.done.emit(digests, "")
        except Exception as exc:
            self.done.emit({}, str(exc))


class ViceQrHashApp(QMainWindow):
    """Main window for Vice QR & Dev Lab."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice QR & Dev Lab — Leonida Toolkit")
        self.resize(900, 640)
        self.setMinimumSize(720, 520)
        icon = _load_app_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)

        self._hash_worker = None
        self._qr_png_path = None
        self._init_ui()
        self._generate_qr()
        self._hash_text_now()

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
        title = QLabel("VICE QR & DEV LAB · ENCODE, HASH & VALIDATE", banner)
        title.setStyleSheet("color: #ffd166; font-size: 18px; font-weight: bold; background: transparent;")
        bl.addWidget(title)
        sub = QLabel("QR Generator · SHA256/SHA512/MD5 File & Text Verifier · Base64/URL/Hex · JSON Lab", banner)
        sub.setStyleSheet("color: #cfc6e6; font-size: 12px; background: transparent;")
        bl.addWidget(sub)
        layout.addWidget(banner)

        tabs = QTabWidget(root)
        tabs.addTab(self._build_qr_tab(), "QR Code Studio")
        tabs.addTab(self._build_hash_tab(), "Hash & Integrity")
        tabs.addTab(self._build_codec_tab(), "Base64 / URL / Hex")
        tabs.addTab(self._build_json_tab(), "JSON Formatter")
        layout.addWidget(tabs, 1)

    def _build_qr_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(12)

        in_row = QHBoxLayout()
        self._qr_input = QLineEdit("https://vice-os.local")
        self._qr_input.setPlaceholderText("Text, URL, or Wi-Fi URI (WIFI:T:WPA;S:SSID;P:PASS;;)...")
        self._qr_input.textChanged.connect(self._generate_qr)
        in_row.addWidget(self._qr_input, 1)

        self._qr_style = QComboBox()
        self._qr_style.addItems(["Classic (Black / White)", "Leonida Neon (Cyan / Midnight)"])
        self._qr_style.currentIndexChanged.connect(self._generate_qr)
        in_row.addWidget(self._qr_style)

        gen_btn = QPushButton("Generate")
        gen_btn.clicked.connect(self._generate_qr)
        in_row.addWidget(gen_btn)
        v.addLayout(in_row)

        mid = QHBoxLayout()
        self._qr_preview = QLabel("QR Preview")
        self._qr_preview.setFixedSize(280, 280)
        self._qr_preview.setAlignment(Qt.AlignCenter)
        self._qr_preview.setStyleSheet("background: #ffffff; border: 2px solid #00e5ff; border-radius: 10px;")
        mid.addWidget(self._qr_preview)

        side = QVBoxLayout()
        self._qr_info = QLabel("Ready.")
        self._qr_info.setWordWrap(True)
        side.addWidget(self._qr_info)

        save_btn = QPushButton("Save QR PNG...")
        save_btn.setObjectName("AccentBtn")
        save_btn.clicked.connect(self._save_qr_png)
        side.addWidget(save_btn)

        copy_img_btn = QPushButton("Copy QR Image")
        copy_img_btn.clicked.connect(self._copy_qr_image)
        side.addWidget(copy_img_btn)
        side.addStretch(1)
        mid.addLayout(side, 1)
        v.addLayout(mid, 1)
        return w

    def _build_hash_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(10)

        txt_row = QHBoxLayout()
        self._hash_text_in = QLineEdit()
        self._hash_text_in.setPlaceholderText("Type text to hash instantly, OR pick a file below...")
        self._hash_text_in.textChanged.connect(self._hash_text_now)
        txt_row.addWidget(self._hash_text_in, 1)

        file_btn = QPushButton("Hash File...")
        file_btn.setObjectName("AccentBtn")
        file_btn.clicked.connect(self._pick_hash_file)
        txt_row.addWidget(file_btn)
        v.addLayout(txt_row)

        self._hash_progress = QProgressBar()
        self._hash_progress.setRange(0, 100)
        v.addWidget(self._hash_progress)

        grid = QGridLayout()
        grid.setSpacing(8)
        self._digest_fields = {}
        for idx, algo in enumerate(("sha256", "sha512", "sha1", "md5")):
            lbl = QLabel(algo.upper() + ":")
            lbl.setStyleSheet("color: #ff8a5b; font-weight: bold;")
            fld = QLineEdit()
            fld.setReadOnly(True)
            fld.setStyleSheet("font-family: 'Noto Sans Mono CJK JP', 'DejaVu Sans Mono', monospace;")
            cpy = QPushButton("Copy")
            cpy.clicked.connect(lambda _=False, f=fld: QApplication.clipboard().setText(f.text()))
            grid.addWidget(lbl, idx, 0)
            grid.addWidget(fld, idx, 1)
            grid.addWidget(cpy, idx, 2)
            self._digest_fields[algo] = fld
        v.addLayout(grid)

        cmp_row = QHBoxLayout()
        cmp_row.addWidget(QLabel("Expected:"))
        self._expected_edit = QLineEdit()
        self._expected_edit.setPlaceholderText("Paste expected MD5/SHA1/SHA256/SHA512 to verify...")
        self._expected_edit.textChanged.connect(self._verify_expected)
        cmp_row.addWidget(self._expected_edit, 1)

        self._verify_lbl = QLabel("Waiting for expected digest")
        self._verify_lbl.setStyleSheet("color: #cfc6e6; font-weight: bold;")
        cmp_row.addWidget(self._verify_lbl)
        v.addLayout(cmp_row)
        v.addStretch(1)
        return w

    def _build_codec_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(10)

        self._codec_in = QPlainTextEdit()
        self._codec_in.setPlaceholderText("Input text...")
        v.addWidget(self._codec_in, 1)

        btns = QHBoxLayout()
        actions = [
            ("Base64 Encode", lambda t: base64.b64encode(t.encode("utf-8")).decode("ascii")),
            ("Base64 Decode", lambda t: base64.b64decode(t.strip()).decode("utf-8", errors="replace")),
            ("URL Encode", lambda t: urllib.parse.quote(t, safe="")),
            ("URL Decode", lambda t: urllib.parse.unquote(t)),
            ("Hex Encode", lambda t: t.encode("utf-8").hex()),
            ("Hex Decode", lambda t: bytes.fromhex(t.strip()).decode("utf-8", errors="replace")),
        ]
        for label, fn in actions:
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, func=fn: self._run_codec(func))
            btns.addWidget(b)

        swap_btn = QPushButton("Swap")
        swap_btn.setObjectName("AccentBtn")
        swap_btn.clicked.connect(self._swap_codec)
        btns.addWidget(swap_btn)
        v.addLayout(btns)

        self._codec_out = QPlainTextEdit()
        self._codec_out.setReadOnly(True)
        self._codec_out.setPlaceholderText("Transformed output...")
        v.addWidget(self._codec_out, 1)
        return w

    def _build_json_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(10)

        self._json_edit = QPlainTextEdit('{\n  "os": "GTA VI OS",\n  "theme": "Leonida Neon",\n  "batch": 1\n}')
        v.addWidget(self._json_edit, 1)

        row = QHBoxLayout()
        fmt_btn = QPushButton("Format (2-Space)")
        fmt_btn.clicked.connect(lambda: self._process_json(minify=False, sort_keys=False))
        row.addWidget(fmt_btn)

        sort_btn = QPushButton("Format + Sort Keys")
        sort_btn.clicked.connect(lambda: self._process_json(minify=False, sort_keys=True))
        row.addWidget(sort_btn)

        min_btn = QPushButton("Minify")
        min_btn.clicked.connect(lambda: self._process_json(minify=True, sort_keys=False))
        row.addWidget(min_btn)

        cpy_btn = QPushButton("Copy JSON")
        cpy_btn.setObjectName("AccentBtn")
        cpy_btn.clicked.connect(lambda: QApplication.clipboard().setText(self._json_edit.toPlainText()))
        row.addWidget(cpy_btn)
        row.addStretch(1)
        v.addLayout(row)

        self._json_status = QLabel("Valid JSON ready.")
        self._json_status.setStyleSheet("color: #64ffda; font-weight: bold;")
        v.addWidget(self._json_status)
        return w

    def _generate_qr(self) -> None:
        text = self._qr_input.text()
        if not text:
            self._qr_preview.clear()
            self._qr_info.setText("Enter text or URL to generate a QR code.")
            return

        neon = self._qr_style.currentIndex() == 1
        fg = "#00e5ff" if neon else "#000000"
        bg = "#120e1e" if neon else "#ffffff"

        if self._qr_png_path and os.path.exists(self._qr_png_path):
            try:
                os.unlink(self._qr_png_path)
            except OSError:
                pass
        fd, out_png = tempfile.mkstemp(prefix="vice_qr_", suffix=".png")
        os.close(fd)
        self._qr_png_path = out_png

        qrencode_bin = shutil.which("qrencode")
        if qrencode_bin:
            cmd = [
                qrencode_bin, "-o", out_png, "-s", "10", "-m", "2",
                "--foreground", fg.lstrip("#"), "--background", bg.lstrip("#"),
                text,
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0 and os.path.isfile(out_png):
                pm = QPixmap(out_png)
                self._qr_preview.setPixmap(pm.scaled(268, 268, Qt.KeepAspectRatio, Qt.FastTransformation))
                self._qr_info.setText(f"Generated via qrencode ({len(text.encode('utf-8'))} bytes).")
                return

        if Image is not None:
            try:
                matrix = build_qr_matrix(text)
                quiet = 3
                scale = 8
                dim = (len(matrix) + quiet * 2) * scale
                fg_rgb = (0, 229, 255) if neon else (0, 0, 0)
                bg_rgb = (18, 14, 30) if neon else (255, 255, 255)
                im = Image.new("RGB", (dim, dim), bg_rgb)
                pix = im.load()
                for r, row in enumerate(matrix):
                    for c, val in enumerate(row):
                        if val:
                            x0 = (c + quiet) * scale
                            y0 = (r + quiet) * scale
                            for dy in range(scale):
                                for dx in range(scale):
                                    pix[x0 + dx, y0 + dy] = fg_rgb
                im.save(out_png, "PNG")
                pm = QPixmap(out_png)
                self._qr_preview.setPixmap(pm.scaled(268, 268, Qt.KeepAspectRatio, Qt.FastTransformation))
                self._qr_info.setText(f"Generated via Python QR encoder ({len(text.encode('utf-8'))} bytes).")
                return
            except Exception as exc:
                self._qr_info.setText(str(exc))
                return

        self._qr_info.setText("Install 'qrencode' or 'python3-pil' for QR generation.")

    def _save_qr_png(self) -> None:
        if not self._qr_png_path or not os.path.isfile(self._qr_png_path):
            return
        dst, _ = QFileDialog.getSaveFileName(self, "Save QR Code PNG", os.path.expanduser("~/vice-qr.png"), "PNG (*.png)")
        if dst:
            shutil.copyfile(self._qr_png_path, dst)
            self._qr_info.setText(f"Saved QR code to {dst}")

    def _copy_qr_image(self) -> None:
        if not self._qr_png_path or not os.path.isfile(self._qr_png_path):
            return
        pm = QPixmap(self._qr_png_path)
        if not pm.isNull():
            QApplication.clipboard().setPixmap(pm)
            self._qr_info.setText("QR image copied to clipboard.")

    def _hash_text_now(self) -> None:
        raw = self._hash_text_in.text().encode("utf-8")
        for algo, fld in self._digest_fields.items():
            fld.setText(hashlib.new(algo, raw).hexdigest())
        self._hash_progress.setValue(100 if raw else 0)
        self._verify_expected()

    def _pick_hash_file(self) -> None:
        if self._hash_worker is not None and self._hash_worker.isRunning():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Select File to Hash", os.path.expanduser("~"))
        if not path:
            return
        self._hash_progress.setValue(0)
        self._hash_worker = FileHashWorker(path)
        self._hash_worker.progress.connect(self._hash_progress.setValue)
        self._hash_worker.done.connect(self._on_file_hash_done)
        self._hash_worker.start()

    def _on_file_hash_done(self, digests: dict, err: str) -> None:
        if err:
            QMessageBox.critical(self, "Hash Error", err)
            return
        for algo, val in digests.items():
            if algo in self._digest_fields:
                self._digest_fields[algo].setText(val)
        self._hash_progress.setValue(100)
        self._verify_expected()

    def _verify_expected(self) -> None:
        exp = self._expected_edit.text().strip().lower()
        if not exp:
            self._verify_lbl.setStyleSheet("color: #cfc6e6; font-weight: bold;")
            self._verify_lbl.setText("Waiting for expected digest")
            return
        matched = [algo.upper() for algo, fld in self._digest_fields.items() if fld.text().strip().lower() == exp]
        if matched:
            self._verify_lbl.setStyleSheet("color: #64ffda; font-weight: bold;")
            self._verify_lbl.setText(f"MATCH ({', '.join(matched)})")
        else:
            self._verify_lbl.setStyleSheet("color: #ff6b8b; font-weight: bold;")
            self._verify_lbl.setText("MISMATCH")

    def _run_codec(self, fn) -> None:
        src = self._codec_in.toPlainText()
        try:
            self._codec_out.setPlainText(fn(src))
        except Exception as exc:
            self._codec_out.setPlainText(f"Decode/Encode Error: {exc}")

    def _swap_codec(self) -> None:
        a = self._codec_in.toPlainText()
        b = self._codec_out.toPlainText()
        self._codec_in.setPlainText(b)
        self._codec_out.setPlainText(a)

    def _process_json(self, minify: bool, sort_keys: bool) -> None:
        raw = self._json_edit.toPlainText()
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            self._json_status.setStyleSheet("color: #ff6b8b; font-weight: bold;")
            self._json_status.setText(f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}")
            return
        formatted = json.dumps(
            obj,
            indent=None if minify else 2,
            separators=(",", ":") if minify else (",", ": "),
            sort_keys=sort_keys,
            ensure_ascii=False,
        )
        self._json_edit.setPlainText(formatted)
        kind = type(obj).__name__
        size_info = f"{len(obj)} entries" if isinstance(obj, (dict, list)) else "scalar"
        self._json_status.setStyleSheet("color: #64ffda; font-weight: bold;")
        self._json_status.setText(f"Valid JSON ({kind}, {size_info}).")
        log_info("Vice QR & Dev Lab formatted JSON")

    def closeEvent(self, event) -> None:
        if self._hash_worker is not None:
            self._hash_worker.stop()
            if self._hash_worker.isRunning():
                self._hash_worker.wait(2000)
        if self._qr_png_path and os.path.exists(self._qr_png_path):
            try:
                os.unlink(self._qr_png_path)
            except OSError:
                pass
        event.accept()


def main() -> None:
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    _configure_cjk_fonts(app)
    app.setStyleSheet(STYLE)
    win = ViceQrHashApp()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
