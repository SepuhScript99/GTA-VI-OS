Developer Guide - GTA VI OS (Vice OS)
This guide provides technical details for developers looking to modify, debug, or extend Vice OS.

🛠️ Development Environment Setup
To build and test Vice OS, you need a Debian or Ubuntu host machine with at least 10GB of free space.

Clone the repository:
git clone https://github.com/your-repo/gta-vi-os.gitcd gta-vi-os
Install Host Dependencies:
The build scripts will attempt to install these automatically, but it's good practice to have them:
sudo apt-get install debootstrap grub2-common grub-efi-amd64-bin grub-pc-bin mtools xorriso squashfs-tools curl qemu-system-x86

🚀 Build & Test Workflow
The project uses a strictly modular build pipeline.

1.Clean Build: Always start with a clean build to ensure reproducibility.
sudo bash build_iso.sh --clean

Note: The build process generates a build.log file in the root directory. If a phase fails, check this log first.

2.Validate the ISO: Before booting, ensure the ISO is structurally sound.
bash tests/validate_iso.sh out/gta-vi-os-amd64.iso

3.Smoke Test (QEMU): Boot the ISO headlessly to verify it reaches a login prompt.
bash tests/smoke_test_qemu.sh out/gta-vi-os-amd64.iso

4.Manual Testing (VMware/VirtualBox): Boot the ISO in a GUI VM to test desktop features, aesthetics, and the physical installer (vp-installer.sh).
🎨 Modifying the Desktop Environment
The custom desktop shell is written in Python (PyQt5).

File Locations
Source Code: desktop/vice_shell.py, desktop/login.py
Styling: desktop/style.qss
Shared Logic: lib/python/vice_utils.py
Rapid UI Testing
Rebuilding the entire ISO just to test a UI tweak is slow. To test UI changes locally on a running Vice OS VM:

1.Edit the Python/QSS files on your host.
2.Copy them to the VM (e.g., using scp or shared folders).
3.Replace the files in /opt/vice-os/ inside the VM:
sudo cp vice_shell.py /opt/vice-os/
sudo cp style.qss /opt/vice-os/

4.Restart the shell by killing the process (it auto-restarts via XDG autostart, or you can run it manually):
killall vice_shell.py
python3 /opt/vice-os/vice_shell.py &

📦 Adding Software Packages
Software installation is handled declaratively.

1.Open config/packages.list.
2.Add the package name on a new line. Group it under the appropriate category comment.
3.The chroot_scripts/01_install_packages.sh script parses this file during the build. Do not add apt-get install commands directly in the chroot scripts unless there is a strict ordering dependency.

🐛 Debugging Common Issues
Build fails during debootstrap: Check your internet connection. The script falls back to a US mirror, but if both fail, the build halts.
Black screen on boot: The compositor (picom) or X11 might have failed. Switch to a TTY (Ctrl+Alt+F3), log in, and check ~/.xsession-errors and /var/log/syslog.
No Audio/Network in Live ISO: Ensure desktop/dbus_session.sh is executable and 05_network_audio_fix.sh ran correctly during the build. DBus and Pipewire must start before Openbox.
vice_shell.py crashes on boot: Ensure /opt/vice-os/lib/python/vice_utils.py exists and is readable. The shell heavily relies on this shared module.