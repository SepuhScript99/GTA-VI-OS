# Developer Guide - GTA VI OS (Vice OS)

This guide provides technical details for developers modifying, debugging, or extending Vice OS.

---

## 🛠️ Development Environment Setup

To build and test Vice OS, you need a Debian (Bookworm) or Ubuntu host machine with at least 15GB of free disk space.

### 1. Clone the Repository
```bash
git clone https://github.com/your-repo/gta-vi-os.git
cd gta-vi-os
```

### 2. Install Host Dependencies
The build pipeline checks and installs dependencies when run with root privileges, but you can pre-install them manually:
```bash
sudo apt-get update
sudo apt-get install -y \
    debootstrap \
    grub2-common \
    grub-efi-amd64-bin \
    grub-pc-bin \
    mtools \
    xorriso \
    squashfs-tools \
    curl \
    qemu-system-x86 \
    python3-pyqt5 \
    flake8 \
    shellcheck
```

---

## 🚀 Build & Test Workflow

Vice OS uses a modular, state-managed build pipeline.

### 1. Clean Build
Always start with a clean build when validating pipeline changes:
```bash
sudo bash build_iso.sh --clean
```
The build process generates `build.log`. If any phase fails, check `build.log` first.

### 2. Validation Suite
Run the full artifact validation suite:
```bash
bash validation/run_all.sh
```
This automatically executes:
- Package list syntax and dependency validation (`validate_packages.sh`)
- Chroot rootfs directory and file integrity (`validate_rootfs.sh`)
- Kernel image, modules, and config verification (`validate_kernel.sh`)
- Initramfs live-boot format and script checks (`validate_initramfs.sh`)
- Final ISO structural integrity and SquashFS decompression checks (`validate_iso.sh`)

### 3. Automated Test Suites
Run local test suites before committing changes:
```bash
# Python unit tests (28 tests)
python3 -m unittest discover -s tests -p "test_*.py"

# Integration tests (20 tests)
bash tests/test_validation.sh

# Bash library tests (11 tests)
bash tests/test_common_sh.sh

# System utilities tests (49+ tests)
bash tests/test_system_utils.sh
bash tests/test_system_utils_runtime.sh

# Apps & installer tests (21 tests)
bash tests/test_apps.sh
```

### 4. Headless Smoke Test (QEMU)
Verify the ISO boots headlessly to a functional login prompt:
```bash
bash tests/smoke_test_qemu.sh out/gta-vi-os-amd64.iso
```

---

## 🎨 Desktop Development (PyQt5)

The desktop shell and applications are written in Python 3 using PyQt5 and styled with Qt Style Sheets (`style.qss`).

### File Locations
- Core Shell: `desktop/vice_shell.py`, `desktop/login.py`
- Panel & Tray: `desktop/panel_config.py`, `desktop/systray_manager.py`
- Sessions: `desktop/dbus_session.sh` (X11/Openbox), `desktop/wayland_session.sh` (Wayland/Labwc)
- Application Suite: `desktop/vice_*.py`
- Styling: `desktop/style.qss`
- Shared Python Library: `lib/python/vice_utils.py`

### Rapid UI Testing in a VM
To test UI changes without rebuilding the ISO:
1. Copy modified `.py` or `.qss` files to `/opt/vice-os/` inside the running VM:
   ```bash
   sudo cp desktop/vice_shell.py /opt/vice-os/
   sudo cp desktop/style.qss /opt/vice-os/
   ```
2. Restart the shell:
   ```bash
   killall vice_shell.py
   python3 /opt/vice-os/vice_shell.py &
   ```

---

## 📦 Adding Software Packages

Software packages are managed declaratively:
1. Open `config/packages.list` (or `config/packages.arm64.list` for ARM64).
2. Add package names under the appropriate category comment.
3. Validate changes with `bash validation/validate_packages.sh`.
4. The `chroot_scripts/01_install_packages.sh` script parses this file during the ISO build.
