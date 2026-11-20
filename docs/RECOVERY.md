# GTA VI OS (Vice OS) Recovery Guide

This document outlines the procedures, tools, and recovery utilities available for restoring a Vice OS installation in the event of system failure, misconfiguration, bootloader corruption, or forgotten credentials.

---

## 🚨 Prerequisites

To use the physical recovery tools:
1. A Vice OS Live USB/CD (the installation ISO works for all recovery tasks).
2. Physical or virtual console access to the target machine.
3. Root privileges (`sudo`).

---

## 💻 Accessing Recovery Tools

### 1. Unified Recovery Menu (`vice-recovery.sh`)
The recommended recovery environment is the unified interactive TUI recovery tool:
```bash
sudo ./recovery/vice-recovery.sh
```
This tool provides a centralized menu with flock-based single-instance locking:
- **1. Filesystem Check & Repair (`fsck`)**: Safely unmounts and scans all detected Linux partitions.
- **2. GRUB Bootloader Repair**: Reinstalls and reconfigures GRUB on EFI or BIOS systems.
- **3. Reset User Password**: Chroots into target root partition and resets user or root passwords.
- **4. Network Configuration Reset**: Flushes broken interfaces and restores DNS/NetworkManager defaults.
- **5. Repair Broken Packages**: Fixes interrupted dpkg locks and repairs unconfigured apt packages.
- **6. Run System Diagnostics**: Runs hardware, disk, memory, and service health checks.
- **7. Restore Boot Themes**: Reinstalls and configures cyberpunk GRUB and Plymouth themes.

### 2. GUI Recovery from the Live Desktop
- Boot the Live ISO into the desktop.
- Launch **Vice OS Settings** from the dock or right-click desktop menu.
- Navigate to the **Diagnostics & Recovery** section.
- Alternatively, launch `vice_diagnostics.py` or `vice-os-menu.sh` from the terminal.

---

## 🛠️ Standalone Recovery Utilities

All recovery scripts are located in `recovery/`:

### 1. Unified Recovery TUI (`recovery/vice-recovery.sh`)
- Central interactive rescue console for live and headless environments.
- Supports both interactive navigation and direct non-interactive CLI flags.

### 2. GRUB Bootloader Repair (`recovery/rebuild_grub.sh`)
Reinstalls and reconfigures GRUB if the bootloader is overwritten (e.g. by Windows updates) or corrupted:
```bash
# Usage: sudo ./recovery/rebuild_grub.sh /dev/sdXN [/dev/sdXY]
sudo ./recovery/rebuild_grub.sh /dev/sda2 /dev/sda1
```
- Automatically detects BIOS vs UEFI systems.
- Mounts pseudo-filesystems (`/dev`, `/proc`, `/sys`, `/sys/firmware/efi/efivars`).
- Reinstalls GRUB to disk and regenerates `/boot/grub/grub.cfg`.

### 3. Password Reset (`recovery/reset_password.sh`)
Resets forgotten user or root passwords:
```bash
# Usage: sudo ./recovery/reset_password.sh /dev/sdXN username
sudo ./recovery/reset_password.sh /dev/sda2 vice
```
- Mounts the root partition in a temporary namespace.
- Chroots into the system to invoke `passwd <username>`.

### 4. Network Configuration Reset (`recovery/reset_network.sh`)
Restores factory network settings when DNS, Wi-Fi, or NetworkManager fail:
```bash
sudo ./recovery/reset_network.sh
```
- Creates a timestamped backup in `/root/vice-os-network-backup-[timestamp]/`.
- Flushes network interfaces and resets routing tables.
- Restores default `/etc/resolv.conf` (Cloudflare / Google DNS).
- Clears conflicting NetworkManager connection profiles.

### 5. Boot Theming Tools (`vice_grub_theme.sh` & `vice_plymouth_theme.sh`)
- `recovery/vice_grub_theme.sh`: Installs the cyberpunk neon Vice OS GRUB theme.
- `recovery/vice_plymouth_theme.sh`: Configures Plymouth animated splash themes for boot and shutdown.

### 6. Desktop Crash Recovery (`desktop/session_watchdog.py`)
- Automatically monitors `vice_shell.py`.
- If the shell crashes or terminates unexpectedly, the watchdog restarts it with exponential backoff.
- Maximum 10 retries before safe degradation.

---

## 💡 Emergency Troubleshooting

### Switching to a Virtual Terminal (TTY)
If the graphical desktop freezes:
1. Press `Ctrl + Alt + F3` (or `F4`, `F5`, `F6`).
2. Log in with user `vice` or `root`.
3. Restart the session or run recovery utilities:
   ```bash
   sudo systemctl restart lightdm || sudo pkill -u vice
   ```

### Emergency Logs Inspection
```bash
# Review system errors from current boot
sudo journalctl -b -p err

# Review desktop session errors
cat ~/.xsession-errors
```
