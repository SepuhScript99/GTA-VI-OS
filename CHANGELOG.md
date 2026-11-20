# Changelog

All notable changes should be documented here.

---

## Unreleased

### Added

- Build Pipeline Hardening & Test Suite (`tests/test_build_pipeline.sh` — 13/13 passed):
  - ARM64 cross-architecture support with two-stage debootstrap and `qemu-aarch64-static` staging.
  - Deterministic SquashFS compression via `-all-root` and `-mkfs-time "$SOURCE_DATE_EPOCH"`.
  - Retention of `/boot` in SquashFS for offline target installation via `vp-installer.sh`.
  - Reproducible `efiboot.img` FAT generation with fixed volume ID (`-i 47544136`).
  - Added `.gitignore` entries for obsolete snapshot directories (`iso_build_prep/`, `state/`).
- Installer & Applications Hardening (`tests/test_apps.sh` — 21/21 passed):
  - Live media detection and anti-self-overwrite protection in `apps/vp-installer.sh`.
  - Safe partition unmounting (swapoff + umount) before disk partitioning.
  - Dedicated 1024MB `/boot` partition when LUKS2 encryption is selected.
  - Credential injection prevention via secure `chpasswd` stdin piping.
  - Hardened sudoers configuration with `visudo` validation and root account locking.
  - Machine-ID and SSH host key regeneration on target systems.
  - Dynamic Docker repository architecture generation in `vp-docker.sh` and flock concurrency protection.
- Recovery Framework Hardening (`tests/test_recovery_suite.sh` — all passed):
  - Concurrency flock lock state protection (`LOCKED` and `MOUNTED` state tracking).
  - Option 7 in `vice-recovery.sh`: "Restore Boot Themes (GRUB & Plymouth)".
  - Chroot mount isolation using `--rbind` and `--make-rslave`.
- Desktop application suite expanded to 81 components:
  - Dual session architecture: X11 (Openbox) + Wayland (`labwc` compositor, `swaybg`, `swayidle`/`swaylock`).
  - Session-aware animated login greeter (`desktop/login.py`) with dropdown session selection.
  - 28-page Settings Center (`desktop/vice_settings.py`).
  - First-boot welcome wizard (`desktop/welcome_wizard.py`).
  - 69 dedicated PyQt5 tools across system, media, settings, and networking.
- Validation Framework Enhancement:
  - 6 validation scripts (`run_all.sh`, `validate_packages.sh`, `validate_rootfs.sh`, `validate_kernel.sh`, `validate_initramfs.sh`, `validate_iso.sh`).
  - Unified runner with pipeline error handling.

### Changed

- Reconciled all documentation drift across 19 files in `docs/` and root governance files (`PROJECT_STATUS.md`, `ROADMAP.md`, `TODO.md`, `README.md`, `ARCHITECTURE.md`).
- Scripts across `system_utils/`, `system_scripts/`, `apps/`, `recovery/`, and `build/` migrated to working shared-library preamble.
- `chroot_setup.sh` stages full `/vice_payload/` including `system_utils/` and `recovery/`.
- `build_iso.sh` scopes `/proc`, `/sys`, `/dev` mounts for initramfs generation and dynamically resolves kernel images.

### Fixed

- Fixed `validation/run_all.sh` crashing under `pipefail` when `$ISODIR` is absent, and corrected skip counter (3 chroot + 1 ISO validator).
- Fixed clobbering EXIT traps in `validation/validate_iso.sh` which previously destroyed `lib/common.sh` cleanup handlers.
- Fixed destructive flock trap bug in `recovery/` scripts where secondary processes tearing down unmounted the active instance's filesystems.
- Fixed stdout pollution in `vice-recovery.sh` partition selection capturing prompt text into device variables.
- Fixed unhandled exit codes under `set -e` in `vice-recovery.sh` causing premature TUI termination.
- Fixed `build/create_rootfs.sh` debootstrap retry failure by cleanly wiping dirty target directories before retrying.
- Fixed BIOS GRUB rescue drop by embedding `search_fs_file`, `part_gpt`, `fat`, and display modules into `grub-mkstandalone`.
- Fixed ARM64 El Torito boot entry ordering in `build/pack_iso.sh`.
- Fixed unbound variable crash (`kernel_img`) in `build_iso.sh` on resumed builds.
- Fixed security eval injection risk in `input_manager.sh` and unsafe home dir expansion in `user_manager.sh`.

---

## v0.3

### Added

Validation framework.

### Changed

Repository architecture.

### Fixed

Various build improvements.
