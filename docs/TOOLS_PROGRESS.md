# Vice OS Tools Progress (`425 / 500`)

**Overall Progress:** **425 / 500 (85%)** — Batch 4A Complete
**Theme:** GTA VI Leonida Sunset (`config/tools_registry.json` & `desktop/vice_theme.py`)
**Target Suite:** Debian 12 (Bookworm `main`) + Official VS Code / .NET 8.0 / Node.js 22 LTS Repos + Native Vice OS Originals

```text
Progress: [#################...] 425 / 500 (85%)
Batch 1 : [####################] 100 / 100 (Complete)
Batch 2 : [####################] 150 / 150 (Complete)
Batch 3 : [####################] 125 / 125 (Complete)
Batch 4A: [####################]  50 /  50 (Complete)
```

---

## Category Breakdown (Batch 4A Cumulative)

| Category | Count | Native / Curated | Notes |
| --- | ---: | --- | --- |
| GTA VI Originals | 18 | 18 `vice-native` apps | Bespoke Leonida Sunset PyQt5 & CLI suite (`vice_tool_*.py`, `vicefetch.sh`, `vice-hw-autodetect.sh`) |
| Office | 11 | 11 Debian Bookworm tools | LibreOffice Writer/Calc/Impress/Draw/Math (GTK3 themed), qpdfview, Evince, Simple Scan, Poppler, Hunspell, qpdf |
| System | 39 | 39 Debian Bookworm tools | Monitors, HW/EDID/I2C/UEFI/backlight probes, Printers, Bluetooth, `rfkill`, `sysbench`, Timeshift, Chrony |
| Network | 72 | 72 Debian Bookworm tools | Wireshark, Nmap, ZMap, DNS/SNMP/LDAP recon, IPv6 discovery, packet crafters, `nghttp`, `iptraf-ng`/`dnstop`/`tcptrack`, SSH/Mosh |
| Security | 133 | 133 Debian Bookworm tools | OpenVPN, WireGuard, Tor/Nyx/ProxyChains, Web fuzzers, Crackers, Wi-Fi/BT, Forensics, Crypto, `mokutil`, `tpm2`, Tunneling |
| Developer | 82 | 82 Debian/Official tools | VS Code, C/C++ (`g++`/`clang`/`clangd`/`lld`), `.NET 8.0` C#, Rust, Node.js 22 + TypeScript, Go, Java 17, Python, PHP, Ruby, Lua, Build/Lint/RE |
| Files & Disk | 29 | 29 Debian Bookworm tools | GNOME Disks, Forensic imagers (`dc3dd`/`dcfldd`/`ewf`/`squashfs-tools`), `fio` IOPS bench, `nwipe`, NTFS/exFAT/FAT/Btrfs, LUKS, S.M.A.R.T. |
| Media | 23 | 23 Debian Bookworm tools | FFmpeg, mpv, Celluloid, PipeWire mixer, `v4l-utils`, Flameshot, Gcolor3, EasyTAG, `exiv2`, `zbar-tools`, EXIF tools |
| Productivity | 18 | 18 Debian Bookworm tools | Firefox ESR, Zim, CherryTree, SpeedCrunch, Qalculate!, Galculator, Calcurse, Taskwarrior, tldr, archivers |
| **Total** | **425** | **18 Native + 407 Debian/Official/Kali** | **All 425 receive custom 64x64 GTA VI icons** |

---

## Batch 4A Highlights (ISO #14 — Pre-Installed IDE, Multi-Language LTS Stack & Universal HW)

- **Pre-Installed Visual Studio Code (`code`)**: Installed from Microsoft's official apt repository (`packages.microsoft.com/repos/code`) in `chroot_scripts/01_install_packages.sh`, pre-styled with GTA VI Leonida Dark colors and `JetBrains Mono` (`config/skel/.config/Code/User/settings.json`), native title bar for smooth `picom` corners, and Desktop shortcut (`config/skel/Desktop/vscode.desktop`).
- **Multi-Language LTS & Stable Dev Stack**:
  - **C & C++**: `build-essential`, `g++`, `clang`, `clangd`, `lld`, `ninja-build`, `pkg-config` (alongside `gcc`, `cmake`, `make`, `gdb`, `valgrind`, `cppcheck`).
  - **C# / .NET 8.0 LTS**: Official Microsoft `dotnet-sdk-8.0` via `packages.microsoft.com/debian/12/prod` (graceful `mono-devel` fallback).
  - **JavaScript / TypeScript / Node.js 22 LTS**: Official NodeSource `nodejs` 22.x LTS (incl. `npm`/`npx`) + `node-typescript` (`tsc`, zero `npm` conflict).
  - **Python, Rust, Go, Java 17 LTS, PHP, Ruby & Lua**: `python3-pip`, `python3-venv`, `ipython3`, `rustc`, `cargo`, `rustfmt`, `golang-go`, `openjdk-17-jdk-headless`, `php-cli`, `ruby`, `lua5.4`, `fonts-jetbrains-mono`.
- **Universal Hardware Firmware, Multi-VM Support & Native HW Auto-Detect**:
  - `vice-tool-hw-autodetect` (`/usr/local/bin/vice-hw-autodetect --status`) for automatic hypervisor, NetworkManager NIC, Wi-Fi, and driver setup.
  - 18 verified hardware/firmware/VM packages in `config/packages.list` (`firmware-iwlwifi`, `firmware-realtek`, `firmware-atheros`, `firmware-brcm80211`, `firmware-sof-signed`, `firmware-intel-sound`, `firmware-amd-graphics`, `intel-microcode`, `amd64-microcode`, `wpasupplicant`, `wireless-regdb`, `modemmanager`, `usb-modeswitch`, `qemu-guest-agent`, `spice-vdagent`, `xserver-xorg-input-all`, `xserver-xorg-input-libinput`, `mesa-vulkan-drivers`).
- **29 Curated Lean Build, Lint, Benchmark & Hardware Diagnostics Tools**: `autoconf`, `automake`, `libtool`, `meson`, `ccache`, `bear`, `astyle`, `universal-ctags`, `shfmt`, `yamllint`, `codespell`, `python3-pytest`, `python3-flake8`, `black`, `pylint`, `pipx`, `dos2unix`, `colordiff`, `capstone-tool`, `i2c-tools`, `edid-decode`, `v4l-utils`, `brightnessctl`, `efibootmgr`, `mokutil`, `tpm2-tools`, `sysbench`, `fio`, `nghttp2-client`.

---

## Full Tool Catalog (`425 / 500`)

