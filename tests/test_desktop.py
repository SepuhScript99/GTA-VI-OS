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
import re
import ast
import glob
import json
import shutil
import subprocess
import configparser
import tempfile
import types
import xml.etree.ElementTree as ET

# Add repo root, lib/, and desktop/ to path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DESKTOP_DIR = os.path.join(REPO_ROOT, 'desktop')
LIB_DIR = os.path.join(REPO_ROOT, 'lib')

sys.path.insert(0, LIB_DIR)
sys.path.insert(0, os.path.join(LIB_DIR, 'python'))
sys.path.insert(0, DESKTOP_DIR)

import panel_config  # noqa: E402
import ob_menu  # noqa: E402
import vice_setup_apps  # noqa: E402
import wallpaper_manager  # noqa: E402
import session_watchdog  # noqa: E402


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

    def test_openbox_theme_and_margins_match_panel_config(self):
        rc_path = os.path.join(REPO_ROOT, "config", "openbox_rc.xml")
        tree = ET.parse(rc_path)
        root = tree.getroot()
        ns = {"ob": "http://openbox.org/3.4/rc"}

        theme_name = root.find("ob:theme/ob:name", ns)
        self.assertIsNotNone(theme_name)
        self.assertEqual(theme_name.text.strip(), "Vice-Dark")

        margins = root.find("ob:margins", ns)
        self.assertIsNotNone(margins)
        self.assertEqual(int(margins.find("ob:top", ns).text), 0)
        self.assertEqual(int(margins.find("ob:bottom", ns).text), panel_config.DOCK_HEIGHT)

        themerc = os.path.join(REPO_ROOT, "config", "themes", "Vice-Dark", "openbox-3", "themerc")
        self.assertTrue(os.path.isfile(themerc), f"Missing custom Openbox theme: {themerc}")

        keyboard_el = root.find("ob:keyboard", ns)
        self.assertIsNotNone(keyboard_el)
        a_f1_cmds = [
            cmd.text.strip()
            for kb in keyboard_el.findall("ob:keybind", ns)
            if kb.attrib.get("key") == "A-F1"
            for cmd in kb.findall(".//ob:command", ns)
            if cmd.text
        ]
        self.assertTrue(any("--toggle-menu" in c for c in a_f1_cmds), "Openbox missing A-F1 --toggle-menu binding")

    def test_vice_shell_has_taskbar_widget(self):
        shell_path = os.path.join(DESKTOP_DIR, "vice_shell.py")
        with open(shell_path, "r", encoding="utf-8") as fp:
            code = fp.read()
        for token in (
            "TaskbarWidget", "StartMenuPopup", "paintEvent",
            "setThemeName", "vice-debian-gta6.png", "wmctrl",
        ):
            self.assertIn(token, code)

    def _assert_launcher_discovery(self, vice_launcher_mod):
        with tempfile.TemporaryDirectory() as tmpdir:
            desktop_file = os.path.join(tmpdir, "sample-debian-app.desktop")
            with open(desktop_file, "w", encoding="utf-8") as fp:
                fp.write(
                    "[Desktop Entry]\n"
                    "Type=Application\n"
                    "Name=Sample Debian App\n"
                    "Comment=Sample Utility\n"
                    "Exec=sample-app %U\n"
                    "Icon=utilities-terminal\n"
                    "Categories=Utility;\n"
                )
            apps = vice_launcher_mod.discover_apps(desktop_app_dirs=[tmpdir], include_vice_scripts=True)
            names = {a["name"] for a in apps}
            labels = {a["label"] for a in apps}
            self.assertIn("Sample Debian App", labels)
            self.assertNotIn("vice_notification_daemon.py", names)

    def test_launcher_discovers_desktop_files_and_skips_daemons(self):
        try:
            import vice_launcher
            self._assert_launcher_discovery(vice_launcher)
        except ImportError:
            import types
            qt_pkg = types.ModuleType("PyQt5")
            qt_widgets = types.ModuleType("PyQt5.QtWidgets")
            qt_core = types.ModuleType("PyQt5.QtCore")
            qt_gui = types.ModuleType("PyQt5.QtGui")
            for name in ("QApplication", "QWidget", "QLabel", "QPushButton", "QVBoxLayout",
                         "QHBoxLayout", "QLineEdit", "QScrollArea", "QGridLayout", "QShortcut"):
                setattr(qt_widgets, name, type(name, (), {}))
            for name in ("Qt", "QProcess", "QSize"):
                setattr(qt_core, name, type(name, (), {}))
            for name in ("QFont", "QIcon", "QKeySequence"):
                setattr(qt_gui, name, type(name, (), {}))
            with patch.dict(sys.modules, {
                "PyQt5": qt_pkg,
                "PyQt5.QtWidgets": qt_widgets,
                "PyQt5.QtCore": qt_core,
                "PyQt5.QtGui": qt_gui,
            }):
                try:
                    import vice_launcher
                    self._assert_launcher_discovery(vice_launcher)
                finally:
                    sys.modules.pop("vice_launcher", None)

    def test_packages_list_has_standard_desktop_utilities(self):
        pkg_path = os.path.join(REPO_ROOT, "config", "packages.list")
        with open(pkg_path, "r", encoding="utf-8") as fp:
            pkgs = {line.strip() for line in fp if line.strip() and not line.strip().startswith("#")}
        for required in [
            "pcmanfm", "xcape", "dbus-user-session", "wmctrl", "xdotool",
            "xfce4-terminal", "papirus-icon-theme", "arc-theme", "xfconf",
            "tumbler", "gvfs",
        ]:
            self.assertIn(required, pkgs, f"Missing standard desktop package: {required}")
        self.assertTrue(os.path.isfile(os.path.join(REPO_ROOT, "config", "qt5ct", "qt5ct.conf")))
        self.assertTrue(os.path.isfile(os.path.join(REPO_ROOT, "config", "skel", "Desktop", "firefox.desktop")))


