# GTA VI OS (Vice OS) Architecture

This document outlines the architecture, modular design, subsystem boundaries, and build pipeline of the Vice OS project. The project strictly adheres to the Single Responsibility Principle (SRP) and the Maturity Model for Linux distributions.

---

## 📂 Subsystems & Responsibilities

### 1. Core Orchestration
- `build_iso.sh`: The main orchestrator for building the ISO image. Manages state tracking, cleanup traps, argument parsing, and invokes pipeline stages in `build/`.
- `chroot_setup.sh`: Manages chroot configuration by mounting pseudo-filesystems (`/dev`, `/proc`, `/sys`), staging the `/vice_payload/` source files, and executing the 49 scripts in `chroot_scripts/` sequentially.

### 2. Build Pipeline (`build/`)
- `create_rootfs.sh`: Stages the minimal Debian Bookworm rootfs using `debootstrap` with retry logic, configurable mirrors (`DEBIAN_MIRROR`), and multi-arch support (`DEBIAN_ARCH`).
- `create_squashfs.sh`: Compresses the chroot into `live/filesystem.squashfs` using high-performance Zstandard (`zstd -Xcompression-level 19`) with automatic XZ and Gzip fallbacks.
- `create_bootloader.sh`: Generates hybrid BIOS (`bios.img`) and UEFI (`efiboot.img`) GRUB boot images. Stages ARM64 EFI and Raspberry Pi bootloader configs (`config/rpi/`) for ARM64 targets.
- `pack_iso.sh`: Assembles the final hybrid bootable ISO using `xorriso`, validating all required artifacts and generating `SHA256SUMS` and `build_info.txt`.

### 3. Chroot Configuration (`chroot_scripts/`)
Contains 49 numbered modular configuration scripts executed in alphabetical order inside the target chroot:
- `00_base_config.sh` – `05_network_audio_fix.sh`: Hostname, apt sources, packages installation from `config/packages.list`, system tuning (sysctl, ZRAM), user creation, desktop autostart, and network/audio fixes.
- `07_polkit_setup.sh` – `20_modprobe_setup.sh`: Polkit rules, udev, PAM, Thunar, GTK themes, terminal colors, `/etc/os-release`, APT policies, PipeWire audio, systemd units, and kernel module blacklists.
- `21_xorg_setup.sh` – `46_user-setup_script.sh`: Xorg display server, skeleton configs, dpkg flags, NTP/Chrony, UFW firewall, cron, logging, Avahi, hardware clocks, SSH, and login configuration.
- `47_rpi_arm64_setup.sh`: Raspberry Pi firmware, U-Boot scripts, and ARM64 kernel module configuration.
- `90_optimize.sh`: Build-time footprint optimization (removes unnecessary documentation, cleans cache, trims non-en_US locales, optimizes services).
- `99_cleanup.sh`: Final sanitization (cleans apt cache, temporary files, machine-id, and removes `/vice_payload/`).

### 4. Shared Libraries (`lib/`)
- `lib/common.sh`: Shared Bash library providing colored logging (`log_info`, `log_success`, `log_warn`, `log_error`), strict mode enforcement (`set -Eeuo pipefail`), error traps, cleanup handlers, root/dependency checks, and disk space validation.
- `lib/state_manager.sh`: Build state and stage persistence for resumable builds.
- `lib/python/vice_utils.py`: Shared Python library providing system metrics (`get_cpu_usage`, `get_ram_usage`, `get_disk_usage`, `get_battery_status`), process execution (`launch_command`, `is_process_running`), and unified logging for PyQt5 applications.

### 5. Desktop Environment (`desktop/`)
The desktop experience comprises 81 components implemented in PyQt5, styled with a Neon Miami theme (`style.qss`):
- **Core & Session**:
  - `vice_shell.py`: Main desktop shell with TopBar metrics, application dock, and RunMenu (Win+Space).
  - `login.py`: Session-aware animated login greeter supporting both X11 (Openbox) and Wayland (Labwc) sessions with user preference persistence.
  - `wayland_session.sh`: Wayland session launcher using the `labwc` compositor, `swaybg` wallpaper, `swayidle`/`swaylock` screen locking, and session-aware shell.
  - `dbus_session.sh`: X11 session initializer launching D-Bus, PipeWire, Xresources, and session watchdog.
  - `session_watchdog.py`: Shell crash watchdog with exponential backoff auto-restart.
- **Panel & Management**:
  - `panel_config.py`: Centralized source of truth for panel geometry, dock apps, and system tray configuration.
  - `systray_manager.py`: System tray manager (`stalonetray`, `nm-applet`, `pavucontrol`).
  - `power_manager.py` & `wallpaper_manager.py`: Power controls and multi-backend wallpaper management (Nitrogen, Feh, Swaybg).
  - `welcome_wizard.py`: 9-page first-boot setup wizard for new installations.
- **Application Suite (69 tools)**:
  - System: `vice_task_manager.py`, `vice_system_monitor.py`, `vice_system_report.py`, `vice_sysinfo_exporter.py`, `vice_service_manager.py`, `vice_update_manager.py`, `vice_driver_manager.py`, `vice_diagnostics.py`, `vice_log_viewer.py`, `vice_log_rotation.py`, `vice_cron_manager.py`, `vice_backup_scheduler.py`, `vice_disk_usage.py`, `vice_iso_validator.py`.
  - Productivity & Media: `vice_file_manager.py`, `vice_file_search.py`, `vice_text_editor.py`, `vice_terminal.py`, `vice_archive_manager.py`, `vice_screenshot.py`, `vice_screen_recorder.py`, `vice_media_player.py`, `vice_image_viewer.py`, `vice_pdf_viewer.py`, `vice_calculator.py`, `vice_calendar.py`, `vice_clipboard_manager.py`.
  - Settings & Administration: `vice_settings.py` (28-page GUI Control Center), `vice_user_manager.py`, `vice_software_center.py`, `vice_theme_manager.py`, `vice_openbox_editor.py`, `vice_firewall_manager.py`, `vice_vpn_manager.py`, `vice_wifi_connect.py`, `vice_bluetooth_manager.py`, `vice_display_manager.py`.

