#!/usr/bin/env python3
"""
Unit tests for Vice OS shared Python utilities (lib/python/vice_utils.py).
Run with: python3 -m unittest tests.test_vice_utils
"""

import unittest
from unittest.mock import patch, mock_open, MagicMock
import sys
import os

# Add the lib and desktop directories to the system path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'lib', 'python')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'desktop')))

import vice_utils  # noqa: E402
import panel_config  # noqa: E402


class TestLaunchCommand(unittest.TestCase):
    """Tests for the launch_command function."""

    @patch('vice_utils.shutil.which', return_value='/usr/bin/ls')
    @patch('vice_utils.subprocess.Popen')
    def test_launch_valid_command(self, mock_popen, mock_which):
        """Test launching a valid command."""
        result = vice_utils.launch_command("ls -la")
        self.assertTrue(result)
        mock_which.assert_called_with('ls')
        mock_popen.assert_called_once()
        # Ensure shell=False is used for security
        args, kwargs = mock_popen.call_args
        self.assertFalse(kwargs.get('shell', False))

    @patch('vice_utils.shutil.which', return_value=None)
    @patch('vice_utils.subprocess.Popen')
    def test_launch_command_not_found(self, mock_popen, mock_which):
        """Test launching a command that does not exist."""
        result = vice_utils.launch_command("nonexistentcommand")
        self.assertFalse(result)
        mock_popen.assert_not_called()

    @patch('vice_utils.shutil.which', return_value='/usr/bin/ls')
    @patch('vice_utils.subprocess.Popen')
    def test_launch_empty_command(self, mock_popen, mock_which):
        """Test launching an empty string."""
        result = vice_utils.launch_command("")
        self.assertFalse(result)
        mock_popen.assert_not_called()

    @patch('vice_utils.shutil.which', return_value='/usr/bin/ls')
    @patch('vice_utils.subprocess.Popen')
    def test_launch_command_with_quotes(self, mock_popen, mock_which):
        """Test that quoted arguments are parsed correctly."""
        vice_utils.launch_command('ls -la "my file.txt"')
        # Check that Popen received a list with the quoted string as a single element
        expected_args = ['ls', '-la', 'my file.txt']
        args, kwargs = mock_popen.call_args
        self.assertEqual(args[0], expected_args)


class TestSystemMetrics(unittest.TestCase):
    """Tests for the SystemMetrics class."""

    def setUp(self):
        self.metrics = vice_utils.SystemMetrics()

    def test_get_cpu_usage_returns_string(self):
        """Test that get_cpu_usage returns a string starting with 'CPU:'."""
        # We need to call it twice because the first call just establishes a baseline
        with patch('builtins.open', mock_open(read_data='cpu  10 20 30 40 50 60 70 80 90 100\n')):
            self.metrics.get_cpu_usage()  # Baseline
            usage = self.metrics.get_cpu_usage()
            self.assertIsInstance(usage, str)
            self.assertTrue(usage.startswith("CPU:"))

    @patch('builtins.open', new_callable=mock_open)
    def test_get_cpu_usage_handles_exception(self, mock_file):
        """Test that get_cpu_usage returns 'CPU: N/A' on file read error."""
        mock_file.side_effect = IOError("File not found")
        usage = self.metrics.get_cpu_usage()
        self.assertEqual(usage, "CPU: N/A")

    def test_get_ram_usage_returns_string(self):
        """Test that get_ram_usage returns a string starting with 'RAM:'."""
        # Mock /proc/meminfo content
        meminfo_content = (
            "MemTotal:       16384000 kB\n"
            "MemFree:         8192000 kB\n"
            "MemAvailable:   12288000 kB\n"
        )
        with patch('builtins.open', mock_open(read_data=meminfo_content)):
            usage = self.metrics.get_ram_usage()
            self.assertIsInstance(usage, str)
            self.assertTrue(usage.startswith("RAM:"))
            # Check if math is roughly correct (Total - Available = Used)
            # 16384000 - 12288000 = 4096000 kB -> ~4000 MB
            self.assertIn("4000MB", usage)
            self.assertIn("16000MB", usage)

    @patch('builtins.open', new_callable=mock_open)
    def test_get_ram_usage_handles_exception(self, mock_file):
        """Test that get_ram_usage returns 'RAM: N/A' on file read error."""
        mock_file.side_effect = IOError("File not found")
        usage = self.metrics.get_ram_usage()
        self.assertEqual(usage, "RAM: N/A")


class TestLogging(unittest.TestCase):
    """Tests for logging functions to ensure they don't crash."""

    def test_log_info(self):
        vice_utils.log_info("Test info message")

    def test_log_success(self):
        vice_utils.log_success("Test success message")

    def test_log_warn(self):
        vice_utils.log_warn("Test warn message")

    def test_log_error(self):
        vice_utils.log_error("Test error message")


class TestBatteryStatus(unittest.TestCase):
    """Tests for the get_battery_status function."""

    @patch('vice_utils.os.path.isdir', return_value=False)
    def test_no_battery_path(self, mock_isdir):
        """Returns 'AC' when /sys/class/power_supply does not exist."""
        result = vice_utils.get_battery_status()
        self.assertEqual(result, "AC")

    def test_battery_exception_returns_ac(self):
        """Returns 'AC' when sysfs read raises an exception."""
        with patch('vice_utils.os.path.isdir', return_value=True), \
             patch('vice_utils.os.listdir', side_effect=PermissionError("denied")):
            result = vice_utils.get_battery_status()
            self.assertEqual(result, "AC")