class TestLiveVmMediaFontDesktopRegression(unittest.TestCase):
    """Regression tests covering CJK fonts, PipeWire/ALSA audio, codecs/Firefox/picom, and shortcuts."""

    def _read(self, *parts):
        with open(os.path.join(REPO_ROOT, *parts), "r", encoding="utf-8") as fp:
            return fp.read()

    def _load_packages(self):
        text = self._read("config", "packages.list")
        pkgs = set()
        for line in text.splitlines():
            clean = line.split("#", 1)[0].strip()
            if clean:
                pkgs.add(clean)
        return pkgs

    def test_cjk_fonts_and_fontconfig_fallback(self):
        pkgs = self._load_packages()
        self.assertIn("fontconfig", pkgs)
        self.assertIn("fonts-noto-cjk", pkgs)

        fc_path = os.path.join(REPO_ROOT, "config", "fontconfig", "99-vice-cjk.conf")
        self.assertTrue(os.path.isfile(fc_path), "Missing config/fontconfig/99-vice-cjk.conf")
        ET.parse(fc_path)
        fc_text = self._read("config", "fontconfig", "99-vice-cjk.conf")
        for token in ("sans-serif", "serif", "monospace", "Noto Sans CJK JP", "Noto Sans CJK SC", "Noto Color Emoji"):
            self.assertIn(token, fc_text)

        tuning = self._read("chroot_scripts", "02_system_tuning.sh")
        self.assertIn("config/fontconfig", tuning)
        self.assertIn("/etc/fonts/conf.avail", tuning)
        self.assertIn("fc-cache -f", tuning)

        qss = self._read("desktop", "style.qss")
        for widget_sel in ("QWidget {", "QPushButton#TaskButton {", "QListWidget#StartCatList {", "QListWidget#StartAppList {"):
            self.assertIn(widget_sel, qss)
        self.assertIn("Noto Sans CJK JP", qss)
        self.assertIn("Noto Sans CJK SC", qss)

        shell_code = self._read("desktop", "vice_shell.py")
        self.assertIn("def _configure_cjk_fonts", shell_code)
        self.assertIn("QFont.insertSubstitutions", shell_code)
        self.assertIn("Noto Sans CJK JP", shell_code)
        self.assertIn("_configure_cjk_fonts(app)", shell_code)

        rc_text = self._read("config", "openbox_rc.xml")
        self.assertIn("Noto Sans CJK JP", rc_text)
        self.assertIn("Noto Sans CJK SC", rc_text)

    def test_pipewire_alsa_audio_stack_and_session_startup(self):
        pkgs = self._load_packages()
        self.assertNotIn("pulseaudio", pkgs, "Conflicting pulseaudio daemon must not be in packages.list")
        for required in (
            "pipewire", "pipewire-audio", "pipewire-pulse", "pipewire-alsa",
            "wireplumber", "alsa-utils", "alsa-ucm-conf", "rtkit",
            "pulseaudio-utils", "pavucontrol", "libcanberra-pulse",
        ):
            self.assertIn(required, pkgs, f"Missing audio package: {required}")

        systemd_setup = self._read("chroot_scripts", "19_systemd_setup.sh")
        self.assertIn("rm -f /etc/pipewire/pipewire.conf", systemd_setup)
        self.assertIn("10-vice-audio.conf", systemd_setup)
        self.assertIn("10-vice-pulse.conf", systemd_setup)
        self.assertNotIn("cat <<'PWCONF'", systemd_setup)
        self.assertNotIn("cat <<'PULSECONF'", systemd_setup)

        modprobe_setup = self._read("chroot_scripts", "20_modprobe_setup.sh")
        self.assertIn("vice-audio-vm.conf", modprobe_setup)
        modprobe_vm = self._read("config", "modprobe.d", "vice-audio-vm.conf")
        self.assertIn("options snd-intel8x0 ac97_clock=48000", modprobe_vm)

        optimize = self._read("chroot_scripts", "90_optimize.sh")
        self.assertIn("rm -f /etc/pipewire/pipewire.conf", optimize)
        self.assertIn("10-vice-audio.conf", optimize)

        net_audio = self._read("chroot_scripts", "05_network_audio_fix.sh")
        self.assertIn("rtkit-daemon.service", net_audio)
        self.assertIn("pipewire.socket", net_audio)
        self.assertIn("wireplumber.service", net_audio)

        for rel in (("desktop", "dbus_session.sh"), ("desktop", "wayland_session.sh")):
            sess = self._read(*rel)
            self.assertIn("start_audio_stack", sess)
            self.assertIn("unmute_alsa_unity", sess)
            self.assertIn("/usr/bin/pipewire", sess)
            self.assertIn("/usr/bin/wireplumber", sess)
            self.assertIn("/usr/bin/pipewire-pulse", sess)
            self.assertIn("amixer", sess)
            self.assertIn("0dB unmute", sess)
            self.assertNotIn('sset "$ctrl" 85% unmute', sess)
            self.assertIn("auto_null", sess)
            self.assertIn("set-sink-volume", sess)

    def test_video_codecs_firefox_prefs_and_vm_safe_picom(self):
        pkgs = self._load_packages()
        for required in (
            "ffmpeg", "libavcodec-extra", "gstreamer1.0-libav",
            "gstreamer1.0-plugins-base", "gstreamer1.0-plugins-good",
            "gstreamer1.0-plugins-bad", "gstreamer1.0-plugins-ugly",
            "gstreamer1.0-pipewire", "libgl1-mesa-dri", "libglx-mesa0",
            "libegl1", "mesa-va-drivers", "mesa-utils", "vainfo",
        ):
            self.assertIn(required, pkgs, f"Missing video/Mesa package: {required}")

        ff_prefs = self._read("config", "firefox", "vice-os.js")
        for expected in (
            'pref("media.av1.enabled", false);',
            'pref("media.ffmpeg.enabled", true);',
            'pref("media.ffvpx.enabled", true);',
            'pref("media.rdd-ffmpeg.enabled", true);',
            'pref("layers.gpu-process.enabled", false);',
            'pref("widget.dmabuf.force-enabled", false);',
            'pref("browser.aboutwelcome.enabled", false);',
        ):
            self.assertIn(expected, ff_prefs)

        policies = json.loads(self._read("config", "firefox", "policies.json"))
        self.assertIn("policies", policies)

        tuning = self._read("chroot_scripts", "02_system_tuning.sh")
        self.assertIn("/etc/firefox-esr/vice-os.js", tuning)
        self.assertIn("/etc/firefox-esr/policies/policies.json", tuning)
        self.assertIn("/etc/xdg/picom.conf", tuning)

        for cfg in ("picom.conf", "compton.conf"):
            text = self._read("config", cfg)
            self.assertIn('backend = "xrender";', text)
            self.assertIn("shadow = false;", text)
            self.assertIn("fading = false;", text)
            self.assertIn("blur-background = false;", text)
            self.assertIn("unredir-if-possible = true;", text)
            self.assertIn("unredir-if-possible-exclude = [];", text)

        autostart = self._read("config", "skel", ".config", "openbox", "autostart")
        self.assertIn("/etc/xdg/picom.conf", autostart)
        self.assertIn("llvmpipe", autostart)

    def test_desktop_shortcuts_polkit_and_runtime_deps(self):
        pkgs = self._load_packages()
        for required in (
            "polkitd", "pkexec", "policykit-1-gnome",
            "librsvg2-common", "libqt5svg5", "python3-pyqt5.qtsvg",
            "hicolor-icon-theme", "desktop-file-utils", "shared-mime-info",
            "dconf-gsettings-backend", "gsettings-desktop-schemas", "libglib2.0-bin",
            "libnotify-bin", "at-spi2-core", "python3-dbus", "python3-gi",
            "python3-psutil", "python3-systemd", "poppler-utils",
            "x11-utils", "xclip", "scrot",
        ):
            self.assertIn(required, pkgs, f"Missing runtime/polkit/SVG package: {required}")

        desktop_dir = os.path.join(REPO_ROOT, "config", "skel", "Desktop")
        shortcuts = sorted(glob.glob(os.path.join(desktop_dir, "*.desktop")))
        self.assertGreaterEqual(len(shortcuts), 10)
        for path in shortcuts:
            cp = configparser.ConfigParser(interpolation=None)
            cp.read(path, encoding="utf-8")
            self.assertIn("Desktop Entry", cp.sections(), f"Missing [Desktop Entry] in {path}")
            entry = cp["Desktop Entry"]
            self.assertEqual(entry.get("Type"), "Application", f"Invalid Type in {path}")
            for field in ("Name", "Exec", "Icon", "Categories"):
                self.assertTrue(entry.get(field, "").strip(), f"Empty {field} in {path}")
            exec_bin = entry["Exec"].split()[0]
            if exec_bin == "python3":
                script_target = os.path.basename(entry["Exec"].split()[1])
                self.assertTrue(os.path.isfile(os.path.join(DESKTOP_DIR, script_target)),
                                f"Shortcut {path} targets missing desktop script {script_target}")
            else:
                self.assertIn(exec_bin, pkgs, f"Shortcut {path} executable '{exec_bin}' not in packages.list")

        skel_setup = self._read("chroot_scripts", "22_skel_setup.sh")
        self.assertIn('chmod 755 "$dest_dir"/Desktop/*.desktop', skel_setup)

        autostart = self._read("config", "skel", ".config", "openbox", "autostart")
        self.assertIn("polkit-gnome-authentication-agent-1", autostart)
        self.assertIn("vice-os-notifications.desktop", autostart)


