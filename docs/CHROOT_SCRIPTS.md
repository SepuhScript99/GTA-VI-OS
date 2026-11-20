# Chroot Scripts Reference

The chroot_scripts/ directory contains 49 numbered scripts executed in alphabetical order
inside the target chroot during the ISO build. Each script configures a specific subsystem.

Scripts 00–46 handle configuration. Scripts 90 and 99 handle optimization and cleanup.

```
00  →  Base Configuration (hostname, hosts, fstab, GRUB defaults, apt sources)
01  →  Package Installation (installs all packages from config/packages.list)
02  →  System Tuning (sysctl, dphys-swapfile, NetworkManager, firewall)
03  →  User & Desktop Setup (vice user, sudoers, desktop files, auto-login)
04  →  Desktop Autostart (compositor, wallpaper, shell, welcome wizard)
05  →  Network & Audio Fix
07  →  Polkit Setup (authentication rules)
08  →  Udev Setup (device rules)
09  →  System Scripts Installation (copies scripts to /usr/local/)
10  →  PAM Setup (authentication modules)
11  →  Thunar Setup (file manager configuration)
12  →  GTK Setup (theme and appearance)
13  →  Xresources Setup (terminal colors)
14  →  Issue Setup (login banner)
15  →  OS Release Setup (/etc/os-release)
16  →  LSB Release Setup (/etc/lsb-release)
17  →  APT Config Setup (no-recommends policy)
18  →  PipeWire Setup (audio server)
19  →  Systemd Unit Setup (ZRAM, auto-update, firewall services)
20  →  Modprobe Setup (kernel module blacklist)
21  →  Xorg Setup (display server configuration)
22  →  Skeleton Setup (user skel directory)
23  →  Dpkg Setup (package manager configuration)
24  →  Nsswitch Setup (name service switch)
25  →  Chrony Setup (NTP time synchronization)
26  →  Hwclock Setup (hardware clock)
27  →  RcS Setup (boot script defaults)
28  →  Devfs Setup (device filesystem)
29  →  Bluetooth Setup
30  →  NTP Setup (alternative NTP)
31  →  UFW Setup (firewall rules)
32  →  NTPDate Setup (legacy NTP)
33  →  Cron Setup (scheduled tasks)
34  →  Rsyslog Setup (system logging)
35  →  Avahi Setup (mDNS/Zeroconf)
36  →  Saned Setup (scanner support)
37  →  Acpid Setup (ACPI events)
38  →  Networking Setup (interfaces)
39  →  Irqbalance Setup (interrupt balancing)
40  →  NFS Setup (network filesystem)
41  →  Rpcbind Setup (RPC services)
42  →  SSH Setup (secure shell)
43  →  Console Setup (console font)
44  →  Smartmontools Setup (disk monitoring)
45  →  Login Setup (login configuration)
46  →  User Setup Script (user defaults)
47  →  Raspberry Pi & ARM64 Setup (firmware, U-Boot scripts, hardware modules)
90  →  Build Optimization (docs, locale, cache, modules, services, sysctl)
99  →  Cleanup (apt cache, logs, machine-id, payload removal)
```

## Adding a New Script

1. Create a new file named `NN_description.sh` where NN is the insertion position
2. Source common.sh from `/vice_payload/lib/common.sh`
3. Wrap logic in a `main()` function
4. Call `main "$@"` at the end
5. Scripts run in strict alphabetical order

## Execution Context

- All scripts run inside the chroot via `chroot "$CHROOTDIR" /bin/bash`
- The payload directory `/vice_payload/` contains the project source files
- `lib/common.sh` provides logging and validation functions
- State tracking via `lib/state_manager.sh` enables resumability
