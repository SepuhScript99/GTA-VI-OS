#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Session Watchdog
Monitors the desktop shell process and auto-restarts it on crash with
exponential backoff. Prevents the user from being stranded on a black
screen after an unexpected shell failure.

Architecture:
  - Launched as a background process from dbus_session.sh or as a standalone
    systemd user service.
  - Polls the vice_shell.py PID every 3 seconds.
  - On crash: auto-restart with exponential backoff (1s → 2s → 4s → ... → 30s max).
  - Max 10 consecutive restarts before giving up (prevents crash loops).
  - All events logged via vice_utils for forensic analysis.
"""

import os
import sys
import time
import subprocess
try:
    import fcntl
except ImportError:
    fcntl = None

sys.path.insert(0, '/opt/vice-os/lib')

from python.vice_utils import log_error, log_info, log_warn  # noqa: E402

SHELL_PATH = "/opt/vice-os/vice_shell.py"
POLL_INTERVAL = 3
MAX_RESTARTS = 10
INITIAL_BACKOFF = 1
MAX_BACKOFF = 30


def _acquire_lock():
    """Ensure single instance of the watchdog runs per user session via flock."""
    if fcntl is None:
        return None
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR") or f"/tmp/vice-{os.getuid()}"
    try:
        os.makedirs(runtime_dir, exist_ok=True)
        lock_file = os.path.join(runtime_dir, "session_watchdog.lock")
        f = open(lock_file, "w")
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return f
    except (IOError, OSError):
        log_warn("Watchdog: another instance is already running for this user. Exiting.")
        return False


def _is_shell_running() -> bool:
    """Check whether vice_shell.py is currently running."""
    try:
        uid = os.getuid()
        result = subprocess.run(
            ["pgrep", "-u", str(uid), "-f", "vice_shell.py"],
            capture_output=True, timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def _start_shell():
    """Launch vice_shell.py as a detached background process."""
    if not os.path.isfile(SHELL_PATH):
        log_error(f"Watchdog: shell not found at {SHELL_PATH}")
        return False
    try:
        subprocess.Popen(
            ["python3", SHELL_PATH],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        log_info("Watchdog: vice_shell.py launched.")
        return True
    except Exception as e:
        log_error(f"Watchdog: failed to launch shell: {e}")
        return False


def main():
    """Main watchdog loop. Runs until max restarts exceeded or user logout."""
    lock_fd = _acquire_lock()
    if lock_fd is False:
        return 0

    consecutive_restarts = 0
    backoff = INITIAL_BACKOFF
    first_run = True

    log_info("Watchdog: session watchdog started.")

    # Allow window manager autostart to launch vice_shell.py before first poll
    time.sleep(POLL_INTERVAL)

    while consecutive_restarts < MAX_RESTARTS:
        if not _is_shell_running():
            if first_run:
                log_info("Watchdog: shell not yet running. Starting...")
                first_run = False
            else:
                consecutive_restarts += 1
                log_warn(
                    f"Watchdog: shell crashed (restart {consecutive_restarts}/{MAX_RESTARTS}). "
                    f"Backing off {backoff}s..."
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, MAX_BACKOFF)

            if not _start_shell():
                log_error("Watchdog: giving up — cannot launch shell binary.")
                return 1
        else:
            first_run = False
            consecutive_restarts = 0
            backoff = INITIAL_BACKOFF

        time.sleep(POLL_INTERVAL)

    log_error(
        f"Watchdog: shell crashed {MAX_RESTARTS} times consecutively. "
        "Giving up to prevent restart loop."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