class TestViceAppsRuntimeSafety(unittest.TestCase):
    """Regression tests for vice_shell responsiveness and live-VM PyQt5 bug fixes."""

    def _read(self, name):
        with open(os.path.join(DESKTOP_DIR, name), "r", encoding="utf-8") as fp:
            return fp.read()

    def test_vice_shell_event_driven_taskbar_and_async_audio(self):
        code = self._read("vice_shell.py")
        self.assertIn('["xprop", "-root", "-spy", "_NET_CLIENT_LIST", "_NET_ACTIVE_WINDOW"]', code)
        self.assertIn("_poll_busy", code)
        self.assertIn("_debounce", code)
        self.assertIn("class VolumePopup", code)
        self.assertIn('"vicevolumepopup"', code)
        self.assertIn("def _get_audio_state", code)
        self.assertIn("timeout=0.6", code)

    def test_no_pyqt5_api_regressions_across_desktop_scripts(self):
        for f in sorted(glob.glob(os.path.join(DESKTOP_DIR, "*.py"))):
            fname = os.path.basename(f)
            code = self._read(fname)
            tree = ast.parse(code, filename=fname)

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module == "PyQt5.QtWidgets":
                    imported = {a.name for a in node.names}
                    self.assertNotIn("QProcess", imported, f"{fname} imports QProcess from QtWidgets")
                if isinstance(node, ast.Call):
                    if all((
                        isinstance(node.func, ast.Attribute),
                        getattr(node.func, "attr", None) == "getlogin",
                        isinstance(getattr(node.func, "value", None), ast.Name),
                        getattr(getattr(node.func, "value", None), "id", None) == "os",
                    )):
                        self.fail(f"{fname} calls os.getlogin(), which fails without utmp/controlling tty")
                    if isinstance(node.func, ast.Name) and node.func.id == "QGraphicsDropShadowEffect":
                        for kw in node.keywords:
                            if kw.arg == "offset":
                                self.assertNotIsInstance(
                                    kw.value, ast.Tuple,
                                    f"{fname} passes tuple to QGraphicsDropShadowEffect(offset=...); use QPointF"
                                )

            self.assertNotIn("setSelectionBehavior(QAbstractItemView.NoSelection)", code, fname)
            self.assertNotIn("setSelectionBehavior(QAbstractItemView.ExtendedSelection)", code, fname)

            table_attrs = set(re.findall(r"self\.(\w+)\s*=\s*QTableWidget\b", code))
            for attr in table_attrs:
                self.assertNotIn(
                    f"self.{attr}.currentRowChanged", code,
                    f"{fname}: QTableWidget '{attr}' has no currentRowChanged signal"
                )

    def test_fixed_vice_apps_behavioral_guards(self):
        cal_tree = ast.parse(self._read("vice_calendar.py"), filename="vice_calendar.py")
        cal_methods = set()
        for node in cal_tree.body:
            if isinstance(node, ast.ClassDef) and node.name == "CalendarTab":
                cal_methods = {n.name for n in node.body if isinstance(n, ast.FunctionDef)}
        self.assertIn("_add_event", cal_methods)

        sc_code = self._read("vice_software_center.py")
        sc_tree = ast.parse(sc_code, filename="vice_software_center.py")
        class_methods = {}
        for node in sc_tree.body:
            if isinstance(node, ast.ClassDef):
                class_methods[node.name] = {n.name for n in node.body if isinstance(n, ast.FunctionDef)}
        self.assertIn("stop", class_methods.get("PackageWorkerThread", set()))
        self.assertIn("shutdown_workers", class_methods.get("SoftwareCenter", set()))
        self.assertIn("closeEvent", class_methods.get("SoftwareCenter", set()))
        self.assertNotIn("QColor(0, 0, 0)", sc_code)

        theme_code = self._read("vice_theme_manager.py")
        self.assertIn("self._preview_layout = QVBoxLayout(self._preview_frame)", theme_code)
        self.assertEqual(theme_code.count("QVBoxLayout(self._preview_frame)"), 1)

        notif_code = self._read("vice_notification_daemon.py")
        self.assertIn("except ImportError", notif_code)
        self.assertIn("_HAS_DBUS", notif_code)

        sys_notif_code = self._read("vice_system_notifier.py")
        self.assertIn('shutil.which("notify-send")', sys_notif_code)

        launcher_code = self._read("vice_launcher.py")
        self.assertNotIn("args = [term_bin, \"-e\"] + args", launcher_code)

    @staticmethod
    def _read_repo(*parts):
        with open(os.path.join(REPO_ROOT, *parts), "r", encoding="utf-8") as fp:
            return fp.read()

    def test_iso9_pipewire_wireplumber_and_rtkit_fixes(self):
        wp_lua = self._read_repo("config", "wireplumber", "main.lua.d", "51-vice-vm-alsa.lua")
        for token in (
            '["api.alsa.period-size"] = 2048',
            '["api.alsa.period-num"] = 8',
            '["api.alsa.headroom"] = 4096',
            '["api.alsa.disable-batch"] = true',
            '["session.suspend-timeout-seconds"] = 0',
            '["api.alsa.soft-mixer"] = true',
            '"alsa_card.*"',
            '"snd_intel8x0"',
        ):
            self.assertIn(token, wp_lua)

        pw_setup = self._read_repo("chroot_scripts", "18_pipewire_setup.sh")
        self.assertNotIn("cp \"$pipewire_src\" \"$pipewire_dest\"", pw_setup)
        self.assertNotIn("default.clock.quantum = 2048", pw_setup)
        self.assertNotIn("pulse.default.req = 2048/48000", pw_setup)
        for token in (
            "rm -f /etc/pipewire/pipewire.conf",
            "/etc/pipewire/pipewire.conf.d/10-vice-audio.conf",
            "/etc/pipewire/pipewire-pulse.conf.d/10-vice-pulse.conf",
            "51-vice-vm-alsa.lua",
            "usermod -aG pipewire vice",
            "/etc/security/limits.d/95-vice-audio.conf",
            "/etc/polkit-1/rules.d/10-vice-rtkit.rules",
        ):
            self.assertIn(token, pw_setup)

        systemd_setup = self._read_repo("chroot_scripts", "19_systemd_setup.sh")
        self.assertIn("51-vice-vm-alsa.lua", systemd_setup)
        self.assertIn("10-vice-audio.conf", systemd_setup)
        self.assertIn("10-vice-pulse.conf", systemd_setup)
        self.assertIn("zramswap.service", systemd_setup)

        modprobe_setup = self._read_repo("chroot_scripts", "20_modprobe_setup.sh")
        self.assertIn("vice-audio-vm.conf", modprobe_setup)
        modprobe_vm = self._read_repo("config", "modprobe.d", "vice-audio-vm.conf")
        self.assertIn("options snd-intel8x0 ac97_clock=48000", modprobe_vm)

        net_audio = self._read_repo("chroot_scripts", "05_network_audio_fix.sh")
        self.assertIn("usermod -aG pipewire vice", net_audio)

        ff_prefs = self._read_repo("config", "firefox", "vice-os.js")
        self.assertNotIn('pref("media.cubeb.sandbox", false)', ff_prefs)

    def test_iso9_desktop_ui_ca_certs_and_live_config_fixes(self):
        pkgs = {
            line.split("#", 1)[0].strip()
            for line in self._read_repo("config", "packages.list").splitlines()
            if line.split("#", 1)[0].strip()
        }
        self.assertIn("ca-certificates", pkgs)

        user_setup = self._read_repo("chroot_scripts", "03_user_setup.sh")
        self.assertIn('LIVE_USERNAME="vice"', user_setup)

        shell_code = self._read("vice_shell.py")
        for token in (
            "self.setFixedHeight(h)",
            "_make_show_desktop_icon",
            '"BatteryButton"',
            "_update_button_layout",
            '"VolumeMuteButton"',
            "Qt.Key_Escape",
            '"Vice Tools"',
            '"StartHubPill"',
            "Tool Hub",
            "_refresh_net_indicator",
            'shutil.which("stalonetray")',
        ):
            self.assertIn(token, shell_code)

        settings_code = self._read("vice_settings.py")
        for token in (
            "preferences-system",
            "QScrollBar:vertical",
            "_PAGE_ICONS",
            "def closeEvent",
        ):
            self.assertIn(token, settings_code)

        qss_code = self._read("style.qss")
        self.assertIn("QPushButton#BatteryButton", qss_code)
        self.assertIn("QPushButton#VolumeMuteButton", qss_code)
        self.assertIn("max-width: 230px;", qss_code)

        desktop_items = self._read_repo("config", "pcmanfm", "vice", "desktop-items-0.conf")
        self.assertIn("desktop_fg=#ffffff", desktop_items)
        self.assertIn("[vice-tool-hub.desktop]", desktop_items)
        self.assertIn("[vice-radio.desktop]", desktop_items)

        autostart = self._read_repo("config", "skel", ".config", "openbox", "autostart")
        self.assertIn("nm-applet.desktop", autostart)
        self.assertIn("command -v stalonetray", autostart)

        for sess_name in ("dbus_session.sh", "wayland_session.sh"):
            self.assertIn("QT_QPA_PLATFORMTHEME", self._read(sess_name))


