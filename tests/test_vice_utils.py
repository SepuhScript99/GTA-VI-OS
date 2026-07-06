#!/usr/bin/env python3
"""
Unit tests for Vice OS shared Python utilities (lib/python/vice_utils.py).
Run with: python3 -m unittest tests.test_vice_utils
"""

import unittest
from unittest.mock import patch, mock_open, MagicMock
import sys
import os

# Add the lib directory to the system path to import the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'lib', 'python')))

import vice_utils

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
            self.metrics.get_cpu_usage() # Baseline
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

if __name__ == '__main__':
    unittest.main()