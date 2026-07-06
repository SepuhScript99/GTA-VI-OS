GTA VI OS (Vice OS) Architecture
This document outlines the architecture, modular design, and build pipeline of the Vice OS project. The project strictly follows the Single Responsibility Principle (SRP) and the Maturity Model for Linux distributions.

📂 Directory Structure & Responsibilities
Core Orchestration
build_iso.sh: The main entry point for building the ISO. It orchestrates the phases by calling modular scripts in the build/ directory.
chroot_setup.sh: Orchestrates the chroot configuration by mounting filesystems and executing modular scripts in chroot_scripts/ in alphabetical order.
Build Pipeline (build/)
create_squashfs.sh: Compresses the chroot into filesystem.squashfs using XZ (with GZIP fallback).
create_bootloader.sh: Generates hybrid BIOS (bios.img) and UEFI (efiboot.img) GRUB boot images.
pack_iso.sh: Uses xorriso to assemble the final hybrid ISO, validating all required artifacts before packing.
Chroot Configuration (chroot_scripts/)
Executed in order inside the target environment:

00_base_config.sh: Hostname, /etc/hosts, and apt sources. Includes mirror fallback.
01_install_packages.sh: Installs live-boot, kernel, and all packages from config/packages.list. Generates locales.
02_system_tuning.sh: Configures ZRAM, sysctl, UFW firewall, and systemd auto-update timers.
03_user_setup.sh: Creates the vice user, installs the desktop shell, and configures X11 auto-login.
Shared Libraries (lib/)
common.sh: Bash library providing colored logging (log_info, log_error), error trapping, and validation (check_root, check_internet, check_dependencies).
python/vice_utils.py: Python library providing system metrics (get_cpu_usage, get_ram_usage), process management (launch_command), and logging for PyQt5 applications.
Desktop Environment (desktop/)
login.py: A PyQt5 animated login screen. Authenticates via su and launches openbox-session.
vice_shell.py: A PyQt5 desktop shell providing a TopBar, Dock, and Run Menu. Imports from lib/python/vice_utils.py.
style.qss: A comprehensive Qt6-compatible stylesheet implementing the Neon Miami aesthetic.
Testing & Validation (tests/)
validate_iso.sh: Checks ISO size, SHA256 checksum, and verifies the presence of El Torito, EFI, and critical payload files using xorriso.
smoke_test_qemu.sh: Boots the ISO in a headless QEMU VM, extracting the kernel directly, and waits for the login prompt to ensure runtime stability.
Recovery (recovery/)
rebuild_grub.sh: A first-class recovery utility to reinstall GRUB on a broken system. Detects BIOS vs UEFI, mounts partitions, and chroots safely.
Automation (.github/workflows/)
ci.yml: GitHub Actions workflow that builds, validates, and smoke-tests the ISO on every push/pull request. Uploads the final ISO as an artifact.
🔄 The Build Flow
Debootstrap: build_iso.sh creates a minimal Debian Bookworm chroot.
Payload Copy: Config files, desktop assets, and lib/ are copied into /vice_payload/ inside the chroot.
Chroot Execution: chroot_setup.sh executes 00 through 03 scripts inside the chroot.
Cleanup: Payload files are removed, and update-initramfs is run.
SquashFS: build/create_squashfs.sh compresses the chroot.
Bootloader: build/create_bootloader.sh creates GRUB images.
ISO Packing: build/pack_iso.sh generates the final gta-vi-os-amd64.iso.
🧩 Maturity Model Layers
Vice OS aims to fulfill all layers of a professional Linux distribution:

Implementation: Modular bash and python scripts.
Configuration: Centralized in config/ and chroot_scripts/.
Validation: tests/validate_iso.sh.
Testing: tests/smoke_test_qemu.sh and GitHub Actions CI.
Recovery: recovery/rebuild_grub.sh.
Documentation: README.md and docs/ARCHITECTURE.md.
Automation: .github/workflows/ci.yml.