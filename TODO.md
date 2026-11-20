# TODO

## Post-v1.0 Subsystem Hardening & Audit

- [x] Validation Framework Resilience (`validation/run_all.sh` pipefail fix, skip counter fix, `validate_iso.sh` unified cleanup trap)
- [x] Installer & Applications Hardening (`vp-installer.sh` live-media protection, LUKS2 dedicated `/boot` partition, secure `chpasswd` stdin piping, `vp-docker.sh` dynamic repo generation, `tests/test_apps.sh` 21/21 passed)
- [x] Recovery Framework Hardening (`vice-recovery.sh` flock lock isolation, interactive stdout separation, `set -e` condition guards, `tests/test_recovery_suite.sh` passed)
- [x] Build Pipeline Hardening (`create_rootfs.sh` debootstrap clean retry, ARM64 cross-architecture support, BIOS GRUB rescue module inclusion, `tests/test_build_pipeline.sh` 13/13 passed)
- [x] Documentation Reconciliation (Zero documentation drift across all 19 `docs/` files, root governance docs, and AI logs)

---

## Post-v1.0 Feature Candidates

- [x] GUI Settings Center — PyQt5 control panel with 28 pages (`desktop/vice_settings.py`)
- [x] Wayland session support — `labwc` compositor, opt-in via `/etc/vice-os/session.conf` (`config/labwc/`, `desktop/wayland_session.sh`)
- [x] Flatpak integration — Flatpak + Flathub support (`system_scripts/vp-flatpak.sh`)
- [x] Raspberry Pi ARM64 image & bootloader config — `config/rpi/`, U-Boot script, raspi-firmware (`chroot_scripts/47_rpi_arm64_setup.sh`, `build/create_bootloader.sh`)
- [x] Welcome wizard auto-launch — autostart `.desktop` + flag file mechanism (`desktop/welcome_wizard.py`)
- [x] CI static analysis — YAML, JSON, whitespace, permissions checks
- [x] ARM64 build foundation — `DEBIAN_ARCH`, `DEBIAN_MIRROR`, arch-aware package selection
- [x] Session-aware greeter — X11/Wayland session switcher in `login.py`

---

## Known Issues for Future Work

- None currently blocking. All post-v1.0 feature candidates and hardening audits complete.

---

## Completed (v0.1 → v1.0)

- [x] Function-level runtime tests for system utilities (`tests/test_system_utils_runtime.sh`)
- [x] Wayland idle management and screen locking (`swaylock` + `swayidle` integration)
- [x] Raspberry Pi ARM64 firmware, U-Boot scripts, and bootloader staging (`config/rpi/`, `chroot_scripts/47_rpi_arm64_setup.sh`)
- [x] Session-aware login greeter with X11 / Wayland session selection dropdown (`desktop/login.py`)
- [x] Expanded test coverage: 142+ automated tests across unit, integration, apps, build, and recovery suites
- [x] Security audit: eval injection fix (`input_manager.sh`), safe home dir lookup (`user_manager.sh`), flock protection
- [x] Panel config integration: `vice_shell.py` and `systray_manager.py` use `panel_config.py` as single source of truth
- [x] All roadmap milestones complete. Repository at v1.0 Stable. See `CHANGELOG.md` for full history.
