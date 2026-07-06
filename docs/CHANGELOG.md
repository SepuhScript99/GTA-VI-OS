Changelog
All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog,and this project adheres to Semantic Versioning.

Unreleased
1.0.0 - 2024-05-24
Added
Modular Build Pipeline: Build phases are now isolated in build/create_squashfs.sh, build/create_bootloader.sh, and build/pack_iso.sh.
Modular Chroot Configuration: chroot_setup.sh now orchestrates numbered scripts in chroot_scripts/ (e.g., 00_base_config.sh to 07_polkit_setup.sh).
Shared Libraries: Centralized Bash utilities in lib/common.sh and Python utilities in lib/python/vice_utils.py to enforce DRY principles.
Testing & Validation Layer: Added tests/validate_iso.sh for structural integrity checks and tests/smoke_test_qemu.sh for runtime boot tests.
Recovery Layer: Added recovery/rebuild_grub.sh and recovery/reset_network.sh for first-class system recovery.
Backup Utility: Added system_scripts/backup_home.sh for user data snapshots.
CI/CD Automation: Added .github/workflows/ci.yml to automate building, testing, and artifact uploading on GitHub.
Desktop Session Fixes: Added desktop/dbus_session.sh to properly initialize DBus and Pipewire/PulseAudio before Openbox starts.
XDG Autostart: Migrated compositor, wallpaper, and shell startup logic to standard .desktop entries in config/.
Polkit Rules: Added config/polkit-1.preset to grant sudo and netdev groups desktop privileges without root passwords.
Sudoers Config: Added config/sudoers snippet with secure_path for safer privilege escalation.
Documentation: Added docs/ARCHITECTURE.md, docs/RECOVERY.md, and docs/CONTRIBUTING.md.
VCS & IDE Config: Added .gitignore and .editorconfig for standardized development.
Changed
Login Flow: desktop/login.py now launches dbus_session.sh instead of openbox-session directly, fixing audio and DBus integration.
NetworkManager: Disabled systemd-resolved in favor of NetworkManager DNS management to prevent race conditions on Live ISO.
System Tuning: sysctl.conf updated with vm.page-cluster=0 for ZRAM optimization, TCP BBR, and expanded vm.max_map_count for gaming/containers.
Installer Robustness: apps/vp-installer.sh now validates disk types, creates BIOS boot partitions correctly, and validates sudoers syntax before finishing.
QSS Theme: desktop/style.qss expanded to cover toolbars, status bars, tabs, and sliders for a consistent neon aesthetic across all Qt apps.
Fixed
DNS Resolution: Fixed intermittent DNS failures on Live ISO by resolving NetworkManager and systemd-resolved conflicts.
Focus Stealing: Fixed desktop shell stealing keyboard focus on boot by adding Qt.WA_ShowWithoutActivating.
SquashFS Corruption: Fixed issue where failed SquashFS builds left partial artifacts that broke subsequent ISO packing.
Login UI Freeze: Fixed authentication UI freeze by using QProcess and waitForStarted instead of blocking subprocess.Popen.
Audio/DBus Failure: Fixed broken audio and desktop IPC by ensuring dbus-update-activation-environment is called before launching the window manager.
0.1.0 - 2023-10-15
Added
Initial Alpha release of GTA VI OS (Vice OS).
Monolithic build_iso.sh and chroot_setup.sh scripts.
Basic PyQt5 desktop shell (vice_shell.py) and login screen (login.py).
Debian Bookworm base with Openbox window manager.
Basic Neon Miami aesthetic (wallpaper, picom config, QSS theme).
Physical installer script (apps/vp-installer.sh).