class TestLeonidaOverhaulAndTimesync(unittest.TestCase):
    """Validates Batch 2 Leonida UI overhaul, galculator/LibreOffice styling, and host clock sync."""

    @staticmethod
    def _read_repo(*parts):
        with open(os.path.join(REPO_ROOT, *parts), "r", encoding="utf-8") as fp:
            return fp.read()

    @staticmethod
    def _find_bash():
        candidates = []
        which_bash = shutil.which("bash")
        if which_bash and "WindowsApps" not in which_bash:
            candidates.append(which_bash)
        git_bash = r"C:\Program Files\Git\bin\bash.exe"
        if os.path.isfile(git_bash) and git_bash not in candidates:
            candidates.append(git_bash)
        for cand in candidates:
            try:
                if subprocess.run([cand, "--version"], capture_output=True, check=False).returncode == 0:
                    return cand
            except OSError:
                continue
        return None

    def test_galculator_dark_legibility_and_gtk_css(self):
        galc_path = os.path.join(REPO_ROOT, "config", "skel", ".config", "galculator", "galculator.conf")
        self.assertTrue(os.path.isfile(galc_path), "Missing skel galculator.conf")
        cp = configparser.ConfigParser(interpolation=None)
        cp.read(galc_path, encoding="utf-8")
        self.assertIn("general", cp.sections())
        gen = cp["general"]
        self.assertEqual(gen.get("display_bkg_color").strip('"'), "#141621")
        self.assertEqual(gen.get("display_result_color").strip('"').lower(), "#f5f6fa")
        self.assertEqual(gen.get("display_stack_color").strip('"').lower(), "#a6aebf")
        self.assertEqual(gen.get("display_module_active_color").strip('"').lower(), "#36d6c3")
        self.assertNotEqual(gen.get("display_result_color").strip('"').lower(), "black")

        gtk_css = self._read_repo("config", "gtk-3.0", "gtk.css")
        self.assertIn("#galculator", gtk_css)
        self.assertIn("vte-terminal", gtk_css)

        skel_setup = self._read_repo("chroot_scripts", "22_skel_setup.sh")
        self.assertIn(".config/galculator", skel_setup)
        self.assertIn(".config/libreoffice/4/user", skel_setup)

    def test_libreoffice_gtk3_theme_and_white_paper_xml(self):
        xcu_path = os.path.join(
            REPO_ROOT, "config", "skel", ".config", "libreoffice", "4", "user", "registrymodifications.xcu"
        )
        self.assertTrue(os.path.isfile(xcu_path), "Missing LibreOffice registrymodifications.xcu")
        tree = ET.parse(xcu_path)
        root = tree.getroot()
        oor_ns = "{http://openoffice.org/2001/registry}"

        items = {}
        for item in root.findall("item"):
            path_key = item.attrib.get(f"{oor_ns}path", "")
            for prop in item.findall("prop"):
                pname = prop.attrib.get(f"{oor_ns}name", "")
                val_el = prop.find("value")
                items[(path_key, pname)] = val_el.text if val_el is not None else ""

        self.assertEqual(items.get(("/org.openoffice.Office.Common/Misc", "SymbolStyle")), "sifr_dark")
        self.assertEqual(items.get(("/org.openoffice.Office.Common/Misc", "ShowTipOfTheDay")), "false")
        self.assertEqual(items.get(("/org.openoffice.Office.Common/View", "DarkMode")), "true")
        self.assertEqual(
            items.get((
                "/org.openoffice.Office.UI/ColorScheme/ColorSchemes/"
                "org.openoffice.Office.UI:ColorScheme['LibreOffice']/AppBackground",
                "Color",
            )),
            "855573",
        )
        self.assertEqual(
            items.get((
                "/org.openoffice.Office.UI/ColorScheme/ColorSchemes/"
                "org.openoffice.Office.UI:ColorScheme['LibreOffice']/DocColor",
                "Color",
            )),
            "16777215",
        )

        self.assertIn("SAL_USE_VCLPLUGIN=gtk3", self._read_repo("chroot_scripts", "02_system_tuning.sh"))
        self.assertIn("SAL_USE_VCLPLUGIN=gtk3", self._read_repo("desktop", "dbus_session.sh"))
        self.assertIn("SAL_USE_VCLPLUGIN=gtk3", self._read_repo("desktop", "wayland_session.sh"))
        self.assertIn("/usr/share/zoneinfo", self._read_repo("chroot_scripts", "90_optimize.sh"))

    def test_host_timesync_script_systemd_nm_and_chrony(self):
        ts_path = os.path.join(REPO_ROOT, "system_scripts", "vice-timesync.sh")
        nm_path = os.path.join(REPO_ROOT, "config", "NetworkManager", "90-vice-timesync")
        svc_path = os.path.join(REPO_ROOT, "config", "systemd", "system", "vice-timesync.service")
        tmr_path = os.path.join(REPO_ROOT, "config", "systemd", "system", "vice-timesync.timer")

        for p in (ts_path, nm_path, svc_path, tmr_path):
            self.assertTrue(os.path.isfile(p), f"Missing host clock sync file: {p}")

        ts_code = self._read_repo("system_scripts", "vice-timesync.sh")
        self.assertNotIn("\r\n", ts_code)
        self.assertTrue(ts_code.splitlines()[0] == "#!/bin/bash")
        self.assertIn("set -Eeuo pipefail", ts_code)
        for token in (
            "--auto", "--force", "--sync-only", "--set", "--status",
            "command -v VBoxService", "https://ipinfo.io/timezone",
            "http://ip-api.com/line/?fields=timezone", "validate_timezone",
            "sync_etc_timezone_file",
        ):
            self.assertIn(token, ts_code)
        self.assertLess(ts_code.index("${ETC_DIR}/localtime"), ts_code.index("${ETC_DIR}/timezone"))

        clock_app = self._read_repo("desktop", "vice_tool_clock_sync.py")
        self.assertLess(clock_app.index('"/etc/localtime"'), clock_app.index('"/etc/timezone"'))

        nm_code = self._read_repo("config", "NetworkManager", "90-vice-timesync")
        self.assertNotIn("\r\n", nm_code)
        self.assertIn("/usr/local/bin/vice-timesync --auto", nm_code)

        bash_bin = self._find_bash()
        if bash_bin:
            for sh_file in (ts_path, nm_path):
                proc = subprocess.run([bash_bin, "-n", sh_file], capture_output=True, text=True, check=False)
                self.assertEqual(proc.returncode, 0, f"bash -n failed on {sh_file}: {proc.stderr}")

        svc_cp = configparser.ConfigParser(interpolation=None)
        svc_cp.read(svc_path, encoding="utf-8")
        self.assertEqual(svc_cp["Service"]["ExecStart"], "/usr/local/bin/vice-timesync --auto")

        tmr_cp = configparser.ConfigParser(interpolation=None)
        tmr_cp.read(tmr_path, encoding="utf-8")
        self.assertEqual(tmr_cp["Timer"]["Unit"], "vice-timesync.service")

        chrony_setup = self._read_repo("chroot_scripts", "25_chrony_setup.sh")
        self.assertIn("makestep 1 -1", chrony_setup)
        self.assertIn("rtcsync", chrony_setup)

        systemd_setup = self._read_repo("chroot_scripts", "19_systemd_setup.sh")
        for token in (
            "90-vice-timesync", "vice-timesync.service", "vice-timesync.timer",
            "tor.service", "privoxy.service", "stubby.service", "unbound.service",
            "chkrootkit.service", "chkrootkit.timer",
        ):
            self.assertIn(token, systemd_setup)

        autostart = self._read_repo("config", "skel", ".config", "openbox", "autostart")
        self.assertIn("/usr/local/bin/vice-timesync --auto", autostart)

    def _assert_vice_theme_contract(self, theme_mod):
        self.assertEqual(theme_mod.COLORS["bg_canvas"], "#0D0E15")
        self.assertEqual(theme_mod.COLORS["bg_surface"], "#141621")
        self.assertEqual(theme_mod.COLORS["accent_coral"], "#FF5E7E")
        self.assertEqual(theme_mod.COLORS["accent_peach"], "#FF9A62")
        self.assertEqual(theme_mod.COLORS["accent_aqua"], "#36D6C3")
        self.assertEqual(theme_mod.COLORS["accent_gold"], "#F7C873")
        self.assertIn("Noto Sans CJK JP", theme_mod.FONT_STACK)
        qss = theme_mod.build_app_qss()
        self.assertIn("#0D0E15", qss)
        self.assertIn("#FF5E7E", qss)

    def test_vice_theme_tokens_and_vice_shell_dynamic_tzset(self):
        try:
            import vice_theme
            self._assert_vice_theme_contract(vice_theme)
        except ImportError:
            qt_pkg = types.ModuleType("PyQt5")
            qt_core = types.ModuleType("PyQt5.QtCore")
            qt_gui = types.ModuleType("PyQt5.QtGui")
            qt_widgets = types.ModuleType("PyQt5.QtWidgets")
            qt_core.Qt = type("Qt", (), {})
            qt_core.QSize = type("QSize", (), {})
            for name in ("QColor", "QFont", "QIcon"):
                setattr(qt_gui, name, type(name, (), {}))
            for name in ("QApplication", "QFrame", "QHBoxLayout", "QLabel", "QPushButton", "QVBoxLayout", "QWidget"):
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
                try:
                    import vice_theme
                    self._assert_vice_theme_contract(vice_theme)
                finally:
                    sys.modules.pop("vice_theme", None)

        self.assertEqual(panel_config.DOCK_HEIGHT, 44)
        shell_code = self._read_repo("desktop", "vice_shell.py")
        for token in (
            "/etc/localtime", "time.tzset()", "vice_tool_clock_sync.py",
            "QFontMetrics(bold_font)", '"Office"', '"Security"',
        ):
            self.assertIn(token, shell_code)

    def test_zero_legacy_neon_colors_in_refactored_ui(self):
        ui_paths = [
            os.path.join(DESKTOP_DIR, "vice_theme.py"),
            os.path.join(DESKTOP_DIR, "style.qss"),
            os.path.join(DESKTOP_DIR, "panel_config.py"),
            os.path.join(DESKTOP_DIR, "vice_shell.py"),
            os.path.join(DESKTOP_DIR, "vice_launcher.py"),
            os.path.join(DESKTOP_DIR, "vice_settings.py"),
            os.path.join(DESKTOP_DIR, "login.py"),
            os.path.join(DESKTOP_DIR, "welcome_wizard.py"),
            os.path.join(REPO_ROOT, "config", "gtk-3.0", "gtk.css"),
            os.path.join(REPO_ROOT, "config", "themes", "Vice-Dark", "openbox-3", "themerc"),
        ] + sorted(glob.glob(os.path.join(DESKTOP_DIR, "vice_tool_*.py")))

        legacy_tokens = ("#00ffff", "#ff00ff", "#120e1e", "#ff4da6", "#00e5c3", "#ff8a5b")
        for path in ui_paths:
            self.assertTrue(os.path.isfile(path), f"Missing UI file: {path}")
            with open(path, "r", encoding="utf-8") as fp:
                content = fp.read().lower()
            for hex_code in legacy_tokens:
                self.assertNotIn(hex_code, content, f"Legacy neon color {hex_code} found in {path}")

    def test_iso12_ui_audio_tray_and_session_fixes(self):
        opt_sh = self._read_repo("chroot_scripts", "90_optimize.sh")
        for token in (
            "zramswap.service",
            "nm-applet.desktop blueman.desktop print-applet.desktop",
            "Hidden=true",
        ):
            self.assertIn(token, opt_sh)

        autostart = self._read_repo("config", "skel", ".config", "openbox", "autostart")
        self.assertIn("nm-applet.desktop|print-applet.desktop", autostart)

        theme_code = self._read_repo("desktop", "vice_theme.py")
        self.assertIn("self.subtitle_label.setWordWrap(True)", theme_code)
        self.assertIn("width: 0px;\n    height: 0px;", theme_code)
        self.assertNotIn("QTabBar::tab {{\n    background-color: {c['bg_surface']};\n    color: {c['text_secondary']};\n    border: 1px solid {c['border']};\n    border-bottom: none;\n    padding: 7px 14px;\n    margin-right: 3px;\n    border-top-left-radius: 8px;\n    border-top-right-radius: 8px;\n    font-weight: 600;", theme_code)

        qss_code = self._read_repo("desktop", "style.qss")
        self.assertIn("font-weight: normal;", qss_code)

        shell_code = self._read_repo("desktop", "vice_shell.py")
        for token in (
            "self.setFixedWidth(geo.width())",
            "self._slider.setRange(0, 100)",
            'any(k in low_class for k in ("xfce4-terminal", "xterm")) or "vice os - " in low_title',
            '("libreoffice calc", "libreoffice-calc")',
        ):
            self.assertIn(token, shell_code)
        self.assertNotIn("setRange(0, 150)", shell_code)

        settings_code = self._read_repo("desktop", "vice_settings.py")
        self.assertIn('f"Open {page_name} Settings".replace("&", "&&")', settings_code)

        office_code = self._read_repo("desktop", "vice_tool_office_hub.py")
        self.assertIn('spec["subtitle"].replace("&", "&&")', office_code)

        net_shield_code = self._read_repo("desktop", "vice_tool_net_shield.py")
        self.assertIn("Tor && Local Proxy", net_shield_code)

        mac_cloak_code = self._read_repo("desktop", "vice_tool_mac_cloak.py")
        self.assertIn("Connections && Ports", mac_cloak_code)
        self.assertIn("History && Trace Wipe", mac_cloak_code)

        runner_code = self._read_repo("system_scripts", "vice-run-tool.sh")
        self.assertIn("--disable-server", runner_code)
        self.assertIn('VICE_NO_HOLD="${VICE_NO_HOLD:-0}"', runner_code)

    def test_iso13_win11_picom_rounded_ui_and_desktop_grid(self):
        picom = self._read_repo("config", "picom.conf")
        compton = self._read_repo("config", "compton.conf")
        self.assertEqual(picom, compton, "picom.conf and compton.conf must stay synchronized")
        for token in (
            "detect-rounded-corners = true;",
            "corner-radius = 12;",
            "rounded-corners-exclude = [",
            '"window_type = \'dock\'"',
            '"window_type = \'desktop\'"',
            '"window_type = \'tooltip\'"',
            '"window_type = \'popup_menu\'"',
            '"window_type = \'dropdown_menu\'"',
            '"window_type = \'menu\'"',
            '"window_type = \'notification\'"',
            '"class_g = \'vice_shell.py\'"',
            '"name = \'ViceTaskbar\'"',
            '"fullscreen"',
            '"_NET_WM_STATE@:32a *= \'_NET_WM_STATE_FULLSCREEN\'"',
            '"_NET_WM_STATE@:32a *= \'_NET_WM_STATE_MAXIMIZED_HORZ\'"',
            '"_NET_WM_STATE@:32a *= \'_NET_WM_STATE_MAXIMIZED_VERT\'"',
        ):
            self.assertIn(token, picom)

        self.assertIn("border-radius: 12px;", self._read_repo("desktop", "vice_theme.py"))
        self.assertIn("border-radius: 14px;", self._read_repo("desktop", "vice_theme.py"))
        self.assertIn("border-radius: 14px;", self._read_repo("desktop", "style.qss"))
        self.assertIn("border-radius: 12px;", self._read_repo("config", "gtk-3.0", "gtk.css"))

        themerc = self._read_repo("config", "themes", "Vice-Dark", "openbox-3", "themerc")
        self.assertIn("padding.width: 12", themerc)
        self.assertIn("padding.height: 8", themerc)
        self.assertIn("window.handle.width: 2", themerc)

        launcher_code = self._read_repo("desktop", "vice_launcher.py")
        self.assertIn("vice_tool_payload_lab.py", launcher_code)
        self.assertIn("Vice Payload Lab", launcher_code)

        hub_code = self._read_repo("desktop", "vice_tool_hub.py")
        self.assertIn("375 / 500 (75%)", hub_code)
        self.assertIn("implemented_count", hub_code)

        grid_cp = configparser.ConfigParser(interpolation=None)
        grid_cp.read(os.path.join(REPO_ROOT, "config", "pcmanfm", "vice", "desktop-items-0.conf"), encoding="utf-8")
        self.assertIn("vicefetch.desktop", grid_cp.sections())
        coords = []
        for sec in grid_cp.sections():
            if sec == "*":
                continue
            x = grid_cp[sec].get("x")
            y = grid_cp[sec].get("y")
            self.assertIsNotNone(x)
            self.assertIsNotNone(y)
            coords.append((int(x), int(y)))
        self.assertEqual(len(coords), len(set(coords)), "Duplicate coordinates in desktop-items-0.conf")

        skel_desktops = {
            os.path.basename(p)
            for p in glob.glob(os.path.join(REPO_ROOT, "config", "skel", "Desktop", "*.desktop"))
        }
        missing_grid = skel_desktops - set(grid_cp.sections())
        self.assertEqual(missing_grid, set(), f"Desktop files missing from desktop-items-0.conf: {missing_grid}")

    def test_iso13_taskbar_right_edge_cutoff_fix_and_width_budget(self):
        qss = self._read_repo("desktop", "style.qss")
        task_block = qss.split("QPushButton#TaskButton {", 1)[1].split("}", 1)[0]
        self.assertIn("min-width: 0px;", task_block)
        self.assertNotIn("min-width: 28px;", task_block)

        shell_code = self._read_repo("desktop", "vice_shell.py")
        for token in (
            "self.setMinimumWidth(0)",
            "QSizePolicy.Ignored",
            "def _available_taskbar_width",
            'elided.replace("&", "&&")',
            "def _format_sysinfo",
            "self.sysinfo.setMaximumWidth(235)",
            "self._battery_btn.setMaximumWidth(94)",
            "self.clock.setMinimumWidth(68)",
            "self.clock.setMaximumWidth(96)",
            "self.show_desk_btn.setFixedSize(26, 32)",
            "self.layout().activate()",
            'time.strftime("%H:%M\\n%a %d/%m")',
            "vice-tool-fetch",
            "vice-tool-payload-lab",
        ):
            self.assertIn(token, shell_code)

        # Arithmetic width budget check at 1280px (Start + 5 Pins + SysInfo + Net + Audio + Bat + Clock + ShowDesk + margins/spacing)
        non_taskbar_max = 12 + 86 + (5 * 32) + 235 + 30 + 30 + 94 + 96 + 26 + (11 * 4)
        self.assertLess(non_taskbar_max, 1280)
        self.assertGreaterEqual(1280 - non_taskbar_max, 400, "Taskbar must retain >=400px at 1280x720")

        # Unit-test _format_sysinfo and _read_registry_counts cleanly without needing live X11/PyQt5
        import importlib
        try:
            vs_mod = importlib.import_module("vice_shell")
        except ImportError:
            qt_pkg = types.ModuleType("PyQt5")
            qt_core = types.ModuleType("PyQt5.QtCore")
            qt_gui = types.ModuleType("PyQt5.QtGui")
            qt_widgets = types.ModuleType("PyQt5.QtWidgets")
            qt_core.Qt = type("Qt", (), {})
            qt_core.QSize = type("QSize", (), {})
            qt_core.QTimer = type("QTimer", (), {})
            qt_core.QEvent = type("QEvent", (), {})
            qt_core.QProcess = type("QProcess", (), {})
            qt_core.pyqtSignal = lambda *a, **k: None
            for name in ("QColor", "QFont", "QFontMetrics", "QIcon", "QKeySequence", "QPainter", "QPen", "QPixmap"):
                setattr(qt_gui, name, type(name, (), {}))
            for name in (
                "QApplication", "QFrame", "QHBoxLayout", "QLabel", "QLineEdit",
                "QListWidget", "QListWidgetItem", "QMenu", "QPushButton",
                "QShortcut", "QSizePolicy", "QSlider", "QStyle", "QStyleOption",
                "QVBoxLayout", "QWidget",
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
                sys.modules.pop("vice_shell", None)
                vs_mod = importlib.import_module("vice_shell")
                short_txt, tip = vs_mod._format_sysinfo("CPU: 14%", "RAM: 1200MB/3900MB", "Disk: 42%", compact=False)
                compact_txt, _ = vs_mod._format_sysinfo("CPU: 14%", "RAM: 1200MB/3900MB", "Disk: 42%", compact=True)
                counts = vs_mod._read_registry_counts()
            sys.modules.pop("vice_shell", None)
            sys.modules.pop("vice_theme", None)
        else:
            short_txt, tip = vs_mod._format_sysinfo("CPU: 14%", "RAM: 1200MB/3900MB", "Disk: 42%", compact=False)
            compact_txt, _ = vs_mod._format_sysinfo("CPU: 14%", "RAM: 1200MB/3900MB", "Disk: 42%", compact=True)
            counts = vs_mod._read_registry_counts()

        self.assertEqual(short_txt, "CPU 14% · RAM 1.2/3.8G · Disk 42%")
        self.assertLess(len(compact_txt), len(short_txt))
        self.assertIn("Click for Task Manager", tip)
        self.assertEqual(counts, (375, 500))

    def test_iso13_interactive_calendar_clock_sync_and_vicefetch_neofetch(self):
        clock_code = self._read_repo("desktop", "vice_tool_clock_sync.py")
        for token in (
            "QCalendarWidget",
            "class ViceCalendarWidget(QCalendarWidget)",
            'self.setObjectName("ViceCalendar")',
            "def paintCell",
            "self.resize(1040, 620)",
            "self.setMinimumSize(880, 540)",
            "Sync With Host && Internet Timezone",
            "Chrony && VirtualBox Diagnostics",
            "Jump to Today",
            "def _jump_to_today",
            "def _update_calendar_banner",
            "Week {iso_week} · Day {day_of_year} of {days_in_year}",
        ):
            self.assertIn(token, clock_code)

        ascii_art = self._read_repo("config", "vice-os", "vice_ascii.txt")
        self.assertNotIn("\r\n", ascii_art)
        for token in ("${c1}", "${c2}", "${c3}", "${c4}", "${c5}", "${c6}", "L E O N I D A", "V I C E"):
            self.assertIn(token, ascii_art)

        nf_conf = self._read_repo("config", "skel", ".config", "neofetch", "config.conf")
        self.assertNotIn("\r\n", nf_conf)
        self.assertIn('image_source="/etc/vice-os/vice_ascii.txt"', nf_conf)
        self.assertIn("ascii_colors=(5 1 9 3 15 6)", nf_conf)
        bash_bin = self._find_bash()
        if bash_bin:
            nf_path = os.path.join(REPO_ROOT, "config", "skel", ".config", "neofetch", "config.conf")
            proc = subprocess.run([bash_bin, "-n", nf_path], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, f"bash -n failed on neofetch config.conf: {proc.stderr}")

        vf_sh = self._read_repo("system_scripts", "vicefetch.sh")
        for token in ("COLORTERM", "--hold", "--plain", "--help", "--version", "Vice Tools"):
            self.assertIn(token, vf_sh)


if __name__ == "__main__":
    unittest.main()
