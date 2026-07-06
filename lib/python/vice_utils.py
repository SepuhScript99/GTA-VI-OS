#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Shared Python Utilities
Provides reusable system metrics, process management, and logging.
"""

import os
import sys
import subprocess
import shlex
import shutil
from typing import Dict, List, Optional

# --- ANSI Color Codes ---
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m' # No Color

# --- Public API Definition ---
__all__ = [
    'log_info', 'log_success', 'log_warn', 'log_error',
    'launch_command',
    'SystemMetrics', 'get_cpu_usage', 'get_ram_usage'
]

# --- Logging Functions ---

def log_info(message: str) -> None:
    """Logs an informational message to stdout."""
    print(f"{BLUE}[INFO]{NC} {message}")

def log_success(message: str) -> None:
    """Logs a success message to stdout."""
    print(f"{GREEN}[SUCCESS]{NC} {message}")

def log_warn(message: str) -> None:
    """Logs a warning message to stdout."""
    print(f"{YELLOW}[WARN]{NC} {message}")

def log_error(message: str) -> None:
    """Logs an error message to stderr."""
    print(f"{RED}[ERROR]{NC} {message}", file=sys.stderr)

# --- Process Management ---

def launch_command(cmd_str: str) -> bool:
    """
    Safely parse and launch a command string.
    Ensures the environment is inherited and quotes are respected.
    """
    try:
        # Guard against unbalanced quotes causing ValueError
        args: List[str] = shlex.split(cmd_str)
        if not args:
            return False
            
        # Verify the binary exists before execution
        if shutil.which(args[0]) is None:
            log_error(f"Command not found: {args[0]}")
            return False

        # Explicitly pass the environment to ensure DISPLAY, etc., are inherited
        subprocess.Popen(args, shell=False, env=os.environ)
        return True
    except ValueError as e:
        log_error(f"Invalid command syntax (check quotes): {e}")
        return False
    except Exception as e:
        log_error(f"Failed to launch command '{cmd_str}': {e}")
        return False

# --- System Metrics ---

class SystemMetrics:
    """Calculates and caches system metrics like CPU and RAM usage."""
    def __init__(self) -> None:
        self._prev_cpu_idle: int = 0
        self._prev_cpu_total: int = 0
        self._prev_cpu_usage: float = 0.0

    def get_cpu_usage(self) -> str:
        """Calculates CPU usage by sampling /proc/stat."""
        try:
            with open('/proc/stat', 'r') as f:
                fields: List[str] = f.readline().split()[1:]
            
            # idle + iowait
            idle: int = int(fields[3]) + int(fields[4])
            total: int = sum(int(i) for i in fields)
            
            idle_delta: int = idle - self._prev_cpu_idle
            total_delta: int = total - self._prev_cpu_total
            
            self._prev_cpu_idle = idle
            self._prev_cpu_total = total
            
            if total_delta > 0:
                usage: float = 100 - (100 * idle_delta / total_delta)
                self._prev_cpu_usage = usage
                return f"CPU: {int(usage)}%"
            
            # If total_delta is 0 (called too fast), return last known usage
            return f"CPU: {int(self._prev_cpu_usage)}%"
        except Exception:
            return "CPU: N/A"

    def get_ram_usage(self) -> str:
        """Reads /proc/meminfo to calculate used RAM safely."""
        try:
            mem_info: Dict[str, int] = {}
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    # Safely split by colon and strip whitespace
                    if ':' in line:
                        key, val_part = line.split(':', 1)
                        # Value is typically "  12345 kB", split and take first token
                        val: int = int(val_part.split()[0])
                        mem_info[key.strip()] = val
            
            total: int = mem_info.get('MemTotal', 0) // 1024
            # MemAvailable is more accurate than MemFree (includes reclaimable cache)
            available: int = mem_info.get('MemAvailable', mem_info.get('MemFree', 0)) // 1024
            used: int = total - available
            
            if total > 0:
                return f"RAM: {used}MB / {total}MB"
            return "RAM: N/A"
        except Exception:
            return "RAM: N/A"

# Module-level instance for backward compatibility with previous imports
_metrics = SystemMetrics()

def get_cpu_usage() -> str:
    """Module-level wrapper for CPU usage."""
    return _metrics.get_cpu_usage()

def get_ram_usage() -> str:
    """Module-level wrapper for RAM usage."""
    return _metrics.get_ram_usage()