| # | ID | Name | Category | Package | Exec | Mode | GTA VI Icon |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | `vice-tool-hub` | Vice Tool Hub | GTA VI Originals | `vice-native` | `python3 /opt/vice-os/vice_tool_hub.py` | GUI | `vice-tool-hub` |
| 2 | `vice-tool-radio` | Leonida FM Radio | GTA VI Originals | `vice-native` | `python3 /opt/vice-os/vice_tool_radio.py` | GUI | `vice-tool-radio` |
| 3 | `vice-tool-net-radar` | Leonida Net Radar | GTA VI Originals | `vice-native` | `python3 /opt/vice-os/vice_tool_net_radar.py` | GUI | `vice-tool-net-radar` |
| 4 | `vice-tool-missions` | Vice Mission Board | GTA VI Originals | `vice-native` | `python3 /opt/vice-os/vice_tool_missions.py` | GUI | `vice-tool-missions` |
| 5 | `vice-tool-vault` | Vice Vault | GTA VI Originals | `vice-native` | `python3 /opt/vice-os/vice_tool_vault.py` | GUI | `vice-tool-vault` |
| 6 | `vice-tool-turbo` | Vice Turbo Mode | GTA VI Originals | `vice-native` | `python3 /opt/vice-os/vice_tool_turbo.py` | GUI | `vice-tool-turbo` |
| 7 | `vice-tool-media-studio` | Vice Media Studio | GTA VI Originals | `vice-native` | `python3 /opt/vice-os/vice_tool_media_studio.py` | GUI | `vice-tool-media-studio` |
| 8 | `vice-tool-qr-hash` | Vice QR & Dev Lab | GTA VI Originals | `vice-native` | `python3 /opt/vice-os/vice_tool_qr_hash.py` | GUI | `vice-tool-qr-hash` |
| 9 | `vice-tool-sys-deck` | Vice Hardware Deck | GTA VI Originals | `vice-native` | `python3 /opt/vice-os/vice_tool_sys_deck.py` | GUI | `vice-tool-sys-deck` |
| 10 | `vice-tool-cheatsheets` | Vice Command Deck | GTA VI Originals | `vice-native` | `python3 /opt/vice-os/vice_tool_cheatsheets.py` | GUI | `vice-tool-cheatsheets` |
| 11 | `htop` | htop Process Viewer | System | `htop` | `htop` | Terminal | `vice-tool-htop` |
| 12 | `btop` | btop++ Resource Monitor | System | `btop` | `btop` | Terminal | `vice-tool-btop` |
| 13 | `iotop-c` | iotop-c Disk I/O Monitor | System | `iotop-c` | `iotop-c` | Terminal | `vice-tool-iotop-c` |
| 14 | `sysstat` | Sysstat I/O & CPU Stats | System | `sysstat` | `iostat -xz 1` | Terminal | `vice-tool-sysstat` |
| 15 | `lsof` | lsof Open Files Inspector | System | `lsof` | `lsof` | Terminal | `vice-tool-lsof` |
| 16 | `lshw` | lshw Hardware Topology | System | `lshw` | `lshw -short` | Terminal | `vice-tool-lshw` |
| 17 | `dmidecode` | dmidecode SMBIOS Decoder | System | `dmidecode` | `dmidecode -t system` | Terminal | `vice-tool-dmidecode` |
| 18 | `pciutils` | lspci PCI Device Inspector | System | `pciutils` | `lspci -nn` | Terminal | `vice-tool-pciutils` |
| 19 | `usbutils` | lsusb USB Bus Inspector | System | `usbutils` | `lsusb` | Terminal | `vice-tool-usbutils` |
| 20 | `inxi` | inxi Full System Report | System | `inxi` | `inxi -Fxz` | Terminal | `vice-tool-inxi` |
| 21 | `neofetch` | Neofetch System Summary | System | `neofetch` | `neofetch` | Terminal | `vice-tool-neofetch` |
| 22 | `lm-sensors` | Hardware Sensors Monitor | System | `lm-sensors` | `sensors` | Terminal | `vice-tool-lm-sensors` |
| 23 | `powertop` | PowerTOP Power Analyzer | System | `powertop` | `powertop` | Terminal | `vice-tool-powertop` |
| 24 | `stacer` | Stacer System Optimizer | System | `stacer` | `stacer` | GUI | `vice-tool-stacer` |
| 25 | `bleachbit` | BleachBit System Cleaner | System | `bleachbit` | `bleachbit` | GUI | `vice-tool-bleachbit` |
| 26 | `xfce4-taskmanager` | Xfce Task Manager | System | `xfce4-taskmanager` | `xfce4-taskmanager` | GUI | `vice-tool-xfce4-taskmanager` |
| 27 | `curl` | cURL Transfer Client | Network | `curl` | `curl` | Terminal | `vice-tool-curl` |
| 28 | `wget` | GNU Wget Downloader | Network | `wget` | `wget` | Terminal | `vice-tool-wget` |
| 29 | `nmap` | Nmap Network Scanner | Network | `nmap` | `nmap` | Terminal | `vice-tool-nmap` |
| 30 | `tcpdump` | tcpdump Packet Capture | Network | `tcpdump` | `tcpdump` | Terminal | `vice-tool-tcpdump` |
| 31 | `tshark` | TShark Traffic Dissector | Network | `tshark` | `tshark` | Terminal | `vice-tool-tshark` |
| 32 | `mtr-tiny` | MTR Live Path Monitor | Network | `mtr-tiny` | `mtr` | Terminal | `vice-tool-mtr-tiny` |
| 33 | `whois` | WHOIS Domain Lookup | Network | `whois` | `whois` | Terminal | `vice-tool-whois` |
| 34 | `bind9-dnsutils` | DNS Lookup Suite (dig) | Network | `bind9-dnsutils` | `dig` | Terminal | `vice-tool-bind9-dnsutils` |
| 35 | `traceroute` | Traceroute Hop Inspector | Network | `traceroute` | `traceroute` | Terminal | `vice-tool-traceroute` |
| 36 | `netcat-openbsd` | OpenBSD Netcat (nc) | Network | `netcat-openbsd` | `nc` | Terminal | `vice-tool-netcat-openbsd` |
| 37 | `iperf3` | iPerf3 Bandwidth Benchmark | Network | `iperf3` | `iperf3` | Terminal | `vice-tool-iperf3` |
| 38 | `iftop` | iftop Connection Monitor | Network | `iftop` | `iftop` | Terminal | `vice-tool-iftop` |
| 39 | `nethogs` | NetHogs Process Bandwidth | Network | `nethogs` | `nethogs` | Terminal | `vice-tool-nethogs` |
| 40 | `iproute2` | IPRoute2 Address & Sockets | Network | `iproute2` | `ip -br addr` | Terminal | `vice-tool-iproute2` |
| 41 | `socat` | Socat Socket Relay | Network | `socat` | `socat` | Terminal | `vice-tool-socat` |
| 42 | `httpie` | HTTPie REST API Client | Network | `httpie` | `http` | Terminal | `vice-tool-httpie` |
| 43 | `openssl` | OpenSSL Crypto Toolkit | Security | `openssl` | `openssl` | Terminal | `vice-tool-openssl` |
| 44 | `gnupg` | GnuPG (gpg) Privacy Guard | Security | `gnupg` | `gpg` | Terminal | `vice-tool-gnupg` |
| 45 | `ufw` | UFW Uncomplicated Firewall | Security | `ufw` | `ufw status verbose` | Terminal | `vice-tool-ufw` |
| 46 | `lynis` | Lynis Security Auditor | Security | `lynis` | `lynis audit system` | Terminal | `vice-tool-lynis` |
| 47 | `chkrootkit` | chkrootkit Rootkit Scanner | Security | `chkrootkit` | `chkrootkit` | Terminal | `vice-tool-chkrootkit` |
| 48 | `rkhunter` | rkhunter Rootkit Hunter | Security | `rkhunter` | `rkhunter --versioncheck` | Terminal | `vice-tool-rkhunter` |
| 49 | `age` | age Modern File Encryption | Security | `age` | `age` | Terminal | `vice-tool-age` |
| 50 | `pass` | pass Unix Password Store | Security | `pass` | `pass` | Terminal | `vice-tool-pass` |
| 51 | `keepassxc` | KeePassXC Password Safe | Security | `keepassxc` | `keepassxc` | GUI | `vice-tool-keepassxc` |
| 52 | `pwgen` | pwgen Password Generator | Security | `pwgen` | `pwgen -s 20 8` | Terminal | `vice-tool-pwgen` |
| 53 | `macchanger` | MAC Changer Privacy Tool | Security | `macchanger` | `macchanger` | Terminal | `vice-tool-macchanger` |
| 54 | `proxychains4` | ProxyChains-NG Router | Security | `proxychains4` | `proxychains4` | Terminal | `vice-tool-proxychains4` |
| 55 | `neovim` | Neovim Code Editor | Developer | `neovim` | `nvim` | Terminal | `vice-tool-neovim` |
| 56 | `tmux` | tmux Terminal Multiplexer | Developer | `tmux` | `tmux` | Terminal | `vice-tool-tmux` |
| 57 | `ripgrep` | ripgrep (rg) Code Search | Developer | `ripgrep` | `rg` | Terminal | `vice-tool-ripgrep` |
| 58 | `fd-find` | fd-find (fdfind) Fast Finder | Developer | `fd-find` | `fdfind` | Terminal | `vice-tool-fd-find` |
| 59 | `bat` | bat (batcat) Syntax Viewer | Developer | `bat` | `batcat` | Terminal | `vice-tool-bat` |
| 60 | `fzf` | fzf Fuzzy Finder | Developer | `fzf` | `fzf` | Terminal | `vice-tool-fzf` |
| 61 | `jq` | jq JSON Processor | Developer | `jq` | `jq` | Terminal | `vice-tool-jq` |
| 62 | `git` | Git Version Control | Developer | `git` | `git --version` | Terminal | `vice-tool-git` |
| 63 | `tig` | Tig Git Text Interface | Developer | `tig` | `tig` | Terminal | `vice-tool-tig` |
| 64 | `gdb` | GDB GNU Debugger | Developer | `gdb` | `gdb` | Terminal | `vice-tool-gdb` |
| 65 | `strace` | strace Syscall Tracer | Developer | `strace` | `strace` | Terminal | `vice-tool-strace` |
| 66 | `ltrace` | ltrace Library Call Tracer | Developer | `ltrace` | `ltrace` | Terminal | `vice-tool-ltrace` |
| 67 | `valgrind` | Valgrind Memory Profiler | Developer | `valgrind` | `valgrind` | Terminal | `vice-tool-valgrind` |
| 68 | `shellcheck` | ShellCheck Script Linter | Developer | `shellcheck` | `shellcheck` | Terminal | `vice-tool-shellcheck` |
| 69 | `sqlite3` | SQLite 3 Database Shell | Developer | `sqlite3` | `sqlite3` | Terminal | `vice-tool-sqlite3` |
| 70 | `ncdu` | ncdu Disk Usage Explorer | Files & Disk | `ncdu` | `ncdu` | Terminal | `vice-tool-ncdu` |
| 71 | `duf` | duf Disk Usage Utility | Files & Disk | `duf` | `duf` | Terminal | `vice-tool-duf` |
| 72 | `baobab` | Disk Usage Analyzer (Baobab) | Files & Disk | `baobab` | `baobab` | GUI | `vice-tool-baobab` |
| 73 | `gparted` | GParted Partition Editor | Files & Disk | `gparted` | `gparted` | GUI | `vice-tool-gparted` |
| 74 | `parted` | GNU Parted CLI Partitioner | Files & Disk | `parted` | `parted -l` | Terminal | `vice-tool-parted` |
| 75 | `smartmontools` | smartctl Drive Health | Files & Disk | `smartmontools` | `smartctl --scan` | Terminal | `vice-tool-smartmontools` |
| 76 | `nvme-cli` | NVMe SSD Management CLI | Files & Disk | `nvme-cli` | `nvme list` | Terminal | `vice-tool-nvme-cli` |
| 77 | `testdisk` | TestDisk Partition Recovery | Files & Disk | `testdisk` | `testdisk` | Terminal | `vice-tool-testdisk` |
| 78 | `gddrescue` | GNU ddrescue Data Recovery | Files & Disk | `gddrescue` | `ddrescue` | Terminal | `vice-tool-gddrescue` |
| 79 | `rsync` | rsync Incremental Sync | Files & Disk | `rsync` | `rsync` | Terminal | `vice-tool-rsync` |
| 80 | `tree` | tree Directory Visualizer | Files & Disk | `tree` | `tree -L 2` | Terminal | `vice-tool-tree` |
| 81 | `mc` | Midnight Commander (mc) | Files & Disk | `mc` | `mc` | Terminal | `vice-tool-mc` |
| 82 | `ranger` | ranger Console File Manager | Files & Disk | `ranger` | `ranger` | Terminal | `vice-tool-ranger` |
| 83 | `ffmpeg` | FFmpeg Media Transcoder | Media | `ffmpeg` | `ffmpeg` | Terminal | `vice-tool-ffmpeg` |
| 84 | `mpv` | mpv Media Player | Media | `mpv` | `mpv --player-operation-mode=pseudo-gui` | GUI | `vice-tool-mpv` |
| 85 | `imagemagick` | ImageMagick CLI (convert) | Media | `imagemagick` | `convert` | Terminal | `vice-tool-imagemagick` |
| 86 | `mediainfo` | MediaInfo Codec Inspector | Media | `mediainfo` | `mediainfo` | Terminal | `vice-tool-mediainfo` |
| 87 | `sox` | SoX Sound eXchange CLI | Media | `sox` | `sox` | Terminal | `vice-tool-sox` |
| 88 | `vorbis-tools` | Ogg Vorbis Audio Tools | Media | `vorbis-tools` | `oggenc` | Terminal | `vice-tool-vorbis-tools` |
| 89 | `flac` | FLAC Lossless Audio Codec | Media | `flac` | `flac` | Terminal | `vice-tool-flac` |
| 90 | `opus-tools` | Opus Audio Codec Tools | Media | `opus-tools` | `opusenc` | Terminal | `vice-tool-opus-tools` |
| 91 | `yt-dlp` | yt-dlp Media Downloader | Media | `yt-dlp` | `yt-dlp` | Terminal | `vice-tool-yt-dlp` |
| 92 | `libimage-exiftool-perl` | ExifTool Metadata Editor | Media | `libimage-exiftool-perl` | `exiftool` | Terminal | `vice-tool-libimage-exiftool-perl` |
| 93 | `qrencode` | QRencode Barcode Generator | Productivity | `qrencode` | `qrencode` | Terminal | `vice-tool-qrencode` |
| 94 | `geany` | Geany Lightweight IDE | Productivity | `geany` | `geany` | GUI | `vice-tool-geany` |
| 95 | `mousepad` | Mousepad Text Editor | Productivity | `mousepad` | `mousepad` | GUI | `vice-tool-mousepad` |
| 96 | `galculator` | Galculator Scientific Calc | Productivity | `galculator` | `galculator` | GUI | `vice-tool-galculator` |
| 97 | `qpdfview` | qpdfview Document Viewer | Office | `qpdfview` | `qpdfview` | GUI | `vice-tool-qpdfview` |
| 98 | `file-roller` | File Roller Archive GUI | Productivity | `file-roller` | `file-roller` | GUI | `vice-tool-file-roller` |
| 99 | `p7zip-full` | 7-Zip CLI Archiver (7z) | Productivity | `p7zip-full` | `7z` | Terminal | `vice-tool-p7zip-full` |
| 100 | `meld` | Meld Visual Diff & Merge | Productivity | `meld` | `meld` | GUI | `vice-tool-meld` |
| 101 | `vice-tool-net-shield` | Vice Net Shield | GTA VI Originals | `vice-native` | `python3 /opt/vice-os/vice_tool_net_shield.py` | GUI | `vice-tool-net-shield` |
| 102 | `vice-tool-cyber-deck` | Vice Cyber Audit Deck | GTA VI Originals | `vice-native` | `python3 /opt/vice-os/vice_tool_cyber_deck.py` | GUI | `vice-tool-cyber-deck` |
| 103 | `vice-tool-mac-cloak` | Vice Privacy & Cloak | GTA VI Originals | `vice-native` | `python3 /opt/vice-os/vice_tool_mac_cloak.py` | GUI | `vice-tool-mac-cloak` |
| 104 | `vice-tool-office-hub` | Vice Office Studio | GTA VI Originals | `vice-native` | `python3 /opt/vice-os/vice_tool_office_hub.py` | GUI | `vice-tool-office-hub` |
| 105 | `vice-tool-clock-sync` | Vice World Clock & Sync | GTA VI Originals | `vice-native` | `python3 /opt/vice-os/vice_tool_clock_sync.py` | GUI | `vice-tool-clock-sync` |
| 106 | `libreoffice-writer` | LibreOffice Writer | Office | `libreoffice-writer` | `libreoffice --writer` | GUI | `vice-tool-libreoffice-writer` |
| 107 | `libreoffice-calc` | LibreOffice Calc | Office | `libreoffice-calc` | `libreoffice --calc` | GUI | `vice-tool-libreoffice-calc` |
| 108 | `libreoffice-impress` | LibreOffice Impress | Office | `libreoffice-impress` | `libreoffice --impress` | GUI | `vice-tool-libreoffice-impress` |
| 109 | `libreoffice-draw` | LibreOffice Draw | Office | `libreoffice-draw` | `libreoffice --draw` | GUI | `vice-tool-libreoffice-draw` |
| 110 | `libreoffice-math` | LibreOffice Math | Office | `libreoffice-math` | `libreoffice --math` | GUI | `vice-tool-libreoffice-math` |
| 111 | `evince` | Evince Document Viewer | Office | `evince` | `evince` | GUI | `vice-tool-evince` |
| 112 | `simple-scan` | Document Scanner | Office | `simple-scan` | `simple-scan` | GUI | `vice-tool-simple-scan` |
| 113 | `poppler-utils` | Poppler PDF Toolkit | Office | `poppler-utils` | `pdftotext` | Terminal | `vice-tool-poppler-utils` |
| 114 | `hunspell` | Hunspell Spell Checker | Office | `hunspell` | `hunspell` | Terminal | `vice-tool-hunspell` |
| 115 | `system-config-printer` | Printers Configuration | System | `system-config-printer` | `system-config-printer` | GUI | `vice-tool-system-config-printer` |
| 116 | `blueman` | Bluetooth Manager | System | `blueman` | `blueman-manager` | GUI | `vice-tool-blueman` |
| 117 | `bluez` | Bluetooth CLI (bluetoothctl) | System | `bluez` | `bluetoothctl` | Terminal | `vice-tool-bluez` |
| 118 | `timeshift` | Timeshift System Snapshots | System | `timeshift` | `timeshift-launcher` | GUI | `vice-tool-timeshift` |
| 119 | `chrony` | Chrony NTP Time Client | System | `chrony` | `chronyc tracking` | Terminal | `vice-tool-chrony` |
| 120 | `arandr` | ARandR Display Layout | System | `arandr` | `arandr` | GUI | `vice-tool-arandr` |
| 121 | `lxappearance` | LXAppearance Theme Switcher | System | `lxappearance` | `lxappearance` | GUI | `vice-tool-lxappearance` |
| 122 | `synaptic` | Synaptic Package Manager | System | `synaptic` | `synaptic-pkexec` | GUI | `vice-tool-synaptic` |
| 123 | `xfce4-terminal` | Xfce Terminal Emulator | System | `xfce4-terminal` | `xfce4-terminal` | GUI | `vice-tool-xfce4-terminal` |
| 124 | `glances` | Glances System Monitor | System | `glances` | `glances` | Terminal | `vice-tool-glances` |
| 125 | `nmon` | nmon Performance Monitor | System | `nmon` | `nmon` | Terminal | `vice-tool-nmon` |
| 126 | `atop` | atop Resource Logger | System | `atop` | `atop` | Terminal | `vice-tool-atop` |
| 127 | `hwinfo` | hwinfo Hardware Probe | System | `hwinfo` | `hwinfo --short` | Terminal | `vice-tool-hwinfo` |
| 128 | `hardinfo` | HardInfo System Profiler | System | `hardinfo` | `hardinfo` | GUI | `vice-tool-hardinfo` |
| 129 | `lnav` | lnav Log File Navigator | System | `lnav` | `lnav` | Terminal | `vice-tool-lnav` |
| 130 | `multitail` | MultiTail Log Monitor | System | `multitail` | `multitail` | Terminal | `vice-tool-multitail` |
| 131 | `wireshark` | Wireshark Packet Analyzer | Network | `wireshark` | `wireshark` | GUI | `vice-tool-wireshark` |
| 132 | `arp-scan` | ARP-Scan LAN Discovery | Network | `arp-scan` | `arp-scan --localnet` | Terminal | `vice-tool-arp-scan` |
| 133 | `netdiscover` | Netdiscover ARP Recon | Network | `netdiscover` | `netdiscover` | Terminal | `vice-tool-netdiscover` |
| 134 | `hping3` | hping3 Packet Crafter | Network | `hping3` | `hping3` | Terminal | `vice-tool-hping3` |
| 135 | `masscan` | Masscan Port Scanner | Network | `masscan` | `masscan` | Terminal | `vice-tool-masscan` |
| 136 | `ncat` | Nmap Ncat Socket Tool | Network | `ncat` | `ncat` | Terminal | `vice-tool-ncat` |
| 137 | `ndiff` | Ndiff Nmap Scan Differ | Network | `ndiff` | `ndiff` | Terminal | `vice-tool-ndiff` |
| 138 | `dnsrecon` | DNSRecon Enumerator | Network | `dnsrecon` | `dnsrecon` | Terminal | `vice-tool-dnsrecon` |
| 139 | `dnsenum` | DNSenum Domain Scanner | Network | `dnsenum` | `dnsenum` | Terminal | `vice-tool-dnsenum` |
| 140 | `fierce` | Fierce DNS Reconnaissance | Network | `fierce` | `fierce` | Terminal | `vice-tool-fierce` |
| 141 | `dmitry` | DMitry Host Gatherer | Network | `dmitry` | `dmitry` | Terminal | `vice-tool-dmitry` |
| 142 | `stubby` | Stubby DNS-over-TLS | Network | `stubby` | `stubby` | Terminal | `vice-tool-stubby` |
| 143 | `unbound` | Unbound Validating DNS | Network | `unbound` | `unbound-checkconf` | Terminal | `vice-tool-unbound` |
| 144 | `tcpflow` | tcpflow Stream Recorder | Network | `tcpflow` | `tcpflow` | Terminal | `vice-tool-tcpflow` |
| 145 | `ngrep` | ngrep Network Packet Grep | Network | `ngrep` | `ngrep` | Terminal | `vice-tool-ngrep` |
| 146 | `ssldump` | ssldump TLS Analyzer | Network | `ssldump` | `ssldump` | Terminal | `vice-tool-ssldump` |
| 147 | `tcpreplay` | tcpreplay Traffic Replayer | Network | `tcpreplay` | `tcpreplay` | Terminal | `vice-tool-tcpreplay` |
| 148 | `nbtscan` | nbtscan NetBIOS Scanner | Network | `nbtscan` | `nbtscan` | Terminal | `vice-tool-nbtscan` |
| 149 | `smbclient` | SMBClient Share CLI | Network | `smbclient` | `smbclient` | Terminal | `vice-tool-smbclient` |
| 150 | `swaks` | Swaks SMTP Tester | Network | `swaks` | `swaks` | Terminal | `vice-tool-swaks` |
| 151 | `autossh` | AutoSSH Tunnel Keeper | Network | `autossh` | `autossh` | Terminal | `vice-tool-autossh` |
| 152 | `mosh` | Mosh Mobile Shell | Network | `mosh` | `mosh` | Terminal | `vice-tool-mosh` |
| 153 | `openssh-client` | OpenSSH Client (ssh) | Network | `openssh-client` | `ssh` | Terminal | `vice-tool-openssh-client` |
| 154 | `bmon` | bmon Bandwidth Monitor | Network | `bmon` | `bmon` | Terminal | `vice-tool-bmon` |
| 155 | `vnstat` | vnStat Traffic Logger | Network | `vnstat` | `vnstat` | Terminal | `vice-tool-vnstat` |
| 156 | `ethtool` | Ethtool NIC Diagnostics | Network | `ethtool` | `ethtool` | Terminal | `vice-tool-ethtool` |
| 157 | `wavemon` | Wavemon Wi-Fi Monitor | Network | `wavemon` | `wavemon` | Terminal | `vice-tool-wavemon` |
| 158 | `fping` | fping Parallel Pinger | Network | `fping` | `fping` | Terminal | `vice-tool-fping` |
| 159 | `openvpn` | OpenVPN Tunnel Client | Security | `openvpn` | `openvpn` | Terminal | `vice-tool-openvpn` |
| 160 | `wireguard-tools` | WireGuard VPN (wg) | Security | `wireguard-tools` | `wg` | Terminal | `vice-tool-wireguard-tools` |
| 161 | `tor` | Tor Anonymity Router | Security | `tor` | `tor` | Terminal | `vice-tool-tor` |
| 162 | `torsocks` | Torsocks Tor Wrapper | Security | `torsocks` | `torsocks` | Terminal | `vice-tool-torsocks` |
| 163 | `privoxy` | Privoxy Privacy Proxy | Security | `privoxy` | `privoxy` | Terminal | `vice-tool-privoxy` |
| 164 | `obfs4proxy` | Tor Obfs4 Bridge | Security | `obfs4proxy` | `obfs4proxy` | Terminal | `vice-tool-obfs4proxy` |
| 165 | `stunnel4` | Stunnel4 TLS Wrapper | Security | `stunnel4` | `stunnel4` | Terminal | `vice-tool-stunnel4` |
| 166 | `sshuttle` | sshuttle SSH VPN | Security | `sshuttle` | `sshuttle` | Terminal | `vice-tool-sshuttle` |
| 167 | `gufw` | GUFW Firewall GUI | Security | `gufw` | `gufw` | GUI | `vice-tool-gufw` |
| 168 | `nftables` | nftables Packet Filter | Security | `nftables` | `nft` | Terminal | `vice-tool-nftables` |
| 169 | `iptables` | iptables Firewall CLI | Security | `iptables` | `iptables` | Terminal | `vice-tool-iptables` |
| 170 | `firejail` | Firejail App Sandbox | Security | `firejail` | `firejail` | Terminal | `vice-tool-firejail` |
| 171 | `fail2ban` | Fail2Ban Intrusion Guard | Security | `fail2ban` | `fail2ban-client` | Terminal | `vice-tool-fail2ban` |
| 172 | `clamav` | ClamAV Malware Scanner | Security | `clamav` | `clamscan` | Terminal | `vice-tool-clamav` |
| 173 | `aide` | AIDE Integrity Checker | Security | `aide` | `aide` | Terminal | `vice-tool-aide` |
| 174 | `auditd` | Auditd Kernel Audit CLI | Security | `auditd` | `auditctl` | Terminal | `vice-tool-auditd` |
| 175 | `apparmor-utils` | AppArmor Policy Utils | Security | `apparmor-utils` | `aa-status` | Terminal | `vice-tool-apparmor-utils` |
| 176 | `mat2` | MAT2 Metadata Cleaner | Security | `mat2` | `mat2` | Terminal | `vice-tool-mat2` |
| 177 | `sqlmap` | SQLMap Injection Auditor | Security | `sqlmap` | `sqlmap` | Terminal | `vice-tool-sqlmap` |
| 178 | `gobuster` | Gobuster URI & DNS Buster | Security | `gobuster` | `gobuster` | Terminal | `vice-tool-gobuster` |
| 179 | `dirb` | DIRB Web Content Scanner | Security | `dirb` | `dirb` | Terminal | `vice-tool-dirb` |
| 180 | `whatweb` | WhatWeb Tech Fingerprinter | Security | `whatweb` | `whatweb` | Terminal | `vice-tool-whatweb` |
| 181 | `wafw00f` | WAFW00F WAF Detector | Security | `wafw00f` | `wafw00f` | Terminal | `vice-tool-wafw00f` |
| 182 | `sslscan` | SSLScan TLS Auditor | Security | `sslscan` | `sslscan` | Terminal | `vice-tool-sslscan` |
| 183 | `testssl.sh` | testssl.sh TLS Auditor | Security | `testssl.sh` | `testssl` | Terminal | `vice-tool-testssl.sh` |
| 184 | `hydra` | THC-Hydra Auth Auditor | Security | `hydra` | `hydra` | Terminal | `vice-tool-hydra` |
| 185 | `medusa` | Medusa Auth Cracker | Security | `medusa` | `medusa` | Terminal | `vice-tool-medusa` |
| 186 | `ncrack` | Ncrack Network Auth Tool | Security | `ncrack` | `ncrack` | Terminal | `vice-tool-ncrack` |
| 187 | `john` | John the Ripper Cracker | Security | `john` | `john` | Terminal | `vice-tool-john` |
| 188 | `crunch` | Crunch Wordlist Builder | Security | `crunch` | `crunch` | Terminal | `vice-tool-crunch` |
| 189 | `cewl` | CeWL Wordlist Spider | Security | `cewl` | `cewl` | Terminal | `vice-tool-cewl` |
| 190 | `fcrackzip` | fcrackzip ZIP Auditor | Security | `fcrackzip` | `fcrackzip` | Terminal | `vice-tool-fcrackzip` |
| 191 | `pdfcrack` | pdfcrack PDF Auditor | Security | `pdfcrack` | `pdfcrack` | Terminal | `vice-tool-pdfcrack` |
| 192 | `aircrack-ng` | Aircrack-ng Wi-Fi Suite | Security | `aircrack-ng` | `aircrack-ng` | Terminal | `vice-tool-aircrack-ng` |
| 193 | `reaver` | Reaver WPS Auditor | Security | `reaver` | `reaver` | Terminal | `vice-tool-reaver` |
| 194 | `wifite` | Wifite Wi-Fi Auditor | Security | `wifite` | `wifite` | Terminal | `vice-tool-wifite` |
| 195 | `ettercap-text-only` | Ettercap Console MITM | Security | `ettercap-text-only` | `ettercap` | Terminal | `vice-tool-ettercap-text-only` |
| 196 | `mitmproxy` | mitmproxy HTTPS Proxy | Security | `mitmproxy` | `mitmproxy` | Terminal | `vice-tool-mitmproxy` |
| 197 | `binwalk` | Binwalk Firmware Analyzer | Security | `binwalk` | `binwalk` | Terminal | `vice-tool-binwalk` |
| 198 | `foremost` | Foremost File Carver | Security | `foremost` | `foremost` | Terminal | `vice-tool-foremost` |
| 199 | `steghide` | Steghide Steganography | Security | `steghide` | `steghide` | Terminal | `vice-tool-steghide` |
| 200 | `sleuthkit` | Sleuth Kit Forensics (fls) | Security | `sleuthkit` | `fls` | Terminal | `vice-tool-sleuthkit` |
| 201 | `yara` | YARA Malware Matcher | Security | `yara` | `yara` | Terminal | `vice-tool-yara` |
| 202 | `gcc` | GCC C/C++ Compiler | Developer | `gcc` | `gcc` | Terminal | `vice-tool-gcc` |
| 203 | `make` | GNU Make Build Tool | Developer | `make` | `make` | Terminal | `vice-tool-make` |
| 204 | `cmake` | CMake Build System | Developer | `cmake` | `cmake` | Terminal | `vice-tool-cmake` |
| 205 | `gdb-multiarch` | GDB Multi-Arch Debugger | Developer | `gdb-multiarch` | `gdb-multiarch` | Terminal | `vice-tool-gdb-multiarch` |
| 206 | `nasm` | NASM x86/x64 Assembler | Developer | `nasm` | `nasm` | Terminal | `vice-tool-nasm` |
| 207 | `binutils` | GNU Binutils (objdump) | Developer | `binutils` | `objdump` | Terminal | `vice-tool-binutils` |
| 208 | `elfutils` | Elfutils ELF Inspector | Developer | `elfutils` | `eu-readelf` | Terminal | `vice-tool-elfutils` |
| 209 | `patchelf` | PatchELF Binary Editor | Developer | `patchelf` | `patchelf` | Terminal | `vice-tool-patchelf` |
| 210 | `hexedit` | Hexedit Terminal Hex | Developer | `hexedit` | `hexedit` | Terminal | `vice-tool-hexedit` |
| 211 | `ghex` | GHex Graphical Hex Editor | Developer | `ghex` | `ghex` | GUI | `vice-tool-ghex` |
| 212 | `xxd` | xxd Hex Dump Utility | Developer | `xxd` | `xxd` | Terminal | `vice-tool-xxd` |
| 213 | `cloc` | cloc Code Line Counter | Developer | `cloc` | `cloc` | Terminal | `vice-tool-cloc` |
| 214 | `hyperfine` | Hyperfine Benchmarker | Developer | `hyperfine` | `hyperfine` | Terminal | `vice-tool-hyperfine` |
| 215 | `entr` | entr File-Change Runner | Developer | `entr` | `entr` | Terminal | `vice-tool-entr` |
| 216 | `cppcheck` | Cppcheck Static Analyzer | Developer | `cppcheck` | `cppcheck` | Terminal | `vice-tool-cppcheck` |
| 217 | `sqlitebrowser` | DB Browser for SQLite | Developer | `sqlitebrowser` | `sqlitebrowser` | GUI | `vice-tool-sqlitebrowser` |
| 218 | `yq` | yq YAML & XML Processor | Developer | `yq` | `yq` | Terminal | `vice-tool-yq` |
| 219 | `gnome-disk-utility` | GNOME Disks Utility | Files & Disk | `gnome-disk-utility` | `gnome-disks` | GUI | `vice-tool-gnome-disk-utility` |
| 220 | `ntfs-3g` | NTFS-3G Windows FS Tools | Files & Disk | `ntfs-3g` | `ntfsfix` | Terminal | `vice-tool-ntfs-3g` |
| 221 | `exfatprogs` | exFAT Filesystem Tools | Files & Disk | `exfatprogs` | `fsck.exfat` | Terminal | `vice-tool-exfatprogs` |
| 222 | `dosfstools` | FAT/vFAT Filesystem Tools | Files & Disk | `dosfstools` | `fsck.fat` | Terminal | `vice-tool-dosfstools` |
| 223 | `btrfs-progs` | Btrfs Filesystem Suite | Files & Disk | `btrfs-progs` | `btrfs` | Terminal | `vice-tool-btrfs-progs` |
| 224 | `cryptsetup` | LUKS Disk Encryption CLI | Files & Disk | `cryptsetup` | `cryptsetup` | Terminal | `vice-tool-cryptsetup` |
| 225 | `hdparm` | hdparm Drive Tuner | Files & Disk | `hdparm` | `hdparm` | Terminal | `vice-tool-hdparm` |
| 226 | `lsscsi` | lsscsi Device Lister | Files & Disk | `lsscsi` | `lsscsi` | Terminal | `vice-tool-lsscsi` |
| 227 | `nnn` | nnn Terminal File Manager | Files & Disk | `nnn` | `nnn` | Terminal | `vice-tool-nnn` |
| 228 | `jdupes` | jdupes Duplicate Finder | Files & Disk | `jdupes` | `jdupes` | Terminal | `vice-tool-jdupes` |
| 229 | `grsync` | Grsync Graphical Rsync | Files & Disk | `grsync` | `grsync` | GUI | `vice-tool-grsync` |
| 230 | `pavucontrol` | PulseAudio/PipeWire Mixer | Media | `pavucontrol` | `pavucontrol` | GUI | `vice-tool-pavucontrol` |
| 231 | `celluloid` | Celluloid Video Player | Media | `celluloid` | `celluloid` | GUI | `vice-tool-celluloid` |
| 232 | `ristretto` | Ristretto Image Viewer | Media | `ristretto` | `ristretto` | GUI | `vice-tool-ristretto` |
| 233 | `feh` | feh Fast Image Viewer | Media | `feh` | `feh --scale-down /usr/share/backgrounds` | GUI | `vice-tool-feh` |
| 234 | `flameshot` | Flameshot Screenshot GUI | Media | `flameshot` | `flameshot gui` | GUI | `vice-tool-flameshot` |
| 235 | `gnome-screenshot` | GNOME Screenshot Tool | Media | `gnome-screenshot` | `gnome-screenshot --interactive` | GUI | `vice-tool-gnome-screenshot` |
| 236 | `gcolor3` | Gcolor3 Color Picker | Media | `gcolor3` | `gcolor3` | GUI | `vice-tool-gcolor3` |
| 237 | `easytag` | EasyTAG Audio Tagger | Media | `easytag` | `easytag` | GUI | `vice-tool-easytag` |
| 238 | `optipng` | OptiPNG Image Optimizer | Media | `optipng` | `optipng` | Terminal | `vice-tool-optipng` |
| 239 | `jpegoptim` | JPEGoptim Optimizer | Media | `jpegoptim` | `jpegoptim` | Terminal | `vice-tool-jpegoptim` |
| 240 | `firefox-esr` | Firefox ESR Browser | Productivity | `firefox-esr` | `firefox-esr` | GUI | `vice-tool-firefox-esr` |
| 241 | `redshift` | Redshift Night Light | Productivity | `redshift` | `redshift` | Terminal | `vice-tool-redshift` |
| 242 | `zim` | Zim Desktop Wiki | Productivity | `zim` | `zim` | GUI | `vice-tool-zim` |
| 243 | `cherrytree` | CherryTree Notes | Productivity | `cherrytree` | `cherrytree` | GUI | `vice-tool-cherrytree` |
| 244 | `calcurse` | Calcurse CLI Calendar | Productivity | `calcurse` | `calcurse` | Terminal | `vice-tool-calcurse` |
| 245 | `taskwarrior` | Taskwarrior Task CLI | Productivity | `taskwarrior` | `task` | Terminal | `vice-tool-taskwarrior` |
| 246 | `speedcrunch` | SpeedCrunch Calculator | Productivity | `speedcrunch` | `speedcrunch` | GUI | `vice-tool-speedcrunch` |
| 247 | `qalculate-gtk` | Qalculate! Calculator | Productivity | `qalculate-gtk` | `qalculate-gtk` | GUI | `vice-tool-qalculate-gtk` |
| 248 | `unzip` | UnZip Archive Extractor | Productivity | `unzip` | `unzip` | Terminal | `vice-tool-unzip` |
| 249 | `zstd` | Zstandard Compressor | Productivity | `zstd` | `zstd` | Terminal | `vice-tool-zstd` |
| 250 | `tealdeer` | tealdeer (tldr) Cheatsheets | Productivity | `tealdeer` | `tldr` | Terminal | `vice-tool-tealdeer` |
| 251 | `vice-tool-fetch` | Vice OS Fetch (GTA VI x Debian) | GTA VI Originals | `vice-native` | `xfce4-terminal --disable-server --title="Vice OS — System Info (GTA VI x Debian)" --geometry=116x30 -e "/usr/local/bin/vicefetch --hold"` | GUI | `vice-tool-fetch` |
| 252 | `vice-tool-payload-lab` | Vice Cyber Encoder & Recon Lab | GTA VI Originals | `vice-native` | `python3 /opt/vice-os/vice_tool_payload_lab.py` | GUI | `vice-tool-payload-lab` |
| 253 | `arping` | ARPing Layer-2 Probe | Network | `arping` | `arping` | Terminal | `vice-tool-arping` |
| 254 | `braa` | Braa Mass SNMP Scanner | Network | `braa` | `braa` | Terminal | `vice-tool-braa` |
| 255 | `firewalk` | Firewalk ACL Prober | Network | `firewalk` | `firewalk` | Terminal | `vice-tool-firewalk` |
| 256 | `ike-scan` | IKE-Scan VPN Fingerprinter | Security | `ike-scan` | `ike-scan` | Terminal | `vice-tool-ike-scan` |
| 257 | `ipcalc-ng` | ipcalc-ng CIDR Subnet Calc | Network | `ipcalc-ng` | `ipcalc-ng` | Terminal | `vice-tool-ipcalc-ng` |
| 258 | `ndisc6` | NDisc6 IPv6 Neighbor Recon | Network | `ndisc6` | `ndisc6` | Terminal | `vice-tool-ndisc6` |
| 259 | `onesixtyone` | Onesixtyone SNMP Scanner | Network | `onesixtyone` | `onesixtyone` | Terminal | `vice-tool-onesixtyone` |
| 260 | `snmp` | Net-SNMP Recon Suite (snmpwalk) | Network | `snmp` | `snmpwalk` | Terminal | `vice-tool-snmp` |
| 261 | `tcptraceroute` | TCPTraceroute Path Prober | Network | `tcptraceroute` | `tcptraceroute` | Terminal | `vice-tool-tcptraceroute` |
| 262 | `zmap` | ZMap Single-Packet Scanner | Network | `zmap` | `zmap` | Terminal | `vice-tool-zmap` |
| 263 | `dnsmap` | DNSmap Subdomain Scanner | Network | `dnsmap` | `dnsmap` | Terminal | `vice-tool-dnsmap` |
| 264 | `dnstracer` | DNSTracer Delegation Tracer | Network | `dnstracer` | `dnstracer` | Terminal | `vice-tool-dnstracer` |
| 265 | `ldnsutils` | LDNS Drill DNSSEC Inspector | Network | `ldnsutils` | `drill` | Terminal | `vice-tool-ldnsutils` |
| 266 | `sublist3r` | Sublist3r OSINT Subdomains | Security | `sublist3r` | `sublist3r` | Terminal | `vice-tool-sublist3r` |
| 267 | `ldap-utils` | LDAPsearch Directory Recon | Network | `ldap-utils` | `ldapsearch` | Terminal | `vice-tool-ldap-utils` |
| 268 | `smb-nat` | SMB-NAT NetBIOS Auditor | Security | `smb-nat` | `smb-nat` | Terminal | `vice-tool-smb-nat` |
| 269 | `smbmap` | SMBMap Share Enumerator | Security | `smbmap` | `smbmap` | Terminal | `vice-tool-smbmap` |
| 270 | `p0f` | p0f Passive OS Fingerprinter | Security | `p0f` | `p0f` | Terminal | `vice-tool-p0f` |
| 271 | `ipv6toolkit` | IPv6Toolkit (scan6) Scanner | Network | `ipv6toolkit` | `scan6` | Terminal | `vice-tool-ipv6toolkit` |
| 272 | `thc-ipv6` | THC-IPv6 Attack Toolkit | Security | `thc-ipv6` | `atk6-alive6` | Terminal | `vice-tool-thc-ipv6` |
| 273 | `heartbleeder` | Heartbleeder TLS Auditor | Security | `heartbleeder` | `heartbleeder` | Terminal | `vice-tool-heartbleeder` |
| 274 | `ssh-audit` | SSH-Audit Server & Client Check | Security | `ssh-audit` | `ssh-audit` | Terminal | `vice-tool-ssh-audit` |
| 275 | `ssl-cert-check` | SSL-Cert-Check Expiry Auditor | Security | `ssl-cert-check` | `ssl-cert-check` | Terminal | `vice-tool-ssl-cert-check` |
| 276 | `zbar-tools` | ZBar QR & Barcode Decoder | Media | `zbar-tools` | `zbarimg` | Terminal | `vice-tool-zbar-tools` |
| 277 | `cadaver` | Cadaver WebDAV CLI Client | Security | `cadaver` | `cadaver` | Terminal | `vice-tool-cadaver` |
| 278 | `ffuf` | FFuf Fast Web Fuzzer | Security | `ffuf` | `ffuf` | Terminal | `vice-tool-ffuf` |
| 279 | `httping` | HTTPing Latency & TLS Probe | Network | `httping` | `httping` | Terminal | `vice-tool-httping` |
| 280 | `siege` | Siege HTTP Load & Stress Tester | Security | `siege` | `siege` | Terminal | `vice-tool-siege` |
| 281 | `w3m` | w3m Terminal Web Inspector | Network | `w3m` | `w3m` | Terminal | `vice-tool-w3m` |
| 282 | `wapiti` | Wapiti Web Vulnerability Scanner | Security | `wapiti` | `wapiti` | Terminal | `vice-tool-wapiti` |
| 283 | `weevely` | Weevely Stealth PHP Shell | Security | `weevely` | `weevely` | Terminal | `vice-tool-weevely` |
| 284 | `wfuzz` | Wfuzz Web Payload Fuzzer | Security | `wfuzz` | `wfuzz` | Terminal | `vice-tool-wfuzz` |
| 285 | `aria2` | aria2c Multi-Source Client | Network | `aria2` | `aria2c` | Terminal | `vice-tool-aria2` |
| 286 | `bruteforce-luks` | Bruteforce-LUKS Volume Auditor | Security | `bruteforce-luks` | `bruteforce-luks` | Terminal | `vice-tool-bruteforce-luks` |
| 287 | `bruteforce-salted-openssl` | OpenSSL Salted Cipher Auditor | Security | `bruteforce-salted-openssl` | `bruteforce-salted-openssl` | Terminal | `vice-tool-bruteforce-salted-openssl` |
| 288 | `bruteforce-wallet` | Bruteforce-Wallet Key Recovery | Security | `bruteforce-wallet` | `bruteforce-wallet` | Terminal | `vice-tool-bruteforce-wallet` |
| 289 | `chntpw` | chntpw Windows SAM Editor | Security | `chntpw` | `chntpw` | Terminal | `vice-tool-chntpw` |
| 290 | `cisco7crack` | Cisco7Crack Type-7 Decoder | Security | `cisco7crack` | `cisco7crack` | Terminal | `vice-tool-cisco7crack` |
| 291 | `cmospwd` | CmosPwd BIOS Recovery Tool | Security | `cmospwd` | `cmospwd` | Terminal | `vice-tool-cmospwd` |
| 292 | `ophcrack-cli` | Ophcrack Rainbow Table CLI | Security | `ophcrack-cli` | `ophcrack-cli` | Terminal | `vice-tool-ophcrack-cli` |
| 293 | `samdump2` | samdump2 SAM Hash Dumper | Security | `samdump2` | `samdump2` | Terminal | `vice-tool-samdump2` |
| 294 | `sipcrack` | SIPcrack VoIP Digest Auditor | Security | `sipcrack` | `sipcrack` | Terminal | `vice-tool-sipcrack` |
| 295 | `sucrack` | Sucrack Local Auth Auditor | Security | `sucrack` | `sucrack` | Terminal | `vice-tool-sucrack` |
| 296 | `princeprocessor` | Princeprocessor Wordlist Gen | Security | `princeprocessor` | `princeprocessor` | Terminal | `vice-tool-princeprocessor` |
| 297 | `apg` | APG Automated Password Gen | Security | `apg` | `apg` | Terminal | `vice-tool-apg` |
| 298 | `sshpass` | SSHPass Non-Interactive Auth | Network | `sshpass` | `sshpass` | Terminal | `vice-tool-sshpass` |
| 299 | `airgraph-ng` | Airgraph-ng Wi-Fi Grapher | Security | `airgraph-ng` | `airgraph-ng` | Terminal | `vice-tool-airgraph-ng` |
| 300 | `bluez-hcidump` | HCIDump Bluetooth Sniffer | Security | `bluez-hcidump` | `hcidump` | Terminal | `vice-tool-bluez-hcidump` |
| 301 | `bluez-tools` | BlueZ-Tools (bt-adapter) | System | `bluez-tools` | `bt-adapter` | Terminal | `vice-tool-bluez-tools` |
| 302 | `btscanner` | BTscanner Bluetooth Enum | Security | `btscanner` | `btscanner` | Terminal | `vice-tool-btscanner` |
| 303 | `bully` | Bully WPS Pixie-Dust Auditor | Security | `bully` | `bully` | Terminal | `vice-tool-bully` |
| 304 | `cowpatty` | coWPAtty WPA-PSK Auditor | Security | `cowpatty` | `cowpatty` | Terminal | `vice-tool-cowpatty` |
| 305 | `hcxdumptool` | hcxdumptool PMKID Capture | Security | `hcxdumptool` | `hcxdumptool` | Terminal | `vice-tool-hcxdumptool` |
| 306 | `hcxtools` | hcxtools (hcxpcapngtool) | Security | `hcxtools` | `hcxpcapngtool` | Terminal | `vice-tool-hcxtools` |
| 307 | `iw` | iw Modern nl80211 Wireless CLI | Network | `iw` | `iw` | Terminal | `vice-tool-iw` |
| 308 | `mdk3` | MDK3 802.11 Stress Tester | Security | `mdk3` | `mdk3` | Terminal | `vice-tool-mdk3` |
| 309 | `mdk4` | MDK4 Next-Gen Wi-Fi Tester | Security | `mdk4` | `mdk4` | Terminal | `vice-tool-mdk4` |
| 310 | `pixiewps` | Pixiewps Offline WPS Auditor | Security | `pixiewps` | `pixiewps` | Terminal | `vice-tool-pixiewps` |
| 311 | `rfkill` | RFKill Radio State Controller | System | `rfkill` | `rfkill` | Terminal | `vice-tool-rfkill` |
| 312 | `wireless-tools` | Wireless-Tools (iwconfig) | Network | `wireless-tools` | `iwconfig` | Terminal | `vice-tool-wireless-tools` |
| 313 | `dsniff` | dSniff LAN Auditing Suite | Security | `dsniff` | `dsniff` | Terminal | `vice-tool-dsniff` |
| 314 | `netsed` | NetSED Stream Packet Editor | Security | `netsed` | `netsed` | Terminal | `vice-tool-netsed` |
| 315 | `sslsniff` | SSLsniff TLS MITM Auditor | Security | `sslsniff` | `sslsniff` | Terminal | `vice-tool-sslsniff` |
| 316 | `sslsplit` | SSLsplit Transparent Proxy | Security | `sslsplit` | `sslsplit` | Terminal | `vice-tool-sslsplit` |
| 317 | `dhcpdump` | DHCPdump Packet Decoder | Network | `dhcpdump` | `dhcpdump` | Terminal | `vice-tool-dhcpdump` |
| 318 | `pcapfix` | PCAPfix Capture Repair Tool | Security | `pcapfix` | `pcapfix` | Terminal | `vice-tool-pcapfix` |
| 319 | `netsniff-ng` | Netsniff-NG Zero-Copy Toolkit | Network | `netsniff-ng` | `netsniff-ng` | Terminal | `vice-tool-netsniff-ng` |
| 320 | `yersinia` | Yersinia Layer-2 Protocol Suite | Security | `yersinia` | `yersinia` | Terminal | `vice-tool-yersinia` |
| 321 | `packit` | Packit Custom Packet Injector | Network | `packit` | `packit` | Terminal | `vice-tool-packit` |
| 322 | `python3-scapy` | Scapy Interactive Packet Shell | Security | `python3-scapy` | `scapy` | Terminal | `vice-tool-python3-scapy` |
| 323 | `sendip` | SendIP Raw Packet Crafter | Network | `sendip` | `sendip` | Terminal | `vice-tool-sendip` |
| 324 | `t50` | T50 Multi-Protocol Injector | Security | `t50` | `t50` | Terminal | `vice-tool-t50` |
| 325 | `dnstop` | DNStop Live Query Monitor | Network | `dnstop` | `dnstop` | Terminal | `vice-tool-dnstop` |
| 326 | `iptraf-ng` | IPTraf-NG Console LAN Monitor | Network | `iptraf-ng` | `iptraf-ng` | Terminal | `vice-tool-iptraf-ng` |
| 327 | `tcptrack` | TCPTrack Live Connection Monitor | Network | `tcptrack` | `tcptrack` | Terminal | `vice-tool-tcptrack` |
| 328 | `scalpel` | Scalpel High-Speed File Carver | Security | `scalpel` | `scalpel` | Terminal | `vice-tool-scalpel` |
| 329 | `fatcat` | fatcat FAT Filesystem Explorer | Security | `fatcat` | `fatcat` | Terminal | `vice-tool-fatcat` |
| 330 | `ext4magic` | ext4magic File Undelete Suite | Security | `ext4magic` | `ext4magic` | Terminal | `vice-tool-ext4magic` |
| 331 | `reglookup` | RegLookup Windows Registry CLI | Security | `reglookup` | `reglookup` | Terminal | `vice-tool-reglookup` |
| 332 | `rifiuti2` | Rifiuti2 Recycle Bin Parser | Security | `rifiuti2` | `rifiuti2` | Terminal | `vice-tool-rifiuti2` |
| 333 | `afflib-tools` | AFFLib Forensic Image Tools | Security | `afflib-tools` | `affcat` | Terminal | `vice-tool-afflib-tools` |
| 334 | `dc3dd` | dc3dd Forensic Disk Imager | Files & Disk | `dc3dd` | `dc3dd` | Terminal | `vice-tool-dc3dd` |
| 335 | `dcfldd` | dcfldd Forensic DD Imager | Files & Disk | `dcfldd` | `dcfldd` | Terminal | `vice-tool-dcfldd` |
| 336 | `ewf-tools` | EWF-Tools (ewfinfo) E01 Suite | Security | `ewf-tools` | `ewfinfo` | Terminal | `vice-tool-ewf-tools` |
| 337 | `ssdeep` | ssdeep Fuzzy Hash Matcher | Security | `ssdeep` | `ssdeep` | Terminal | `vice-tool-ssdeep` |
| 338 | `tlsh-tools` | TLSH Locality-Sensitive Hash | Security | `tlsh-tools` | `tlsh` | Terminal | `vice-tool-tlsh-tools` |
| 339 | `unhide` | Unhide Hidden Process Detector | Security | `unhide` | `unhide` | Terminal | `vice-tool-unhide` |
| 340 | `exiv2` | Exiv2 EXIF/XMP/IPTC Inspector | Media | `exiv2` | `exiv2` | Terminal | `vice-tool-exiv2` |
| 341 | `qpdf` | qpdf PDF Structure & Crypto CLI | Office | `qpdf` | `qpdf` | Terminal | `vice-tool-qpdf` |
| 342 | `squashfs-tools` | SquashFS (unsquashfs) Extractor | Files & Disk | `squashfs-tools` | `unsquashfs` | Terminal | `vice-tool-squashfs-tools` |
| 343 | `gifshuffle` | Gifshuffle GIF Steganography | Security | `gifshuffle` | `gifshuffle` | Terminal | `vice-tool-gifshuffle` |
| 344 | `outguess` | OutGuess DCT Steganography | Security | `outguess` | `outguess` | Terminal | `vice-tool-outguess` |
| 345 | `stegsnow` | Stegsnow Whitespace Stego | Security | `stegsnow` | `stegsnow` | Terminal | `vice-tool-stegsnow` |
| 346 | `pngcheck` | PNGcheck Chunk Integrity Tool | Security | `pngcheck` | `pngcheck` | Terminal | `vice-tool-pngcheck` |
| 347 | `cgdb` | CGDB Split-Pane Curses Debugger | Developer | `cgdb` | `cgdb` | Terminal | `vice-tool-cgdb` |
| 348 | `checksec` | Checksec Binary Hardening Audit | Security | `checksec` | `checksec` | Terminal | `vice-tool-checksec` |
| 349 | `dwarfdump` | DWARFdump Debug Symbol Inspector | Developer | `dwarfdump` | `dwarfdump` | Terminal | `vice-tool-dwarfdump` |
| 350 | `gdbserver` | GDBserver Remote Debug Target | Developer | `gdbserver` | `gdbserver` | Terminal | `vice-tool-gdbserver` |
| 351 | `pax-utils` | PaX-Utils (scanelf) ELF Auditor | Security | `pax-utils` | `scanelf` | Terminal | `vice-tool-pax-utils` |
| 352 | `yasm` | YASM Modular x86/x64 Assembler | Developer | `yasm` | `yasm` | Terminal | `vice-tool-yasm` |
| 353 | `zydis-tools` | ZydisDisasm x86/64 Disassembler | Developer | `zydis-tools` | `ZydisDisasm` | Terminal | `vice-tool-zydis-tools` |
| 354 | `hexyl` | Hexyl Colorized Hex Viewer | Developer | `hexyl` | `hexyl` | Terminal | `vice-tool-hexyl` |
| 355 | `vbindiff` | VBinDiff Visual Binary Diff | Developer | `vbindiff` | `vbindiff` | Terminal | `vice-tool-vbindiff` |
| 356 | `uefitool-cli` | UEFITool (UEFIExtract) Firmware | Security | `uefitool-cli` | `UEFIExtract` | Terminal | `vice-tool-uefitool-cli` |
| 357 | `adb` | Android Debug Bridge (adb) | Developer | `adb` | `adb` | Terminal | `vice-tool-adb` |
| 358 | `fastboot` | Android Fastboot Bootloader CLI | Developer | `fastboot` | `fastboot` | Terminal | `vice-tool-fastboot` |
| 359 | `rlwrap` | rlwrap Readline Shell Wrapper | Developer | `rlwrap` | `rlwrap` | Terminal | `vice-tool-rlwrap` |
| 360 | `ccrypt` | ccrypt Rijndael File Encryptor | Security | `ccrypt` | `ccrypt` | Terminal | `vice-tool-ccrypt` |
| 361 | `scrypt` | scrypt Memory-Hard Encryptor | Security | `scrypt` | `scrypt` | Terminal | `vice-tool-scrypt` |
| 362 | `b3sum` | b3sum BLAKE3 High-Speed Hash | Security | `b3sum` | `b3sum` | Terminal | `vice-tool-b3sum` |
| 363 | `hashdeep` | Hashdeep Recursive File Auditor | Security | `hashdeep` | `hashdeep` | Terminal | `vice-tool-hashdeep` |
| 364 | `rhash` | RHash Multi-Digest Calculator | Security | `rhash` | `rhash` | Terminal | `vice-tool-rhash` |
| 365 | `minisign` | Minisign Ed25519 Signature CLI | Security | `minisign` | `minisign` | Terminal | `vice-tool-minisign` |
| 366 | `gnutls-bin` | GnuTLS CertTool & TLS CLI | Security | `gnutls-bin` | `certtool` | Terminal | `vice-tool-gnutls-bin` |
| 367 | `nwipe` | Nwipe Secure Disk Eraser | Files & Disk | `nwipe` | `nwipe` | Terminal | `vice-tool-nwipe` |
| 368 | `nyx` | Nyx Tor Relay & Circuit Monitor | Security | `nyx` | `nyx` | Terminal | `vice-tool-nyx` |
| 369 | `icmptx` | ICMPTX IP-over-ICMP Tunnel | Security | `icmptx` | `icmptx` | Terminal | `vice-tool-icmptx` |
| 370 | `proxytunnel` | ProxyTunnel HTTP Pivot Client | Security | `proxytunnel` | `proxytunnel` | Terminal | `vice-tool-proxytunnel` |
| 371 | `tinyproxy-bin` | Tinyproxy On-Demand HTTP Proxy | Security | `tinyproxy-bin` | `tinyproxy` | Terminal | `vice-tool-tinyproxy-bin` |
| 372 | `debsums` | Debsums Package Integrity Check | Security | `debsums` | `debsums` | Terminal | `vice-tool-debsums` |
| 373 | `fwknop-client` | fwknop Single Packet Auth CLI | Security | `fwknop-client` | `fwknop` | Terminal | `vice-tool-fwknop-client` |
| 374 | `flawfinder` | Flawfinder C/C++ Security Audit | Developer | `flawfinder` | `flawfinder` | Terminal | `vice-tool-flawfinder` |
| 375 | `zzuf` | zzuf Transparent App Fuzzer | Security | `zzuf` | `zzuf` | Terminal | `vice-tool-zzuf` |
| 376 | `vice-tool-hw-autodetect` | Vice HW & VM Auto-Detect | GTA VI Originals | `vice-native` | `/usr/local/bin/vice-hw-autodetect --status` | Terminal | `vice-tool-hw-autodetect` |
| 377 | `vscode` | Visual Studio Code | Developer | `code` | `code` | GUI | `vice-tool-vscode` |
| 378 | `g++` | GCC G++ C++ Compiler | Developer | `g++` | `g++` | Terminal | `vice-tool-g++` |
| 379 | `clang` | Clang C/C++ Compiler | Developer | `clang` | `clang` | Terminal | `vice-tool-clang` |
| 380 | `clangd` | Clangd C/C++ Language Server | Developer | `clangd` | `clangd` | Terminal | `vice-tool-clangd` |
| 381 | `lld` | LLD Fast LLVM Linker | Developer | `lld` | `lld` | Terminal | `vice-tool-lld` |
| 382 | `ninja-build` | Ninja Fast Build System | Developer | `ninja-build` | `ninja` | Terminal | `vice-tool-ninja-build` |
| 383 | `pkg-config` | pkg-config Library Resolver | Developer | `pkg-config` | `pkg-config` | Terminal | `vice-tool-pkg-config` |
| 384 | `python3-pip` | Python pip3 Package Manager | Developer | `python3-pip` | `pip3` | Terminal | `vice-tool-python3-pip` |
| 385 | `ipython3` | IPython Interactive Shell | Developer | `ipython3` | `ipython3` | Terminal | `vice-tool-ipython3` |
| 386 | `rustc` | Rust Compiler (rustc) | Developer | `rustc` | `rustc` | Terminal | `vice-tool-rustc` |
| 387 | `cargo` | Cargo Rust Package Manager | Developer | `cargo` | `cargo` | Terminal | `vice-tool-cargo` |
| 388 | `rustfmt` | Rustfmt Code Formatter | Developer | `rustfmt` | `rustfmt` | Terminal | `vice-tool-rustfmt` |
| 389 | `nodejs` | Node.js 22 LTS Runtime | Developer | `nodejs` | `node` | Terminal | `vice-tool-nodejs` |
| 390 | `node-typescript` | TypeScript Compiler (tsc) | Developer | `node-typescript` | `tsc` | Terminal | `vice-tool-node-typescript` |
| 391 | `dotnet-sdk-8.0` | .NET 8.0 LTS SDK (C#) | Developer | `dotnet-sdk-8.0` | `dotnet` | Terminal | `vice-tool-dotnet-sdk-8.0` |
| 392 | `golang-go` | Go Compiler & Toolchain | Developer | `golang-go` | `go` | Terminal | `vice-tool-golang-go` |
| 393 | `openjdk-17-jdk-headless` | OpenJDK 17 LTS Compiler | Developer | `openjdk-17-jdk-headless` | `javac` | Terminal | `vice-tool-openjdk-17-jdk-headless` |
| 394 | `php-cli` | PHP CLI Interpreter | Developer | `php-cli` | `php` | Terminal | `vice-tool-php-cli` |
| 395 | `ruby` | Ruby Language Interpreter | Developer | `ruby` | `ruby` | Terminal | `vice-tool-ruby` |
| 396 | `lua5.4` | Lua 5.4 Scripting Shell | Developer | `lua5.4` | `lua5.4` | Terminal | `vice-tool-lua5.4` |
| 397 | `autoconf` | GNU Autoconf | Developer | `autoconf` | `autoconf` | Terminal | `vice-tool-autoconf` |
| 398 | `automake` | GNU Automake | Developer | `automake` | `automake` | Terminal | `vice-tool-automake` |
| 399 | `libtool` | GNU Libtool | Developer | `libtool` | `libtoolize` | Terminal | `vice-tool-libtool` |
| 400 | `meson` | Meson Build System | Developer | `meson` | `meson` | Terminal | `vice-tool-meson` |
| 401 | `ccache` | ccache Compiler Cache | Developer | `ccache` | `ccache` | Terminal | `vice-tool-ccache` |
| 402 | `bear` | Bear Compile Database Tool | Developer | `bear` | `bear` | Terminal | `vice-tool-bear` |
| 403 | `astyle` | Artistic Style Formatter | Developer | `astyle` | `astyle` | Terminal | `vice-tool-astyle` |
| 404 | `universal-ctags` | Universal Ctags Indexer | Developer | `universal-ctags` | `ctags-universal` | Terminal | `vice-tool-universal-ctags` |
| 405 | `shfmt` | shfmt Shell Formatter | Developer | `shfmt` | `shfmt` | Terminal | `vice-tool-shfmt` |
| 406 | `yamllint` | yamllint YAML Validator | Developer | `yamllint` | `yamllint` | Terminal | `vice-tool-yamllint` |
| 407 | `codespell` | Codespell Source Checker | Developer | `codespell` | `codespell` | Terminal | `vice-tool-codespell` |
| 408 | `python3-pytest` | Pytest Python Test Runner | Developer | `python3-pytest` | `pytest` | Terminal | `vice-tool-python3-pytest` |
| 409 | `python3-flake8` | Flake8 Python Linter | Developer | `python3-flake8` | `flake8` | Terminal | `vice-tool-python3-flake8` |
| 410 | `black` | Black Python Formatter | Developer | `black` | `black` | Terminal | `vice-tool-black` |
| 411 | `pylint` | Pylint Static Analyzer | Developer | `pylint` | `pylint` | Terminal | `vice-tool-pylint` |
| 412 | `pipx` | pipx Isolated CLI Runner | Developer | `pipx` | `pipx` | Terminal | `vice-tool-pipx` |
| 413 | `dos2unix` | dos2unix Line-Ending Tool | Developer | `dos2unix` | `dos2unix` | Terminal | `vice-tool-dos2unix` |
| 414 | `colordiff` | Colordiff Unified Diff | Developer | `colordiff` | `colordiff` | Terminal | `vice-tool-colordiff` |
| 415 | `capstone-tool` | Capstone Disassembler CLI | Developer | `capstone-tool` | `cstool` | Terminal | `vice-tool-capstone-tool` |
| 416 | `i2c-tools` | I2C Bus Hardware Probe | System | `i2c-tools` | `i2cdetect` | Terminal | `vice-tool-i2c-tools` |
| 417 | `edid-decode` | EDID Display Timing Decoder | System | `edid-decode` | `edid-decode` | Terminal | `vice-tool-edid-decode` |
| 418 | `v4l-utils` | Video4Linux Camera Control | Media | `v4l-utils` | `v4l2-ctl` | Terminal | `vice-tool-v4l-utils` |
| 419 | `brightnessctl` | Backlight Brightness Control | System | `brightnessctl` | `brightnessctl` | Terminal | `vice-tool-brightnessctl` |
| 420 | `efibootmgr` | UEFI Boot Manager CLI | System | `efibootmgr` | `efibootmgr` | Terminal | `vice-tool-efibootmgr` |
| 421 | `mokutil` | UEFI Secure Boot MOK CLI | Security | `mokutil` | `mokutil` | Terminal | `vice-tool-mokutil` |
| 422 | `tpm2-tools` | TPM 2.0 Security Tools | Security | `tpm2-tools` | `tpm2` | Terminal | `vice-tool-tpm2-tools` |
| 423 | `sysbench` | Sysbench CPU & Memory Bench | System | `sysbench` | `sysbench` | Terminal | `vice-tool-sysbench` |
| 424 | `fio` | FIO Storage I/O Benchmarker | Files & Disk | `fio` | `fio` | Terminal | `vice-tool-fio` |
| 425 | `nghttp2-client` | nghttp HTTP/2 Analyzer | Network | `nghttp2-client` | `nghttp` | Terminal | `vice-tool-nghttp2-client` |

---

## Batch 4 Roadmap (`425 / 500` -> `500 / 500`)

| Batch | Cumulative Target | Planned Focus |
| --- | --- | --- |
| **Batch 1 (Complete)** | **100 / 500 (20%)** | 10 GTA VI Native Apps + 90 Core Debian Bookworm Power Tools (`vice-tool-hub`, `vice-run-tool`, 64x64 GTA VI icons) |
| **Batch 2 (Complete)** | **250 / 500 (50%)** | +5 GTA VI Native Apps (Net Shield, Cyber Deck, Privacy Cloak, Office Studio, Clock Sync) + LibreOffice Suite + 140 Verified Bookworm Cybersecurity, VPN/Tor/DNS, and Standard Debian Tools |
| **Batch 3 (Complete)** | **375 / 500 (75%)** | +2 GTA VI Native Apps (`vice-tool-fetch`, `vice-tool-payload-lab`) + 123 Verified Lean Kali Linux Recon, Web, Cracking, Wireless, MITM, Forensics, Reversing & Crypto Tools |
| **Batch 4A (Complete)** | **425 / 500 (85%)** | +1 Native Utility (`vice-tool-hw-autodetect`) + Official VS Code, .NET 8.0 LTS, Node.js 22 LTS + Multi-Language Compilers, Universal Firmware & 29 Lean Dev/HW Diagnostics Tools |
| **Batch 4B (Planned)** | **500 / 500 (100%)** | +2–4 GTA VI Finale Native Apps + ~72 Container/VM, Science, Media, Security & Automation Tools completing full 500/500 catalog |
