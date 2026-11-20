# GTA VI OS (Vice OS) Installation Guide

This guide covers installing Vice OS onto physical hardware or virtual machine primary disks.

---

## 📋 Prerequisites

1. A Vice OS Live USB/CD (created from `out/gta-vi-os-amd64.iso`).
2. A target drive with at least 15GB of free space (20GB+ recommended).
3. A backup of any important data on the target drive (installation overwrites the selected disk).

---

## 🚀 Booting the Live ISO

1. Insert the Vice OS Live USB into the target computer.
2. Power on the machine and access the BIOS/UEFI boot menu (press `F12`, `F10`, `F2`, or `Del`).
3. Select the USB device to boot.
4. From the GRUB boot menu, select **GTA VI OS (Vice OS) [Live]**.
5. The system boots into the Live desktop environment and automatically logs in as user `vice`.

---

## 💿 Running the Installer (`vp-installer.sh`)

### Graphical Launcher
From the desktop, click the **Install to Disk** desktop shortcut, or right-click the desktop and choose **Vice OS Settings -> Install Vice OS to Disk**.

### Terminal Command
Open a terminal and execute:
```bash
sudo /usr/local/bin/vp-installer.sh
```

### Installation Steps & Features:
1. **Safety Checks**:
   - The installer verifies the target disk is not the active live boot medium to prevent accidental self-overwrite.
   - Automatically deactivates swap and safely unmounts existing partitions on the target drive.
2. **Partitioning**:
   - Detects UEFI vs BIOS firmware.
   - For UEFI systems: creates an EFI System Partition (`ESP`, FAT32).
   - For BIOS systems: creates a `bios_boot` partition.
   - Creates root partition (or separate `/boot` and LUKS container).
3. **LUKS2 Disk Encryption (Optional)**:
   - When encryption is selected, the installer creates a dedicated unencrypted `/boot` partition (1024MB ext4) alongside the encrypted root container.
   - Configures `/etc/crypttab` with `luks,discard` parameters and Argon2id-compatible GRUB configurations.
4. **Filesystem Copying**:
   - Copies the live SquashFS rootfs to the target partitions with progress reporting.
5. **Bootloader Installation**:
   - Chroots into the target environment, configures GRUB for BIOS or UEFI, and generates initramfs.

---

## 🔑 Post-Installation Setup & Accounts

During finalization, the installer configures system accounts:
- **User Account**: Set a custom username and password (piped securely via `chpasswd`).
- **Sudo Privileges**: Sudoers configuration is validated using `visudo -c` before writing.
- **Root Account**: Choose between locking root (recommended; use `sudo`) or setting a root password.
- **Auto-login**: Optionally enable graphical auto-login for the primary user.
- **Host Identity**: Machine-ID and SSH host keys are regenerated fresh for the new system.

---

## 🧙 First-Boot Welcome Wizard

Upon first boot into the installed system:
1. The **Vice OS Welcome Wizard** (`welcome_wizard.py`) launches automatically.
2. The 9-page wizard guides you through:
   - Timezone and locale selection
   - Keyboard layout configuration
   - Wi-Fi network setup
   - Theme and accent color selection (8 Neon themes)
   - Optional developer packages (Flatpak, Docker, VS Code)
3. Once completed, a flag file (`~/.config/vice-os/wizard.done`) prevents the wizard from displaying on subsequent boots.
