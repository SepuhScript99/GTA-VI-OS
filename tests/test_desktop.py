#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Desktop Subsystem Unit Tests
Tests panel_config, ob_menu, vice_setup_apps, session_watchdog,
wallpaper_manager, and desktop code standards/AST integrity.
Run with: python3 -m unittest tests.test_desktop
"""

import unittest
from unittest.mock import patch, mock_open, MagicMock
import sys
import os
import ast
import glob
import tempfile
import xml.etree.ElementTree as ET

# Add repo root, lib/, and desktop/ to path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DESKTOP_DIR = os.path.join(REPO_ROOT, 'desktop')
LIB_DIR = os.path.join(REPO_ROOT, 'lib')

sys.path.insert(0, LIB_DIR)
sys.path.insert(0, os.path.join(LIB_DIR, 'python'))
sys.path.insert(0, DESKTOP_DIR)

import panel_config
import ob_menu
import vice_setup_apps
import wallpaper_manager
import session_watchdog


class TestPanelConfig(unittest.TestCase):
    """Verifies panel_config constants and color palette."""

    def test_dimensions(self):
        self.assertGreater(panel_config.TOPBAR_HEIGHT, 0)
        self.assertGreater(panel_config.DOCK_HEIGHT, 0)
        self.assertGreater(panel_config.DOCK_WIDTH, 0)
        self.assertGreater(panel_config.RUNMENU_WIDTH, 0)
        self.assertGreater(panel_config.RUNMENU_HEIGHT, 0)
        self.assertGreater(panel_config.SYSTRAY_ICON_SIZE, 0)

    def test_dock_apps(self):
        self.assertIsInstance(panel_config.DOCK_APPS, list)
        self.assertGreater(len(panel_config.DOCK_APPS), 0)
        for app in panel_config.DOCK_APPS:
            self.assertEqual(len(app), 3, f"Dock app {app} must be a 3-tuple (label, cmd, tooltip)")
            label, cmd, tip = app
            self.assertIsInstance(label, str)
            self.assertIsInstance(cmd, str)
            self.assertIsInstance(tip, str)

    def test_neon_miami_palette(self):
        colors = [
            panel_config.COLOR_BG_DARK,
            panel_config.COLOR_CYAN,
            panel_config.COLOR_MAGENTA,
            panel_config.COLOR_WHITE,
            panel_config.COLOR_BORDER,
        ]
        for c in colors:
            self.assertTrue(c.startswith("#"), f"Color {c} should be a hex color")

    def test_stalonetray_args(self):
        args = panel_config.STALONETRAY_ARGS
        self.assertIn("--geometry", args)
        self.assertIn("--max-geometry", args)
        self.assertIn("--background", args)


class TestObMenu(unittest.TestCase):
    """Tests Openbox pipe menu generation and desktop file parsing."""

    def test_category_map(self):
        expected_cats = ["Development", "Graphics", "Internet", "Multimedia", "Office", "Settings", "System", "Utilities"]
        for cat in expected_cats:
            self.assertIn(cat, ob_menu.CATEGORY_MAP)

    def test_parse_desktop_file_valid(self):
        content = """[Desktop Entry]
Name=Test Editor
Exec=test-editor %F
Categories=Development;IDE;
Type=Application
"""
        with patch("builtins.open", mock_open(read_data=content)):
            info = ob_menu.parse_desktop_file("/fake/test.desktop")
            self.assertIsNotNone(info)
            self.assertEqual(info["name"], "Test Editor")
            self.assertEqual(info["exec"], "test-editor")
            self.assertIn("Development", info["categories"])

    def test_parse_desktop_file_nodisplay(self):
        content = """[Desktop Entry]
