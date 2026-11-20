# System Utilities Reference

The system_utils/ directory contains 47 standalone utility scripts for system management.
Each script follows a consistent pattern: shared-library preamble (WORKDIR resolution, sourcing `lib/common.sh`, `install_cleanup`), dependency checks, and `main()`.

## Audio & Sound

| Script | Purpose |
|--------|---------|
| audio_manager.sh | Volume control, mute toggling, audio device management |
| sound_manager.sh | Audio server status (PipeWire/PulseAudio), server restart |

## Display & Graphics

| Script | Purpose |
|--------|---------|
| display_config.sh | DPI scaling, display profiles, Xorg configuration generation |
| display_manager.sh | Runtime resolution, rotation, refresh rate via xrandr |

## Hardware & Power

| Script | Purpose |
|--------|---------|
| battery_manager.sh | Battery diagnostics, health reporting, charging thresholds |
| power_manager.sh | Suspend, hibernate, power profile management |
| thermal_manager.sh | Temperature monitoring, fan control, thermal throttling |

## Input & Peripherals

| Script | Purpose |
|--------|---------|
| input_manager.sh | Keyboard layout, mouse acceleration, touchpad settings |
| keyboard.sh | (integrated into input_manager.sh) |

## Network

| Script | Purpose |
|--------|---------|
| network_manager.sh | Wi-Fi scanning, connection management, IP reporting |
| network_diagnostics.sh | Connectivity tests, bandwidth measurement, DNS checks |
| bluetooth_manager.sh | Bluetooth device pairing, discovery, trust management |

## Packages & Updates

| Script | Purpose |
|--------|---------|
| package_manager.sh | Install, remove, purge packages; full system updates |
| update_manager.sh | Update package lists, upgrade, dist-upgrade, security updates |

## System Management

| Script | Purpose |
|--------|---------|
| system_info.sh | Comprehensive system information (CPU, memory, disk, network) |
| system_monitor.sh | Real-time dashboard (CPU, memory, disk, network, temperature) |
| system_health.sh | System health evaluation against thresholds |
| system_audit.sh | Security and configuration audit |
| system_cleaner.sh | Temporary file cleanup, orphan removal |
| system_maintenance.sh | Health checks, integrity verification, audits |

## Security

| Script | Purpose |
|--------|---------|
| security_manager.sh | Firewall rules, service lockdown, audit controls |
| security_hardener.sh | SSH hardening, kernel parameters, service minimization |

## Users & Sessions

| Script | Purpose |
|--------|---------|
| user_manager.sh | User creation, deletion, group management, shell changes |
| hostname_manager.sh | System hostname management |
| locale_manager.sh | Locale and language settings |

## Storage

| Script | Purpose |
|--------|---------|
| disk_manager.sh | Disk listing, formatting, mounting, SMART health |
| usb_manager.sh | USB device management, safe removal |
| backup_manager.sh | System backup and restore |
| archive_manager.sh | Archive creation and extraction |
| file_manager.sh | File operations (copy, move, permissions) |

## Services & Processes

| Script | Purpose |
|--------|---------|
| service_manager.sh | Systemd service enable, disable, start, stop, status |
| process_manager.sh | Process listing, priority, kill management |
| cron_manager.sh | Cron job management |
| log_manager.sh | Log rotation, journal management |
| log_analyzer.sh | Error frequency tracking, security event extraction |

## Desktop & UI

| Script | Purpose |
|--------|---------|
| theme_manager.sh | GTK/Qt theme switching |
| wallpaper_manager.sh | Wallpaper setting via nitrogen/feh |
| font_manager.sh | Font installation and management |
| panel_manager.sh | Panel/taskbar configuration |
| dock_manager.sh | Application dock management |
| shortcut_manager.sh | Desktop shortcut creation |
| notification_manager.sh | Desktop notification sending |
| screenshot_manager.sh | Screenshot capture |
| clipboard_manager.sh | Clipboard management |

## System Configuration

| Script | Purpose |
|--------|---------|
| config_backup.sh | Configuration file backup and restore |
| dependency_checker.sh | System dependency verification |
| kernel_manager.sh | Kernel module loading and parameters |
| performance_tuner.sh | CPU governor, I/O scheduler, kernel tuning |

## Usage

All scripts are installed to /usr/local/bin/ and can be run directly:
```bash
sudo audio_manager.sh status
network_manager.sh wifi-list
display_manager.sh --help
```

Each script supports `--help` for usage information.
