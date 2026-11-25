# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

---

## [0.01-alpha] - 2026-11-25

**GTA-VI-OS 0.01 Alpha — Build #16**

First public alpha release featuring a full-width Applications Launcher, 29 live inline Settings pages, de-gimmicked native Vice OS tools, Debian Backports Linux 6.12 LTS kernel & firmware support, native upstream hardware auto-mount/auto-play, and a `xorriso`-based >2 GB ISO CI validator.

### Added

- **Debian Backports Linux 6.12 LTS Kernel & Unattended Security Updates**:
  - Enabled `bookworm-backports` in `config/apt/sources.list`.
  - Added codename-pinned APT preferences (`config/apt/preferences.d/90-vice-backports-kernel`, `Pin: release n=bookworm-backports`, `Pin-Priority: 550`) for `linux-image-*`, `linux-headers-*`, `firmware-*`, `intel-microcode`, and `amd64-microcode` while preserving core Debian 12 Bookworm stability.
  - Added `unattended-upgrades` configuration (`config/apt/apt.conf.d/20auto-upgrades` and `50unattended-upgrades`) installed alongside APT preferences in `chroot_scripts/00_base_config.sh` and `17_apt_config_setup.sh`.
- **100% Native Upstream Hardware Auto-Mount & Media Auto-Play**:
  - Added 9 verified packages to `config/packages.list` (`thunar-volman`, `gvfs-fuse`, `gvfs-daemons`, `mtp-tools`, `usbmuxd`, `fwupd`, `unattended-upgrades`, `dkms`, `udisks2-btrfs` — `552` total packages, `0` duplicates).
  - Enabled `[volume]` auto-mount/autorun defaults in `config/libfm/libfm.conf` (`mount_on_startup=1`, `mount_removable=1`, `autorun=1`).
  - Added `config/skel/.config/xfce4/xfconf/xfce-perchannel-xml/thunar-volman.xml` (copied via `chroot_scripts/22_skel_setup.sh`) for native USB/media auto-mount, auto-browse, and audio/video CD auto-play (`/usr/bin/mpv`).
  - Added passwordless local console `udisks2` auto-mount polkit rules (`config/polkit-1/rules.d/50-vice-udisks-automount.rules`) wired in `chroot_scripts/07_polkit_setup.sh`.
- **29 Real Inline Settings Center Pages (`desktop/vice_settings_pages.py`)**:
  - Replaced all `AppLauncherPage` open-me stub cards in `desktop/vice_settings.py` with live inline Linux control panels across all 29 `PAGE_NAMES` (`Display`, `Sound` with `0–100%` PipeWire/WirePlumber cap, `Network`/`VPN`, `Bluetooth`, `Firewall`, `Date & Time`, `Storage`/`USB` auto-mount toggles, `Updates`/`Kernel` backports status, `Power`, `Users`, `Printers`, `Theme`, `Wallpaper`, `Diagnostics`, `Drivers`, `About`, etc.) using non-blocking background `QThread` loading and clean shutdown.
- **Beginner Indonesian Documentation (`README.md`)**:
  - Rewrote `README.md` for first-time users covering split-ISO (`~2.56 GB`, `.part1` + `.part2`) merge instructions (`GABUNG-ISO-WINDOWS.bat`, `copy /b`, and `gabung-iso-linux.sh`), VirtualBox/VMware/USB flashdrive guides, default `vice`/`vice` login tour, feature overview, and beginner FAQ.

### Changed

- **Full-Width Applications Launcher Overhaul (`desktop/vice_launcher.py`)**:
  - Replaced crushed `AppButton(QPushButton)` tiles with full-width horizontal `AppCard(QFrame)` cards (`[40x40 Icon] [Title + Category] [Favorite]`) inside a uniform-stretch responsive `QGridLayout` (`1040x640`), live category counts, debounced search, and incremental `QTimer` batch rendering.
