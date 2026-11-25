#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Tools Registry, Icon Generator, & Tool Deployment Tests.
Tests config/tools_registry.json (425/500 Batch 4A), all 18 native Vice tools
(including vice_tool_payload_lab.py, vicefetch.sh, and vice-hw-autodetect.sh),
assets/generate_tool_icons.py live PNG + .desktop generation,
system_scripts/vice-run-tool.sh, chroot deployment, and docs/TOOLS_PROGRESS.md.
Run with: python3 -m unittest tests.test_tools_registry
"""

import ast
import configparser
import glob
import importlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_DIR = os.path.join(REPO_ROOT, "config")
DESKTOP_DIR = os.path.join(REPO_ROOT, "desktop")
ASSETS_DIR = os.path.join(REPO_ROOT, "assets")
CHROOT_DIR = os.path.join(REPO_ROOT, "chroot_scripts")
SYSTEM_SCRIPTS_DIR = os.path.join(REPO_ROOT, "system_scripts")
DOCS_DIR = os.path.join(REPO_ROOT, "docs")

EXPECTED_CATEGORIES = {
    "GTA VI Originals",
    "Office",
    "System",
    "Network",
    "Security",
    "Developer",
    "Files & Disk",
    "Media",
    "Productivity",
}

EXPECTED_NATIVE_IDS = {
    "vice-tool-hub",
    "vice-tool-radio",
    "vice-tool-net-radar",
    "vice-tool-missions",
    "vice-tool-vault",
    "vice-tool-turbo",
    "vice-tool-media-studio",
    "vice-tool-qr-hash",
    "vice-tool-sys-deck",
    "vice-tool-cheatsheets",
    "vice-tool-net-shield",
    "vice-tool-cyber-deck",
    "vice-tool-mac-cloak",
    "vice-tool-office-hub",
    "vice-tool-clock-sync",
    "vice-tool-fetch",
    "vice-tool-payload-lab",
    "vice-tool-hw-autodetect",
}

EXTERNAL_DEV_PACKAGES = {
    "code",
    "dotnet-sdk-8.0",
    "nodejs",
    "node-typescript",
}

BANNED_PACKAGES = {
    "nikto",
    "typst",
    "dnscrypt-proxy",
    "hashcat",
    "pandoc",
    "pulseaudio",
    "bettercap",
    "dns2tcp",
    "ptunnel-ng",
    "xkcdpass",
}

DEBIAN_BASE_PACKAGES = {
    "bash",
    "coreutils",
    "findutils",
    "grep",
    "gzip",
    "iproute2",
    "openssl",
    "procps",
    "sed",
    "tar",
    "util-linux",
}


def _read_text(*parts) -> str:
    with open(os.path.join(REPO_ROOT, *parts), "r", encoding="utf-8") as fp:
        return fp.read()


def _load_packages_list() -> list:
    pkgs = []
    for line in _read_text("config", "packages.list").splitlines():
        clean = line.split("#", 1)[0].strip()
        if clean:
            pkgs.append(clean)
    return pkgs


def _load_registry() -> dict:
    with open(os.path.join(CONFIG_DIR, "tools_registry.json"), "r", encoding="utf-8") as fp:
        return json.load(fp)


def _tool_slug(tool_id: str) -> str:
    clean = str(tool_id).strip().lower().replace(" ", "-")
    return clean if clean.startswith("vice-tool-") else f"vice-tool-{clean}"


def _read_png_dimensions(path: str) -> tuple:
    with open(path, "rb") as fp:
        header = fp.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError(f"Invalid PNG signature in {path}")
    if header[12:16] != b"IHDR":
        raise AssertionError(f"Missing IHDR chunk in {path}")
    return struct.unpack(">II", header[16:24])


class TestToolsRegistry(unittest.TestCase):
    """Validates config/tools_registry.json, native apps, and Debian Bookworm packages."""

    def test_registry_schema_and_batch4_counts(self):
        reg = _load_registry()
        self.assertEqual(reg.get("target_count"), 500)
        self.assertEqual(reg.get("total_slots"), 500)
        self.assertEqual(reg.get("implemented_count"), 425)
        self.assertEqual(reg.get("batch"), 4)
        self.assertTrue(isinstance(reg.get("theme"), str) and reg["theme"].strip())

        tools = reg.get("tools")
        self.assertIsInstance(tools, list)
        self.assertEqual(len(tools), 425, "Batch 4A must contain exactly 425 tools")
        self.assertEqual(reg.get("current_count"), len(tools))

        ids = [t.get("id") for t in tools]
        self.assertEqual(len(set(ids)), 425, "All 425 tool IDs must be unique")

        seen_categories = {}
        for tool in tools:
            for key in ("id", "name", "description", "category", "package", "exec", "icon_glyph"):
                val = tool.get(key)
                self.assertIsInstance(val, str, f"Tool {tool.get('id')} field '{key}' must be str")
                self.assertTrue(val.strip(), f"Tool {tool.get('id')} has empty '{key}'")
            self.assertIsInstance(tool.get("terminal"), bool, f"Tool {tool.get('id')} terminal must be bool")
            self.assertIsInstance(tool.get("gta_themed"), bool, f"Tool {tool.get('id')} gta_themed must be bool")
            cat = tool["category"]
            self.assertIn(cat, EXPECTED_CATEGORIES, f"Unexpected category '{cat}' for {tool['id']}")
            seen_categories[cat] = seen_categories.get(cat, 0) + 1

        self.assertEqual(set(seen_categories.keys()), EXPECTED_CATEGORIES)
        self.assertEqual(seen_categories["GTA VI Originals"], 18)
        self.assertEqual(seen_categories["Office"], 11)
        self.assertGreaterEqual(seen_categories["Security"], 133)
        self.assertGreaterEqual(seen_categories["Developer"], 82)
        self.assertEqual(sum(v for k, v in seen_categories.items() if k != "GTA VI Originals"), 407)

    def test_office_security_vpn_dns_and_debian_coverage(self):
        reg = _load_registry()
        tools_by_id = {t["id"]: t for t in reg["tools"]}
        pkgs_set = set(_load_packages_list())

        for banned in BANNED_PACKAGES:
            self.assertNotIn(banned, pkgs_set, f"Banned/absent/bloated package '{banned}' in packages.list")
            self.assertFalse(
                any(t["package"] == banned for t in reg["tools"]),
                f"Banned/absent/bloated package '{banned}' in tools_registry.json",
            )

        required_office = (
            "libreoffice-writer", "libreoffice-calc", "libreoffice-impress",
            "libreoffice-draw", "libreoffice-math", "qpdfview", "evince", "simple-scan",
        )
        for tid in required_office:
            self.assertIn(tid, tools_by_id, f"Missing Office tool '{tid}'")
            self.assertEqual(tools_by_id[tid]["category"], "Office")

        for lo_support in ("libreoffice-gtk3", "libreoffice-style-sifr", "libreoffice-style-colibre"):
            self.assertIn(lo_support, pkgs_set, f"Missing LibreOffice GTK3/theme package '{lo_support}'")

        for pkg in ("network-manager-openvpn-gnome", "openresolv", "neofetch"):
            self.assertIn(pkg, pkgs_set, f"Missing required package '{pkg}'")

        required_security_vpn_dns_kali = (
            "openvpn", "wireguard-tools",
            "tor", "torsocks", "privoxy", "stubby", "unbound",
            "macchanger", "ufw", "gufw", "clamav", "firejail", "keepassxc",
            "sqlmap", "gobuster", "dirb", "hydra", "john", "aircrack-ng",
            "wireshark", "nmap", "binwalk", "yara", "lynis", "chkrootkit",
            "whatweb", "wafw00f", "sslscan", "testssl.sh", "dnsrecon", "mat2",
            # Batch 3 verified Debian 12 bookworm/main Kali tools
            "ffuf", "wfuzz", "wapiti", "weevely",
            "hcxdumptool", "hcxtools", "bully", "pixiewps", "btscanner", "mdk4",
            "dsniff", "netsniff-ng", "yersinia", "sslsplit", "python3-scapy",
            "scalpel", "ewf-tools", "dc3dd", "ssdeep", "exiv2", "outguess",
            "checksec", "dwarfdump", "zydis-tools", "hexyl", "adb", "uefitool-cli",
            "chntpw", "ophcrack-cli", "princeprocessor", "bruteforce-luks",
            "b3sum", "minisign", "nyx", "proxytunnel", "sublist3r", "zmap", "iptraf-ng",
        )
        for pkg in required_security_vpn_dns_kali:
            self.assertIn(pkg, pkgs_set, f"Missing Security/VPN/DNS/Kali package '{pkg}'")
            self.assertTrue(
                any(t["package"] == pkg for t in reg["tools"]),
                f"Missing Security/VPN/DNS/Kali tool entry for package '{pkg}'",
            )

        required_debian_features = (
            "cups", "system-config-printer", "bluez", "blueman", "udisks2",
            "ntfs-3g", "exfatprogs", "gnome-disk-utility", "timeshift",
            "flameshot", "gcolor3", "redshift", "xdg-desktop-portal-gtk",
            "bash-completion", "chrony",
        )
        for pkg in required_debian_features:
            self.assertIn(pkg, pkgs_set, f"Missing standard Debian feature '{pkg}'")

    def test_native_gta_tools_exist_and_meet_standards(self):
        reg = _load_registry()
        natives = [t for t in reg["tools"] if t.get("package") == "vice-native"]
        self.assertEqual(len(natives), 18)
        self.assertEqual({t["id"] for t in natives}, EXPECTED_NATIVE_IDS)

        for tool in natives:
            self.assertTrue(tool["gta_themed"], f"{tool['id']} must set gta_themed=true")
            self.assertEqual(tool["category"], "GTA VI Originals")

            if tool["id"] == "vice-tool-fetch":
                self.assertFalse(tool["terminal"], "vice-tool-fetch wraps terminal via xfce4-terminal")
                self.assertIn("xfce4-terminal", tool["exec"])
                self.assertIn("--geometry=116x30", tool["exec"])
                self.assertIn("/usr/local/bin/vicefetch --hold", tool["exec"])
                self.assertEqual(tool["icon_glyph"], "fetch")
                self.assertTrue(os.path.isfile(os.path.join(SYSTEM_SCRIPTS_DIR, "vicefetch.sh")))
                continue

            if tool["id"] == "vice-tool-hw-autodetect":
                self.assertTrue(tool["terminal"], "vice-tool-hw-autodetect runs CLI status in terminal")
                self.assertEqual(tool["exec"], "/usr/local/bin/vice-hw-autodetect --status")
                self.assertEqual(tool["icon_glyph"], "hw_detect")
                self.assertTrue(os.path.isfile(os.path.join(SYSTEM_SCRIPTS_DIR, "vice-hw-autodetect.sh")))
                continue

            self.assertFalse(tool["terminal"], f"{tool['id']} must set terminal=false")
            parts = tool["exec"].split()
            self.assertEqual(parts[0], "python3", f"{tool['id']} exec must launch via python3")
            script_name = os.path.basename(parts[-1])
            script_path = os.path.join(DESKTOP_DIR, script_name)
            self.assertTrue(os.path.isfile(script_path), f"Missing native script {script_path}")

            with open(script_path, "r", encoding="utf-8") as fp:
                code = fp.read()

            first_line = code.splitlines()[0] if code else ""
            self.assertTrue(first_line.startswith("#!/usr/bin/env python3"), f"Missing shebang in {script_name}")
            tree = ast.parse(code, filename=script_name)
            doc = ast.get_docstring(tree)
            self.assertTrue(bool(doc and len(doc.strip()) > 10), f"Missing docstring in {script_name}")
            self.assertIn("vice_theme", code, f"Native app {script_name} must adopt vice_theme")
            self.assertIn("Noto Sans CJK", code, f"Missing CJK font fallback in {script_name}")
            self.assertIn("closeEvent", code, f"Missing clean closeEvent shutdown in {script_name}")
            for legacy_hex in ("#00ffff", "#ff00ff", "#120e1e", "#ff4da6"):
                self.assertNotIn(legacy_hex, code.lower(), f"Legacy neon color {legacy_hex} in {script_name}")

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module == "PyQt5.QtWidgets":
                    imported = {a.name for a in node.names}
                    self.assertNotIn("QProcess", imported, f"{script_name} imports QProcess from QtWidgets")
                if all((
                    isinstance(node, ast.Call),
                    isinstance(getattr(node, "func", None), ast.Attribute),
                    getattr(getattr(node, "func", None), "attr", None) == "getlogin",
                    isinstance(getattr(getattr(node, "func", None), "value", None), ast.Name),
                    getattr(getattr(getattr(node, "func", None), "value", None), "id", None) == "os",
                )):
                    self.fail(f"{script_name} calls os.getlogin()")

    def test_payload_lab_functional_logic(self):
        """Verify vice_tool_payload_lab codecs, JWT parser, hashes, CIDR, regex, and header audit."""
        sys.path.insert(0, DESKTOP_DIR)
        try:
            try:
                import vice_tool_payload_lab as mod
            except ImportError:
                qt_pkg = types.ModuleType("PyQt5")
                qt_core = types.ModuleType("PyQt5.QtCore")
                qt_gui = types.ModuleType("PyQt5.QtGui")
                qt_widgets = types.ModuleType("PyQt5.QtWidgets")
                qt_core.Qt = type("Qt", (), {})
                qt_core.QSize = type("QSize", (), {})
                for name in ("QColor", "QFont", "QIcon", "QTextCharFormat"):
                    setattr(qt_gui, name, type(name, (), {}))
                for name in (
                    "QApplication", "QCheckBox", "QFrame", "QGridLayout", "QHBoxLayout",
                    "QHeaderView", "QLabel", "QLineEdit", "QMainWindow", "QPlainTextEdit",
                    "QPushButton", "QSplitter", "QTabWidget", "QTableWidget",
                    "QTableWidgetItem", "QTextEdit", "QVBoxLayout", "QWidget",
                ):
                    setattr(qt_widgets, name, type(name, (), {}))
                qt_pkg.QtCore = qt_core
                qt_pkg.QtGui = qt_gui
                qt_pkg.QtWidgets = qt_widgets
                with patch.dict(sys.modules, {
                    "PyQt5": qt_pkg,
                    "PyQt5.QtCore": qt_core,
                    "PyQt5.QtGui": qt_gui,
                    "PyQt5.QtWidgets": qt_widgets,
                }):
                    sys.modules.pop("vice_theme", None)
                    sys.modules.pop("vice_tool_payload_lab", None)
                    mod = importlib.import_module("vice_tool_payload_lab")

            b64 = mod.encode_decode_payload("b64_enc", "Leonida13")
            self.assertEqual(mod.encode_decode_payload("b64_dec", b64), "Leonida13")
            self.assertEqual(mod.encode_decode_payload("rot13", "Vice"), "Ivpr")
            self.assertEqual(mod.encode_decode_payload("hex_dec", "0x56696365"), "Vice")

            import base64 as _b64
            hdr = _b64.urlsafe_b64encode(b'{"alg":"HS256"}').decode().rstrip("=")
            pay = _b64.urlsafe_b64encode(b'{"sub":"vice"}').decode().rstrip("=")
            jwt_out = mod.decode_jwt_token(f"Bearer {hdr}.{pay}.sig")
            self.assertIn('"sub": "vice"', jwt_out)

            digests = mod.compute_hashes_and_hmac("abc", "key", hex_key=False)
            self.assertEqual(len(digests["sha256"]), 64)
            self.assertEqual(len(digests["hmac_sha256"]), 64)

            cidr = mod.analyze_cidr("192.168.1.42/24")
            self.assertEqual(cidr["network"], "192.168.1.0/24")
            self.assertEqual(cidr["usable_hosts"], "254")
            self.assertEqual(cidr["rfc1918"], "Yes")

            matches = mod.evaluate_regex(r"(?P<id>vice-\d+)", "id=vice-13")
            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0]["groupdict"]["id"], "vice-13")

            audit = mod.audit_http_headers("Strict-Transport-Security: max-age=31536000\nServer: nginx")
            self.assertTrue(audit["score"].startswith("1 / "))
            self.assertEqual(audit["info_leak"], ["server: nginx"])
        finally:
            for name in ("vice_tool_payload_lab", "vice_theme"):
                sys.modules.pop(name, None)
            if DESKTOP_DIR in sys.path:
                sys.path.remove(DESKTOP_DIR)

    def test_non_native_packages_in_packages_list_and_no_duplicates(self):
        pkgs_list = _load_packages_list()
        self.assertEqual(len(pkgs_list), len(set(pkgs_list)), "Duplicate entries found in config/packages.list")
        pkgs_set = set(pkgs_list)
        self.assertNotIn("pulseaudio", pkgs_set, "Conflicting pulseaudio daemon must not be in packages.list")
        self.assertNotIn("npm", pkgs_set, "Conflicting Debian npm package must not be in packages.list (NodeSource nodejs provides npm)")
        self.assertNotIn("node-typescript", pkgs_set, "Conflicting Debian node-typescript (Depends: nodejs:any) must not be in packages.list")

        install_sh = _read_text("chroot_scripts", "01_install_packages.sh")
        reg = _load_registry()
        non_native = [t for t in reg["tools"] if t.get("package") != "vice-native"]
        self.assertEqual(len(non_native), 407)
        for tool in non_native:
            self.assertFalse(tool["gta_themed"], f"Debian tool {tool['id']} should have gta_themed=false")
            pkg = tool["package"]
            ts_wired = pkg == "node-typescript" and "npm install -g typescript" in install_sh
            in_external_installer = pkg in EXTERNAL_DEV_PACKAGES and (pkg in install_sh or ts_wired)
            self.assertTrue(
                pkg in pkgs_set or pkg in DEBIAN_BASE_PACKAGES or in_external_installer,
                f"Tool {tool['id']} package '{pkg}' missing from config/packages.list and external installer",
            )

    def test_batch4a_vscode_lts_dev_stack_and_hw_firmware(self):
        pkgs_set = set(_load_packages_list())
        install_sh = _read_text("chroot_scripts", "01_install_packages.sh")
        reg = _load_registry()
        tools_by_id = {t["id"]: t for t in reg["tools"]}

        for token in (
            "configure_dev_repos",
            "install_dev_suite",
            "packages.microsoft.com/repos/code",
            "packages.microsoft.com/debian/12/prod",
            "deb.nodesource.com/node_22.x",
            "has_install_candidate code",
            "has_install_candidate dotnet-sdk-8.0",
            "apt-cache policy nodejs",
            "npm install -g typescript",
        ):
            self.assertIn(token, install_sh, f"01_install_packages.sh missing dev repo/suite logic '{token}'")

        required_hw_firmware = (
            "firmware-iwlwifi", "firmware-realtek", "firmware-atheros", "firmware-brcm80211",
            "firmware-sof-signed", "firmware-intel-sound", "firmware-amd-graphics",
            "intel-microcode", "amd64-microcode", "wpasupplicant", "wireless-regdb",
            "modemmanager", "usb-modeswitch", "qemu-guest-agent", "spice-vdagent",
            "xserver-xorg-input-all", "xserver-xorg-input-libinput", "mesa-vulkan-drivers",
            "fonts-jetbrains-mono", "build-essential", "python3-venv",
        )
        for pkg in required_hw_firmware:
            self.assertIn(pkg, pkgs_set, f"Missing Batch 4A HW/firmware/toolchain support package '{pkg}'")

        required_dev_packages = (
            "g++", "clang", "clangd", "lld", "ninja-build", "pkg-config",
            "python3-pip", "ipython3", "rustc", "cargo", "rustfmt",
            "golang-go", "openjdk-17-jdk-headless", "php-cli", "ruby", "lua5.4",
            "autoconf", "automake", "libtool", "meson", "ccache", "bear", "astyle",
            "universal-ctags", "shfmt", "yamllint", "codespell", "python3-pytest",
            "python3-flake8", "black", "pylint", "pipx", "dos2unix", "colordiff",
            "capstone-tool", "i2c-tools", "edid-decode", "v4l-utils", "brightnessctl",
            "efibootmgr", "mokutil", "tpm2-tools", "sysbench", "fio", "nghttp2-client",
        )
        for pkg in required_dev_packages:
            self.assertIn(pkg, pkgs_set, f"Missing Batch 4A dev/diag package '{pkg}'")
            self.assertTrue(
                any(t["package"] == pkg for t in reg["tools"]),
                f"Missing Batch 4A registry entry for package '{pkg}'",
            )

        for ext_id, ext_pkg in (
            ("vscode", "code"),
            ("dotnet-sdk-8.0", "dotnet-sdk-8.0"),
            ("nodejs", "nodejs"),
            ("node-typescript", "node-typescript"),
        ):
            self.assertIn(ext_id, tools_by_id)
            self.assertEqual(tools_by_id[ext_id]["package"], ext_pkg)
        self.assertEqual(tools_by_id["node-typescript"]["exec"], "tsc")
        self.assertEqual(tools_by_id["python3-flake8"]["exec"], "python3 -m flake8")

        for native_hw_pkg in (
            "thunar-volman", "gvfs-fuse", "gvfs-daemons", "mtp-tools",
            "usbmuxd", "fwupd", "unattended-upgrades", "dkms", "udisks2-btrfs",
        ):
            self.assertIn(native_hw_pkg, pkgs_set, f"Missing ISO #16 native HW/update pkg '{native_hw_pkg}'")

    def test_iso15_bookworm_install_order_and_typescript_wiring(self):
        pkgs_set = set(_load_packages_list())
        self.assertNotIn("node-typescript", pkgs_set)
        arm64_pkgs = {
            line.split("#", 1)[0].strip()
            for line in _read_text("config", "packages.arm64.list").splitlines()
            if line.split("#", 1)[0].strip()
        }
        self.assertNotIn("node-typescript", arm64_pkgs)

        install_sh = _read_text("chroot_scripts", "01_install_packages.sh")
        main_body = install_sh.split("\nmain() {", 1)[1]
        avail_pos = main_body.index('apt-get "${APT_OPTS[@]}" install -y --no-install-recommends "${available_pkgs[@]}"')
        clean_pos = main_body.index("apt-get clean", avail_pos)
        repos_pos = main_body.index('configure_dev_repos "${build_arch}"')
        suite_pos = main_body.index("install_dev_suite")
        self.assertLess(avail_pos, clean_pos, "apt-get clean must follow available_pkgs installation")
        self.assertLess(clean_pos, repos_pos, "configure_dev_repos must run AFTER Bookworm available_pkgs installation")
        self.assertLess(repos_pos, suite_pos, "install_dev_suite must run AFTER configure_dev_repos")

        dev_suite_body = install_sh.split("install_dev_suite() {", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("npm install -g typescript", dev_suite_body)
        self.assertIn("install_debian_nodejs_fallback", dev_suite_body)
        self.assertIn("apt-get clean", dev_suite_body)

        fallback_body = install_sh.split("install_debian_nodejs_fallback() {", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("node-typescript", fallback_body)

        self.assertNotIn("apt-cache policy nodejs 2>/dev/null | grep -q", install_sh)
        self.assertIn("awk '/Candidate:/ {if (!c) c=$2} END {print c}'", install_sh)
        self.assertIn('-o Dir::Etc::sourcelist="$list_path"', install_sh)

    def test_tool_exec_consistency_and_gui_launch_fixes(self):
        import shlex
        reg = _load_registry()
        tools_by_id = {t["id"]: t for t in reg["tools"]}

        expected_gui_fixes = {
            "timeshift": "timeshift-launcher",
            "feh": "feh --scale-down /usr/share/backgrounds",
            "flameshot": "flameshot gui",
            "gnome-screenshot": "gnome-screenshot --interactive",
        }
        for tid, expected_exec in expected_gui_fixes.items():
            self.assertIn(tid, tools_by_id)
            self.assertEqual(tools_by_id[tid]["exec"], expected_exec)
            self.assertFalse(tools_by_id[tid]["terminal"])

        gui_only_bins = {
            "python3", "libreoffice", "firefox-esr", "gparted", "wireshark",
            "qpdfview", "evince", "galculator", "mousepad", "geany",
            "pavucontrol", "synaptic-pkexec", "timeshift-launcher", "flameshot",
            "gnome-screenshot", "feh", "stacer", "bleachbit", "xfce4-taskmanager",
            "xfce4-terminal", "arandr", "lxappearance", "keepassxc", "baobab",
            "gufw", "ghex", "sqlitebrowser", "grsync", "celluloid", "ristretto",
            "gcolor3", "easytag", "zim", "cherrytree", "speedcrunch",
            "qalculate-gtk", "gnome-disks", "hardinfo", "simple-scan",
            "system-config-printer", "blueman-manager", "meld", "file-roller", "code",
        }
        for tool in reg["tools"]:
            ex = tool["exec"]
            parts = shlex.split(ex)
            self.assertTrue(parts, f"Empty shlex tokens for {tool['id']}")
            head = parts[0]
            self.assertNotIn("vice-run-tool", head, f"Registry exec for {tool['id']} should not pre-wrap vice-run-tool")
            for bad_tok in ("|", ";", "&&", "||", "`"):
                self.assertNotIn(bad_tok, ex, f"Shell metacharacter '{bad_tok}' in {tool['id']} exec: {ex}")
            if tool["terminal"]:
                if tool["id"] == "python3-flake8" and ex == "python3 -m flake8":
                    continue
                self.assertNotIn(head, gui_only_bins, f"GUI app '{head}' marked terminal=true for {tool['id']}")
            else:
                self.assertTrue(
                    head in gui_only_bins or head == "mpv",
                    f"Unexpected terminal=false head binary '{head}' for {tool['id']}",
                )


class TestToolIconGenerator(unittest.TestCase):
    """Validates assets/generate_tool_icons.py and runs live generation smoke test."""

    def test_generator_script_metadata_and_syntax(self):
        gen_path = os.path.join(ASSETS_DIR, "generate_tool_icons.py")
        self.assertTrue(os.path.isfile(gen_path))
        with open(gen_path, "r", encoding="utf-8") as fp:
            code = fp.read()
        self.assertTrue(code.splitlines()[0].startswith("#!/usr/bin/env python3"))
        tree = ast.parse(code, filename="generate_tool_icons.py")
        self.assertTrue(bool(ast.get_docstring(tree)))
        for flag in ("--registry", "--icon-dir", "--pixmap-dir", "--desktop-dir"):
            self.assertIn(flag, code)

    def _validate_desktop_outputs(self, desktop_dir: str, tools: list):
        desktop_files = sorted(glob.glob(os.path.join(desktop_dir, "*.desktop")))
        self.assertEqual(len(desktop_files), len(tools))
        by_slug = {_tool_slug(t["id"]): t for t in tools}

        for df in desktop_files:
            slug = os.path.splitext(os.path.basename(df))[0]
            self.assertIn(slug, by_slug)
            tool = by_slug[slug]

            cp = configparser.ConfigParser(interpolation=None)
            cp.read(df, encoding="utf-8")
            self.assertIn("Desktop Entry", cp.sections(), f"Missing [Desktop Entry] in {df}")
            entry = cp["Desktop Entry"]
            self.assertEqual(entry.get("Type"), "Application")
            self.assertTrue(entry.get("Name", "").strip())
            self.assertTrue(entry.get("Comment", "").strip())
            self.assertEqual(entry.get("Icon"), slug)
            self.assertEqual(entry.get("Terminal"), "false")
            self.assertTrue(entry.get("Categories", "").strip())
            if tool["terminal"]:
                self.assertTrue(
                    entry.get("Exec", "").startswith("vice-run-tool "),
                    f"Terminal tool {slug} Exec must wrap with vice-run-tool",
                )
            else:
                self.assertEqual(entry.get("Exec"), tool["exec"])

    def test_live_generate_425_icons_and_desktop_files(self):
        reg = _load_registry()
        tools = reg["tools"]
        self.assertEqual(len(tools), 425)
        gen_path = os.path.join(ASSETS_DIR, "generate_tool_icons.py")
        reg_path = os.path.join(CONFIG_DIR, "tools_registry.json")

        with open(gen_path, "r", encoding="utf-8") as fp:
            gen_code = fp.read()
        for glyph in (
            "fetch", "payload", "wireless", "forensics", "reversing", "exploit",
            "osint", "web_pentest", "password", "sniff", "tunnel", "crypto", "steg",
            "vscode", "cpp", "csharp", "rust", "nodejs", "typescript", "golang",
            "java", "php", "ruby", "lua", "hw_detect",
        ):
            self.assertIn(f'"{glyph}"', gen_code, f"generate_tool_icons.py missing glyph '{glyph}'")

        with tempfile.TemporaryDirectory() as tmpdir:
            icon_dir = os.path.join(tmpdir, "icons")
            pixmap_dir = os.path.join(tmpdir, "pixmaps")
            desktop_dir = os.path.join(tmpdir, "applications")

            try:
                import PIL  # noqa: F401
                has_pil = True
            except ImportError:
                has_pil = False

            if has_pil:
                proc = subprocess.run(
                    [
                        sys.executable,
                        gen_path,
                        "--registry", reg_path,
                        "--icon-dir", icon_dir,
                        "--pixmap-dir", pixmap_dir,
                        "--desktop-dir", desktop_dir,
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(proc.returncode, 0, f"generate_tool_icons.py failed:\n{proc.stderr}\n{proc.stdout}")
                icons = sorted(glob.glob(os.path.join(icon_dir, "*.png")))
                pixmaps = sorted(glob.glob(os.path.join(pixmap_dir, "*.png")))
                self.assertEqual(len(icons), 425)
                self.assertEqual(len(pixmaps), 425)
                for png in icons + pixmaps:
                    w, h = _read_png_dimensions(png)
                    self.assertEqual((w, h), (64, 64), f"Expected 64x64 PNG, got {(w, h)} for {png}")
                self._validate_desktop_outputs(desktop_dir, tools)
            else:
                # Minimal CI runner without Pillow: still validate .desktop generation and glyph lookup
                pil_pkg = types.ModuleType("PIL")
                pil_img = types.ModuleType("PIL.Image")
                pil_chops = types.ModuleType("PIL.ImageChops")
                pil_draw = types.ModuleType("PIL.ImageDraw")
                pil_filt = types.ModuleType("PIL.ImageFilter")
                pil_img.Image = object
                pil_draw.ImageDraw = object
                pil_pkg.Image = pil_img
                pil_pkg.ImageChops = pil_chops
                pil_pkg.ImageDraw = pil_draw
                pil_pkg.ImageFilter = pil_filt
                sys.path.insert(0, ASSETS_DIR)
                try:
                    with patch.dict(sys.modules, {
                        "PIL": pil_pkg,
                        "PIL.Image": pil_img,
                        "PIL.ImageChops": pil_chops,
                        "PIL.ImageDraw": pil_draw,
                        "PIL.ImageFilter": pil_filt,
                    }):
                        mod = importlib.import_module("generate_tool_icons")
                        os.makedirs(desktop_dir, exist_ok=True)
                        for tool in tools:
                            slug = mod.tool_slug(tool["id"])
                            self.assertTrue(mod._resolve_glyph_kind(tool))
                            with open(os.path.join(desktop_dir, f"{slug}.desktop"), "w", encoding="utf-8") as fp:
                                fp.write(mod.format_desktop_entry(tool))
                        self._validate_desktop_outputs(desktop_dir, tools)
                finally:
                    sys.modules.pop("generate_tool_icons", None)
                    if ASSETS_DIR in sys.path:
                        sys.path.remove(ASSETS_DIR)


class TestToolsIntegrationAndDeployment(unittest.TestCase):
    """Validates vice-run-tool.sh, vicefetch.sh, chroot deployment, desktop shortcuts, and progress docs."""

    @staticmethod
    def _find_bash():
        bash_candidates = []
        which_bash = shutil.which("bash")
        if which_bash and "WindowsApps" not in which_bash:
            bash_candidates.append(which_bash)
        git_bash = r"C:\Program Files\Git\bin\bash.exe"
        if os.path.isfile(git_bash) and git_bash not in bash_candidates:
            bash_candidates.append(git_bash)

        for cand in bash_candidates:
            try:
                probe = subprocess.run([cand, "--version"], capture_output=True, text=True, check=False)
                if probe.returncode == 0:
                    return cand
            except OSError:
                continue
        return None

    def test_vice_run_tool_script_structure_and_syntax(self):
        runner = os.path.join(SYSTEM_SCRIPTS_DIR, "vice-run-tool.sh")
        self.assertTrue(os.path.isfile(runner), "Missing system_scripts/vice-run-tool.sh")
        code = _read_text("system_scripts", "vice-run-tool.sh")
        self.assertTrue(code.splitlines()[0] == "#!/bin/bash")
        self.assertIn("set -Eeuo pipefail", code)
        self.assertIn('main "$@"', code)
        self.assertIn("xfce4-terminal", code)
        self.assertIn("/usr/sbin", code)
        self.assertIn("needs_root_exec", code)
        self.assertIn('[ "${cmd_args[1]}" = "-m" ]', code)
        self.assertNotIn("\r\n", code)

        for batch_cli in (
            "testssl", "sqlmap", "gobuster", "dirb", "whatweb", "wafw00f",
            "wg-quick", "openvpn", "tor", "binwalk", "yara", "mat2", "tldr", "yq",
            "ffuf", "wfuzz", "wapiti", "weevely", "hcxdumptool", "hcxpcapngtool",
            "dsniff", "netsniff-ng", "yersinia", "scalpel", "dc3dd", "checksec",
            "dwarfdump", "ZydisDisasm", "adb", "chntpw", "ophcrack-cli", "b3sum",
            "minisign", "proxytunnel", "sublist3r", "zmap", "tcptraceroute",
            "clang", "clangd", "lld", "ninja", "pkg-config", "pip3", "rustc",
            "cargo", "rustfmt", "tsc", "dotnet", "go", "javac", "php", "ruby",
            "v4l2-ctl", "tpm2", "sysbench", "fio", "nghttp",
        ):
            self.assertIn(batch_cli, code, f"vice-run-tool.sh missing CLI tool '{batch_cli}'")

        case_block = code.split("needs_args_prompt()", 1)[1].split("run_help_and_prompt()", 1)[0]
        for direct_tool in ("apg", "btscanner", "cadaver", "cgdb", "iptraf-ng", "iwconfig", "nwipe", "nyx", "rfkill", "scapy", "ipython3", "lua5.4"):
            self.assertNotIn(f"|{direct_tool}|", case_block, f"Interactive tool '{direct_tool}' should launch directly")

        bash_bin = self._find_bash()
        if bash_bin:
            proc = subprocess.run([bash_bin, "-n", runner], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, f"bash -n failed on vice-run-tool.sh: {proc.stderr}")

    def test_vicefetch_script_modes_and_registry_output(self):
        vf_path = os.path.join(SYSTEM_SCRIPTS_DIR, "vicefetch.sh")
        self.assertTrue(os.path.isfile(vf_path), "Missing system_scripts/vicefetch.sh")
        code = _read_text("system_scripts", "vicefetch.sh")
        self.assertEqual(code.splitlines()[0], "#!/bin/bash")
        self.assertIn("set -Eeuo pipefail", code)
        self.assertIn('main "$@"', code)
        self.assertNotIn("\r\n", code)
        for token in ("--plain", "--no-color", "--256", "--truecolor", "--hold", "--help", "--version", "COLORTERM", "config/os-release"):
            self.assertIn(token, code)

        bash_bin = self._find_bash()
        if bash_bin:
            syntax = subprocess.run([bash_bin, "-n", vf_path], capture_output=True, text=True, check=False)
            self.assertEqual(syntax.returncode, 0, f"bash -n failed on vicefetch.sh: {syntax.stderr}")

            help_p = subprocess.run([bash_bin, vf_path, "--help"], capture_output=True, text=True, check=False)
            self.assertEqual(help_p.returncode, 0)
            self.assertIn("--hold", help_p.stdout)

            clean_env = dict(os.environ, TERM="dumb")
            clean_env.pop("COLORTERM", None)
            plain_p = subprocess.run(
                [bash_bin, vf_path, "--plain"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", env=clean_env, check=False,
            )
            self.assertEqual(plain_p.returncode, 0, f"vicefetch.sh --plain failed: {plain_p.stderr}")
            self.assertIn("Vice OS", plain_p.stdout)
            self.assertIn("425 / 500 (85%)", plain_p.stdout)
            self.assertNotIn("\033[", plain_p.stdout)

            mode256 = subprocess.run(
                [bash_bin, vf_path, "--256"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", env=clean_env, check=False,
            )
            self.assertEqual(mode256.returncode, 0)
            self.assertIn("\033[", mode256.stdout)

    def test_chroot_deployment_hooks(self):
        user_setup = _read_text("chroot_scripts", "03_user_setup.sh")
        for token in (
            "/vice_payload/config/vice-os/vice_ascii.txt",
            "/etc/vice-os/vice_ascii.txt",
            "/vice_payload/config/tools_registry.json",
            "/opt/vice-os/tools_registry.json",
            "/vice_payload/assets/generate_tool_icons.py",
            "/opt/vice-os/generate_tool_icons.py",
            "/usr/share/icons/hicolor/64x64/apps",
            "/usr/share/pixmaps",
            "/usr/share/applications",
            "libreoffice-${lo_app}.desktop",
            "code.desktop",
            "vice-tool-vscode",
            "lynis.desktop",
            "Icon=vice-tool-lynis",
            "gtk-update-icon-cache",
            "update-desktop-database",
        ):
            self.assertIn(token, user_setup)

        sys_install = _read_text("chroot_scripts", "09_install_system_scripts.sh")
        self.assertIn('install_scripts "system_scripts"', sys_install)
        self.assertIn("vice-run-tool.sh", sys_install)
        self.assertIn("/usr/local/bin/vice-run-tool", sys_install)
        self.assertIn("vice-timesync.sh", sys_install)
        self.assertIn("/usr/local/bin/vice-timesync", sys_install)
        self.assertIn("vicefetch.sh", sys_install)
        self.assertIn("/usr/local/bin/vicefetch", sys_install)
        self.assertIn("vice-hw-autodetect.sh", sys_install)
        self.assertIn("/usr/local/bin/vice-hw-autodetect", sys_install)

        skel_setup = _read_text("chroot_scripts", "22_skel_setup.sh")
        self.assertIn(".config/neofetch/config.conf", skel_setup)
        self.assertIn(".config/Code/User/settings.json", skel_setup)
        self.assertIn("Desktop/vicefetch.desktop", skel_setup)
        self.assertIn("Desktop/vscode.desktop", skel_setup)

    def test_skel_desktop_shortcuts_for_new_tools(self):
        expected = {
            "vice-tool-hub.desktop": ("vice-tool-hub", "vice_tool_hub.py"),
            "vice-radio.desktop": ("vice-tool-radio", "vice_tool_radio.py"),
            "vice-office.desktop": ("vice-tool-office-hub", "vice_tool_office_hub.py"),
            "vice-net-shield.desktop": ("vice-tool-net-shield", "vice_tool_net_shield.py"),
            "vicefetch.desktop": ("vice-tool-fetch", "/usr/local/bin/vicefetch --hold"),
            "vscode.desktop": ("vice-tool-vscode", "/usr/bin/code %F"),
        }
        for fname, (icon_name, exec_target) in expected.items():
            path = os.path.join(CONFIG_DIR, "skel", "Desktop", fname)
            self.assertTrue(os.path.isfile(path), f"Missing {path}")
            cp = configparser.ConfigParser(interpolation=None)
            cp.read(path, encoding="utf-8")
            self.assertIn("Desktop Entry", cp.sections())
            entry = cp["Desktop Entry"]
            self.assertEqual(entry.get("Type"), "Application")
            self.assertEqual(entry.get("Icon"), icon_name)
            self.assertEqual(entry.get("Terminal"), "false")
            self.assertIn(exec_target, entry.get("Exec", ""))
            if exec_target.endswith(".py"):
                self.assertTrue(os.path.isfile(os.path.join(DESKTOP_DIR, exec_target)))
            if fname == "vice-tool-hub.desktop":
                self.assertIn("425/500", entry.get("Comment", ""))
                self.assertNotIn("375/500", entry.get("Comment", ""))
            if fname == "vicefetch.desktop":
                self.assertIn("--geometry=116x30", entry.get("Exec", ""))

    def test_tools_progress_markdown_matches_registry(self):
        doc_path = os.path.join(DOCS_DIR, "TOOLS_PROGRESS.md")
        self.assertTrue(os.path.isfile(doc_path), "Missing docs/TOOLS_PROGRESS.md")
        doc = _read_text("docs", "TOOLS_PROGRESS.md")
        self.assertIn("425 / 500", doc)
        self.assertIn("85%", doc)

        reg = _load_registry()
        for tool in reg["tools"]:
            self.assertIn(f"`{tool['id']}`", doc, f"TOOLS_PROGRESS.md missing tool ID {tool['id']}")

    def test_iso16_vscode_leonida_icon_and_turbo_radio_degimmick(self):
        gen_code = _read_text("assets", "generate_tool_icons.py")
        vscode_block = gen_code.split('elif kind == "vscode":', 1)[1].split("elif kind ==", 1)[0]
        self.assertNotIn("sky", vscode_block, "VS Code icon must use Leonida Sunset/Aqua, not legacy blue 'sky'")
        self.assertIn("coral", vscode_block)
        self.assertIn("aqua", vscode_block)

        turbo_code = _read_text("desktop", "vice_tool_turbo.py")
        for token in (
            "def _read_cpufreq_info",
            "def _read_zram_stats",
            "def _read_proc_stat_cpus",
            "vm.drop_caches=3",
            "Host-managed (VM)",
        ):
            self.assertIn(token, turbo_code)

        radio_code = _read_text("desktop", "vice_tool_radio.py")
        for token in (
            "def _pick_local_folder",
            "--audio-display=no",
            "defcon-128-mp3",
            "lush-128-mp3",
            "poptron-128-mp3",
        ):
            self.assertIn(token, radio_code)


if __name__ == "__main__":
    unittest.main()
