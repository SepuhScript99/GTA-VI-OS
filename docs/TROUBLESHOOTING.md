Troubleshooting Guide - GTA VI OS (Vice OS)
This guide covers common issues and their solutions. If you are facing a system-breaking issue, please consult the Recovery Guide first.

🖥️ Boot & Display Issues
Black Screen on Boot
If the system boots to a black screen after the GRUB menu:

Use Safe Graphics: Reboot, navigate to the GRUB menu, and select "GTA VI OS (Vice OS) [Safe Graphics (Nomodeset)]". This disables hardware acceleration, which helps with incompatible GPUs or VM setups.
Check Xorg Logs: Switch to a TTY (Ctrl + Alt + F3), log in, and check /var/log/Xorg.0.log for errors (EE).
Restart Compositor: Sometimes picom fails to start. Run killall picom && picom -b --config /etc/xdg/compton.conf in a terminal.
GRUB Rescue Prompt
If you are dropped into a grub rescue> prompt:

The GRUB bootloader is corrupted or missing. Please follow the GRUB Recovery procedure using the Live ISO.
🌐 Network Issues
No Internet Connection
Check Interface: Run ip a to see if your network interface is recognized and has an IP address.
Restart NetworkManager: Run sudo systemctl restart NetworkManager.
Reset Network Config: If the network is completely broken, run the Network Reset tool:
sudo /usr/local/bin/reset_network.sh
Slow DNS Resolution
If websites take a long time to load but ping works:

Ensure systemd-resolved is not running (it conflicts with NetworkManager in Vice OS):
sudo systemctl disable --now systemd-resolvedsudo rm -f /etc/resolv.confsudo systemctl restart NetworkManager
🔊 Audio Issues
No Sound
Check Volume: Use the media keys or run pavucontrol to ensure the volume isn't muted and the correct output device is selected.
Restart Audio Daemon:
systemctl --user restart pipewire pipewire-pulse wireplumber
Check Kernel Modules: Ensure the sound module is loaded: lsmod | grep snd.
Audio Crackling
Ensure you are using the PipeWire backend (not legacy PulseAudio). Check /etc/pipewire/pipewire.conf for the realtime module (libpipewire-module-rt).
📦 Package Management (APT)
"Could not get lock /var/lib/dpkg/lock-frontend"
Another package manager is running or was interrupted.

Wait a minute to see if it finishes.
If it persists, kill the process or run the repair tool:
sudo /usr/local/bin/repair_packages.sh
Broken Dependencies
If apt complains about unmet dependencies or broken packages:

sudo apt-get install -fsudo dpkg --configure -a
Or use the built-in repair tool:
sudo /usr/local/bin/repair_packages.sh

🐍 Desktop Shell (Python) Issues
TopBar or Dock Missing
If the custom UI shell crashes or doesn't appear:

Try restarting it manually: python3 /opt/vice-os/vice_shell.py &

Check for errors in the terminal output or ~/.xsession-errors.
High CPU Usage from vice_shell.py
The CPU metrics parser might be polling too fast. Ensure the timer in vice_shell.py is set to 1000 ms (1 second).
If the issue persists, kill the process and restart it.