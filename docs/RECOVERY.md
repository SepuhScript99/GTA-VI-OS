GTA VI OS (Vice OS) Recovery Guide
This document outlines the procedures and utilities available for recovering a Vice OS installation in the event of a system failure, misconfiguration, or lost password.

🚨 Prerequisites
To use the physical recovery tools, you will need:

A Vice OS Live USB/CD (the installation ISO works for this).
Physical or virtual console access to the machine.
Root privileges (sudo).
💻 Accessing Recovery Tools (GUI Menu)
The easiest way to access all recovery tools is through the Vice OS Settings Menu.

Boot the Live ISO.
Right-click the desktop and select Vice OS Settings.
Choose the desired recovery option (e.g., "Reset User Password", "Reinstall GRUB Bootloader").
If you are in a terminal-only environment (e.g., via SSH or a TTY), you can launch the same menu by running:

sudo /usr/local/bin/vice-os-menu.sh
🛠️ Recovery Utilities
Vice OS includes several first-class recovery scripts. If you are booted into the Live ISO, these scripts are located in the extracted payload or can be run from the project repository.

1. Password Reset (recovery/reset_password.sh)
If you forget your vice or root password, you can reset it from the Live ISO.

Usage:
Boot the Live ISO, open a terminal, and run: 
sudo ./recovery/reset_password.sh /dev/sdXN username

/dev/sdXN: Your Linux root partition (e.g., /dev/sda2, /dev/nvme0n1p2). Use lsblk to find it.
username: The user whose password you want to reset (e.g., vice).
The script will mount the partition, chroot into your system, and prompt you to enter a new password.

2. GRUB Bootloader Repair (recovery/rebuild_grub.sh)
If your system fails to boot (e.g., "Operating System not found", "GRUB rescue>" prompt, or a botched Windows update overwrote the MBR), use this tool to reinstall and reconfigure GRUB.

Usage:
Boot the Live ISO, open a terminal, and run:
# Identify your root and (if UEFI) EFI partitions using 'lsblk' or 'sudo fdisk -l'
sudo ./recovery/rebuild_grub.sh /dev/sdXN [/dev/sdXY]

3. Network Configuration Reset (recovery/reset_network.sh)
If your network interfaces are misconfigured, DNS is broken, or NetworkManager is failing to connect, this tool resets all network configurations to factory defaults.

Usage: sudo ./recovery/reset_network.sh

What it does:

Backs up existing configs to /root/vice-os-network-backup-[timestamp]/.
Flushes all network interfaces.
Restores default interfaces and resolv.conf (Cloudflare/Google DNS).
Clears NetworkManager profiles and restarts the service.
4. Home Directory Backup (system_scripts/backup_home.sh)
While not strictly a recovery tool, running this before major system updates or risky configurations can save your data.

Usage: sudo ./system_scripts/backup_home.sh /mnt/usb

Creates a compressed tar.xz archive of /home/vice, excluding caches, and keeps the 3 most recent backups.

💡 General Troubleshooting
Switching to a TTY
If the graphical desktop environment freezes or crashes, switch to a virtual terminal:

Press Ctrl + Alt + F3 (or F4, F5, F6).
Log in with your username and password.
You can now run recovery scripts or restart the display manager.
Checking Logs
If a service fails to start, check the systemd journal:
sudo journalctl -u NetworkManager -e  # Check NetworkManager logs
sudo journalctl -b -p err             # Check all error logs from the current boot