### 6. System Utilities (`system_utils/` & `system_scripts/`)
- `system_utils/`: 48 modular shell management utilities and 4 Python tools providing CLI controls for audio, displays, network, power, security, users, and storage.
- `system_scripts/`: 7 system administration scripts installed to `/usr/local/bin/` (`vice-os-menu.sh`, `backup_home.sh`, `clean_logs.sh`, `repair_packages.sh`, `vp-autoupdate.sh`, `vp-firewall.sh`, `vp-flatpak.sh`).

### 7. Recovery Framework (`recovery/`)
- `vice-recovery.sh`: Unified interactive TUI recovery environment featuring GRUB reinstallation, password reset, network reset, filesystem check (`fsck`), package repair, and system diagnostics.
- `rebuild_grub.sh`: Dedicated GRUB bootloader reinstallation utility for UEFI and BIOS.
- `reset_password.sh`: Offline user and root password reset tool.
- `reset_network.sh`: Network configuration reset and DNS recovery tool.
- `vice_grub_theme.sh` & `vice_plymouth_theme.sh`: Cyberpunk GRUB boot menu and Plymouth splash themes.

### 8. Validation Suite (`validation/`)
- `run_all.sh`: Unified validation runner executing all validators with granular pass/fail/skip reporting and pipeline error handling.
- `validate_packages.sh`: Verifies `config/packages.list` for syntax, duplicate entries, formatting, and required dependencies.
- `validate_rootfs.sh`: Inspects target chroot for required directories, critical system binaries, configuration files, and `vice` user setup.
- `validate_kernel.sh`: Verifies kernel binary, kernel modules (`ext4`, `squashfs`, `overlay`, `virtio`), and kernel configuration.
- `validate_initramfs.sh`: Checks initramfs image integrity, format, live-boot component inclusion, and kernel version matching.
- `validate_iso.sh`: Isoinfo-based deep inspection of the built ISO: verifies ISO9660, El Torito, UEFI boot records, SquashFS integrity, kernel/initramfs extraction, and GRUB configuration.

### 9. Testing Framework (`tests/`)
- `test_vice_utils.py`: 28 Python unit tests validating `vice_utils` metrics, process execution, and error handling.
- `test_validation.sh`: 20 cross-subsystem integration tests verifying packages, configs, modules, Wayland integration, ARM64/RPi boot files, and login greeter.
- `test_system_utils.sh`: 9 tests validating syntax, shared-library preambles, and structure across all `system_utils/` scripts.
- `test_system_utils_runtime.sh`: 40+ function-level runtime tests checking argument parsing, exit codes, and execution behavior.
- `test_common_sh.sh`: 11 tests verifying shared Bash functions (`get_timestamp`, `retry_command`, logging, cleanup).
- `smoke_test_qemu.sh`: Headless QEMU virtual machine boot verification.

### 10. Automation & CI/CD (`.github/workflows/` & `scripts/`)
- `.github/workflows/ci.yml`: Full multi-stage CI pipeline running linting, static analysis, unit tests, integration tests, chroot validation, ISO build, and release publishing.
- `scripts/release.sh`: Automated release orchestrator handling pre-flight checks, clean builds, Git tagging, and GitHub Releases.

---

## 🔄 The Build Flow

```
[1. Debootstrap]       --> Minimal Debian Bookworm rootfs staged via create_rootfs.sh
[2. Payload Staging]   --> Project configs, desktop, system_utils, apps staged to /vice_payload/
[3. Chroot Setup]      --> chroot_setup.sh executes 49 chroot_scripts (00-47, 90, 99)
[4. Optimization]      --> 90_optimize.sh strips docs, optimizes locales, cleans cache
[5. Cleanup]           --> 99_cleanup.sh purges payload and generates final initramfs
[6. SquashFS]          --> create_squashfs.sh compresses rootfs with Zstandard (XZ/Gzip fallback)
[7. Bootloader]        --> create_bootloader.sh builds hybrid BIOS + UEFI GRUB images (or ARM64 U-Boot)
[8. ISO Packing]       --> pack_iso.sh runs xorriso, creates out/gta-vi-os-{arch}.iso and SHA256SUMS
[9. Validation]        --> run_all.sh & validate_iso.sh verify ISO structural and payload integrity
```

---

## 🧩 Distribution Maturity Model

Vice OS fulfills all ten layers of a modern production Linux distribution:
1. **Implementation**: Modular, idempotent Bash and Python components.
2. **Configuration**: Declarative configuration in `config/` and modular `chroot_scripts/`.
3. **Desktop**: Rich 81-component PyQt5 suite supporting both X11 (Openbox) and Wayland (Labwc).
4. **Validation**: 6-part validation suite in `validation/` with deep artifact verification.
5. **Testing**: 112+ automated tests covering unit, integration, runtime, and smoke tests.
6. **Recovery**: Unified recovery menu, rescue tools, and desktop crash watchdog.
7. **Security**: Hardened sysctl, UFW firewall, LUKS disk encryption, and polkit rules.
8. **Performance**: Zstandard SquashFS compression, ZRAM swap, and build optimization.
9. **Documentation**: Comprehensive guides in `docs/` and root governance files.
10. **Automation**: Robust GitHub Actions CI/CD workflows and release automation.
