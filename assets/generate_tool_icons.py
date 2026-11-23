#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Tool Icon & XDG .desktop Launcher Generator.
Reads config/tools_registry.json (or --registry) and procedurally generates
crisp 64x64 Leonida neon-sunset PNG icons and valid XDG .desktop files.
"""

import argparse
import hashlib
import json
import math
import os
from PIL import Image, ImageDraw, ImageFilter

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_REGISTRY = (
    os.path.join(REPO_ROOT, "config", "tools_registry.json")
    if os.path.isfile(os.path.join(REPO_ROOT, "config", "tools_registry.json"))
    else "/opt/vice-os/tools_registry.json"
)

BADGE_BG = (18, 13, 34, 255)  # #120d22 deep midnight

# Category palettes: (top_color, mid_color, bottom_color, primary_neon, secondary_neon)
CATEGORY_PALETTES = {
    "GTA VI Originals": (
        (255, 209, 102, 255),
        (255, 77, 166, 255),
        (0, 229, 255, 255),
        (0, 229, 255, 255),
        (255, 138, 91, 255),
    ),
    "System": (
        (255, 138, 91, 255),
        (255, 46, 151, 255),
        (132, 64, 255, 255),
        (0, 229, 255, 255),
        (255, 209, 102, 255),
    ),
    "Network": (
        (0, 229, 255, 255),
        (255, 77, 166, 255),
        (140, 59, 255, 255),
        (110, 247, 255, 255),
        (255, 138, 91, 255),
    ),
    "Security": (
        (255, 209, 102, 255),
        (255, 58, 130, 255),
        (170, 32, 128, 255),
        (255, 214, 112, 255),
        (0, 229, 255, 255),
    ),
    "Developer": (
        (100, 255, 218, 255),
        (255, 77, 166, 255),
        (140, 59, 255, 255),
        (100, 255, 218, 255),
        (255, 138, 91, 255),
    ),
    "Files & Disk": (
        (255, 209, 102, 255),
        (255, 122, 89, 255),
        (232, 46, 140, 255),
        (255, 209, 102, 255),
        (0, 229, 255, 255),
    ),
    "Media": (
        (255, 150, 113, 255),
        (255, 46, 151, 255),
        (0, 212, 255, 255),
        (255, 112, 184, 255),
        (0, 229, 255, 255),
    ),
    "Productivity": (
        (255, 220, 128, 255),
        (255, 110, 130, 255),
        (158, 72, 255, 255),
        (255, 178, 120, 255),
        (0, 229, 255, 255),
    ),
}

XDG_CATEGORY_MAP = {
    "System": "System;Monitor;",
    "Network": "Network;System;",
    "Security": "System;Security;",
    "Developer": "Development;Utility;",
    "Files & Disk": "System;Utility;FileManager;",
    "Media": "AudioVideo;Audio;Video;",
    "Productivity": "Office;Utility;",
}

NATIVE_XDG_CATEGORIES = {
    "vice-tool-hub": "Utility;System;",
    "vice-tool-radio": "AudioVideo;Audio;",
    "vice-tool-net-radar": "Network;System;",
    "vice-tool-missions": "Office;Utility;",
    "vice-tool-vault": "Utility;System;",
    "vice-tool-turbo": "System;Monitor;",
    "vice-tool-media-studio": "AudioVideo;Video;",
    "vice-tool-qr-hash": "Development;Utility;",
    "vice-tool-sys-deck": "System;Monitor;",
    "vice-tool-cheatsheets": "Development;Utility;",
}

GLYPH_ALIASES = {
    "hub": "hub",
    "explorer": "hub",
    "grid": "hub",
    "radio": "radio",
    "fm": "radio",
    "broadcast": "radio",
    "radar": "radar",
    "sonar": "radar",
    "missions": "star",
    "star": "star",
    "stars": "star",
    "vault": "lock",
    "lock": "lock",
    "crypto": "lock",
    "turbo": "bolt",
    "bolt": "bolt",
    "boost": "bolt",
    "media": "clapper",
    "clapper": "clapper",
    "qr": "qr",
    "qrcode": "qr",
    "sysdeck": "chip",
    "chip": "chip",
    "cpu": "chip",
    "hardware": "chip",
    "cheatsheet": "prompt",
    "cheatsheets": "prompt",
    "prompt": "prompt",
    "monitor": "pulse",
    "pulse": "pulse",
    "stats": "pulse",
    "perf": "pulse",
    "terminal": "terminal",
    "shell": "terminal",
    "tmux": "terminal",
    "network": "globe",
    "globe": "globe",
    "net": "globe",
    "dns": "globe",
    "wifi": "wifi",
    "signal": "wifi",
    "shield": "shield",
    "firewall": "shield",
    "audit": "shield",
    "security": "shield",
    "code": "code",
    "dev": "code",
    "debug": "code",
    "git": "branch",
    "branch": "branch",
    "disk": "disk",
    "drive": "disk",
    "storage": "disk",
    "folder": "folder",
    "file": "folder",
    "files": "folder",
    "tree": "tree",
    "archive": "archive",
    "zip": "archive",
    "editor": "edit",
    "edit": "edit",
    "text": "edit",
    "notes": "edit",
    "audio": "equalizer",
    "sound": "equalizer",
    "equalizer": "equalizer",
    "music": "equalizer",
    "video": "play",
    "film": "play",
    "play": "play",
    "image": "camera",
    "camera": "camera",
    "photo": "camera",
    "search": "search",
    "find": "search",
    "grep": "search",
    "calc": "calc",
    "math": "calc",
    "pdf": "doc",
    "doc": "doc",
    "document": "doc",
    "key": "key",
    "gpg": "key",
    "usb": "usb",
    "pci": "usb",
    "clock": "clock",
    "timer": "clock",
    "cron": "clock",
    "clean": "sparkle",
    "broom": "sparkle",
    "gear": "gear",
    "wrench": "gear",
    "system": "gear",
    "database": "database",
    "sql": "database",
    "download": "download",
    "transfer": "download",
    "sync": "download",
    "package": "package",
    "sliders": "sliders",
    "settings": "sliders",
}

CATEGORY_DEFAULT_GLYPH = {
    "GTA VI Originals": "hub",
    "System": "pulse",
    "Network": "globe",
    "Security": "shield",
    "Developer": "code",
    "Files & Disk": "disk",
    "Media": "equalizer",
    "Productivity": "doc",
}


def tool_slug(tool_id: str) -> str:
    """Return canonical icon/.desktop stem without duplicating 'vice-tool-'."""
    clean = str(tool_id).strip().lower().replace(" ", "-")
    return clean if clean.startswith("vice-tool-") else f"vice-tool-{clean}"


def _lerp_color(c1: tuple, c2: tuple, t: float) -> tuple:
    t = max(0.0, min(1.0, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(len(c1)))


def _diagonal_gradient(size: int, c_top: tuple, c_mid: tuple, c_bot: tuple) -> Image.Image:
    """Generate a smooth diagonal GTA VI sunset gradient at size x size."""
    ramp_h = size * 2
    ramp = Image.new("RGBA", (1, ramp_h))
    pix = ramp.load()
    for y in range(ramp_h):
        t = y / max(1, ramp_h - 1)
        if t <= 0.5:
            pix[0, y] = _lerp_color(c_top, c_mid, t * 2.0)
        else:
            pix[0, y] = _lerp_color(c_mid, c_bot, (t - 0.5) * 2.0)
    grad = ramp.resize((ramp_h, ramp_h), Image.BILINEAR).rotate(-25, resample=Image.BILINEAR)
    off = (ramp_h - size) // 2
    return grad.crop((off, off, off + size, off + size))


def _resolve_glyph_kind(tool: dict) -> str:
    raw = str(tool.get("icon_glyph", "")).strip().lower()
    if raw in GLYPH_ALIASES:
        return GLYPH_ALIASES[raw]

    tid = str(tool.get("id", "")).lower()
    desc = str(tool.get("description", "")).lower()
    hay = f"{raw} {tid} {desc}"

    keyword_rules = [
        (("hub",), "hub"),
        (("radio", "fm"), "radio"),
        (("radar", "nmap", "mtr", "traceroute", "ping"), "radar"),
        (("mission", "todo", "task"), "star"),
        (("vault", "crypt", "cipher", "openssl", "age", "keepass"), "lock"),
        (("turbo", "boost", "speed"), "bolt"),
        (("studio", "ffmpeg", "convert"), "clapper"),
        (("qr", "barcode"), "qr"),
        (("sys-deck", "lscpu", "dmidecode", "lshw", "inxi", "neofetch"), "chip"),
        (("cheat", "tldr", "man"), "prompt"),
        (("htop", "btop", "top", "glances", "sysstat", "iotop", "nmon"), "pulse"),
        (("tmux", "screen", "terminal", "zsh", "fish", "zellij"), "terminal"),
        (("iftop", "nethogs", "iperf", "tcpdump", "tshark", "wireshark", "ss", "netstat"), "wifi"),
        (("curl", "wget", "aria2", "rsync", "rclone", "scp", "ftp"), "download"),
        (("ufw", "lynis", "chkrootkit", "rkhunter", "fail2ban", "firejail"), "shield"),
        (("gpg", "ssh", "pass", "key"), "key"),
        (("git", "tig", "lazygit", "diff"), "branch"),
        (("sqlite", "psql", "db"), "database"),
        (("gdb", "strace", "ltrace", "valgrind", "shellcheck", "python", "gcc", "make", "cmake"), "code"),
        (("ncdu", "parted", "gparted", "smart", "testdisk", "ddrescue", "lsblk", "baobab", "duf", "dust"), "disk"),
        (("tree",), "tree"),
        (("mc", "ranger", "nnn", "lf", "thunar"), "folder"),
        (("7z", "tar", "zip", "unzip", "gzip", "roller", "zstd", "xz"), "archive"),
        (("vim", "nvim", "nano", "geany", "mousepad", "micro"), "edit"),
        (("mpv", "sox", "flac", "opus", "vorbis", "pavucontrol", "alsa", "pulse"), "equalizer"),
        (("vlc", "celluloid", "yt-dlp"), "play"),
        (("gimp", "ristretto", "feh", "scrot", "imagemagick", "exif"), "camera"),
        (("rg", "ripgrep", "fd", "fzf", "grep", "ag", "search"), "search"),
        (("calc", "bc", "qalculate"), "calc"),
        (("pdf", "evince", "qpdf", "pandoc", "poppler", "jq", "yq"), "doc"),
        (("usb", "pci", "lsusb", "lspci"), "usb"),
        (("cron", "at", "watch", "time"), "clock"),
        (("bleachbit", "clean"), "sparkle"),
    ]
    for tokens, g_name in keyword_rules:
        if any(tok in hay for tok in tokens):
            return g_name

    cat = str(tool.get("category", "System"))
    return CATEGORY_DEFAULT_GLYPH.get(cat, "gear")


def _star_points(cx: float, cy: float, r_outer: float, r_inner: float, points: int = 5) -> list:
    pts = []
    for i in range(points * 2):
        ang = -math.pi / 2 + i * math.pi / points
        r = r_outer if i % 2 == 0 else r_inner
        pts.append((cx + math.cos(ang) * r, cy + math.sin(ang) * r))
    return pts


def _draw_glyph(draw: ImageDraw.ImageDraw, kind: str, c1: tuple, c2: tuple, white: tuple) -> None:
    """Draw a bold, crisp geometric vector glyph centered in a 256x256 canvas."""
    cx, cy = 128, 128

    if kind == "hub":
        # Four sleek neon grid tiles + glowing sunset ring
        draw.ellipse([54, 54, 202, 202], outline=c2, width=8)
        for dx, dy, col in [(-32, -32, c1), (6, -32, c2), (-32, 6, white), (6, 6, c1)]:
            draw.rounded_rectangle([cx + dx, cy + dy, cx + dx + 26, cy + dy + 26], radius=7, fill=col)

    elif kind == "radio":
        # Synthwave broadcast tower + left/right signal arcs safely inside badge
        tip_y = 92
        draw.polygon([(cx, tip_y + 4), (cx - 26, 188), (cx + 26, 188)], outline=c1, width=9)
        draw.line([(cx - 17, 152), (cx + 17, 152)], fill=c2, width=8)
        draw.ellipse([cx - 9, tip_y - 9, cx + 9, tip_y + 9], fill=white)
        for rad, col in [(26, c2), (44, c1)]:
            draw.arc([cx - rad, tip_y - rad, cx + rad, tip_y + rad], 138, 222, fill=col, width=8)
            draw.arc([cx - rad, tip_y - rad, cx + rad, tip_y + rad], 318, 42, fill=col, width=8)

    elif kind == "radar":
        for rad in (28, 52, 74):
            draw.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], outline=c1, width=7)
        draw.line([(cx - 76, cy), (cx + 76, cy)], fill=(c1[0], c1[1], c1[2], 140), width=5)
        draw.line([(cx, cy - 76), (cx, cy + 76)], fill=(c1[0], c1[1], c1[2], 140), width=5)
        draw.line([(cx, cy), (cx + 52, cy - 52)], fill=c2, width=10)
        draw.ellipse([cx + 34, cy - 54, cx + 52, cy - 36], fill=white)

    elif kind == "star":
        draw.polygon(_star_points(cx, cy - 4, 66, 28, 5), fill=c2, outline=white)
        draw.polygon(_star_points(cx, cy - 4, 34, 15, 5), fill=c1)

    elif kind == "lock":
        draw.arc([84, 52, 172, 134], 180, 360, fill=c1, width=14)
        draw.line([(84, 92), (84, 114)], fill=c1, width=14)
        draw.line([(172, 92), (172, 114)], fill=c1, width=14)
        draw.rounded_rectangle([70, 108, 186, 196], radius=18, fill=c2, outline=white, width=6)
        draw.ellipse([116, 134, 140, 158], fill=BADGE_BG)
        draw.rectangle([123, 152, 133, 176], fill=BADGE_BG)

    elif kind == "bolt":
        pts = [(144, 48), (78, 136), (124, 136), (110, 208), (180, 116), (132, 116)]
        draw.polygon(pts, fill=c2, outline=white)
        draw.line([(134, 72), (98, 126)], fill=c1, width=6)

    elif kind == "clapper":
        draw.rounded_rectangle([62, 92, 194, 192], radius=14, outline=c1, width=10)
        draw.polygon([(62, 92), (194, 72), (190, 96), (62, 112)], fill=c2)
        draw.polygon([(112, 120), (112, 168), (156, 144)], fill=white)

    elif kind == "qr":
        # Crisp 5x5 high-contrast QR blocks
        cells = [
            (0, 0, c1), (1, 0, c1), (3, 0, c2), (4, 0, c2),
            (0, 1, c1), (4, 1, c2),
            (2, 2, white), (3, 2, c1),
            (0, 3, c2), (2, 3, c1), (4, 3, white),
            (0, 4, c2), (1, 4, c2), (3, 4, white), (4, 4, c1),
        ]
        start, step, box = 66, 26, 20
        for gx, gy, col in cells:
            x0 = start + gx * step
            y0 = start + gy * step
            draw.rounded_rectangle([x0, y0, x0 + box, y0 + box], radius=4, fill=col)

    elif kind == "chip":
        draw.rounded_rectangle([76, 76, 180, 180], radius=16, outline=c1, width=10)
        draw.rounded_rectangle([100, 100, 156, 156], radius=8, fill=c2)
        for offset in (92, 128, 164):
            draw.line([(offset, 52), (offset, 74)], fill=white, width=8)
            draw.line([(offset, 182), (offset, 204)], fill=white, width=8)
            draw.line([(52, offset), (74, offset)], fill=c1, width=8)
            draw.line([(182, offset), (204, offset)], fill=c1, width=8)

    elif kind == "prompt":
        draw.rounded_rectangle([58, 68, 198, 188], radius=16, outline=c1, width=10)
        draw.line([(84, 102), (114, 128), (84, 154)], fill=c2, width=12)
        draw.line([(126, 154), (170, 154)], fill=white, width=12)

    elif kind == "pulse":
        draw.rounded_rectangle([58, 66, 198, 190], radius=16, outline=c1, width=9)
        pts = [(70, 134), (94, 134), (108, 92), (126, 168), (144, 108), (158, 134), (186, 134)]
        draw.line(pts, fill=c2, width=11, joint="curve")

    elif kind == "terminal":
        draw.rounded_rectangle([54, 62, 202, 194], radius=16, outline=c1, width=10)
        draw.line([(56, 94), (200, 94)], fill=c1, width=7)
        draw.line([(82, 118), (110, 140), (82, 162)], fill=white, width=11)
        draw.line([(122, 162), (166, 162)], fill=c2, width=11)

    elif kind == "globe":
        draw.ellipse([58, 58, 198, 198], outline=c1, width=10)
        draw.ellipse([96, 58, 160, 198], outline=c2, width=8)
        draw.line([(60, 106), (196, 106)], fill=c1, width=7)
        draw.line([(60, 150), (196, 150)], fill=c1, width=7)

    elif kind == "wifi":
        draw.ellipse([116, 164, 140, 188], fill=white)
        for rad, col in [(36, c2), (62, c1), (88, c2)]:
            draw.arc([cx - rad, 174 - rad, cx + rad, 174 + rad], 222, 318, fill=col, width=11)

    elif kind == "shield":
        pts = [(cx, 54), (188, 78), (182, 142), (cx, 202), (74, 142), (68, 78)]
        draw.polygon(pts, outline=c1, width=11)
        draw.line([(98, 128), (120, 150), (160, 102)], fill=c2, width=12)

    elif kind == "code":
        draw.line([(96, 86), (62, 128), (96, 170)], fill=c1, width=12)
        draw.line([(160, 86), (194, 128), (160, 170)], fill=c1, width=12)
        draw.line([(142, 76), (114, 180)], fill=c2, width=11)

    elif kind == "branch":
        draw.line([(92, 78), (92, 178)], fill=c1, width=11)
        draw.line([(92, 144), (162, 102)], fill=c2, width=11)
        for px, py, col in [(92, 78, white), (92, 178, c1), (162, 102, c2)]:
            draw.ellipse([px - 15, py - 15, px + 15, py + 15], fill=col)

    elif kind == "disk":
        draw.rounded_rectangle([66, 56, 190, 200], radius=16, outline=c1, width=10)
        draw.ellipse([86, 74, 170, 158], outline=c2, width=10)
        draw.ellipse([116, 104, 140, 128], fill=white)
        draw.line([(88, 178), (168, 178)], fill=c1, width=10)

    elif kind == "folder":
        pts = [(56, 76), (108, 76), (124, 94), (200, 94), (200, 188), (56, 188)]
        draw.polygon(pts, outline=c1, width=10)
        draw.line([(76, 126), (180, 126)], fill=c2, width=10)
        draw.line([(76, 154), (146, 154)], fill=white, width=9)

    elif kind == "tree":
        draw.line([(80, 66), (80, 182)], fill=c1, width=10)
        for y, col, w in [(86, white, 88), (128, c2, 72), (170, c1, 88)]:
            draw.line([(80, y), (80 + w, y)], fill=col, width=10)
            draw.ellipse([80 + w - 10, y - 10, 80 + w + 10, y + 10], fill=col)

    elif kind == "archive":
        draw.rounded_rectangle([66, 60, 190, 196], radius=16, outline=c1, width=10)
        draw.line([(128, 62), (128, 194)], fill=c2, width=8)
        for y in (84, 110, 136, 162):
            draw.rectangle([114, y, 142, y + 12], fill=white)

    elif kind == "edit":
        draw.polygon([(70, 186), (80, 142), (158, 64), (192, 98), (114, 176)], outline=c1, width=10)
        draw.line([(144, 78), (178, 112)], fill=c2, width=10)
        draw.polygon([(70, 186), (80, 148), (108, 176)], fill=white)

    elif kind == "equalizer":
        bars = [(72, 112, c1), (100, 74, c2), (128, 96, white), (156, 64, c1), (184, 118, c2)]
        for bx, top_y, col in bars:
            draw.line([(bx, top_y), (bx, 188)], fill=col, width=14)

    elif kind == "play":
        draw.ellipse([58, 58, 198, 198], outline=c1, width=10)
        draw.polygon([(104, 88), (104, 168), (172, 128)], fill=c2, outline=white)

    elif kind == "camera":
        draw.rounded_rectangle([56, 78, 200, 184], radius=16, outline=c1, width=10)
        draw.rounded_rectangle([98, 62, 158, 82], radius=6, fill=c2)
        draw.ellipse([96, 98, 160, 162], outline=c2, width=10)
        draw.ellipse([118, 120, 138, 140], fill=white)

    elif kind == "search":
        draw.ellipse([64, 64, 156, 156], outline=c1, width=12)
        draw.line([(142, 142), (192, 192)], fill=c2, width=16)
        draw.arc([80, 80, 140, 140], 200, 265, fill=white, width=7)

    elif kind == "calc":
        draw.rounded_rectangle([68, 56, 188, 200], radius=14, outline=c1, width=10)
        draw.rounded_rectangle([84, 72, 172, 106], radius=6, fill=c2)
        for gx in (94, 128, 162):
            for gy in (130, 164):
                draw.ellipse([gx - 10, gy - 10, gx + 10, gy + 10], fill=white)

    elif kind == "doc":
        pts = [(70, 56), (154, 56), (186, 88), (186, 200), (70, 200)]
        draw.polygon(pts, outline=c1, width=10)
        draw.line([(92, 108), (164, 108)], fill=c2, width=10)
        draw.line([(92, 138), (164, 138)], fill=white, width=9)
        draw.line([(92, 168), (140, 168)], fill=c2, width=9)

    elif kind == "key":
        draw.ellipse([60, 94, 126, 160], outline=c1, width=12)
        draw.line([(126, 127), (198, 127)], fill=c2, width=12)
        draw.line([(168, 127), (168, 158)], fill=white, width=11)
        draw.line([(190, 127), (190, 150)], fill=white, width=11)

    elif kind == "usb":
        draw.line([(cx, 62), (cx, 194)], fill=c1, width=11)
        draw.polygon([(cx, 54), (cx - 14, 78), (cx + 14, 78)], fill=white)
        draw.line([(cx, 146), (82, 114), (82, 92)], fill=c2, width=9)
        draw.line([(cx, 132), (174, 102), (174, 86)], fill=c2, width=9)
        draw.ellipse([112, 174, 144, 206], fill=c1)

    elif kind == "clock":
        draw.ellipse([58, 58, 198, 198], outline=c1, width=10)
        draw.line([(cx, cy), (cx, 82)], fill=white, width=10)
        draw.line([(cx, cy), (164, 144)], fill=c2, width=10)
        draw.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], fill=white)

    elif kind == "sparkle":
        draw.polygon([(cx, 56), (142, 114), (200, cy), (142, 142), (cx, 200), (114, 142), (56, cy), (114, 114)],
                     fill=c2, outline=white)
        draw.ellipse([66, 66, 86, 86], fill=c1)
        draw.ellipse([172, 170, 190, 188], fill=c1)

    elif kind == "database":
        draw.ellipse([68, 62, 188, 96], outline=c1, width=9)
        draw.line([(68, 79), (68, 176)], fill=c1, width=9)
        draw.line([(188, 79), (188, 176)], fill=c1, width=9)
        draw.arc([68, 110, 188, 144], 0, 180, fill=c2, width=9)
        draw.arc([68, 158, 188, 192], 0, 180, fill=white, width=9)

    elif kind == "download":
        draw.line([(cx, 58), (cx, 152)], fill=c1, width=12)
        draw.line([(90, 120), (cx, 156), (166, 120)], fill=c2, width=12)
        draw.line([(68, 184), (188, 184)], fill=white, width=12)

    elif kind == "package":
        pts = [(cx, 58), (192, 92), (192, 164), (cx, 198), (64, 164), (64, 92)]
        draw.polygon(pts, outline=c1, width=10)
        draw.line([(66, 94), (cx, 126), (190, 94)], fill=c2, width=9)
        draw.line([(cx, 126), (cx, 196)], fill=white, width=9)

    elif kind == "sliders":
        for y, knob_x, col in [(84, 102, c1), (128, 156, c2), (172, 118, white)]:
            draw.line([(66, y), (190, y)], fill=c1, width=8)
            draw.ellipse([knob_x - 14, y - 14, knob_x + 14, y + 14], fill=col)

    else:  # "gear" default
        for deg in range(0, 360, 45):
            ang = math.radians(deg)
            x1 = cx + math.cos(ang) * 44
            y1 = cy + math.sin(ang) * 44
            x2 = cx + math.cos(ang) * 72
            y2 = cy + math.sin(ang) * 72
            draw.line([(x1, y1), (x2, y2)], fill=c2, width=16)
        draw.ellipse([80, 80, 176, 176], outline=c1, width=14)
        draw.ellipse([108, 108, 148, 148], fill=white)


def render_tool_icon(tool: dict, size: int = 64) -> Image.Image:
    """Render a crisp 64x64 GTA VI Leonida neon-sunset PNG icon for a tool."""
    s = 256  # 4x supersampling
    category = str(tool.get("category", "System"))
    c_top, c_mid, c_bot, neon_a, neon_b = CATEGORY_PALETTES.get(
        category, CATEGORY_PALETTES["System"]
    )
    white = (246, 242, 255, 255)

    canvas = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    pad = 18
    radius = 52
    box = [pad, pad, s - pad, s - pad]

    # 1. Soft neon glow behind the badge border
    glow_src = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_src)
    glow_draw.rounded_rectangle(box, radius=radius, outline=(c_mid[0], c_mid[1], c_mid[2], 145), width=14)
    glow_layer = glow_src.filter(ImageFilter.GaussianBlur(10))
    canvas = Image.alpha_composite(canvas, glow_layer)

    # 2. Deep #120d22 rounded badge fill
    badge_mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(badge_mask).rounded_rectangle(box, radius=radius, fill=255)
    badge_fill = Image.new("RGBA", (s, s), BADGE_BG)

    # Subtle lower-edge Leonida horizon bars inside badge for authentic synthwave depth
    decor = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d_draw = ImageDraw.Draw(decor)
    for idx, y_off in enumerate((182, 198, 214)):
        alpha = 32 - idx * 6
        d_draw.rectangle([pad, y_off, s - pad, y_off + 5], fill=(c_mid[0], c_mid[1], c_mid[2], alpha))
    badge_with_decor = Image.alpha_composite(badge_fill, decor)
    canvas.paste(badge_with_decor, (0, 0), badge_mask)

    # 3. Vibrant Leonida sunset gradient frame
    frame_mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(frame_mask).rounded_rectangle(box, radius=radius, outline=255, width=10)
    grad_img = _diagonal_gradient(s, c_top, c_mid, c_bot)
    canvas.paste(grad_img, (0, 0), frame_mask)

    # Subtle deterministic neon corner pip based on tool id so every tool looks bespoke
    digest = hashlib.sha256(str(tool.get("id", "")).encode("utf-8")).digest()
    pip_col = neon_a if (digest[0] % 2 == 0) else neon_b
    pip_draw = ImageDraw.Draw(canvas)
    pip_draw.ellipse([s - pad - 34, pad + 20, s - pad - 20, pad + 34], fill=(pip_col[0], pip_col[1], pip_col[2], 210))

    # 4. Central vector glyph + subtle neon bloom
    glyph_kind = _resolve_glyph_kind(tool)
    glyph_layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    _draw_glyph(ImageDraw.Draw(glyph_layer), glyph_kind, neon_a, neon_b, white)

    glyph_bloom = glyph_layer.filter(ImageFilter.GaussianBlur(6))
    r_ch, g_ch, b_ch, a_ch = glyph_bloom.split()
    a_ch = a_ch.point(lambda px: int(px * 0.55))
    glyph_bloom = Image.merge("RGBA", (r_ch, g_ch, b_ch, a_ch))

    canvas = Image.alpha_composite(canvas, glyph_bloom)
    canvas = Image.alpha_composite(canvas, glyph_layer)

    return canvas.resize((size, size), Image.LANCZOS)


def _desktop_categories(tool: dict) -> str:
    tid = tool_slug(str(tool.get("id", "")))
    if tid in NATIVE_XDG_CATEGORIES:
        return NATIVE_XDG_CATEGORIES[tid]
    return XDG_CATEGORY_MAP.get(str(tool.get("category", "")), "Utility;")


def _sanitize_desktop_value(value: str) -> str:
    return " ".join(str(value).replace("\r", " ").replace("\n", " ").split())


def format_desktop_entry(tool: dict) -> str:
    """Build a valid XDG .desktop entry string for a registry tool."""
    slug = tool_slug(str(tool["id"]))
    name = _sanitize_desktop_value(tool.get("name", slug))
    comment = _sanitize_desktop_value(tool.get("description", name))
    raw_exec = _sanitize_desktop_value(tool.get("exec", ""))
    is_terminal = bool(tool.get("terminal", False))

    if is_terminal:
        escaped_title = name.replace("\\", "\\\\").replace('"', '\\"')
        exec_line = f'vice-run-tool "{escaped_title}" {raw_exec}'.strip()
    else:
        exec_line = raw_exec

    lines = [
        "[Desktop Entry]",
        "Type=Application",
        f"Name={name}",
        f"Comment={comment}",
        f"Exec={exec_line}",
        f"Icon={slug}",
        "Terminal=false",
        f"Categories={_desktop_categories(tool)}",
        "StartupNotify=true",
    ]
    return "\n".join(lines) + "\n"


def generate_all(registry_path: str, icon_dir: str, pixmap_dir: str, desktop_dir: str) -> tuple:
    """Generate 64x64 PNG icons and .desktop files for every tool in registry_path."""
    with open(registry_path, "r", encoding="utf-8") as fp:
        data = json.load(fp)

    tools = data.get("tools", [])
    if not isinstance(tools, list):
        raise ValueError("tools_registry.json 'tools' field must be a list")

    os.makedirs(icon_dir, exist_ok=True)
    if pixmap_dir:
        os.makedirs(pixmap_dir, exist_ok=True)
    if desktop_dir:
        os.makedirs(desktop_dir, exist_ok=True)

    icon_count = 0
    desktop_count = 0
    same_pixmap_dir = bool(
        pixmap_dir and os.path.abspath(pixmap_dir) == os.path.abspath(icon_dir)
    )

    for tool in tools:
        slug = tool_slug(str(tool["id"]))
        img = render_tool_icon(tool, size=64)

        icon_path = os.path.join(icon_dir, f"{slug}.png")
        img.save(icon_path, "PNG")
        icon_count += 1

        if pixmap_dir and not same_pixmap_dir:
            pixmap_path = os.path.join(pixmap_dir, f"{slug}.png")
            img.save(pixmap_path, "PNG")

        if desktop_dir:
            desktop_path = os.path.join(desktop_dir, f"{slug}.desktop")
            entry_text = format_desktop_entry(tool)
            with open(desktop_path, "w", encoding="utf-8", newline="\n") as dfp:
                dfp.write(entry_text)
            desktop_count += 1

    return icon_count, desktop_count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate GTA VI Leonida tool icons and .desktop launchers."
    )
    parser.add_argument(
        "--registry", type=str, default=DEFAULT_REGISTRY,
        help="Path to tools_registry.json"
    )
    parser.add_argument(
        "--icon-dir", type=str, default="/usr/share/icons/hicolor/64x64/apps",
        help="Output directory for 64x64 hicolor PNG icons"
    )
    parser.add_argument(
        "--pixmap-dir", type=str, default="/usr/share/pixmaps",
        help="Output directory for fallback pixmap PNG icons"
    )
    parser.add_argument(
        "--desktop-dir", type=str, default="/usr/share/applications",
        help="Output directory for XDG .desktop launchers"
    )
    args = parser.parse_args()

    icons, desktops = generate_all(
        args.registry, args.icon_dir, args.pixmap_dir, args.desktop_dir
    )
    print(f"[SUCCESS] Generated {icons} icons (64x64) and {desktops} .desktop launchers.")


if __name__ == "__main__":
    main()
