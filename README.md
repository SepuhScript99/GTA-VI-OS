# Vice OS

Version: 1.0 Stable

---

## Overview

Vice OS is a Debian Bookworm-based Linux distribution developed as a long-term engineering project.

The primary objective is not merely to create another Linux distribution, but to build a maintainable, modular, well-documented operating system using professional software engineering practices.

---

## Features

| Layer | Capabilities |
|-------|-------------|
| **Build** | State-managed, resumable ISO pipeline. Debootstrap clean retry logic. ARM64 cross-architecture support. Zstd SquashFS compression with /boot retention. |
| **Desktop** | Dual-session architecture: X11 (Openbox) + Wayland (Labwc). Session-aware login greeter. 81 PyQt5 components. 28-page Settings Center. First-boot welcome wizard. Crash watchdog. |
| **Recovery** | Flock-isolated unified TUI menu (vice-recovery.sh: GRUB rebuild, password reset, network reset, fsck, package repair, theme restore, diagnostics). |
| **Installer** | Hardened installer (vp-installer.sh) with anti-self-overwrite protection, LUKS2 disk encryption with dedicated /boot partition, and secure credentials piping. |
| **Validation** | 6 scripts: packages, rootfs, kernel, initramfs, ISO (deep isoinfo inspection), and resilient unified runner. |
| **Testing** | 142+ automated tests: 28 Python unit tests, 20 integration tests, 21 apps tests, 13 build pipeline tests, 11 common-library tests, 9 system_utils tests, 40+ runtime tests, recovery suite, QEMU smoke test. |
| **Security** | UFW firewall, fail2ban, LUKS2 encryption, polkit authentication, kernel sysctl hardening, and flock concurrency protection. |
| **Automation** | GitHub Actions CI (10+ quality gates: ShellCheck, unit tests, integration tests, config validation, ISO build, kernel/initramfs validation, smoke test, release). Static analysis. |
| **Release** | Automated pre-flight checklist, clean build, git tagging, GitHub Release with artifact upload (scripts/release.sh). |

---

## Repository Structure

```
build/           ISO build pipeline (4 modular scripts)
config/          Declarative configuration (packages, GRUB, systemd, X11, labwc, rpi)
desktop/         PyQt5 desktop environment (81 components — full app suite)
apps/            Application installers (physical disk with LUKS2, Docker, VS Code)
lib/             Shared libraries (bash + Python)
validation/      Build artifact validation scripts (6 scripts + unified runner)
recovery/        System recovery tools (6 scripts + watchdog)
tests/           Test suites (unit, integration, apps, build, system_utils, recovery, QEMU)
docs/            Documentation (19 files)
AI/              AI governance documents (15 files)
scripts/         Release automation
chroot_scripts/  Chroot configuration (49 numbered scripts)
system_scripts/  System maintenance (7 scripts)
system_utils/    System utilities (48 scripts + 4 python tools)
```

---

## Building

```bash
sudo bash build_iso.sh          # Normal build
sudo bash build_iso.sh --clean  # Fresh build (removes cached chroot)
```

Generated: `out/gta-vi-os-amd64.iso`

Build requirements: Debian/Ubuntu host with debootstrap, grub-pc-bin, grub-efi-amd64-bin, xorriso, squashfs-tools, mtools, dosfstools.

---

## Quick Start

1. Boot the ISO in VMware/VirtualBox (4GB RAM, 30GB disk recommended)
2. Login: `vice` / `vice`
3. Install to disk: `sudo vp-installer.sh`
4. Follow the first-boot welcome wizard for setup

---

## Engineering Priorities

This project follows a strict engineering priority model:

1. Broken builds
2. Security issues
3. Data loss or recovery
4. Validation
5. Testing
6. Reliability
7. Maintainability
8. Documentation
9. Performance
10. New features

All priorities 1–9 are addressed. Active development focuses on priority 10.

---

## Documentation

Before contributing, read:

- PROJECT_STATUS.md
- ROADMAP.md
- TODO.md
- ARCHITECTURE.md
- AI_BOOTSTRAP.md
- All files in AI/

---

## License

See LICENSE.
