Code Structure - GTA VI OS (Vice OS)
This document provides a granular, directory-by-directory breakdown of the repository layout. Use this guide to determine where to place new files.

📂 Root Directory
build_iso.sh: The main entry point for the ISO build pipeline. Orchestrates phases via state tracking.
chroot_setup.sh: The orchestrator for the chroot configuration phase. Executes scripts in chroot_scripts/ sequentially.
README.md, LICENSE: Standard repository files.
📁 Core Directories
build/
Contains modular scripts for specific phases of the ISO build pipeline.

Example: create_rootfs.sh (Debootstrap), create_squashfs.sh (SquashFS compression), pack_iso.sh (xorriso packing).
Add here: New build phases (e.g., create_delta.sh).
chroot_scripts/
Contains numbered bash scripts executed inside the chroot environment to configure the OS.

Naming: NN_description.sh (e.g., 01_install_packages.sh). Executed in alphabetical order.
Add here: Scripts that modify the chroot filesystem (e.g., installing packages, writing configs).
config/
Contains declarative configuration files copied into the chroot or ISO.

packages.list: List of apt packages to install.
grub.cfg, sysctl.conf: System-wide configurations.
apt/, pipewire/, systemd/, X11/, etc.: Subdirectories mirroring the target Linux filesystem hierarchy (/etc/).
skel/: User skeleton directory (copied to /etc/skel and /home/vice).
Add here: Any static configuration file.
desktop/
Contains the custom PyQt5 desktop environment components.

vice_shell.py: The main desktop shell (TopBar, Dock, Run Menu).
login.py: The graphical login screen.
style.qss: The global Qt Stylesheet (Neon Miami theme).
ob_menu.py: Openbox pipe menu generator.
Add here: New Python UI components or desktop helpers.
apps/
Contains user-facing application installer scripts.

vp-installer.sh: Physical disk installer.
vp-code.sh, vp-docker.sh: Third-party software installers.
Add here: Scripts that install specific user applications.
system_scripts/
Contains utility scripts installed to /usr/local/bin/ on the target system.

vp-firewall.sh: Firewall configuration tool.
vice-os-menu.sh: TUI settings menu.
Add here: System maintenance, cleanup, or management scripts.
recovery/
Contains first-class recovery utilities for fixing broken systems.

rebuild_grub.sh: GRUB bootloader repair.
reset_network.sh: Network configuration reset.
Add here: Scripts designed to be run from a Live CD or rescue TTY.
lib/
Contains shared libraries used by other scripts.

common.sh: Bash library providing logging, error handling, and validation.
state_manager.sh: Bash library for build/install state tracking.
python/: Shared Python modules (e.g., vice_utils.py).
Add here: Reusable logic sourced by multiple scripts.
tests/
Contains automated tests and validation scripts.

test_vice_utils.py: Python unit tests.
validate_iso.sh: ISO structural integrity check.
smoke_test_qemu.sh: QEMU boot smoke test.
Add here: New test suites or testing utilities.
docs/
Contains all project documentation.

ARCHITECTURE.md, DEVELOPMENT.md, TESTING.md, etc.
Add here: New guides, RFCs, or design documents.
assets/
Contains scripts used to generate assets (wallpapers, icons) during the build.

Add here: Procedural generation scripts for UI assets.
state/
Directory used by lib/state_manager.sh to store build state files (e.g., build.state).

Note: This directory is tracked by git (via .gitkeep) but the state files themselves are ignored.
.github/workflows/
Contains GitHub Actions CI/CD pipeline definitions.

ci.yml: Main build and smoke test pipeline.
lint.yml: Code quality and unit test pipeline.