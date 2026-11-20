# Code Structure - GTA VI OS (Vice OS)

This document provides a directory-by-directory breakdown of the repository layout. Use this guide to understand subsystem boundaries and locate files.

---

## 📂 Root Directory

- `build_iso.sh`: The main entry point for the ISO build pipeline. Coordinates build stages and state tracking.
- `chroot_setup.sh`: Orchestrator for the chroot configuration phase. Mounts filesystems and executes chroot scripts.
- `AI_BOOTSTRAP.md`: Authoritative engineering guidelines and onboarding document for contributors.
- `PROJECT_STATUS.md`: Authoritative project state, milestone tracking, and subsystem status.
- `ROADMAP.md`: Project development roadmap and version milestones.
- `TODO.md`: Task tracker and implementation backlog.
- `CHANGELOG.md`: Chronological log of notable additions, modifications, and fixes.
- `ARCHITECTURE.md`: High-level architecture and layered design principles.
- `README.md`, `LICENSE`, `CONTRIBUTING.md`: Standard open-source repository files.

---

## 📁 Core Directories

### `build/`
Contains modular scripts for specific phases of the ISO build pipeline:
- `create_rootfs.sh`: Debootstrap root filesystem staging.
- `create_squashfs.sh`: Zstandard-compressed SquashFS image creation.
- `create_bootloader.sh`: Hybrid BIOS and UEFI GRUB boot images (plus ARM64/RPi staging).
- `pack_iso.sh`: Final bootable ISO packaging via `xorriso`.

### `chroot_scripts/`
Contains 49 numbered Bash scripts executed sequentially inside the chroot environment:
- `00_base_config.sh` through `46_user-setup_script.sh`: System configuration, networking, audio, display, services, security.
- `47_rpi_arm64_setup.sh`: Raspberry Pi & ARM64 boot configuration.
- `90_optimize.sh`: Build-time disk footprint and performance optimization.
- `99_cleanup.sh`: Temporary files sanitization, cache purging, and payload removal.

### `config/`
Declarative system configurations staged into the target system or ISO:
- `packages.list`, `packages.arm64.list`: Package manifests for x86_64 and ARM64.
- `grub.cfg`, `fstab`, `sysctl.conf`, `os-release`, `openbox_rc.xml`: Core system configurations.
- `apt/`, `pipewire/`, `systemd/`, `X11/`, `modprobe.d/`, `polkit-1.preset`: Subsystem configurations mirroring target filesystem paths.
- `labwc/`: Labwc compositor configuration for Wayland sessions (`rc.xml`, `autostart`, `environment`, `menu.xml`).
- `rpi/`: Raspberry Pi boot firmware and U-Boot scripts (`config.txt`, `cmdline.txt`, `boot.cmd`).
- `skel/`: User skeleton files copied to `/etc/skel` and `/home/vice`.

### `desktop/`
Contains the 81 PyQt5 desktop environment components:
- `vice_shell.py`: Main desktop shell (TopBar, Dock, Run Menu).
- `login.py`: Session-aware animated greeter with X11 / Wayland session selection.
- `wayland_session.sh`: Wayland session launcher using the `labwc` compositor.
- `dbus_session.sh`: X11 session launcher and watchdog startup.
- `panel_config.py`: Central geometry and layout configuration for panel components.
- `systray_manager.py`, `power_manager.py`, `wallpaper_manager.py`: Panel sub-managers.
- `session_watchdog.py`: Shell crash watchdog with auto-restart.
- `welcome_wizard.py`: First-boot configuration wizard.
- `style.qss`: Global Qt stylesheet (Neon Miami theme).
- 69 dedicated PyQt5 applications (System Tools, Media, Settings, Networking).

### `validation/`
Comprehensive build artifact validation suite:
- `run_all.sh`: Unified validation runner with pipeline error handling.
- `validate_packages.sh`: Validates `config/packages.list` format, syntax, and dependencies.
- `validate_rootfs.sh`: Verifies target root filesystem directories and required files.
- `validate_kernel.sh`: Validates kernel binary, modules, and kernel configuration.
- `validate_initramfs.sh`: Checks initramfs format and live-boot support.
- `validate_iso.sh`: Isoinfo-based deep inspection of built ISO images.

### `recovery/`
First-class recovery and rescue tools:
- `vice-recovery.sh`: Unified interactive TUI recovery menu (flock locked).
- `rebuild_grub.sh`: GRUB bootloader repair for BIOS and UEFI.
- `reset_password.sh`: Offline user and root password reset.
- `reset_network.sh`: Network configuration reset and DNS recovery.
- `vice_grub_theme.sh`, `vice_plymouth_theme.sh`: Cyberpunk boot theming tools.

### `tests/`
Automated testing framework:
- `test_vice_utils.py`: 28 Python unit tests.
- `test_validation.sh`: 20 cross-subsystem integration tests.
- `test_system_utils.sh`: 9 system utilities structure and compliance tests.
- `test_system_utils_runtime.sh`: 40+ system utilities runtime behavior tests.
- `test_common_sh.sh`: 11 Bash shared library tests.
- `validate_iso.sh`: Standalone ISO size and checksum verification.
- `smoke_test_qemu.sh`: Headless QEMU boot test.

### `system_utils/`
48 standalone CLI utility scripts and 4 Python tools for administration:
- Audio, display, battery, power, network, update, security, storage, service, and UI managers.

### `system_scripts/`
7 system administration and maintenance scripts installed to `/usr/local/bin/`:
- `vice-os-menu.sh`, `backup_home.sh`, `clean_logs.sh`, `repair_packages.sh`, `vp-autoupdate.sh`, `vp-firewall.sh`, `vp-flatpak.sh`.

### `apps/`
User-facing installation scripts:
- `vp-installer.sh`: Physical disk installer with LUKS encryption support.
- `vp-code.sh`: Visual Studio Code installer.
- `vp-docker.sh`: Docker Engine and Compose installer.

### `lib/`
Shared core libraries:
- `common.sh`: Shared Bash library (logging, error traps, dependency checks).
- `state_manager.sh`: Build state and step tracking.
- `python/vice_utils.py`: Shared Python library (metrics, process execution, logging).

### `docs/`
All project documentation guides and technical specifications (19 documents).

### `AI/`
AI governance guidelines, standards, health logs, and decision logs (15 documents).

### `scripts/`
Release automation scripts:
- `release.sh`: Pre-flight checklist, ISO build, git tagging, and GitHub release creation.

### `.github/workflows/`
GitHub Actions CI/CD workflows:
- `ci.yml`: Full automated build, test, and release workflow.
- `lint.yml`: Static analysis and linting workflow.
