#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Tool Icon & XDG .desktop Launcher Generator.
Reads config/tools_registry.json (or --registry) and procedurally generates
clean, modern 64x64 satin-slate squircle PNG icons with Leonida sunset accents
and valid XDG .desktop files (zero neon scanline clutter).
"""

import argparse
import json
import math
import os
from PIL import Image, ImageChops, ImageDraw

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_REGISTRY = (
    os.path.join(REPO_ROOT, "config", "tools_registry.json")
    if os.path.isfile(os.path.join(REPO_ROOT, "config", "tools_registry.json"))
    else "/opt/vice-os/tools_registry.json"
)

BADGE_BG = (21, 24, 38, 255)       # #151826 satin slate core
BADGE_TOP = (29, 33, 52, 255)      # #1D2134 top highlight
BADGE_BOT = (15, 17, 28, 255)      # #0F111C deep base
RIM_BASE = (46, 52, 74, 235)       # #2E344A structural hairline
ALABASTER = (245, 246, 250, 255)   # #F5F6FA crisp primary glyph tone

# Category palettes: (primary_accent, secondary_accent, highlight_tone)
CATEGORY_PALETTES = {
    "GTA VI Originals": (
        (255, 94, 126, 255),   # #FF5E7E coral-pink
        (255, 154, 98, 255),   # #FF9A62 warm peach
        (245, 246, 250, 255),  # #F5F6FA alabaster
    ),
    "Office": (
        (245, 246, 250, 255),  # #F5F6FA paper alabaster
        (82, 183, 255, 255),   # #52B7FF crisp office blue
        (247, 200, 115, 255),  # #F7C873 warm gold
    ),
    "System": (
        (255, 154, 98, 255),   # #FF9A62 peach
        (220, 226, 240, 255),  # #DCE2F0 cool slate-white
        (247, 200, 115, 255),  # #F7C873 gold
    ),
    "Network": (
        (54, 214, 195, 255),   # #36D6C3 coastal aqua
        (225, 231, 244, 255),  # #E1E7F4 alabaster slate
        (255, 154, 98, 255),   # #FF9A62 peach
    ),
    "Security": (
        (255, 94, 126, 255),   # #FF5E7E coral
        (247, 200, 115, 255),  # #F7C873 warm gold
        (245, 246, 250, 255),  # #F5F6FA alabaster
    ),
    "Developer": (
        (54, 214, 195, 255),   # #36D6C3 aqua
        (255, 154, 98, 255),   # #FF9A62 peach
        (245, 246, 250, 255),  # #F5F6FA alabaster
    ),
    "Files & Disk": (
        (247, 200, 115, 255),  # #F7C873 warm gold
        (220, 226, 240, 255),  # #DCE2F0 slate-white
        (255, 154, 98, 255),   # #FF9A62 peach
    ),
    "Media": (
        (255, 94, 126, 255),   # #FF5E7E coral
        (54, 214, 195, 255),   # #36D6C3 aqua
        (245, 246, 250, 255),  # #F5F6FA alabaster
    ),
    "Productivity": (
        (247, 200, 115, 255),  # #F7C873 gold
        (54, 214, 195, 255),   # #36D6C3 aqua
        (245, 246, 250, 255),  # #F5F6FA alabaster
    ),
}

XDG_CATEGORY_MAP = {
    "Office": "Office;",
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
    "vice-tool-vault": "Utility;System;Security;",
    "vice-tool-turbo": "System;Monitor;",
    "vice-tool-media-studio": "AudioVideo;Video;",
    "vice-tool-qr-hash": "Development;Utility;",
    "vice-tool-sys-deck": "System;Monitor;",
    "vice-tool-cheatsheets": "Development;Utility;",
    "vice-tool-net-shield": "Network;Security;System;",
    "vice-tool-cyber-deck": "System;Security;",
    "vice-tool-mac-cloak": "System;Security;Network;",
    "vice-tool-office-hub": "Office;Utility;",
    "vice-tool-clock-sync": "Utility;System;Settings;",
    "vice-tool-fetch": "System;Utility;",
    "vice-tool-payload-lab": "System;Security;Development;",
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
    "nmap": "radar",
    "missions": "star",
    "star": "star",
    "stars": "star",
    "vault": "lock",
    "lock": "lock",
    "crypto": "crypto",
    "cipher": "crypto",
    "fetch": "fetch",
    "vicefetch": "fetch",
    "payload": "payload",
    "payload-lab": "payload",
    "encoder": "payload",
    "wireless": "wireless",
    "rf": "wireless",
    "forensics": "forensics",
    "carving": "forensics",
    "reversing": "reversing",
    "reverse": "reversing",
    "disasm": "reversing",
    "binary": "reversing",
    "exploit": "exploit",
    "pentest": "exploit",
    "vuln": "exploit",
    "osint": "osint",
    "recon": "osint",
    "web_pentest": "web_pentest",
    "webapp": "web_pentest",
    "fuzzer": "web_pentest",
    "password": "password",
    "crack": "password",
    "bruteforce": "password",
    "wordlist": "password",
    "sniff": "sniff",
    "mitm": "sniff",
    "capture": "sniff",
    "tunnel": "tunnel",
    "pivot": "tunnel",
    "steg": "steg",
    "stego": "steg",
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
    "dns": "dns",
    "wifi": "wifi",
    "signal": "wifi",
    "shield": "shield",
    "firewall": "shield",
    "audit": "cyber",
    "cyber": "cyber",
    "cyberdeck": "cyber",
    "security": "shield",
    "vpn": "vpn",
    "netshield": "vpn",
    "tor": "tor",
    "onion": "tor",
    "proxy": "tor",
    "cloak": "cloak",
    "privacy": "cloak",
    "wireshark": "wireshark",
    "packet": "wireshark",
    "office": "office",
    "writer": "writer",
    "spreadsheet": "spreadsheet",
    "sheet": "spreadsheet",
    "calc_sheet": "spreadsheet",
    "impress": "impress",
    "presentation": "impress",
    "slides": "impress",
    "draw": "draw",
    "vector": "draw",
    "math": "math",
    "formula": "math",
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
    "scanner": "scanner",
    "screenshot": "scanner",
    "search": "search",
    "find": "search",
    "grep": "search",
    "calc": "calc",
    "calculator": "calc",
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
    "printer": "printer",
    "print": "printer",
    "bluetooth": "bluetooth",
    "palette": "palette",
    "color": "palette",
    "backup": "backup",
    "timeshift": "backup",
    "vscode": "vscode",
    "ide": "vscode",
    "cpp": "cpp",
    "clang": "cpp",
    "csharp": "csharp",
    "dotnet": "csharp",
    "rust": "rust",
    "cargo": "rust",
    "nodejs": "nodejs",
    "node": "nodejs",
    "javascript": "nodejs",
    "typescript": "typescript",
    "ts": "typescript",
    "golang": "golang",
    "go": "golang",
    "java": "java",
    "jdk": "java",
    "php": "php",
    "ruby": "ruby",
    "lua": "lua",
    "hw_detect": "hw_detect",
    "hw-detect": "hw_detect",
    "autodetect": "hw_detect",
}

CATEGORY_DEFAULT_GLYPH = {
    "GTA VI Originals": "hub",
    "Office": "office",
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


def _vertical_gradient(size: int, c_top: tuple, c_mid: tuple, c_bot: tuple) -> Image.Image:
    strip = Image.new("RGBA", (1, size))
    pix = strip.load()
    for y in range(size):
        t = y / max(1, size - 1)
        if t <= 0.5:
            pix[0, y] = _lerp_color(c_top, c_mid, t * 2.0)
        else:
            pix[0, y] = _lerp_color(c_mid, c_bot, (t - 0.5) * 2.0)
    return strip.resize((size, size), Image.BILINEAR)


def _horizontal_gradient(size: int, stops: list) -> Image.Image:
    strip = Image.new("RGBA", (size, 1))
    pix = strip.load()
    for x in range(size):
        pos = x / max(1, size - 1)
        col = stops[-1][1]
        for idx in range(len(stops) - 1):
            p0, c0 = stops[idx]
            p1, c1 = stops[idx + 1]
            if p0 <= pos <= p1:
                lt = (pos - p0) / max(1e-6, p1 - p0)
                col = _lerp_color(c0, c1, lt)
                break
        pix[x, 0] = col
    return strip.resize((size, size), Image.BILINEAR)


def _resolve_glyph_kind(tool: dict) -> str:
    raw = str(tool.get("icon_glyph", "")).strip().lower()
    tid = str(tool.get("id", "")).strip().lower()
    desc = str(tool.get("description", "")).lower()

    # Bespoke tool-ID recognition takes precedence over generic aliases like 'network' or 'security'
    exact_id_map = {
        "vice-tool-fetch": "fetch",
        "vice-tool-payload-lab": "payload",
        "vice-hw-autodetect": "hw_detect",
        "code": "vscode",
        "vscode": "vscode",
        "g++": "cpp",
        "clang": "cpp",
        "clangd": "cpp",
        "lld": "cpp",
        "dotnet-sdk-8.0": "csharp",
        "rustc": "rust",
        "cargo": "rust",
        "rustfmt": "rust",
        "nodejs": "nodejs",
        "node-typescript": "typescript",
        "golang-go": "golang",
        "openjdk-17-jdk-headless": "java",
        "php-cli": "php",
        "ruby": "ruby",
        "lua5.4": "lua",
        "nmap": "radar",
        "masscan": "radar",
        "arp-scan": "radar",
        "netdiscover": "radar",
        "mtr": "radar",
        "wireshark": "wireshark",
        "tshark": "wireshark",
        "tcpdump": "wireshark",
        "tcpflow": "wireshark",
        "ngrep": "wireshark",
        "tor": "tor",
        "torsocks": "tor",
        "privoxy": "tor",
        "obfs4proxy": "tor",
        "openvpn": "vpn",
        "wireguard-tools": "vpn",
        "network-manager-openvpn-gnome": "vpn",
        "stunnel4": "vpn",
        "sshuttle": "vpn",
        "macchanger": "cloak",
        "mat2": "cloak",
        "galculator": "calc",
        "speedcrunch": "calc",
        "qalculate-gtk": "calc",
        "libreoffice-writer": "writer",
        "libreoffice-calc": "spreadsheet",
        "libreoffice-impress": "impress",
        "libreoffice-draw": "draw",
        "libreoffice-math": "math",
    }
    if tid in exact_id_map:
        return exact_id_map[tid]

    if raw in GLYPH_ALIASES:
        return GLYPH_ALIASES[raw]

    hay = f"{raw} {tid} {desc}"

    keyword_rules = [
        (("libreoffice-writer", "writer"), "writer"),
        (("libreoffice-calc",), "spreadsheet"),
        (("libreoffice-impress", "impress"), "impress"),
        (("libreoffice-draw",), "draw"),
        (("libreoffice-math",), "math"),
        (("office-hub", "office"), "office"),
        (("net-shield", "openvpn", "wireguard", "wg-quick", "stunnel", "sshuttle"), "vpn"),
        (("tor", "torsocks", "privoxy", "proxychains"), "tor"),
        (("mac-cloak", "cloak", "macchanger", "mat2"), "cloak"),
        (("cyber-deck", "lynis", "nikto", "hydra", "sqlmap", "gobuster", "dirb", "john", "hashcat"), "cyber"),
        (("wireshark", "tshark", "tcpdump", "tcpflow", "ngrep"), "wireshark"),
        (("clock-sync", "chrony", "cron", "at", "watch", "time"), "clock"),
        (("hub",), "hub"),
        (("radio", "fm"), "radio"),
        (("radar", "nmap", "mtr", "traceroute", "ping", "arp-scan", "masscan"), "radar"),
        (("mission", "todo", "task"), "star"),
        (("vault", "crypt", "cipher", "openssl", "age", "keepass"), "lock"),
        (("turbo", "boost", "speed"), "bolt"),
        (("studio", "ffmpeg", "convert"), "clapper"),
        (("qr", "barcode"), "qr"),
        (("sys-deck", "lscpu", "dmidecode", "lshw", "inxi", "neofetch"), "chip"),
        (("cheat", "tldr", "man"), "prompt"),
        (("stubby", "unbound", "dnsrecon", "dnsenum", "fierce", "whois", "dns"), "dns"),
        (("printer", "cups"), "printer"),
        (("bluetooth", "blueman"), "bluetooth"),
        (("gcolor", "redshift", "palette"), "palette"),
        (("timeshift", "backup"), "backup"),
        (("flameshot", "screenshot", "scrot"), "scanner"),
        (("htop", "btop", "top", "glances", "sysstat", "iotop", "nmon"), "pulse"),
        (("tmux", "screen", "terminal", "zsh", "fish", "zellij"), "terminal"),
        (("iftop", "nethogs", "iperf", "ss", "netstat", "aircrack"), "wifi"),
        (("curl", "wget", "aria2", "rsync", "rclone", "scp", "ftp"), "download"),
        (("ufw", "gufw", "chkrootkit", "rkhunter", "fail2ban", "firejail", "clamav", "nftables", "iptables"), "shield"),
        (("gpg", "ssh", "pass", "key"), "key"),
        (("git", "tig", "lazygit", "diff"), "branch"),
        (("sqlite", "psql", "db"), "database"),
        (("vscode", "visual studio code"), "vscode"),
        (("g++", "clang", "clangd", "lld", "c++"), "cpp"),
        (("dotnet", "c#", "csharp"), "csharp"),
        (("rust", "cargo"), "rust"),
        (("typescript", "tsc"), "typescript"),
        (("nodejs", "npm", "npx", "node.js"), "nodejs"),
        (("golang",), "golang"),
        (("openjdk", "javac", "java"), "java"),
        (("php",), "php"),
        (("ruby",), "ruby"),
        (("lua",), "lua"),
        (("hw-autodetect", "hw_detect", "autodetect"), "hw_detect"),
        (("gdb", "strace", "ltrace", "valgrind", "shellcheck", "python", "gcc", "make", "cmake"), "code"),
        (("ncdu", "parted", "gparted", "smart", "testdisk", "ddrescue", "lsblk", "baobab", "duf", "dust"), "disk"),
        (("tree",), "tree"),
        (("mc", "ranger", "nnn", "lf", "thunar"), "folder"),
        (("7z", "tar", "zip", "unzip", "gzip", "roller", "zstd", "xz"), "archive"),
        (("vim", "nvim", "nano", "geany", "mousepad", "micro"), "edit"),
        (("mpv", "sox", "flac", "opus", "vorbis", "pavucontrol", "alsa", "pulse"), "equalizer"),
        (("vlc", "celluloid", "yt-dlp"), "play"),
        (("gimp", "ristretto", "feh", "imagemagick", "exif"), "camera"),
        (("rg", "ripgrep", "fd", "fzf", "grep", "ag", "search"), "search"),
        (("galculator", "calc", "bc", "qalculate"), "calc"),
        (("pdf", "evince", "qpdf", "pandoc", "poppler", "jq", "yq"), "doc"),
        (("usb", "pci", "lsusb", "lspci"), "usb"),
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


def _draw_glyph(draw: ImageDraw.ImageDraw, kind: str, c1: tuple, c2: tuple, hi: tuple) -> None:
    """Draw a crisp 2-tone geometric vector glyph centered in a 256x256 canvas."""
    cx, cy = 128, 128

    if kind == "hub":
        for dx, dy, col in [(-38, -38, c1), (6, -38, c2), (-38, 6, hi), (6, 6, c1)]:
            draw.rounded_rectangle([cx + dx, cy + dy, cx + dx + 32, cy + dy + 32], radius=8, fill=col)

    elif kind == "radio":
        tip_y = 86
        draw.polygon([(cx, tip_y + 6), (cx - 24, 186), (cx + 24, 186)], outline=hi, width=8)
        draw.line([(cx - 16, 152), (cx + 16, 152)], fill=c2, width=8)
        draw.ellipse([cx - 9, tip_y - 9, cx + 9, tip_y + 9], fill=c1)
        for rad, col in [(26, c2), (46, c1)]:
            draw.arc([cx - rad, tip_y - rad, cx + rad, tip_y + rad], 138, 222, fill=col, width=8)
            draw.arc([cx - rad, tip_y - rad, cx + rad, tip_y + rad], 318, 42, fill=col, width=8)

    elif kind == "radar":
        for rad in (26, 48, 70):
            draw.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], outline=c1, width=6)
        draw.line([(cx - 72, cy), (cx + 72, cy)], fill=(c1[0], c1[1], c1[2], 125), width=4)
        draw.line([(cx, cy - 72), (cx, cy + 72)], fill=(c1[0], c1[1], c1[2], 125), width=4)
        draw.line([(cx, cy), (cx + 48, cy - 48)], fill=c2, width=9)
        draw.ellipse([cx + 30, cy - 50, cx + 48, cy - 32], fill=hi)

    elif kind == "star":
        draw.polygon(_star_points(cx, cy - 2, 62, 26, 5), fill=c2)
        draw.polygon(_star_points(cx, cy - 2, 34, 14, 5), fill=c1)

    elif kind == "lock":
        draw.arc([86, 54, 170, 132], 180, 360, fill=hi, width=12)
        draw.line([(86, 92), (86, 112)], fill=hi, width=12)
        draw.line([(170, 92), (170, 112)], fill=hi, width=12)
        draw.rounded_rectangle([72, 108, 184, 194], radius=16, fill=c1)
        draw.ellipse([116, 134, 140, 158], fill=BADGE_BG)
        draw.rectangle([123, 152, 133, 176], fill=BADGE_BG)

    elif kind == "bolt":
        pts = [(144, 52), (80, 136), (124, 136), (112, 204), (176, 116), (132, 116)]
        draw.polygon(pts, fill=c2)
        draw.line([(134, 76), (102, 126)], fill=hi, width=6)

    elif kind == "clapper":
        draw.rounded_rectangle([64, 92, 192, 190], radius=14, outline=hi, width=9)
        draw.polygon([(64, 92), (192, 74), (188, 96), (64, 112)], fill=c1)
        draw.polygon([(112, 120), (112, 166), (156, 143)], fill=c2)

    elif kind == "qr":
        cells = [
            (0, 0, hi), (1, 0, hi), (3, 0, c1), (4, 0, c1),
            (0, 1, hi), (4, 1, c1),
            (2, 2, c2), (3, 2, hi),
            (0, 3, c1), (2, 3, hi), (4, 3, c2),
            (0, 4, c1), (1, 4, c1), (3, 4, c2), (4, 4, hi),
        ]
        start, step, box = 68, 25, 19
        for gx, gy, col in cells:
            x0 = start + gx * step
            y0 = start + gy * step
            draw.rounded_rectangle([x0, y0, x0 + box, y0 + box], radius=4, fill=col)

    elif kind == "chip":
        draw.rounded_rectangle([78, 78, 178, 178], radius=16, outline=hi, width=9)
        draw.rounded_rectangle([102, 102, 154, 154], radius=8, fill=c1)
        for offset in (94, 128, 162):
            draw.line([(offset, 54), (offset, 76)], fill=c2, width=8)
            draw.line([(offset, 180), (offset, 202)], fill=c2, width=8)
            draw.line([(54, offset), (76, offset)], fill=c2, width=8)
            draw.line([(180, offset), (202, offset)], fill=c2, width=8)

    elif kind == "prompt":
        draw.rounded_rectangle([60, 70, 196, 186], radius=14, outline=c1, width=9)
        draw.line([(86, 104), (114, 128), (86, 152)], fill=hi, width=11)
        draw.line([(126, 152), (168, 152)], fill=c2, width=11)

    elif kind == "vpn":
        pts = [(cx, 54), (186, 76), (180, 140), (cx, 200), (76, 140), (70, 76)]
        draw.polygon(pts, fill=(28, 34, 52, 255), outline=(54, 214, 195, 255), width=9)
        draw.arc([104, 92, 152, 138], 180, 360, fill=ALABASTER, width=8)
        draw.rounded_rectangle([98, 122, 158, 162], radius=8, fill=(255, 94, 126, 255))
        draw.ellipse([122, 136, 134, 148], fill=BADGE_BG)

    elif kind == "tor":
        # Concentric layered onion rings with clean top sprout
        onion_violet = (179, 136, 255, 255)
        peach = (255, 154, 98, 255)
        draw.line([(cx, 52), (cx, 72)], fill=peach, width=9)
        draw.line([(cx, 62), (cx + 18, 52)], fill=peach, width=7)
        draw.ellipse([72, 74, 184, 194], outline=onion_violet, width=10)
        draw.ellipse([90, 94, 166, 178], outline=ALABASTER, width=8)
        draw.ellipse([108, 114, 148, 160], fill=onion_violet)

    elif kind == "cloak":
        # Privacy visor / incognito shield + masked line
        draw.line([(68, 124), (188, 124)], fill=c1, width=10)
        draw.polygon([(84, 122), (98, 78), (158, 78), (172, 122)], fill=hi)
        draw.ellipse([80, 138, 118, 176], outline=c2, width=8)
        draw.ellipse([138, 138, 176, 176], outline=c2, width=8)
        draw.line([(118, 156), (138, 156)], fill=c2, width=8)

    elif kind == "cyber":
        # Hexagonal security workbench reticle
        pts = [
            (cx, 56), (188, 92), (188, 164), (cx, 200), (68, 164), (68, 92)
        ]
        draw.polygon(pts, outline=c1, width=9)
        draw.ellipse([94, 94, 162, 162], outline=c2, width=7)
        draw.line([(cx, 78), (cx, 102)], fill=hi, width=7)
        draw.line([(cx, 154), (cx, 178)], fill=hi, width=7)
        draw.line([(78, cy), (102, cy)], fill=hi, width=7)
        draw.line([(154, cy), (178, cy)], fill=hi, width=7)
        draw.ellipse([121, 121, 135, 135], fill=c1)

    elif kind == "wireshark":
        aqua = (54, 214, 195, 255)
        fin_pts = [
            (72, 162), (82, 130), (104, 96), (144, 72),
            (136, 106), (142, 138), (160, 162),
        ]
        draw.polygon(fin_pts, fill=aqua)
        draw.line([(60, 164), (196, 164)], fill=ALABASTER, width=8)
        draw.line([(72, 182), (184, 182)], fill=aqua, width=6)

    elif kind == "dns":
        draw.ellipse([66, 62, 190, 186], outline=c1, width=8)
        draw.ellipse([98, 62, 158, 186], outline=c2, width=7)
        draw.line([(68, 124), (188, 124)], fill=c1, width=7)
        for nx, ny, col in [(88, 86, hi), (168, 86, c2), (128, 178, hi)]:
            draw.ellipse([nx - 10, ny - 10, nx + 10, ny + 10], fill=col)

    elif kind == "office":
        draw.rounded_rectangle([68, 56, 188, 200], radius=14, outline=hi, width=9)
        draw.rectangle([136, 56, 162, 108], fill=(255, 94, 126, 255))
        draw.line([(88, 126), (168, 126)], fill=(247, 200, 115, 255), width=9)
        draw.line([(88, 152), (168, 152)], fill=hi, width=8)
        draw.line([(88, 176), (140, 176)], fill=(54, 214, 195, 255), width=8)

    elif kind == "writer":
        sky = (82, 183, 255, 255)
        draw.rounded_rectangle([70, 56, 186, 200], radius=12, outline=ALABASTER, width=8)
        draw.rounded_rectangle([84, 72, 172, 98], radius=5, fill=sky)
        for y, w in [(120, 86), (144, 86), (168, 60)]:
            draw.line([(86, y), (86 + w, y)], fill=ALABASTER, width=8)

    elif kind == "spreadsheet":
        emerald = (62, 213, 152, 255)
        draw.rounded_rectangle([64, 62, 192, 194], radius=12, outline=ALABASTER, width=8)
        draw.rounded_rectangle([74, 72, 182, 98], radius=5, fill=emerald)
        for gx in (108, 148):
            draw.line([(gx, 100), (gx, 186)], fill=ALABASTER, width=6)
        for gy in (128, 158):
            draw.line([(72, gy), (184, gy)], fill=ALABASTER, width=6)

    elif kind == "impress":
        coral = (255, 123, 98, 255)
        draw.rounded_rectangle([58, 66, 198, 166], radius=12, outline=ALABASTER, width=8)
        draw.line([(cx, 166), (cx, 196)], fill=ALABASTER, width=8)
        draw.line([(96, 196), (160, 196)], fill=ALABASTER, width=8)
        draw.pieslice([80, 88, 134, 142], 30, 310, fill=coral)
        draw.line([(146, 102), (178, 102)], fill=ALABASTER, width=8)
        draw.line([(146, 126), (174, 126)], fill=coral, width=8)

    elif kind == "draw":
        gold = (247, 200, 115, 255)
        coral = (255, 94, 126, 255)
        draw.polygon([(112, 66), (62, 166), (162, 166)], outline=gold, width=9)
        draw.ellipse([122, 108, 192, 178], fill=coral)
        draw.ellipse([104, 58, 120, 74], fill=ALABASTER)
        draw.ellipse([56, 158, 72, 174], fill=ALABASTER)

    elif kind == "math":
        aqua = (54, 214, 195, 255)
        draw.rounded_rectangle([66, 60, 190, 196], radius=14, outline=ALABASTER, width=8)
        draw.line([(84, 136), (100, 164), (124, 92), (174, 92)], fill=aqua, width=10)
        draw.line([(134, 120), (168, 162)], fill=ALABASTER, width=9)
        draw.line([(168, 120), (134, 162)], fill=ALABASTER, width=9)

    elif kind == "printer":
        draw.rounded_rectangle([84, 56, 172, 92], radius=6, fill=hi)
        draw.rounded_rectangle([58, 92, 198, 158], radius=14, fill=c1)
        draw.rounded_rectangle([84, 138, 172, 196], radius=6, fill=hi)
        draw.line([(98, 158), (158, 158)], fill=BADGE_BG, width=7)
        draw.line([(98, 176), (142, 176)], fill=BADGE_BG, width=7)

    elif kind == "bluetooth":
        aqua = (54, 214, 195, 255)
        draw.line([(cx, 56), (cx, 200)], fill=aqua, width=10)
        draw.line([(cx, 56), (168, 94), (92, 158)], fill=aqua, width=10)
        draw.line([(cx, 200), (168, 162), (92, 98)], fill=aqua, width=10)

    elif kind == "palette":
        draw.polygon([(cx, 56), (176, 132), (162, 182), (cx, 198), (94, 182), (80, 132)], fill=c1)
        draw.ellipse([104, 120, 152, 168], fill=c2)

    elif kind == "backup":
        draw.arc([64, 64, 192, 192], 35, 315, fill=c1, width=12)
        draw.polygon([(164, 64), (192, 88), (156, 100)], fill=c1)
        draw.line([(cx, 94), (cx, 132), (154, 148)], fill=hi, width=10)

    elif kind == "scanner":
        for x0, y0, dx, dy in [(64, 64, 34, 34), (192, 64, -34, 34), (64, 192, 34, -34), (192, 192, -34, -34)]:
            draw.line([(x0, y0), (x0 + dx, y0)], fill=hi, width=10)
            draw.line([(x0, y0), (x0, y0 + dy)], fill=hi, width=10)
        draw.ellipse([104, 104, 152, 152], fill=c1)

    elif kind == "pulse":
        draw.rounded_rectangle([60, 68, 196, 188], radius=14, outline=hi, width=8)
        pts = [(74, 132), (96, 132), (110, 94), (126, 164), (144, 108), (158, 132), (182, 132)]
        draw.line(pts, fill=c1, width=10, joint="curve")

    elif kind == "terminal":
        draw.rounded_rectangle([58, 66, 198, 190], radius=14, outline=hi, width=9)
        draw.line([(84, 108), (112, 130), (84, 152)], fill=c1, width=10)
        draw.line([(124, 152), (168, 152)], fill=c2, width=10)

    elif kind == "globe":
        draw.ellipse([60, 60, 196, 196], outline=c1, width=9)
        draw.ellipse([96, 60, 160, 196], outline=c2, width=7)
        draw.line([(62, 106), (194, 106)], fill=c1, width=7)
        draw.line([(62, 150), (194, 150)], fill=c1, width=7)

    elif kind == "wifi":
        draw.ellipse([116, 164, 140, 188], fill=hi)
        for rad, col in [(36, c2), (62, c1), (86, c2)]:
            draw.arc([cx - rad, 174 - rad, cx + rad, 174 + rad], 222, 318, fill=col, width=10)

    elif kind == "shield":
        pts = [(cx, 54), (186, 78), (180, 142), (cx, 200), (76, 142), (70, 78)]
        draw.polygon(pts, outline=c1, width=10)
        draw.line([(98, 128), (120, 150), (158, 102)], fill=c2, width=11)

    elif kind == "code":
        draw.line([(96, 86), (62, 128), (96, 170)], fill=c1, width=11)
        draw.line([(160, 86), (194, 128), (160, 170)], fill=c1, width=11)
        draw.line([(142, 76), (114, 180)], fill=c2, width=10)

    elif kind == "branch":
        draw.line([(92, 78), (92, 178)], fill=c1, width=10)
        draw.line([(92, 144), (162, 102)], fill=c2, width=10)
        for px, py, col in [(92, 78, hi), (92, 178, c1), (162, 102, c2)]:
            draw.ellipse([px - 14, py - 14, px + 14, py + 14], fill=col)

    elif kind == "disk":
        draw.rounded_rectangle([68, 58, 188, 198], radius=14, outline=hi, width=9)
        draw.ellipse([88, 76, 168, 156], outline=c1, width=9)
        draw.ellipse([116, 104, 140, 128], fill=hi)
        draw.line([(90, 178), (166, 178)], fill=c1, width=9)

    elif kind == "folder":
        pts = [(58, 78), (108, 78), (124, 96), (198, 96), (198, 186), (58, 186)]
        draw.polygon(pts, outline=c1, width=9)
        draw.line([(78, 128), (178, 128)], fill=hi, width=9)
        draw.line([(78, 154), (144, 154)], fill=c2, width=8)

    elif kind == "tree":
        draw.line([(82, 68), (82, 182)], fill=c1, width=9)
        for y, col, w in [(88, hi, 84), (128, c2, 70), (168, c1, 84)]:
            draw.line([(82, y), (82 + w, y)], fill=col, width=9)
            draw.ellipse([82 + w - 9, y - 9, 82 + w + 9, y + 9], fill=col)

    elif kind == "archive":
        draw.rounded_rectangle([68, 62, 188, 194], radius=14, outline=c1, width=9)
        draw.line([(128, 64), (128, 192)], fill=c2, width=8)
        for y in (86, 112, 138, 164):
            draw.rectangle([114, y, 142, y + 11], fill=hi)

    elif kind == "edit":
        draw.polygon([(70, 186), (80, 142), (158, 64), (192, 98), (114, 176)], outline=hi, width=9)
        draw.line([(144, 78), (178, 112)], fill=c1, width=9)
        draw.polygon([(70, 186), (80, 148), (108, 176)], fill=c1)

    elif kind == "equalizer":
        bars = [(74, 114, c1), (101, 76, c2), (128, 96, hi), (155, 66, c1), (182, 118, c2)]
        for bx, top_y, col in bars:
            draw.line([(bx, top_y), (bx, 188)], fill=col, width=13)

    elif kind == "play":
        draw.ellipse([60, 60, 196, 196], outline=hi, width=9)
        draw.polygon([(104, 88), (104, 168), (170, 128)], fill=c1)

    elif kind == "camera":
        draw.rounded_rectangle([58, 80, 198, 182], radius=14, outline=hi, width=9)
        draw.rounded_rectangle([100, 64, 156, 82], radius=5, fill=c1)
        draw.ellipse([96, 100, 160, 164], outline=c2, width=9)
        draw.ellipse([118, 122, 138, 142], fill=c1)

    elif kind == "search":
        draw.ellipse([66, 66, 154, 154], outline=hi, width=11)
        draw.line([(142, 142), (190, 190)], fill=c1, width=14)

    elif kind == "calc":
        draw.rounded_rectangle([68, 56, 188, 200], radius=14, outline=hi, width=8)
        draw.rounded_rectangle([84, 72, 172, 106], radius=6, fill=(54, 214, 195, 255))
        for gx in (94, 128, 162):
            for gy in (132, 166):
                col = (255, 94, 126, 255) if (gx == 162 and gy == 166) else hi
                draw.ellipse([gx - 10, gy - 10, gx + 10, gy + 10], fill=col)

    elif kind == "doc":
        pts = [(70, 56), (154, 56), (186, 88), (186, 200), (70, 200)]
        draw.polygon(pts, outline=hi, width=9)
        draw.line([(92, 108), (164, 108)], fill=c1, width=9)
        draw.line([(92, 138), (164, 138)], fill=hi, width=8)
        draw.line([(92, 168), (140, 168)], fill=c2, width=8)

    elif kind == "key":
        draw.ellipse([62, 96, 124, 158], outline=c1, width=11)
        draw.line([(124, 127), (196, 127)], fill=hi, width=11)
        draw.line([(166, 127), (166, 156)], fill=c2, width=10)
        draw.line([(188, 127), (188, 148)], fill=c2, width=10)

    elif kind == "usb":
        draw.line([(cx, 62), (cx, 192)], fill=hi, width=10)
        draw.polygon([(cx, 54), (cx - 13, 76), (cx + 13, 76)], fill=c1)
        draw.line([(cx, 146), (82, 114), (82, 94)], fill=c2, width=9)
        draw.line([(cx, 132), (174, 102), (174, 86)], fill=c2, width=9)
        draw.ellipse([114, 174, 142, 202], fill=c1)

    elif kind == "clock":
        draw.ellipse([58, 58, 198, 198], outline=hi, width=9)
        draw.line([(cx, cy), (cx, 82)], fill=hi, width=10)
        draw.line([(cx, cy), (162, 142)], fill=(255, 154, 98, 255), width=9)
        draw.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], fill=(255, 94, 126, 255))

    elif kind == "sparkle":
        draw.polygon(
            [(cx, 58), (142, 114), (198, cy), (142, 142), (cx, 198), (114, 142), (58, cy), (114, 114)],
            fill=c1,
        )
        draw.ellipse([68, 68, 84, 84], fill=hi)
        draw.ellipse([172, 170, 188, 186], fill=c2)

    elif kind == "database":
        draw.ellipse([68, 62, 188, 94], outline=c1, width=9)
        draw.line([(68, 78), (68, 176)], fill=c1, width=9)
        draw.line([(188, 78), (188, 176)], fill=c1, width=9)
        draw.arc([68, 110, 188, 142], 0, 180, fill=hi, width=9)
        draw.arc([68, 158, 188, 190], 0, 180, fill=c2, width=9)

    elif kind == "download":
        draw.line([(cx, 58), (cx, 150)], fill=c1, width=11)
        draw.line([(90, 120), (cx, 154), (166, 120)], fill=hi, width=11)
        draw.line([(68, 184), (188, 184)], fill=c2, width=11)

    elif kind == "package":
        pts = [(cx, 58), (192, 92), (192, 164), (cx, 198), (64, 164), (64, 92)]
        draw.polygon(pts, outline=hi, width=9)
        draw.line([(66, 94), (cx, 126), (190, 94)], fill=c1, width=9)
        draw.line([(cx, 126), (cx, 196)], fill=c2, width=9)

    elif kind == "sliders":
        for y, knob_x, col in [(84, 102, c1), (128, 156, c2), (172, 118, hi)]:
            draw.line([(66, y), (190, y)], fill=RIM_BASE, width=8)
            draw.ellipse([knob_x - 14, y - 14, knob_x + 14, y + 14], fill=col)

    elif kind == "fetch":
        # GTA VI Sunset Debian Open-Use swirl + bold geometric VI + Aqua horizon accent
        scx, scy = 114.0, 114.0
        pts_n = 360
        for idx in range(pts_n):
            t = idx / (pts_n - 1)
            theta = 0.55 + t * (2.92 * math.pi)
            rad = 4.0 + 72.0 * (t ** 1.05)
            px = scx + rad * math.cos(theta)
            py = scy + rad * math.sin(theta)
            if t < 0.72:
                hw = 3.0 + 9.2 * math.sin((t / 0.72) * (math.pi * 0.65))
            else:
                tail_t = (t - 0.72) / 0.28
                hw = 10.2 * (1.0 - tail_t ** 0.85) + 1.5
            col = _lerp_color(
                (155, 93, 229, 255),
                (255, 110, 127, 255),
                t * 2.0,
            ) if t < 0.5 else _lerp_color(
                (255, 110, 127, 255),
                (255, 209, 102, 255),
                (t - 0.5) * 2.0,
            )
            draw.ellipse([px - hw, py - hw, px + hw, py + hw], fill=col)
        # Vice Aqua coastal horizon hairline at bottom-left
        draw.line([(54, 190), (122, 190)], fill=(54, 214, 195, 255), width=7)
        # Crisp VI monogram tucked at bottom-right with clean dark slate halo
        v_poly = [(129, 132), (146, 132), (158, 174), (170, 132), (187, 132), (166, 196), (150, 196)]
        i_poly = [(193, 132), (208, 132), (208, 196), (193, 196)]
        for poly in (v_poly, i_poly):
            draw.polygon(poly, fill=BADGE_BG)
            for j in range(len(poly)):
                draw.line([poly[j], poly[(j + 1) % len(poly)]], fill=BADGE_BG, width=10)
        draw.polygon(v_poly, fill=ALABASTER)
        draw.polygon(i_poly, fill=(247, 200, 115, 255))

    elif kind == "payload":
        # Encoder / Recon Lab: Aqua < > brackets + Sunset lightning/hex core
        aqua = (54, 214, 195, 255)
        coral = (255, 94, 126, 255)
        gold = (247, 200, 115, 255)
        draw.line([(90, 80), (54, 128), (90, 176)], fill=aqua, width=11)
        draw.line([(166, 80), (202, 128), (166, 176)], fill=aqua, width=11)
        bolt = [(138, 66), (104, 132), (128, 132), (118, 190), (154, 122), (130, 122)]
        draw.polygon(bolt, fill=coral)
        draw.line([(134, 84), (116, 126)], fill=gold, width=6)

    elif kind == "wireless":
        # RF / Wireless auditing antenna + dual signal arcs + target diamond
        aqua = (54, 214, 195, 255)
        coral = (255, 94, 126, 255)
        draw.line([(cx, 92), (cx, 192)], fill=ALABASTER, width=10)
        draw.line([(cx - 26, 192), (cx + 26, 192)], fill=ALABASTER, width=9)
        draw.polygon([(cx, 72), (cx + 14, 88), (cx, 104), (cx - 14, 88)], fill=coral)
        for rad, col in [(36, aqua), (62, c2)]:
            draw.arc([cx - rad, 88 - rad, cx + rad, 88 + rad], 140, 220, fill=col, width=9)
            draw.arc([cx - rad, 88 - rad, cx + rad, 88 + rad], 320, 40, fill=col, width=9)

    elif kind == "forensics":
        # Forensics magnifier over hex/binary stack
        aqua = (54, 214, 195, 255)
        coral = (255, 94, 126, 255)
        for y, w in [(92, 40), (114, 52), (136, 34)]:
            draw.line([(86, y), (86 + w, y)], fill=aqua, width=8)
        draw.ellipse([64, 64, 158, 158], outline=ALABASTER, width=11)
        draw.line([(146, 146), (192, 192)], fill=coral, width=15)

    elif kind == "reversing":
        # Binary disassembly chip + inward probe arrows
        coral = (255, 94, 126, 255)
        gold = (247, 200, 115, 255)
        draw.rounded_rectangle([84, 78, 172, 178], radius=14, outline=ALABASTER, width=9)
        draw.line([(104, 108), (128, 128), (104, 148)], fill=coral, width=9)
        draw.line([(136, 148), (156, 148)], fill=gold, width=9)
        for py in (100, 128, 156):
            draw.line([(56, py), (82, py)], fill=gold, width=8)
            draw.line([(174, py), (200, py)], fill=gold, width=8)

    elif kind == "exploit":
        # Precision vulnerability crosshairs + diamond strike
        coral = (255, 94, 126, 255)
        gold = (247, 200, 115, 255)
        draw.ellipse([68, 68, 188, 188], outline=coral, width=9)
        for x0, y0, x1, y1 in [(cx, 50, cx, 92), (cx, 164, cx, 206), (50, cy, 92, cy), (164, cy, 206, cy)]:
            draw.line([(x0, y0), (x1, y1)], fill=ALABASTER, width=9)
        draw.polygon([(cx, 104), (152, cy), (cx, 152), (104, cy)], fill=gold)

    elif kind == "osint":
        # OSINT reconnaissance eye + linked satellite nodes
        aqua = (54, 214, 195, 255)
        peach = (255, 154, 98, 255)
        draw.arc([58, 86, 198, 170], 200, 340, fill=ALABASTER, width=9)
        draw.arc([58, 86, 198, 170], 20, 160, fill=ALABASTER, width=9)
        draw.ellipse([104, 104, 152, 152], outline=aqua, width=8)
        draw.ellipse([120, 120, 136, 136], fill=peach)
        for nx, ny in [(72, 70), (184, 70), (128, 188)]:
            draw.ellipse([nx - 8, ny - 8, nx + 8, ny + 8], fill=aqua)

    elif kind == "web_pentest":
        # Web pentest browser frame + slash probe
        aqua = (54, 214, 195, 255)
        coral = (255, 94, 126, 255)
        draw.rounded_rectangle([58, 66, 198, 190], radius=14, outline=ALABASTER, width=9)
        draw.line([(62, 98), (194, 98)], fill=RIM_BASE, width=7)
        draw.ellipse([74, 78, 86, 90], fill=coral)
        draw.ellipse([94, 78, 106, 90], fill=(247, 200, 115, 255))
        draw.line([(114, 168), (144, 116)], fill=coral, width=10)
        draw.line([(86, 124), (108, 142), (86, 160)], fill=aqua, width=9)
        draw.line([(170, 124), (148, 142), (170, 160)], fill=aqua, width=9)

    elif kind == "password":
        # Credential cracking bar + key bit
        coral = (255, 94, 126, 255)
        gold = (247, 200, 115, 255)
        draw.rounded_rectangle([56, 74, 200, 130], radius=14, outline=ALABASTER, width=9)
        for px, col in [(88, coral), (128, gold), (168, coral)]:
            draw.ellipse([px - 10, 92, px + 10, 112], fill=col)
        draw.ellipse([68, 152, 106, 190], outline=gold, width=9)
        draw.line([(106, 171), (190, 171)], fill=ALABASTER, width=9)
        draw.line([(160, 171), (160, 194)], fill=coral, width=9)
        draw.line([(182, 171), (182, 188)], fill=coral, width=9)

    elif kind == "sniff":
        # Packet capture waveform + pulse nodes
        aqua = (54, 214, 195, 255)
        peach = (255, 154, 98, 255)
        pts = [(56, 146), (86, 146), (104, 88), (128, 170), (154, 98), (172, 146), (200, 146)]
        draw.line(pts, fill=aqua, width=10, joint="curve")
        for nx, ny, col in [(104, 88, peach), (128, 170, ALABASTER), (154, 98, c1)]:
            draw.ellipse([nx - 10, ny - 10, nx + 10, ny + 10], fill=col)

    elif kind == "tunnel":
        # Encrypted tunnel arches + directional arrow
        aqua = (54, 214, 195, 255)
        peach = (255, 154, 98, 255)
        draw.arc([62, 62, 194, 194], 180, 360, fill=aqua, width=10)
        draw.arc([86, 86, 170, 170], 180, 360, fill=peach, width=9)
        draw.line([(62, 128), (62, 186)], fill=aqua, width=10)
        draw.line([(194, 128), (194, 186)], fill=aqua, width=10)
        draw.line([(92, 160), (164, 160)], fill=ALABASTER, width=10)
        draw.line([(142, 138), (166, 160), (142, 182)], fill=ALABASTER, width=10)

    elif kind == "crypto":
        # Isometric cipher cube + coral keyhole
        gold = (247, 200, 115, 255)
        coral = (255, 94, 126, 255)
        pts = [(cx, 56), (190, 92), (190, 164), (cx, 200), (66, 164), (66, 92)]
        draw.polygon(pts, outline=gold, width=9)
        draw.line([(68, 94), (cx, 126), (188, 94)], fill=ALABASTER, width=8)
        draw.line([(cx, 126), (cx, 196)], fill=ALABASTER, width=8)
        draw.ellipse([cx - 14, 80, cx + 14, 108], fill=coral)

    elif kind == "steg":
        # Layered image frame with tucked hidden reveal corner
        aqua = (54, 214, 195, 255)
        coral = (255, 94, 126, 255)
        draw.rounded_rectangle([62, 66, 194, 190], radius=14, outline=ALABASTER, width=9)
        draw.polygon([(78, 170), (110, 118), (138, 152), (158, 128), (180, 170)], fill=aqua)
        draw.polygon([(142, 66), (194, 66), (194, 118)], fill=coral)

    elif kind == "vscode":
        # Visual Studio Code geometric infinity-ribbon emblem
        sky = (82, 183, 255, 255)
        aqua = (54, 214, 195, 255)
        draw.line([(68, 92), (166, 174)], fill=aqua, width=20)
        draw.line([(68, 164), (166, 82)], fill=sky, width=22)
        draw.polygon([(156, 62), (192, 76), (192, 180), (156, 194)], fill=sky)
        draw.line([(162, 80), (162, 176)], fill=ALABASTER, width=6)

    elif kind == "cpp":
        # C++ bold C arc + dual plus marks
        aqua = (54, 214, 195, 255)
        peach = (255, 154, 98, 255)
        draw.arc([58, 76, 138, 180], 45, 315, fill=aqua, width=15)
        for px, col in [(154, ALABASTER), (188, peach)]:
            draw.line([(px - 12, cy), (px + 12, cy)], fill=col, width=9)
            draw.line([(px, cy - 12), (px, cy + 12)], fill=col, width=9)

    elif kind == "csharp":
        # C# / .NET bold C arc + sharp grid
        coral = (255, 94, 126, 255)
        gold = (247, 200, 115, 255)
        draw.arc([58, 76, 140, 180], 45, 315, fill=coral, width=15)
        for vx in (160, 182):
            draw.line([(vx, 98), (vx, 158)], fill=ALABASTER, width=8)
        for hy in (116, 140):
            draw.line([(146, hy), (196, hy)], fill=gold, width=8)

    elif kind == "rust":
        # Rust industrial cog gear + inner R
        peach = (255, 154, 98, 255)
        for deg in range(0, 360, 45):
            ang = math.radians(deg)
            x1 = cx + math.cos(ang) * 52
            y1 = cy + math.sin(ang) * 52
            x2 = cx + math.cos(ang) * 72
            y2 = cy + math.sin(ang) * 72
            draw.line([(x1, y1), (x2, y2)], fill=peach, width=15)
        draw.ellipse([70, 70, 186, 186], outline=peach, width=12)
        draw.line([(106, 98), (106, 158)], fill=ALABASTER, width=10)
        draw.arc([104, 98, 150, 132], 270, 90, fill=ALABASTER, width=10)
        draw.line([(126, 130), (150, 158)], fill=(255, 94, 126, 255), width=10)

    elif kind == "nodejs":
        # Node.js hexagonal perimeter + crisp N core
        emerald = (62, 213, 152, 255)
        aqua = (54, 214, 195, 255)
        pts = [(cx, 54), (192, 90), (192, 166), (cx, 202), (64, 166), (64, 90)]
        draw.polygon(pts, outline=emerald, width=10)
        draw.line([(98, 158), (98, 98), (158, 158), (158, 98)], fill=ALABASTER, width=11)
        draw.ellipse([150, 90, 166, 106], fill=aqua)

    elif kind == "typescript":
        # TypeScript framed TS mark
        aqua = (54, 214, 195, 255)
        gold = (247, 200, 115, 255)
        draw.rounded_rectangle([62, 62, 194, 194], radius=18, outline=aqua, width=10)
        draw.line([(82, 102), (126, 102)], fill=ALABASTER, width=11)
        draw.line([(104, 102), (104, 164)], fill=ALABASTER, width=11)
        draw.line([(172, 104), (144, 104), (144, 132), (172, 132), (172, 162), (142, 162)], fill=gold, width=10)

    elif kind == "golang":
        # Go speed trails + bold GO emblem
        aqua = (54, 214, 195, 255)
        for sx, sy in [(56, 106), (50, 128), (56, 150)]:
            draw.line([(sx, sy), (sx + 24, sy)], fill=aqua, width=7)
        draw.arc([84, 86, 140, 170], 35, 325, fill=ALABASTER, width=10)
        draw.line([(114, 128), (140, 128)], fill=ALABASTER, width=10)
        draw.ellipse([148, 86, 200, 170], outline=aqua, width=10)

    elif kind == "java":
        # Java steaming cup + saucer
        coral = (255, 94, 126, 255)
        peach = (255, 154, 98, 255)
        draw.rounded_rectangle([78, 112, 162, 174], radius=16, outline=ALABASTER, width=9)
        draw.arc([150, 122, 184, 158], 270, 90, fill=ALABASTER, width=9)
        draw.line([(68, 188), (178, 188)], fill=peach, width=9)
        for sx in (104, 132):
            draw.line([(sx, 98), (sx + 10, 80), (sx, 62)], fill=coral, width=8, joint="curve")

    elif kind == "php":
        # PHP pill frame + web script chevrons
        sky = (82, 183, 255, 255)
        coral = (255, 94, 126, 255)
        draw.ellipse([54, 84, 202, 172], outline=sky, width=9)
        draw.line([(98, 112), (78, 128), (98, 144)], fill=ALABASTER, width=8)
        draw.line([(136, 106), (120, 150)], fill=coral, width=8)
        draw.line([(158, 112), (178, 128), (158, 144)], fill=ALABASTER, width=8)

    elif kind == "ruby":
        # Ruby faceted gemstone
        coral = (255, 94, 126, 255)
        gold = (247, 200, 115, 255)
        pts = [(90, 68), (166, 68), (196, 106), (cx, 192), (60, 106)]
        draw.polygon(pts, fill=(130, 32, 58, 255), outline=coral, width=9)
        draw.line([(62, 106), (194, 106)], fill=ALABASTER, width=7)
        draw.line([(96, 106), (cx, 190), (160, 106)], fill=gold, width=7)
        draw.line([(90, 68), (96, 106), (cx, 68), (160, 106), (166, 68)], fill=ALABASTER, width=6)

    elif kind == "lua":
        # Lua planet + orbital ring + moon
        sky = (82, 183, 255, 255)
        aqua = (54, 214, 195, 255)
        peach = (255, 154, 98, 255)
        draw.arc([52, 56, 200, 204], 125, 345, fill=aqua, width=7)
        draw.ellipse([68, 76, 172, 180], fill=(32, 58, 102, 255), outline=sky, width=9)
        draw.ellipse([126, 94, 152, 120], fill=ALABASTER)
        draw.ellipse([166, 64, 194, 92], fill=peach)

    elif kind == "hw_detect":
        # Universal Hardware Auto-Detect silicon board + active probe core
        aqua = (54, 214, 195, 255)
        gold = (247, 200, 115, 255)
        coral = (255, 94, 126, 255)
        draw.rounded_rectangle([76, 76, 180, 180], radius=16, outline=ALABASTER, width=9)
        for offset in (96, 128, 160):
            draw.line([(offset, 52), (offset, 74)], fill=gold, width=8)
            draw.line([(offset, 182), (offset, 204)], fill=gold, width=8)
            draw.line([(52, offset), (74, offset)], fill=gold, width=8)
            draw.line([(182, offset), (204, offset)], fill=gold, width=8)
        draw.ellipse([98, 98, 158, 158], outline=aqua, width=8)
        draw.polygon([(cx, 108), (148, cy), (cx, 148), (108, cy)], fill=coral)

    else:  # "gear" default
        for deg in range(0, 360, 45):
            ang = math.radians(deg)
            x1 = cx + math.cos(ang) * 44
            y1 = cy + math.sin(ang) * 44
            x2 = cx + math.cos(ang) * 70
            y2 = cy + math.sin(ang) * 70
            draw.line([(x1, y1), (x2, y2)], fill=c1, width=15)
        draw.ellipse([82, 82, 174, 174], outline=hi, width=13)
        draw.ellipse([108, 108, 148, 148], fill=c2)


def render_tool_icon(tool: dict, size: int = 64) -> Image.Image:
    """Render a refined 64x64 satin-slate squircle GTA VI icon (zero slop clutter)."""
    s = 256  # 4x supersampling
    category = str(tool.get("category", "System"))
    c1, c2, hi = CATEGORY_PALETTES.get(category, CATEGORY_PALETTES["System"])

    canvas = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    pad = 16
    radius = 56
    box = [pad, pad, s - pad, s - pad]

    # 1. Satin deep slate squircle fill
    badge_mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(badge_mask).rounded_rectangle(box, radius=radius, fill=255)
    satin_fill = _vertical_gradient(s, BADGE_TOP, BADGE_BG, BADGE_BOT)
    canvas.paste(satin_fill, (0, 0), badge_mask)

    # 2. Structural hairline border + delicate coral-gold top sheen
    rim_w = 5
    rim_base = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(rim_base).rounded_rectangle(
        box, radius=radius, outline=RIM_BASE, width=rim_w
    )
    canvas = Image.alpha_composite(canvas, rim_base)

    sheen_mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(sheen_mask).rounded_rectangle(
        box, radius=radius, outline=255, width=rim_w
    )
    sheen_fade = _vertical_gradient(
        s, (215, 215, 215, 215), (45, 45, 45, 45), (0, 0, 0, 0)
    ).convert("L")
    sheen_mask = ImageChops.multiply(sheen_mask, sheen_fade)
    sheen_grad = _horizontal_gradient(s, [
        (0.0, (255, 94, 126, 255)),
        (0.5, (255, 154, 98, 255)),
        (1.0, (247, 200, 115, 255)),
    ])
    sheen_layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    sheen_layer.paste(sheen_grad, (0, 0), sheen_mask)
    canvas = Image.alpha_composite(canvas, sheen_layer)

    # 3. Crisp 2-tone app-authentic vector glyph (no blurry bloom)
    glyph_kind = _resolve_glyph_kind(tool)
    glyph_layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    _draw_glyph(ImageDraw.Draw(glyph_layer), glyph_kind, c1, c2, hi)
    canvas = Image.alpha_composite(canvas, glyph_layer)

    return canvas.resize((size, size), Image.LANCZOS)


def _desktop_categories(tool: dict) -> str:
    tid = tool_slug(str(tool.get("id", "")))
    if tid in NATIVE_XDG_CATEGORIES:
        return NATIVE_XDG_CATEGORIES[tid]
    if tid == "vice-tool-vscode":
        return "Development;IDE;"
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
        help="Path to tools_registry.json",
    )
    parser.add_argument(
        "--icon-dir", type=str, default="/usr/share/icons/hicolor/64x64/apps",
        help="Output directory for 64x64 hicolor PNG icons",
    )
    parser.add_argument(
        "--pixmap-dir", type=str, default="/usr/share/pixmaps",
        help="Output directory for fallback pixmap PNG icons",
    )
    parser.add_argument(
        "--desktop-dir", type=str, default="/usr/share/applications",
        help="Output directory for XDG .desktop launchers",
    )
    args = parser.parse_args()

    icons, desktops = generate_all(
        args.registry, args.icon_dir, args.pixmap_dir, args.desktop_dir
    )
    print(f"[SUCCESS] Generated {icons} icons (64x64) and {desktops} .desktop launchers.")


if __name__ == "__main__":
    main()