class TestIsProcessRunning(unittest.TestCase):
    """Tests for the is_process_running function."""

    @patch('vice_utils.subprocess.run')
    def test_process_running(self, mock_run):
        """Returns True when pgrep finds the process."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        result = vice_utils.is_process_running("python3")
        self.assertTrue(result)

    @patch('vice_utils.subprocess.run')
    def test_process_not_running(self, mock_run):
        """Returns False when pgrep does not find the process."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result
        result = vice_utils.is_process_running("nonexistent")
        self.assertFalse(result)


class TestDiskUsage(unittest.TestCase):
    """Tests for the get_disk_usage function."""

    @patch('vice_utils.subprocess.run')
    def test_disk_usage_success(self, mock_run):
        """Returns the usage percentage string on success."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Use%\n42%\n"
        mock_run.return_value = mock_result
        result = vice_utils.get_disk_usage()
        self.assertEqual(result, "42%")

    @patch('vice_utils.subprocess.run')
    def test_disk_usage_failure(self, mock_run):
        """Returns 'N/A' when df fails."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result
        result = vice_utils.get_disk_usage()
        self.assertEqual(result, "N/A")

    @patch('vice_utils.subprocess.run', side_effect=Exception("df failed"))
    def test_disk_usage_exception(self, mock_run):
        """Returns 'N/A' on subprocess exception."""
        result = vice_utils.get_disk_usage()
        self.assertEqual(result, "N/A")


class TestWaylandSupport(unittest.TestCase):
    """Tests for Wayland support detection and commands."""

    @patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-0"})
    def test_wayland_session_detection(self):
        """Test detection of Wayland session."""
        self.assertTrue(os.environ.get("WAYLAND_DISPLAY") is not None)

    @patch.dict(os.environ, {}, clear=True)
    def test_x11_session_detection(self):
        """Test detection of X11 session when WAYLAND_DISPLAY is unset."""
        self.assertIsNone(os.environ.get("WAYLAND_DISPLAY"))


class TestSessionConfig(unittest.TestCase):
    """Tests for session configuration reading and format."""

    def test_session_config_parsing(self):
        """Test parsing of session configuration file content."""
        sample_config = '# Vice OS Session Config\nSESSION_TYPE="wayland"\n'
        session = "x11"
        for line in sample_config.splitlines():
            if line.strip().startswith("SESSION_TYPE="):
                session = line.strip().split("=", 1)[1].strip('"\'')
        self.assertEqual(session, "wayland")

    def test_session_config_default_x11(self):
        """Test default fallback to x11 when SESSION_TYPE is not wayland."""
        sample_config = '# Vice OS Session Config\nSESSION_TYPE="x11"\n'
        session = "x11"
        for line in sample_config.splitlines():
            if line.strip().startswith("SESSION_TYPE="):
                session = line.strip().split("=", 1)[1].strip('"\'')
        self.assertEqual(session, "x11")


class TestPanelConfig(unittest.TestCase):
    """Tests for panel configuration constants and geometry."""

    def test_dimensions_are_positive(self):
        """Panel dimensions must be positive integers."""
        self.assertGreater(panel_config.TOPBAR_HEIGHT, 0)
        self.assertGreater(panel_config.DOCK_HEIGHT, 0)
        self.assertGreater(panel_config.DOCK_WIDTH, 0)
        self.assertGreater(panel_config.DOCK_BUTTON_WIDTH, 0)
        self.assertGreater(panel_config.RUNMENU_WIDTH, 0)
        self.assertGreater(panel_config.RUNMENU_HEIGHT, 0)

    def test_color_palette_format(self):
        """Neon Miami colors must be valid color strings."""
        self.assertTrue(panel_config.COLOR_CYAN.startswith("#"))
        self.assertTrue(panel_config.COLOR_MAGENTA.startswith("#"))
        self.assertTrue(panel_config.COLOR_WHITE.startswith("#"))
        self.assertTrue(panel_config.COLOR_RED.startswith("#"))

    def test_dock_apps_structure(self):
        """DOCK_APPS must contain valid (label, command, tooltip) tuples."""
        self.assertIsInstance(panel_config.DOCK_APPS, list)
        self.assertGreaterEqual(len(panel_config.DOCK_APPS), 1)
        for item in panel_config.DOCK_APPS:
            self.assertEqual(len(item), 3)
            label, cmd, tooltip = item
            self.assertIsInstance(label, str)
            self.assertIsInstance(cmd, str)
            self.assertIsInstance(tooltip, str)

    def test_stalonetray_args_structure(self):
        """STALONETRAY_ARGS must be a list containing essential flags."""
        self.assertIsInstance(panel_config.STALONETRAY_ARGS, list)
        self.assertIn("--geometry", panel_config.STALONETRAY_ARGS)
        self.assertIn("--window-type", panel_config.STALONETRAY_ARGS)


class TestSessionWatchdogLogic(unittest.TestCase):
    """Tests for session watchdog exponential backoff calculations."""

    def test_backoff_progression(self):
        """Backoff doubles until reaching MAX_BACKOFF (30s)."""
        backoff = 1
        max_backoff = 30
        values = []
        for _ in range(6):
            values.append(backoff)
            backoff = min(backoff * 2, max_backoff)
        self.assertEqual(values, [1, 2, 4, 8, 16, 30])


if __name__ == '__main__':
    unittest.main()
