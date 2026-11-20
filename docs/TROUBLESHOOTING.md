# Troubleshooting Guide - GTA VI OS (Vice OS)

This guide covers common issues and resolutions. If facing critical system failures, consult the [Recovery Guide](RECOVERY.md) first.

---

## 🖥️ Boot & Display Issues

### Black Screen on Boot
If the system boots to a black screen after the GRUB menu:
1. **Safe Graphics Mode**: Reboot, enter the GRUB menu, and select **GTA VI OS (Vice OS) [Safe Graphics (Nomodeset)]**. This disables hardware acceleration, resolving driver conflicts.
2. **Switch to Virtual Terminal (TTY)**: Press `Ctrl + Alt + F3`, log in, and check `/var/log/Xorg.0.log` for errors marked `(EE)`.
3. **Restart Display Session**:
   - For X11 / Openbox:
     ```bash
     killall compton 2>/dev/null || true
     compton -b --config /etc/xdg/compton.conf
     ```
   - For Wayland / Labwc:
     ```bash
     killall labwc 2>/dev/null || true
     WAYLAND_DISPLAY=wayland-0 labwc &
     ```

### GRUB Rescue Prompt (`grub rescue>`)
The GRUB bootloader or boot partition configuration is damaged.
Boot the Vice OS Live USB and run the GRUB repair tool:
```bash
sudo /usr/local/bin/rebuild_grub.sh /dev/sdXN
```
Or launch the unified recovery menu: `sudo ./recovery/vice-recovery.sh`.

---

## 🌐 Network Issues

### No Internet Connection
1. **Verify Interface**:
   ```bash
   ip a
   ```
2. **Restart NetworkManager**:
   ```bash
   sudo systemctl restart NetworkManager
   ```
3. **Network Configuration Reset**:
   Run the dedicated reset script:
   ```bash
   sudo /usr/local/bin/reset_network.sh
   ```

### Slow DNS Resolution
If websites load slowly but pinging IP addresses works:
Ensure `systemd-resolved` does not conflict with NetworkManager:
```bash
sudo systemctl disable --now systemd-resolved
sudo rm -f /etc/resolv.conf
sudo systemctl restart NetworkManager
```

---

## 🔊 Audio Issues

### No Sound Output
1. Check volume levels in the system tray or run `pavucontrol` to verify the default sink.
2. Restart the PipeWire audio stack:
   ```bash
   systemctl --user restart pipewire pipewire-pulse wireplumber
   ```
3. Verify kernel audio modules:
   ```bash
   lsmod | grep snd
   ```

---

## 📦 Package Management & APT Locks

### "Could not get lock /var/lib/dpkg/lock-frontend"
Another package process was interrupted or is holding the lock:
```bash
sudo /usr/local/bin/repair_packages.sh
```

### Unmet Dependencies or Broken Packages
Run dpkg repair:
```bash
sudo dpkg --configure -a
sudo apt-get install -f
```

---

## 🐍 Desktop Shell Issues

### TopBar or Dock Missing
If the custom PyQt5 shell crashed:
1. Restart the shell manually:
   ```bash
   python3 /opt/vice-os/vice_shell.py &
   ```
2. Check for error tracebacks:
   ```bash
   cat ~/.xsession-errors
   ```
3. The background watchdog (`desktop/session_watchdog.py`) monitors and restarts the shell automatically up to 10 consecutive crashes.
