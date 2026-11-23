#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) — Vice Cyber Encoder & Recon Lab.
Multi-tab cybersecurity workbench providing Base64/Base64URL/Base32/URL/Hex/HTML/ROT13
codecs + JWT inspector, MD5/SHA1/SHA256/SHA512/SHA3-256 + HMAC-SHA256 forge,
IPv4/IPv6 CIDR & RFC1918 recon calculator, and live Python regex matcher + HTTP
security header audit suite. Styled via vice_theme (Noto Sans CJK fallback).
"""

import base64
import binascii
import codecs
from datetime import datetime, timezone
import hashlib
import hmac
import html
import ipaddress
import json
import os
import re
import secrets
import signal
import sys
import urllib.parse

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QTextCharFormat
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QGridLayout, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMainWindow, QPlainTextEdit, QSplitter,
    QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget
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
    from python.vice_utils import log_info  # noqa: E402
except ImportError:
    def log_info(msg: str) -> None:
        print(f"[INFO] {msg}")


_CGNAT_NET = ipaddress.IPv4Network("100.64.0.0/10")

SECURITY_HEADER_CHECKLIST = [
    (
        "Strict-Transport-Security",
        "Forces HTTPS and prevents protocol downgrade / SSL stripping",
        "max-age=31536000; includeSubDomains; preload",
        "High",
    ),
    (
        "Content-Security-Policy",
        "Mitigates XSS, script injection, and unauthorized frame embedding",
        "default-src 'self'; object-src 'none'; frame-ancestors 'none'",
        "High",
    ),
    (
        "X-Content-Type-Options",
        "Blocks MIME-type sniffing attacks across browsers",
        "nosniff",
        "Medium",
    ),
    (
        "X-Frame-Options",
        "Prevents clickjacking via legacy iframe embedding controls",
        "DENY (or SAMEORIGIN)",
        "Medium",
    ),
    (
        "Referrer-Policy",
        "Limits sensitive path/query leakage in outbound Referer headers",
        "strict-origin-when-cross-origin",
        "Low",
    ),
    (
        "Permissions-Policy",
        "Restricts camera, microphone, geolocation, and sensor APIs",
        "geolocation=(), microphone=(), camera=()",
        "Low",
    ),
    (
        "Cross-Origin-Opener-Policy",
        "Isolates browsing context group against Spectre/cross-origin leaks",
        "same-origin",
        "Medium",
    ),
    (
        "Cache-Control",
        "Prevents sensitive authenticated responses from being cached",
        "no-store, max-age=0",
        "Medium",
    ),
]


def _b64url_decode_bytes(segment: str) -> bytes:
    cleaned = segment.strip()
    if not cleaned:
        raise ValueError("Empty Base64URL segment")
    padded = cleaned + ("=" * ((4 - len(cleaned) % 4) % 4))
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def decode_jwt_token(token: str) -> str:
    """Decode JWT header & payload JSON safely without verifying cryptographic signature."""
    cleaned = token.strip()
    if cleaned.lower().startswith("bearer "):
        cleaned = cleaned[7:].strip()
    parts = cleaned.split(".")
    if len(parts) not in (2, 3):
        raise ValueError("JWT must have 2 or 3 dot-separated segments (header.payload[.signature]).")

    header_raw = _b64url_decode_bytes(parts[0]).decode("utf-8")
    payload_raw = _b64url_decode_bytes(parts[1]).decode("utf-8")
    header_obj = json.loads(header_raw)
    payload_obj = json.loads(payload_raw)

    notes = []
    alg = str(header_obj.get("alg", ""))
    if alg.lower() == "none":
        notes.append("WARNING: Unsigned token ('alg': 'none')!")
    elif alg:
        notes.append(f"Algorithm: {alg}")

    now_ts = datetime.now(timezone.utc).timestamp()
    for claim in ("iat", "nbf", "exp"):
        val = payload_obj.get(claim)
        if isinstance(val, (int, float)):
            dt_str = datetime.fromtimestamp(val, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            if claim == "exp":
                state = "EXPIRED" if val < now_ts else "VALID"
                notes.append(f"exp: {dt_str} ({state})")
            else:
                notes.append(f"{claim}: {dt_str}")

    sig_info = "(none)"
    if len(parts) == 3 and parts[2]:
        try:
            sig_bytes = _b64url_decode_bytes(parts[2])
            sig_info = f"{len(sig_bytes)} bytes ({sig_bytes[:12].hex()}...)"
        except (ValueError, binascii.Error):
            sig_info = f"raw ({len(parts[2])} chars)"

    lines = [
        "=== JWT HEADER ===",
        json.dumps(header_obj, indent=2, ensure_ascii=False),
        "",
        "=== JWT PAYLOAD ===",
        json.dumps(payload_obj, indent=2, ensure_ascii=False),
        "",
        f"=== SIGNATURE ===\n{sig_info}",
    ]
    if notes:
        lines.extend(["", "=== CLAIMS AUDIT ===", *[f"- {n}" for n in notes]])
    return "\n".join(lines)


def encode_decode_payload(mode: str, text: str) -> str:
    """Transform text via selected encoder, decoder, or JWT parser."""
    if mode == "b64_enc":
        return base64.b64encode(text.encode("utf-8")).decode("ascii")
    if mode == "b64_dec":
        cleaned = "".join(text.split())
        if not cleaned:
            return ""
        padded = cleaned + ("=" * ((4 - len(cleaned) % 4) % 4))
        return base64.b64decode(padded.encode("ascii"), validate=True).decode("utf-8", errors="replace")
    if mode == "b64url_enc":
        return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii").rstrip("=")
    if mode == "b64url_dec":
        cleaned = "".join(text.split())
        if not cleaned:
            return ""
        return _b64url_decode_bytes(cleaned).decode("utf-8", errors="replace")
    if mode == "b32_enc":
        return base64.b32encode(text.encode("utf-8")).decode("ascii")
    if mode == "b32_dec":
        cleaned = "".join(text.split()).upper()
        if not cleaned:
            return ""
        padded = cleaned + ("=" * ((8 - len(cleaned) % 8) % 8))
        return base64.b32decode(padded.encode("ascii")).decode("utf-8", errors="replace")
    if mode == "url_enc":
        return urllib.parse.quote(text, safe="")
    if mode == "url_dec":
        return urllib.parse.unquote(text)
    if mode == "hex_enc":
        return text.encode("utf-8").hex()
    if mode == "hex_dec":
        cleaned = "".join(text.split())
        if cleaned.lower().startswith("0x"):
            cleaned = cleaned[2:]
        return bytes.fromhex(cleaned).decode("utf-8", errors="replace")
    if mode == "html_enc":
        return html.escape(text, quote=True)
    if mode == "html_dec":
        return html.unescape(text)
    if mode == "rot13":
        return codecs.encode(text, "rot_13")
    if mode == "jwt_dec":
        return decode_jwt_token(text)
    raise ValueError(f"Unsupported codec mode: {mode}")


def compute_hashes_and_hmac(text: str, key_text: str, hex_key: bool = False) -> dict:
    """Return MD5, SHA-1, SHA-256, SHA-512, SHA3-256, and HMAC-SHA256 hex digests."""
    raw = text.encode("utf-8")
    if hex_key:
        cleaned = "".join(key_text.split())
        if cleaned.lower().startswith("0x"):
            cleaned = cleaned[2:]
        key_bytes = bytes.fromhex(cleaned) if cleaned else b""
    else:
        key_bytes = key_text.encode("utf-8")

    return {
        "md5": hashlib.md5(raw).hexdigest(),
        "sha1": hashlib.sha1(raw).hexdigest(),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "sha512": hashlib.sha512(raw).hexdigest(),
        "sha3_256": hashlib.sha3_256(raw).hexdigest(),
        "hmac_sha256": hmac.new(key_bytes, raw, hashlib.sha256).hexdigest(),
        "payload_bytes": len(raw),
        "key_bytes": len(key_bytes),
    }


def analyze_cidr(spec: str) -> dict:
    """Compute IPv4/IPv6 network, masks, host bounds, privacy classification, and subnets."""
    cleaned = spec.strip()
    if not cleaned:
        raise ValueError("Enter an IPv4/IPv6 address or CIDR block (e.g. 192.168.1.42/24).")

    iface = ipaddress.ip_interface(cleaned)
    net = iface.network
    addr = iface.ip
    is_v4 = (net.version == 4)

    if is_v4:
        wildcard = str(net.hostmask)
        broadcast = str(net.broadcast_address)
        if net.prefixlen == 32:
            first_host = str(net.network_address)
            last_host = str(net.network_address)
            usable = 1
        elif net.prefixlen == 31:
            first_host = str(net.network_address)
            last_host = str(net.broadcast_address)
            usable = 2
        else:
            first_host = str(net.network_address + 1)
            last_host = str(net.broadcast_address - 1)
            usable = max(0, net.num_addresses - 2)
    else:
        wildcard = "N/A (IPv6)"
        broadcast = "N/A (IPv6)"
        if net.prefixlen == 128:
            first_host = str(net.network_address)
            last_host = str(net.network_address)
            usable = 1
        elif net.prefixlen == 127:
            first_host = str(net.network_address)
            last_host = str(net.network_address + 1)
            usable = 2
        else:
            first_host = str(net.network_address + 1)
            last_host = str(net.broadcast_address)
            usable = net.num_addresses

    flags = []
    if is_v4 and (addr in _CGNAT_NET or net.subnet_of(_CGNAT_NET)):
        flags.append("RFC6598 CGNAT (100.64.0.0/10)")
    elif addr.is_private:
        flags.append("RFC1918 Private" if is_v4 else "RFC4193 Unique Local / Private")
    if addr.is_loopback:
        flags.append("Loopback")
    if addr.is_link_local:
        flags.append("Link-Local")
    if addr.is_multicast:
        flags.append("Multicast")
    if addr.is_reserved:
        flags.append("Reserved")
    if addr.is_global and not (is_v4 and addr in _CGNAT_NET):
        flags.append("Global Routable (Public)")
    scope = ", ".join(flags) if flags else "Special / Unspecified"

    subnets = []
    if net.prefixlen < net.max_prefixlen:
        diff = min(2, net.max_prefixlen - net.prefixlen)
        subnets = [f"{sub}  ({sub.num_addresses:,} addrs)" for sub in list(net.subnets(prefixlen_diff=diff))[:16]]

    return {
        "version": f"IPv{net.version}",
        "interface": str(iface),
        "address": str(addr),
        "network": str(net),
        "netmask": str(net.netmask),
        "wildcard": wildcard,
        "broadcast": broadcast,
        "host_range": f"{first_host}  —  {last_host}",
        "total_addresses": f"{net.num_addresses:,}",
        "usable_hosts": f"{usable:,}",
        "scope": scope,
        "rfc1918": "Yes" if (is_v4 and addr.is_private and not addr.is_loopback and not addr.is_link_local) else "No",
        "reverse_ptr": addr.reverse_pointer,
        "hex_repr": hex(int(addr)),
        "subnets": subnets,
    }


def evaluate_regex(pattern: str, text: str, flags: int = 0) -> list:
    """Compile and evaluate *pattern* against *text*, returning structured match dicts."""
    if not pattern:
        return []
    compiled = re.compile(pattern, flags)
    matches = []
    for idx, m in enumerate(compiled.finditer(text), 1):
        matches.append({
            "index": idx,
            "start": m.start(),
            "end": m.end(),
            "match": m.group(0),
            "groups": list(m.groups()),
            "groupdict": dict(m.groupdict()),
        })
        if idx >= 200:
            break
    return matches


def audit_http_headers(raw_headers: str) -> dict:
    """Evaluate pasted raw HTTP response headers against SECURITY_HEADER_CHECKLIST."""
    parsed = {}
    for line in raw_headers.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        key = k.strip().lower()
        if key:
            parsed.setdefault(key, []).append(v.strip())

    present = []
    missing = []
    for hdr, _purpose, rec, risk in SECURITY_HEADER_CHECKLIST:
        vals = parsed.get(hdr.lower())
        if vals:
            present.append((hdr, "; ".join(vals)))
        else:
            missing.append((hdr, risk, rec))

    info_leak = [
        f"{k}: {', '.join(parsed[k])}"
        for k in ("server", "x-powered-by", "x-aspnet-version")
        if k in parsed
    ]
    return {
        "present": present,
        "missing": missing,
        "info_leak": info_leak,
        "score": f"{len(present)} / {len(SECURITY_HEADER_CHECKLIST)}",
    }


class VicePayloadLabApp(QMainWindow):
    """Main window for Vice Cyber Encoder & Recon Lab."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice Cyber Encoder & Recon Lab — Vice OS")
        self.resize(1040, 680)
        self.setMinimumSize(820, 540)
        icon = load_tool_icon("vice-tool-payload-lab", "security-high", "utilities-terminal")
        if not icon.isNull():
            self.setWindowIcon(icon)

        self._init_ui()
        self._load_sample("jwt")
        self._update_hashes()
        self._calculate_cidr()
        self._run_regex()
        self._update_curl_cmd()

    def _init_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("RootWidget")
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.setSpacing(12)

        header = make_header(
            title="Vice Cyber Encoder & Recon Lab",
            subtitle="Payload codecs, JWT inspector, hash & HMAC forge, IPv4/IPv6 CIDR calculator, and regex/HTTP header audit",
            icon_name="vice-tool-payload-lab",
            badge_text="RECON LAB",
            badge_variant="aqua",
            parent=root,
        )
        layout.addWidget(header)

        tabs = QTabWidget(root)
        tabs.addTab(self._build_encoder_tab(), "Encoder && Decoder")
        tabs.addTab(self._build_hash_tab(), "Hash && HMAC Forge")
        tabs.addTab(self._build_cidr_tab(), "CIDR && IP Recon")
        tabs.addTab(self._build_regex_http_tab(), "Regex && HTTP Audit")
        layout.addWidget(tabs, 1)

    # ------------------------------------------------------------------
    # Tab 1: Encoder / Decoder + JWT Decoder
    # ------------------------------------------------------------------
    def _build_encoder_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(10)

        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)
        for label, kind in (
            ("Sample JWT", "jwt"),
            ("Sample URL Payload", "url"),
            ("Sample Text", "text"),
        ):
            btn = make_button(label, variant="secondary")
            btn.clicked.connect(lambda _=False, k=kind: self._load_sample(k))
            top_bar.addWidget(btn)
        top_bar.addStretch(1)

        swap_btn = make_button("Swap Input / Output", variant="primary")
        swap_btn.clicked.connect(self._swap_codec_panes)
        top_bar.addWidget(swap_btn)

        clr_btn = make_button("Clear", variant="secondary")
        clr_btn.clicked.connect(self._clear_codec_panes)
        top_bar.addWidget(clr_btn)
        v.addLayout(top_bar)

        self._codec_in = QPlainTextEdit()
        self._codec_in.setPlaceholderText("Paste payload, Base64/Hex/URL string, or JWT token...")
        v.addWidget(self._codec_in, 1)

        ops = [
            ("Base64 Enc", "b64_enc"),
            ("Base64 Dec", "b64_dec"),
            ("B64URL Enc", "b64url_enc"),
            ("B64URL Dec", "b64url_dec"),
            ("Base32 Enc", "b32_enc"),
            ("Base32 Dec", "b32_dec"),
            ("ROT13", "rot13"),
            ("URL Enc", "url_enc"),
            ("URL Dec", "url_dec"),
            ("Hex Enc", "hex_enc"),
            ("Hex Dec", "hex_dec"),
            ("HTML Enc", "html_enc"),
            ("HTML Dec", "html_dec"),
            ("JWT Decode", "jwt_dec"),
        ]
        grid = QGridLayout()
        grid.setSpacing(6)
        for idx, (label, mode) in enumerate(ops):
            variant = "primary" if mode == "jwt_dec" else "secondary"
            btn = make_button(label, variant=variant)
            btn.clicked.connect(lambda _=False, m=mode, lb=label: self._apply_codec(m, lb))
            grid.addWidget(btn, idx // 7, idx % 7)
        v.addLayout(grid)

        self._codec_out = QPlainTextEdit()
        self._codec_out.setReadOnly(True)
        self._codec_out.setPlaceholderText("Transformed output or decoded JWT JSON appears here...")
        v.addWidget(self._codec_out, 1)

        bot = QHBoxLayout()
        bot.setSpacing(8)
        self._codec_status = QLabel("Ready.")
        self._codec_status.setStyleSheet(f"color: {COLORS['text_secondary']}; font-weight: bold;")
        bot.addWidget(self._codec_status, 1)

        copy_out = make_button("Copy Output", variant="secondary")
        copy_out.clicked.connect(self._copy_codec_out)
        bot.addWidget(copy_out)
        v.addLayout(bot)
        return w

    def _load_sample(self, kind: str) -> None:
        if kind == "jwt":
            hdr = base64.urlsafe_b64encode(
                json.dumps({"alg": "HS256", "typ": "JWT"}).encode("utf-8")
            ).decode("ascii").rstrip("=")
            pay = base64.urlsafe_b64encode(
                json.dumps({
                    "sub": "vice-analyst",
                    "role": "pentest",
                    "iss": "vice-os.local",
                    "iat": 1795430400,
                    "exp": 1890000000,
                }).encode("utf-8")
            ).decode("ascii").rstrip("=")
            sig = base64.urlsafe_b64encode(b"leonida-sunset-sample-sig").decode("ascii").rstrip("=")
            self._codec_in.setPlainText(f"{hdr}.{pay}.{sig}")
            self._apply_codec("jwt_dec", "JWT Decode")
        elif kind == "url":
            self._codec_in.setPlainText("https://target.local/search?q=admin%27%20OR%201%3D1--&next=%2Fpanel")
            self._apply_codec("url_dec", "URL Dec")
        else:
            self._codec_in.setPlainText("Vice OS — GTA VI Leonida Recon Payload <script>alert(1)</script>")
            self._apply_codec("b64_enc", "Base64 Enc")

    def _apply_codec(self, mode: str, label: str) -> None:
        src = self._codec_in.toPlainText()
        try:
            res = encode_decode_payload(mode, src)
            self._codec_out.setPlainText(res)
            self._codec_status.setStyleSheet(f"color: {COLORS['success']}; font-weight: bold;")
            self._codec_status.setText(f"{label} succeeded ({len(res)} chars).")
        except Exception as exc:
            self._codec_status.setStyleSheet(f"color: {COLORS['danger']}; font-weight: bold;")
            self._codec_status.setText(f"{label} error: {exc}")

    def _swap_codec_panes(self) -> None:
        a = self._codec_in.toPlainText()
        b = self._codec_out.toPlainText()
        self._codec_in.setPlainText(b)
        self._codec_out.setPlainText(a)
        self._codec_status.setStyleSheet(f"color: {COLORS['accent_aqua']}; font-weight: bold;")
        self._codec_status.setText("Swapped input and output.")

    def _clear_codec_panes(self) -> None:
        self._codec_in.clear()
        self._codec_out.clear()
        self._codec_status.setStyleSheet(f"color: {COLORS['text_secondary']}; font-weight: bold;")
        self._codec_status.setText("Cleared.")

    def _copy_codec_out(self) -> None:
        QApplication.clipboard().setText(self._codec_out.toPlainText())
        self._codec_status.setStyleSheet(f"color: {COLORS['accent_aqua']}; font-weight: bold;")
        self._codec_status.setText("Output copied to clipboard.")

    # ------------------------------------------------------------------
    # Tab 2: Hash & HMAC Forge
    # ------------------------------------------------------------------
    def _build_hash_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(10)

        msg_card = make_card(title="Payload Message & HMAC Secret Key", parent=w)
        self._hash_msg = QPlainTextEdit("vice-os-recon-token-2026")
        self._hash_msg.setMaximumHeight(110)
        self._hash_msg.textChanged.connect(self._update_hashes)
        msg_card.body_layout.addWidget(self._hash_msg)

        key_row = QHBoxLayout()
        key_row.setSpacing(8)
        key_row.addWidget(QLabel("HMAC Key:"))
        self._hmac_key = QLineEdit("leonida-sunset-key")
        self._hmac_key.setPlaceholderText("Enter UTF-8 or hex HMAC secret key...")
        self._hmac_key.textChanged.connect(self._update_hashes)
        key_row.addWidget(self._hmac_key, 1)

        self._hex_key_chk = QCheckBox("Hex Key")
        self._hex_key_chk.stateChanged.connect(self._update_hashes)
        key_row.addWidget(self._hex_key_chk)

        gen_key_btn = make_button("Random 256-bit Key", variant="secondary")
        gen_key_btn.clicked.connect(self._gen_random_hmac_key)
        key_row.addWidget(gen_key_btn)
        msg_card.body_layout.addLayout(key_row)
        v.addWidget(msg_card)

        out_card = make_card(title="Cryptographic Digests & HMAC-SHA256", parent=w)
        grid = QGridLayout()
        grid.setSpacing(8)
        self._hash_fields = {}
        algos = [
            ("md5", "MD5"),
            ("sha1", "SHA-1"),
            ("sha256", "SHA-256"),
            ("sha512", "SHA-512"),
            ("sha3_256", "SHA3-256"),
            ("hmac_sha256", "HMAC-SHA256"),
        ]
        for idx, (key, title) in enumerate(algos):
            lbl = QLabel(title)
            lbl.setStyleSheet(f"color: {COLORS['accent_peach']}; font-weight: bold;")
            fld = QLineEdit()
            fld.setReadOnly(True)
            fld.setStyleSheet(f"font-family: {MONO_STACK};")
            cpy = make_button("Copy", variant="secondary")
            cpy.clicked.connect(lambda _=False, f=fld, t=title: self._copy_digest(f, t))
            grid.addWidget(lbl, idx, 0)
            grid.addWidget(fld, idx, 1)
            grid.addWidget(cpy, idx, 2)
            self._hash_fields[key] = fld
        out_card.body_layout.addLayout(grid)

        cmp_row = QHBoxLayout()
        cmp_row.setSpacing(8)
        cmp_row.addWidget(QLabel("Verify Digest:"))
        self._hash_verify_edit = QLineEdit()
        self._hash_verify_edit.setPlaceholderText("Paste expected hex digest to verify match...")
        self._hash_verify_edit.textChanged.connect(self._verify_digest_match)
        cmp_row.addWidget(self._hash_verify_edit, 1)

        self._hash_match_lbl = QLabel("No expected digest")
        self._hash_match_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-weight: bold;")
        cmp_row.addWidget(self._hash_match_lbl)
        out_card.body_layout.addLayout(cmp_row)
        v.addWidget(out_card, 1)

        self._hash_status = QLabel("Ready.")
        self._hash_status.setStyleSheet(f"color: {COLORS['text_secondary']}; font-weight: bold;")
        v.addWidget(self._hash_status)
        return w

    def _gen_random_hmac_key(self) -> None:
        self._hex_key_chk.setChecked(True)
        self._hmac_key.setText(secrets.token_hex(32))

    def _update_hashes(self) -> None:
        try:
            res = compute_hashes_and_hmac(
                self._hash_msg.toPlainText(),
                self._hmac_key.text(),
                hex_key=self._hex_key_chk.isChecked(),
            )
            for k, fld in self._hash_fields.items():
                fld.setText(res[k])
            self._hash_status.setStyleSheet(f"color: {COLORS['success']}; font-weight: bold;")
            self._hash_status.setText(
                f"Computed 6 digests ({res['payload_bytes']} payload bytes, {res['key_bytes']} key bytes)."
            )
            self._verify_digest_match()
        except ValueError as exc:
            self._hash_fields["hmac_sha256"].setText("")
            self._hash_status.setStyleSheet(f"color: {COLORS['danger']}; font-weight: bold;")
            self._hash_status.setText(f"Invalid Hex HMAC Key: {exc}")

    def _copy_digest(self, fld: QLineEdit, title: str) -> None:
        QApplication.clipboard().setText(fld.text())
        self._hash_status.setStyleSheet(f"color: {COLORS['accent_aqua']}; font-weight: bold;")
        self._hash_status.setText(f"Copied {title} digest to clipboard.")

    def _verify_digest_match(self) -> None:
        exp = self._hash_verify_edit.text().strip().lower()
        if not exp:
            self._hash_match_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-weight: bold;")
            self._hash_match_lbl.setText("No expected digest")
            return
        matched = [k.upper() for k, fld in self._hash_fields.items() if fld.text().strip().lower() == exp]
        if matched:
            self._hash_match_lbl.setStyleSheet(f"color: {COLORS['success']}; font-weight: bold;")
            self._hash_match_lbl.setText(f"MATCH ({', '.join(matched)})")
        else:
            self._hash_match_lbl.setStyleSheet(f"color: {COLORS['danger']}; font-weight: bold;")
            self._hash_match_lbl.setText("MISMATCH")

    # ------------------------------------------------------------------
    # Tab 3: CIDR & IP Recon Calculator
    # ------------------------------------------------------------------
    def _build_cidr_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(10)

        in_row = QHBoxLayout()
        in_row.setSpacing(8)
        self._cidr_edit = QLineEdit("192.168.1.42/24")
        self._cidr_edit.setPlaceholderText("IPv4/IPv6 address or CIDR (e.g. 10.10.14.5/24, 2001:db8::/48)...")
        self._cidr_edit.textChanged.connect(self._calculate_cidr)
        self._cidr_edit.returnPressed.connect(self._calculate_cidr)
        in_row.addWidget(self._cidr_edit, 1)

        calc_btn = make_button("Calculate", variant="primary")
        calc_btn.clicked.connect(self._calculate_cidr)
        in_row.addWidget(calc_btn)

        cpy_btn = make_button("Copy Report", variant="secondary")
        cpy_btn.clicked.connect(self._copy_cidr_report)
        in_row.addWidget(cpy_btn)
        v.addLayout(in_row)

        presets = QHBoxLayout()
        presets.setSpacing(6)
        for cidr in ("10.0.0.0/8", "172.16.0.0/12", "192.168.1.42/24", "100.64.0.1/22", "2001:db8:vice::1/64"):
            b = make_button(cidr, variant="secondary")
            b.clicked.connect(lambda _=False, c=cidr: self._cidr_edit.setText(c))
            presets.addWidget(b)
        presets.addStretch(1)
        v.addLayout(presets)

        split = QHBoxLayout()
        split.setSpacing(12)

        info_card = make_card(title="Network & Classification", parent=w)
        grid = QGridLayout()
        grid.setSpacing(7)
        self._cidr_labels = {}
        fields = [
            ("version", "IP Version"),
            ("network", "Network CIDR"),
            ("netmask", "Netmask"),
            ("wildcard", "Wildcard Mask"),
            ("broadcast", "Broadcast"),
            ("host_range", "Usable Range"),
            ("total_addresses", "Total Addresses"),
            ("usable_hosts", "Usable Hosts"),
            ("rfc1918", "RFC1918 Private"),
            ("scope", "Scope / Class"),
            ("reverse_ptr", "Reverse PTR"),
            ("hex_repr", "Hex Integer"),
        ]
        for idx, (key, title) in enumerate(fields):
            k_lbl = QLabel(f"{title}:")
            k_lbl.setStyleSheet(f"color: {COLORS['accent_aqua']}; font-weight: bold;")
            v_lbl = QLabel("-")
            v_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            v_lbl.setStyleSheet(f"font-family: {MONO_STACK}; color: {COLORS['text_primary']};")
            v_lbl.setWordWrap(True)
            grid.addWidget(k_lbl, idx, 0, Qt.AlignTop)
            grid.addWidget(v_lbl, idx, 1)
            self._cidr_labels[key] = v_lbl
        grid.setColumnStretch(1, 1)
        info_card.body_layout.addLayout(grid)
        info_card.body_layout.addStretch(1)
        split.addWidget(info_card, 3)

        sub_card = make_card(title="Subnet Split Preview", parent=w)
        self._cidr_subnets = QPlainTextEdit()
        self._cidr_subnets.setReadOnly(True)
        sub_card.body_layout.addWidget(self._cidr_subnets, 1)
        split.addWidget(sub_card, 2)
        v.addLayout(split, 1)

        self._cidr_status = QLabel("Ready.")
        self._cidr_status.setStyleSheet(f"color: {COLORS['text_secondary']}; font-weight: bold;")
        v.addWidget(self._cidr_status)
        return w

    def _calculate_cidr(self) -> None:
        try:
            info = analyze_cidr(self._cidr_edit.text())
            for k, lbl in self._cidr_labels.items():
                lbl.setText(info.get(k, "-"))
            subs = info.get("subnets", [])
            self._cidr_subnets.setPlainText(
                "\n".join(subs) if subs else "Single host prefix (/32 or /128) — no smaller subnets."
            )
            self._cidr_status.setStyleSheet(f"color: {COLORS['success']}; font-weight: bold;")
            self._cidr_status.setText(f"Parsed {info['version']} network {info['network']} ({info['scope']}).")
        except ValueError as exc:
            self._cidr_status.setStyleSheet(f"color: {COLORS['danger']}; font-weight: bold;")
            self._cidr_status.setText(f"Invalid IP / CIDR input: {exc}")

    def _copy_cidr_report(self) -> None:
        lines = [f"{k}: {lbl.text()}" for k, lbl in self._cidr_labels.items()]
        QApplication.clipboard().setText("\n".join(lines))
        self._cidr_status.setStyleSheet(f"color: {COLORS['accent_aqua']}; font-weight: bold;")
        self._cidr_status.setText("CIDR breakdown copied to clipboard.")

    # ------------------------------------------------------------------
    # Tab 4: Regex & HTTP Header Audit
    # ------------------------------------------------------------------
    def _build_regex_http_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(10)

        splitter = QSplitter(Qt.Vertical, w)

        # Top: Live Regex Tester
        rx_card = make_card(title="Live Python Regex Matcher", margins=(12, 10, 12, 10), spacing=8)
        rx_row = QHBoxLayout()
        rx_row.setSpacing(8)
        self._rx_pat = QLineEdit(r"(?P<proto>https?)://(?P<host>[A-Za-z0-9.-]+)(?::(?P<port>\d+))?")
        self._rx_pat.setPlaceholderText("Python regex pattern...")
        self._rx_pat.textChanged.connect(self._run_regex)
        rx_row.addWidget(self._rx_pat, 1)

        self._rx_icase = QCheckBox("re.I")
        self._rx_mline = QCheckBox("re.M")
        self._rx_dotall = QCheckBox("re.S")
        for chk in (self._rx_icase, self._rx_mline, self._rx_dotall):
            chk.stateChanged.connect(self._run_regex)
            rx_row.addWidget(chk)
        rx_card.body_layout.addLayout(rx_row)

        rx_split = QHBoxLayout()
        rx_split.setSpacing(8)
        self._rx_text = QTextEdit()
        self._rx_text.setPlainText(
            "2026-11-23 GET https://vice-os.local:8443/api/v1/tools\n"
            "2026-11-23 GET http://127.0.0.1:8080/health\n"
            "2026-11-23 POST https://leonida.example.org/auth"
        )
        self._rx_text.textChanged.connect(self._run_regex)
        rx_split.addWidget(self._rx_text, 1)

        self._rx_out = QPlainTextEdit()
        self._rx_out.setReadOnly(True)
        rx_split.addWidget(self._rx_out, 1)
        rx_card.body_layout.addLayout(rx_split, 1)

        self._rx_status = QLabel("Ready.")
        self._rx_status.setStyleSheet(f"color: {COLORS['text_secondary']}; font-weight: bold;")
        rx_card.body_layout.addWidget(self._rx_status)
        splitter.addWidget(rx_card)

        # Bottom: HTTP Security Header Audit + Checklist
        http_card = make_card(title="HTTP Security Headers Audit && Reference", margins=(12, 10, 12, 10), spacing=8)
        curl_row = QHBoxLayout()
        curl_row.setSpacing(8)
        curl_row.addWidget(QLabel("Target URL:"))
        self._http_url = QLineEdit("https://debian.org")
        self._http_url.textChanged.connect(self._update_curl_cmd)
        curl_row.addWidget(self._http_url, 1)

        self._curl_preview = QLineEdit()
        self._curl_preview.setReadOnly(True)
        self._curl_preview.setStyleSheet(f"font-family: {MONO_STACK}; color: {COLORS['accent_aqua']};")
        curl_row.addWidget(self._curl_preview, 2)

        cpy_curl = make_button("Copy curl", variant="primary")
        cpy_curl.clicked.connect(self._copy_curl_cmd)
        curl_row.addWidget(cpy_curl)
        http_card.body_layout.addLayout(curl_row)

        http_split = QHBoxLayout()
        http_split.setSpacing(10)

        self._hdr_table = QTableWidget(len(SECURITY_HEADER_CHECKLIST), 4)
        self._hdr_table.setHorizontalHeaderLabels(["Header", "Risk", "Recommended Value", "Purpose"])
        self._hdr_table.verticalHeader().setVisible(False)
        self._hdr_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._hdr_table.setAlternatingRowColors(True)
        hh = self._hdr_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.Stretch)
        for row_idx, (hdr, purpose, rec, risk) in enumerate(SECURITY_HEADER_CHECKLIST):
            self._hdr_table.setItem(row_idx, 0, QTableWidgetItem(hdr))
            risk_item = QTableWidgetItem(risk)
            risk_item.setTextAlignment(Qt.AlignCenter)
            self._hdr_table.setItem(row_idx, 1, risk_item)
            self._hdr_table.setItem(row_idx, 2, QTableWidgetItem(rec))
            self._hdr_table.setItem(row_idx, 3, QTableWidgetItem(purpose))
        http_split.addWidget(self._hdr_table, 3)

        audit_col = QVBoxLayout()
        audit_col.setSpacing(6)
        self._raw_headers_in = QPlainTextEdit()
        self._raw_headers_in.setPlaceholderText(
            "Paste raw HTTP response headers here to audit:\n"
            "HTTP/2 200\nStrict-Transport-Security: max-age=31536000\n..."
        )
        self._raw_headers_in.textChanged.connect(self._run_header_audit)
        audit_col.addWidget(self._raw_headers_in, 1)

        self._raw_headers_out = QPlainTextEdit()
        self._raw_headers_out.setReadOnly(True)
        self._raw_headers_out.setPlainText("Paste raw HTTP headers above for instant present/missing security score.")
        audit_col.addWidget(self._raw_headers_out, 1)
        http_split.addLayout(audit_col, 2)
        http_card.body_layout.addLayout(http_split, 1)
        splitter.addWidget(http_card)

        v.addWidget(splitter, 1)
        return w

    def _run_regex(self) -> None:
        pat = self._rx_pat.text()
        txt = self._rx_text.toPlainText()
        flags = 0
        if self._rx_icase.isChecked():
            flags |= re.IGNORECASE
        if self._rx_mline.isChecked():
            flags |= re.MULTILINE
        if self._rx_dotall.isChecked():
            flags |= re.DOTALL

        try:
            matches = evaluate_regex(pat, txt, flags=flags)
        except re.error as exc:
            self._rx_text.setExtraSelections([])
            self._rx_out.setPlainText(f"Regex syntax error: {exc}")
            self._rx_status.setStyleSheet(f"color: {COLORS['danger']}; font-weight: bold;")
            self._rx_status.setText(f"Regex error: {exc}")
            return

        selections = []
        hl_fmt = QTextCharFormat()
        hl_fmt.setBackground(QColor("#3D253B"))
        hl_fmt.setForeground(QColor(COLORS["accent_gold"]))

        lines = []
        for m in matches:
            cur = self._rx_text.textCursor()
            cur.setPosition(m["start"])
            cur.setPosition(m["end"], cur.KeepAnchor)
            sel = QTextEdit.ExtraSelection()
            sel.cursor = cur
            sel.format = hl_fmt
            selections.append(sel)

            line = f"[{m['index']}] ({m['start']}:{m['end']}) {m['match']!r}"
            if m["groupdict"]:
                line += f"  named={m['groupdict']}"
            elif m["groups"]:
                line += f"  groups={m['groups']}"
            lines.append(line)

        self._rx_text.setExtraSelections(selections)
        self._rx_out.setPlainText("\n".join(lines) if lines else "No matches found.")
        self._rx_status.setStyleSheet(f"color: {COLORS['success']}; font-weight: bold;")
        self._rx_status.setText(f"Compiled OK — {len(matches)} match(es) found.")

    def _update_curl_cmd(self) -> None:
        url = self._http_url.text().strip() or "https://example.com"
        safe_url = url.replace("'", "")
        cmd = (
            f"curl -sSL -D - -o /dev/null --max-time 10 '{safe_url}' | "
            "grep -iE '^(HTTP/|strict-transport|content-security|x-frame|x-content-type|"
            "referrer-policy|permissions-policy|cross-origin|cache-control|server|set-cookie)'"
        )
        self._curl_preview.setText(cmd)

    def _copy_curl_cmd(self) -> None:
        QApplication.clipboard().setText(self._curl_preview.text())

    def _run_header_audit(self) -> None:
        raw = self._raw_headers_in.toPlainText().strip()
        if not raw:
            self._raw_headers_out.setPlainText("Paste raw HTTP headers above for instant present/missing security score.")
            return
        res = audit_http_headers(raw)
        lines = [f"Security Header Score: {res['score']}", ""]
        if res["present"]:
            lines.append("[PRESENT]")
            lines.extend(f"+ {h}: {v}" for h, v in res["present"])
            lines.append("")
        if res["missing"]:
            lines.append("[MISSING]")
            lines.extend(f"- {h} [{risk}] -> {rec}" for h, risk, rec in res["missing"])
        if res["info_leak"]:
            lines.extend(["", "[INFO DISCLOSURE]", *[f"! {x}" for x in res["info_leak"]]])
        self._raw_headers_out.setPlainText("\n".join(lines))

    def closeEvent(self, event) -> None:
        event.accept()


def main() -> None:
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    apply_app_theme(app)
    win = VicePayloadLabApp()
    win.show()
    log_info("Vice Cyber Encoder & Recon Lab started")
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
