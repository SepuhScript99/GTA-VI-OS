GTA VI OS (Vice OS) Installation Guide
This guide covers how to install Vice OS onto physical hardware or a virtual machine's primary disk.

📋 Prerequisites
A Vice OS Live USB/CD (created from gta-vi-os-amd64.iso).
A target hard drive with at least 20GB of free space.
A backup of any important data on the target drive (the installation will erase it).
🚀 Booting the Live ISO
Insert the Vice OS Live USB/CD into the computer.
Power on the computer and enter the BIOS/UEFI boot menu (usually by pressing F12, F10, F2, or Del).
Select the USB/CD drive to boot from.
You will see the GRUB menu. Select "GTA VI OS (Vice OS) [Live]" and press Enter.
The system will boot into the Live desktop environment and automatically log in as the vice user.
💿 Running the Installer
Once on the Live desktop, right-click the background to open the Openbox menu.
Navigate to Vice OS Settings and click it. A terminal window will open with the Settings Menu.(Alternatively, open a terminal manually and run sudo /usr/local/bin/vice-os-menu.sh).
Select option 1. Install Vice OS to Disk.
The installer script will prompt you for the target disk (e.g., sda or nvme0n1).WARNING: All data on the selected disk will be destroyed.
You will be asked to type the disk name again to confirm the destructive action.
The installer will automatically partition the disk (creating a BIOS boot partition or UEFI ESP, and a root partition), format them, and copy the Live filesystem to the disk.
Once the file copy is complete, it will install the GRUB bootloader and regenerate the initramfs for the physical hardware.
🔑 Post-Installation Setup
After the GRUB installation completes, the script will prompt you to set up passwords:

Vice User Password: You will be asked to enter a new password for the vice user. If you leave it blank, it will remain vice (not recommended for physical installs).
Root Password: You will be asked to enter a new root password. If you leave it blank, the root account will be locked (recommended; use sudo instead).
Once completed, you will see a success message. Reboot the system and remove the Live USB/CD.
🛠️ Installing Developer Tools
Once booted into your newly installed Vice OS, you can install developer tools using the same Settings Menu:

Right-click desktop -> Vice OS Settings.
Select 2. Install Visual Studio Code or 3. Install Docker Engine.
Follow the on-screen prompts. The scripts will automatically add the necessary repositories and install the software securely.
