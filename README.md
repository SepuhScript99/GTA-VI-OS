# GTA VI OS (Vice OS)

A complete, lightweight, Linux-based operating system inspired by a modern crime-themed open world aesthetic.

Built on Debian Bookworm, optimized for VMware, VirtualBox, and real x86_64 hardware.

---

## Features

- **Performance:** <15s boot time, <1GB RAM usage, ZRAM enabled.
- **Aesthetic:** Custom PyQt5 Desktop Shell, Neon Miami theme, Blur & Transparency.
- **Compatibility:** VMware Tools, VirtualBox Guest Additions, auto-resolution.
- **Apps:** Firefox, MPV, Geany, custom terminal, file manager.

---

## Building the OS

1. Run:

```bash
sudo bash build_iso.sh
```

on a Debian/Ubuntu host.

2. The script generates:

```text
gta-vi-os-amd64.iso
```

---

## Installation

1. Boot the ISO in VMware or VirtualBox.
   - Recommended: **4GB RAM**
   - Recommended Disk: **30GB**

2. Login using:

```text
User: vice
Password: vice
```

3. Open Terminal and run:

```bash
sudo /apps/vp-installer.sh
```

to install the operating system to disk.

---

## Default Credentials

```text
Username : vice
Password : vice
```

---

## System Requirements

| Component | Minimum | Recommended |
|----------|----------|-------------|
| CPU | 2 Cores | 4+ Cores |
| RAM | 2 GB | 4 GB |
| Storage | 20 GB | 30 GB SSD |
| Graphics | Virtual GPU | 3D Acceleration Enabled |

---

## Virtual Machine Support

✔ VMware Workstation

✔ VMware Player

✔ Oracle VirtualBox

✔ UEFI Boot

✔ Dynamic Resolution

✔ Shared Clipboard

✔ Shared Folders

✔ Drag & Drop (where supported)

✔ Virtual GPU Acceleration

---

## Included Applications

- Firefox
- MPV Media Player
- Geany IDE
- File Manager
- Custom Terminal
- Settings
- Package Manager

---

## License

This project is an original fictional Linux distribution inspired by a modern neon crime-themed aesthetic.

No Rockstar Games assets, code, trademarks, or copyrighted materials are included.

---

Enjoy Vice OS!