- **De-Gimmicked Native Tools & Launcher (`desktop/vice_tool_*.py`, `system_scripts/vice-run-tool.sh`)**:
  - Upgraded `desktop/vice_tool_turbo.py` with real Linux telemetry and system tuning: per-core CPU load, live Disk R/W & Net RX/TX rates, ZRAM compression stats, CPU scaling governor switching, `picom` compositor pause/resume, `vm.drop_caches=3`/`vm.swappiness` tuning, and interactive process `renice`/kill controls.
  - Upgraded `desktop/vice_tool_radio.py` to 9 verified HTTPS SomaFM/Nightride streams plus local music folder M3U8 playlist playback, Prev/Next track controls, and custom stream URLs.
  - Added `/usr/local/sbin:/usr/sbin:/sbin` lookup fallbacks across `vice_tool_cyber_deck.py`, `vice_tool_net_shield.py`, `vice_tool_mac_cloak.py`, and `vice_tool_sys_deck.py` (plus `zramctl` readout), and synced `425 / 500` strings in `vice_tool_cheatsheets.py` and `vice_tool_missions.py`.
  - Updated `system_scripts/vice-run-tool.sh` with `sudo` auto-elevation for root-only CLI/TUI utilities and interactive argument prompting for `python3 -m <module>` commands.
- **Native Hardware Detection & Clean Systemd Units (`system_scripts/vice-hw-autodetect.sh`, `chroot_scripts/19_systemd_setup.sh`)**:
  - Streamlined hardware detection to rely on native `systemd-udevd`, `udisks2`, `NetworkManager`, and `rfkill` instead of custom PCI/USB modalias `modprobe` loops while keeping `80-vice-net-tune` and conditional VM guest unit masking (`fwupd-refresh` masked for offline/VM cleanliness).
- **Updated Test Suites (`tests/test_desktop.py`, `tests/test_tools_registry.py`, `tests/test_validation.sh`)**:
  - Updated test assertions for the full-width `AppCard` launcher, 29 inline settings pages, backports pinning, native auto-mount configs, tool registry fixes, and `xorriso` ISO validation (`86` Python unit tests + `8/8` shell suites passing).

### Fixed

- **>2 GB ISO CI Validator (`validation/validate_iso.sh`)**:
  - Replaced legacy `isoinfo` inspection/extraction (which failed on ISO #15's `2562.9 MB` image) with `xorriso` (`-osirrox on -extract` for `/vmlinuz`, `/initrd.img`, `/boot/grub/grub.cfg` and `-lsl /live/filesystem.squashfs` size check) and eliminated `grep -q` `SIGPIPE` hazards under `set -Eeuo pipefail`.
- **VS Code ("Blue UI/Icon") & LibreOffice Impress Visual Fixes**:
  - Recolored `kind == "vscode"` in `assets/generate_tool_icons.py` from default blue to Leonida Sunset & Aqua (`#FF5E7E` / `#FF9A62` / `#36D6C3`).
  - Updated `config/skel/.config/Code/User/settings.json` to disable the Copilot Welcome modal (`workbench.startupEditor: "none"`), hide the Copilot chat sidebar (`chat.disableAIFeatures: true`, `workbench.secondarySideBar.defaultVisibility: "hidden"`), and replace remaining blue accents with Leonida Sunset & Aqua.
  - Disabled LibreOffice Impress startup template selection dialog in `config/skel/.config/libreoffice/4/user/registrymodifications.xcu`.
- **425 / 500 Tool Registry Fixes (`config/tools_registry.json`, `docs/TOOLS_PROGRESS.md`)**:
  - Fixed broken `python3-flake8` command (`flake8` -> `python3 -m flake8` for Debian 12 packaging) and updated `node-typescript` (`tsc --version` -> `tsc`) so interactive help/argument prompting triggers cleanly.

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
  - Resilient unified runner with pipeline error handling.

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

- Validation framework.

### Changed

- Repository architecture.

### Fixed

- Various build improvements.
