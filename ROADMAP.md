# Vice OS Roadmap

---

## v0.1 — Foundation

Status: Completed

Minimal Debian Bookworm base, package manifests, and repository structure.

---

## v0.2 — Build System

Status: Completed

Modular pipeline (`build/`), state-managed orchestrator (`build_iso.sh`), clean debootstrap retry wiping, ARM64 cross-architecture support, and Zstandard SquashFS compression.

---

## v0.3 — Validation

Status: Completed

6 validation scripts in `validation/`: packages, rootfs, kernel, initramfs, ISO (deep isoinfo integrity inspection), and resilient unified runner (`run_all.sh`).

---

## v0.4 — Recovery

Status: Completed

Flock-isolated unified recovery menu (`recovery/vice-recovery.sh`), GRUB repair, password reset, network reset, filesystem check (`fsck`), package repair, boot theme restore, and desktop crash watchdog.

---

## v0.5 — Testing

Status: Completed

142+ automated tests: 28 Python unit tests + 20 integration tests + 21 apps tests + 13 build pipeline tests + 11 common-library tests + 9 system_utils structure tests + 40+ system_utils runtime tests + recovery verification suite, `tests/__init__.py`.

---

## v0.6 — Desktop Improvements

Status: Completed

Dual session architecture: X11 (Openbox) + Wayland (`labwc`), session-aware login greeter (`login.py`), 81 desktop components, 28-page Settings Center (`vice_settings.py`), first-boot welcome wizard (`welcome_wizard.py`), and 69 dedicated PyQt5 tools.

---

## v0.7 — Installer

Status: Completed

Hardened physical installer (`vp-installer.sh`) with anti-self-overwrite protection, LUKS2 disk encryption with dedicated `/boot` partition, secure stdin `chpasswd` piping, and post-install hooks.

---

## v0.8 — Optimization

Status: Completed

Build-time optimization (`90_optimize.sh`): documentation trimming, locale deduplication, apt cache cleanup, redundant module removal, and sysctl kernel tuning.

---

## v0.9 — Release Candidate

Status: Completed

Release automation (`scripts/release.sh`), CI release workflow with artifact upload, pre-flight checklists, and checksum generation.

---

## v1.0 — Stable

Status: Completed

All milestones and post-v1.0 enhancements complete. Repository at v1.0 Stable with 100% subsystem test coverage and zero documentation drift.