Name=Hidden App
Exec=hidden
NoDisplay=true
Type=Application
"""
        with patch("builtins.open", mock_open(read_data=content)):
            info = ob_menu.parse_desktop_file("/fake/hidden.desktop")
            self.assertIsNone(info)


class TestViceSetupApps(unittest.TestCase):
    """Verifies that APP_METADATA is accurate and mapped files exist."""

    def test_app_metadata_targets_exist(self):
        for script_name in vice_setup_apps.APP_METADATA.keys():
            full_path = os.path.join(DESKTOP_DIR, script_name)
            self.assertTrue(
                os.path.isfile(full_path),
                f"APP_METADATA references {script_name} which does not exist in desktop/"
            )

    def test_desktop_file_generation_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            orig_dir = vice_setup_apps.DESKTOP_APP_DIR
            try:
                vice_setup_apps.DESKTOP_APP_DIR = tmpdir
                meta = {"name": "Test Tool", "comment": "Test Comment", "cat": "Utility"}
                success, path = vice_setup_apps.create_desktop_file("vice_test.py", meta)
                self.assertTrue(success)
                self.assertTrue(os.path.exists(path))
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.assertIn("Name=Test Tool", content)
                self.assertIn("Comment=Test Comment", content)
                self.assertIn("Categories=Utility;", content)
            finally:
                vice_setup_apps.DESKTOP_APP_DIR = orig_dir


class TestSessionWatchdog(unittest.TestCase):
    """Tests session watchdog parameters and backoff logic."""

    def test_watchdog_constants(self):
        self.assertGreater(session_watchdog.POLL_INTERVAL, 0)
        self.assertGreaterEqual(session_watchdog.MAX_RESTARTS, 5)
        self.assertGreater(session_watchdog.INITIAL_BACKOFF, 0)
        self.assertGreater(session_watchdog.MAX_BACKOFF, session_watchdog.INITIAL_BACKOFF)

    @patch("session_watchdog.fcntl", None)
    def test_acquire_lock_when_no_fcntl(self):
        # On Windows or platforms where fcntl is None, should return None safely
        self.assertIsNone(session_watchdog._acquire_lock())


class TestWallpaperManager(unittest.TestCase):
    """Tests wallpaper search and generation detection."""

    def test_wallpaper_search(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_img = os.path.join(tmpdir, "vice-neon.png")
            with open(test_img, "wb") as f:
                f.write(b"PNG_DATA")
            with patch("wallpaper_manager._WALLPAPER_DIRS", [tmpdir]):
                found = wallpaper_manager._find_wallpaper()
                self.assertEqual(found, test_img)


class TestDesktopIntegrity(unittest.TestCase):
    """Tests AST parsing, shebang, and docstring on all desktop python files."""

    def setUp(self):
        self.py_files = sorted(glob.glob(os.path.join(DESKTOP_DIR, "*.py")))

    def test_all_files_compile(self):
        self.assertGreaterEqual(len(self.py_files), 70, "Should have 70+ desktop python components")
        for f in self.py_files:
            fname = os.path.basename(f)
            with open(f, "r", encoding="utf-8", errors="ignore") as fp:
                code = fp.read()
            try:
                tree = ast.parse(code, filename=fname)
                self.assertIsNotNone(tree)
            except SyntaxError as e:
                self.fail(f"Syntax error in {fname}: {e}")

    def test_all_files_have_docstrings(self):
        for f in self.py_files:
            fname = os.path.basename(f)
            with open(f, "r", encoding="utf-8", errors="ignore") as fp:
                code = fp.read()
            tree = ast.parse(code, filename=fname)
            doc = ast.get_docstring(tree)
            self.assertTrue(
                bool(doc and len(doc.strip()) > 5),
                f"Missing or empty docstring in {fname}"
            )

    def test_all_files_have_shebang(self):
        for f in self.py_files:
            fname = os.path.basename(f)
            with open(f, "r", encoding="utf-8", errors="ignore") as fp:
                first_line = fp.readline()
            self.assertTrue(
                first_line.startswith("#!/usr/bin/env python3"),
                f"Missing shebang in {fname}: {first_line.strip()}"
            )


class TestWindowManagementConfig(unittest.TestCase):
    """Regression tests for Openbox mouse controls, EWMH dock panels, and wizard chrome."""

    def test_openbox_rc_has_window_controls_and_resize_contexts(self):
        rc_path = os.path.join(REPO_ROOT, "config", "openbox_rc.xml")
        tree = ET.parse(rc_path)
        root = tree.getroot()
        ns = {"ob": "http://openbox.org/3.4/rc"}

        mouse_el = root.find("ob:mouse", ns)
        self.assertIsNotNone(mouse_el, "openbox_rc.xml missing <mouse> section")

        contexts = {c.attrib.get("name"): c for c in mouse_el.findall("ob:context", ns)}
        required_contexts = [
            "Titlebar", "Close", "Iconify", "Maximize", "Client",
            "Top", "Bottom", "Left", "Right", "TRCorner BRCorner TLCorner BLCorner",
        ]
        for ctx_name in required_contexts:
            self.assertIn(ctx_name, contexts, f"Missing Openbox mouse context: {ctx_name}")

        all_actions = {
            a.attrib.get("name")
            for a in mouse_el.findall(".//ob:action", ns)
        }
        for action_name in ["Move", "Resize", "Close", "Iconify", "ToggleMaximize"]:
            self.assertIn(action_name, all_actions, f"Missing Openbox mouse action: {action_name}")

    def test_vice_shell_single_instance_and_ewmh_dock(self):
        shell_path = os.path.join(DESKTOP_DIR, "vice_shell.py")
        with open(shell_path, "r", encoding="utf-8") as fp:
            code = fp.read()
        self.assertIn("_acquire_shell_lock", code)
        self.assertIn("WA_X11NetWmWindowTypeDock", code)
        self.assertNotIn("availableGeometry()", code)

    def test_welcome_wizard_is_managed_window(self):
        wizard_path = os.path.join(DESKTOP_DIR, "welcome_wizard.py")
        with open(wizard_path, "r", encoding="utf-8") as fp:
            code = fp.read()
        self.assertNotIn("FramelessWindowHint", code)


if __name__ == "__main__":
    unittest.main()
