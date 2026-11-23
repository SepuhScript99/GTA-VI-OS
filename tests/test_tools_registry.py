#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Tools Registry, Icon Generator, & Tool Deployment Tests.
Tests config/tools_registry.json (100/500 Batch 1), all 10 vice_tool_*.py
native apps, assets/generate_tool_icons.py live PNG + .desktop generation,
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

    def test_registry_schema_and_batch1_counts(self):
        reg = _load_registry()
        self.assertEqual(reg.get("target_count"), 500)
        self.assertEqual(reg.get("batch"), 1)
        self.assertTrue(isinstance(reg.get("theme"), str) and reg["theme"].strip())

        tools = reg.get("tools")
        self.assertIsInstance(tools, list)
        self.assertEqual(len(tools), 100, "Batch 1 must contain exactly 100 tools")
        self.assertEqual(reg.get("current_count"), len(tools))

        ids = [t.get("id") for t in tools]
        self.assertEqual(len(set(ids)), 100, "All 100 tool IDs must be unique")

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
        self.assertEqual(seen_categories["GTA VI Originals"], 10)
        self.assertEqual(sum(v for k, v in seen_categories.items() if k != "GTA VI Originals"), 90)

    def test_native_gta_tools_exist_and_meet_standards(self):
        reg = _load_registry()
        natives = [t for t in reg["tools"] if t.get("package") == "vice-native"]
        self.assertEqual(len(natives), 10)
        self.assertEqual({t["id"] for t in natives}, EXPECTED_NATIVE_IDS)

        for tool in natives:
            self.assertTrue(tool["gta_themed"], f"{tool['id']} must set gta_themed=true")
            self.assertFalse(tool["terminal"], f"{tool['id']} must set terminal=false")
            self.assertEqual(tool["category"], "GTA VI Originals")

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
            self.assertIn("Noto Sans CJK", code, f"Missing CJK font fallback in {script_name}")
            self.assertIn("closeEvent", code, f"Missing clean closeEvent shutdown in {script_name}")

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

    def test_non_native_packages_in_packages_list_and_no_duplicates(self):
        pkgs_list = _load_packages_list()
        self.assertEqual(len(pkgs_list), len(set(pkgs_list)), "Duplicate entries found in config/packages.list")
        pkgs_set = set(pkgs_list)
        self.assertNotIn("pulseaudio", pkgs_set, "Conflicting pulseaudio daemon must not be in packages.list")

        reg = _load_registry()
        non_native = [t for t in reg["tools"] if t.get("package") != "vice-native"]
        self.assertEqual(len(non_native), 90)
        for tool in non_native:
            self.assertFalse(tool["gta_themed"], f"Debian tool {tool['id']} should have gta_themed=false")
            pkg = tool["package"]
            self.assertTrue(
                pkg in pkgs_set or pkg in DEBIAN_BASE_PACKAGES,
                f"Tool {tool['id']} package '{pkg}' is missing from config/packages.list",
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

    def test_live_generate_100_icons_and_desktop_files(self):
        reg = _load_registry()
        tools = reg["tools"]
        gen_path = os.path.join(ASSETS_DIR, "generate_tool_icons.py")
        reg_path = os.path.join(CONFIG_DIR, "tools_registry.json")

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
                self.assertEqual(len(icons), 100)
                self.assertEqual(len(pixmaps), 100)
                for png in icons + pixmaps:
                    w, h = _read_png_dimensions(png)
                    self.assertEqual((w, h), (64, 64), f"Expected 64x64 PNG, got {(w, h)} for {png}")
                self._validate_desktop_outputs(desktop_dir, tools)
            else:
                # Minimal CI runner without Pillow: still validate .desktop generation and glyph lookup
                pil_pkg = types.ModuleType("PIL")
                pil_img = types.ModuleType("PIL.Image")
                pil_draw = types.ModuleType("PIL.ImageDraw")
                pil_filt = types.ModuleType("PIL.ImageFilter")
                pil_img.Image = object
                pil_draw.ImageDraw = object
                pil_pkg.Image = pil_img
                pil_pkg.ImageDraw = pil_draw
                pil_pkg.ImageFilter = pil_filt
                sys.path.insert(0, ASSETS_DIR)
                try:
                    with patch.dict(sys.modules, {
                        "PIL": pil_pkg,
                        "PIL.Image": pil_img,
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
    """Validates vice-run-tool.sh, chroot deployment, desktop shortcuts, and progress docs."""

    def test_vice_run_tool_script_structure_and_syntax(self):
        runner = os.path.join(SYSTEM_SCRIPTS_DIR, "vice-run-tool.sh")
        self.assertTrue(os.path.isfile(runner), "Missing system_scripts/vice-run-tool.sh")
        code = _read_text("system_scripts", "vice-run-tool.sh")
        self.assertTrue(code.splitlines()[0] == "#!/bin/bash")
        self.assertIn("set -Eeuo pipefail", code)
        self.assertIn('main "$@"', code)
        self.assertIn("xfce4-terminal", code)
        self.assertIn("/usr/sbin", code)
        self.assertNotIn("\r\n", code)

        bash_candidates = []
        which_bash = shutil.which("bash")
        if which_bash and "WindowsApps" not in which_bash:
            bash_candidates.append(which_bash)
        git_bash = r"C:\Program Files\Git\bin\bash.exe"
        if os.path.isfile(git_bash) and git_bash not in bash_candidates:
            bash_candidates.append(git_bash)

        bash_bin = None
        for cand in bash_candidates:
            try:
                probe = subprocess.run([cand, "--version"], capture_output=True, text=True, check=False)
                if probe.returncode == 0:
                    bash_bin = cand
                    break
            except OSError:
                continue

        if bash_bin:
            proc = subprocess.run([bash_bin, "-n", runner], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, f"bash -n failed on vice-run-tool.sh: {proc.stderr}")

    def test_chroot_deployment_hooks(self):
        user_setup = _read_text("chroot_scripts", "03_user_setup.sh")
        for token in (
            "/vice_payload/config/tools_registry.json",
            "/opt/vice-os/tools_registry.json",
            "/vice_payload/assets/generate_tool_icons.py",
            "/opt/vice-os/generate_tool_icons.py",
            "/usr/share/icons/hicolor/64x64/apps",
            "/usr/share/pixmaps",
            "/usr/share/applications",
            "gtk-update-icon-cache",
            "update-desktop-database",
        ):
            self.assertIn(token, user_setup)

        sys_install = _read_text("chroot_scripts", "09_install_system_scripts.sh")
        self.assertIn('install_scripts "system_scripts"', sys_install)
        self.assertIn("vice-run-tool.sh", sys_install)
        self.assertIn("/usr/local/bin/vice-run-tool", sys_install)

    def test_skel_desktop_shortcuts_for_new_tools(self):
        expected = {
            "vice-tool-hub.desktop": ("vice-tool-hub", "vice_tool_hub.py"),
            "vice-radio.desktop": ("vice-tool-radio", "vice_tool_radio.py"),
        }
        for fname, (icon_name, script_name) in expected.items():
            path = os.path.join(CONFIG_DIR, "skel", "Desktop", fname)
            self.assertTrue(os.path.isfile(path), f"Missing {path}")
            cp = configparser.ConfigParser(interpolation=None)
            cp.read(path, encoding="utf-8")
            self.assertIn("Desktop Entry", cp.sections())
            entry = cp["Desktop Entry"]
            self.assertEqual(entry.get("Type"), "Application")
            self.assertEqual(entry.get("Icon"), icon_name)
            self.assertEqual(entry.get("Terminal"), "false")
            self.assertIn(script_name, entry.get("Exec", ""))
            self.assertTrue(os.path.isfile(os.path.join(DESKTOP_DIR, script_name)))

    def test_tools_progress_markdown_matches_registry(self):
        doc_path = os.path.join(DOCS_DIR, "TOOLS_PROGRESS.md")
        self.assertTrue(os.path.isfile(doc_path), "Missing docs/TOOLS_PROGRESS.md")
        doc = _read_text("docs", "TOOLS_PROGRESS.md")
        self.assertIn("100 / 500", doc)
        self.assertIn("20%", doc)

        reg = _load_registry()
        for tool in reg["tools"]:
            self.assertIn(f"`{tool['id']}`", doc, f"TOOLS_PROGRESS.md missing tool ID {tool['id']}")


if __name__ == "__main__":
    unittest.main()
