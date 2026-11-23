# Vice OS Tools Progress (`250 / 500`)

**Overall Progress:** **250 / 500 (50%)** — Batch 2 Complete
**Theme:** GTA VI Leonida Sunset (`config/tools_registry.json` & `desktop/vice_theme.py`)
**Target Suite:** Debian 12 (Bookworm `main`) + Native PyQt5 Vice OS Originals

```text
Progress: [##########..........] 250 / 500 (50%)
Batch 1 : [####################] 100 / 100 (Complete)
Batch 2 : [####################] 150 / 150 (Complete)
```

---

## Category Breakdown (Batch 2 Cumulative)

| Category | Count | Native / Curated | Notes |
| --- | ---: | --- | --- |
| GTA VI Originals | 15 | 15 `vice-native` GUI apps | Bespoke Leonida Sunset PyQt5 suite (`vice_tool_*.py` on `vice_theme.py`) |
| Office | 10 | 10 Debian Bookworm tools | LibreOffice Writer/Calc/Impress/Draw/Math (GTK3 themed), qpdfview, Evince, Simple Scan, Poppler, Hunspell |
| System | 32 | 32 Debian Bookworm tools | Monitors, hardware probes, Printers (`system-config-printer`), Bluetooth (`blueman`/`bluez`), Timeshift, Chrony |
| Network | 44 | 44 Debian Bookworm tools | Wireshark, Nmap, DNS recon/DoT (`stubby`/`unbound`), packet dissectors, SSH/Mosh, bandwidth monitors |
| Security | 55 | 55 Debian Bookworm tools | OpenVPN, WireGuard, Tor/Privoxy/ProxyChains, UFW/GUFW/nftables, ClamAV, Firejail, pentest & forensics suites |
| Developer | 32 | 32 Debian Bookworm tools | Compilers, reverse engineering (`gdb-multiarch`/`nasm`/`binutils`/`elfutils`), hex editors, linters, SQLite |
| Files & Disk | 24 | 24 Debian Bookworm tools | GNOME Disks, NTFS/exFAT/FAT/Btrfs tools, LUKS `cryptsetup`, S.M.A.R.T., NVMe, recovery, and rsync GUIs |
| Media | 20 | 20 Debian Bookworm tools | FFmpeg, mpv, Celluloid, PipeWire mixer, Flameshot, Gcolor3, EasyTAG, image optimizers, and EXIF tools |
| Productivity | 18 | 18 Debian Bookworm tools | Firefox ESR, Zim, CherryTree, SpeedCrunch, Qalculate!, Galculator, Calcurse, Taskwarrior, tldr, archivers |
| **Total** | **250** | **15 Native + 235 Debian** | **All 250 receive custom 64x64 GTA VI icons** |

---

## Batch 2 Highlights (ISO #10)

- **5 New Native GTA VI PyQt5 Applications (`vice_theme.py` Design System)**:
  - `vice-tool-net-shield`: OpenVPN / WireGuard / Tor / Privoxy / Secure DNS & UFW Shield Console.
  - `vice-tool-cyber-deck`: Ethical recon & security workbench (`nmap`, `sslscan`, `dnsrecon`, `lynis`, `binwalk`, `yara`).
  - `vice-tool-mac-cloak`: Interface MAC spoofer, active connection watchdog, and `exiftool`/`mat2` metadata scrubber.
  - `vice-tool-office-hub`: Unified GTA VI Office Studio for LibreOffice apps, recent docs, and Dark/Light LibreOffice mode.
  - `vice-tool-clock-sync`: Live host/internet timezone sync (`vice-timesync`), searchable IANA timezone picker, and Chrony telemetry.
- **Debian LibreOffice Suite**: `libreoffice-writer`, `libreoffice-calc`, `libreoffice-impress`, `libreoffice-draw`, `libreoffice-math` + `libreoffice-gtk3` + `sifr`/`colibre` icon styles, themed with dark GTA VI chrome and crisp white paper sheets, plus GTA VI icon badges in `/usr/share/applications`.
- **Safe Network Defaults**: `tor`, `privoxy`, `stubby`, `unbound`, `openvpn`, `clamav-daemon`, and `clamav-freshclam` remain **disabled by default at boot** so normal browsing works out of the box and users enable privacy tunnels on demand via `Vice Net Shield`.
- **Standard Debian Desktop Essentials**: Printing (`cups`, `system-config-printer`), Bluetooth (`bluez`, `blueman`), Disks & Filesystems (`udisks2`, `gnome-disk-utility`, `ntfs-3g`, `exfatprogs`, `dosfstools`, `btrfs-progs`), Snapshots (`timeshift`), NTP (`chrony`), Screenshots & Color (`flameshot`, `gcolor3`, `redshift`), Portals & Shell (`xdg-desktop-portal-gtk`, `bash-completion`, `zram-tools`, `earlyoom`).

---

## Full Tool Catalog (`250 / 500`)

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
| 118 | `timeshift` | Timeshift System Snapshots | System | `timeshift` | `timeshift-gtk` | GUI | `vice-tool-timeshift` |
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
| 233 | `feh` | feh Fast Image Viewer | Media | `feh` | `feh` | GUI | `vice-tool-feh` |
| 234 | `flameshot` | Flameshot Screenshot GUI | Media | `flameshot` | `flameshot` | GUI | `vice-tool-flameshot` |
| 235 | `gnome-screenshot` | GNOME Screenshot Tool | Media | `gnome-screenshot` | `gnome-screenshot` | GUI | `vice-tool-gnome-screenshot` |
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

---

## Batches 3–4 Roadmap (`375 / 500` -> `500 / 500`)

| Batch | Cumulative Target | Planned Focus |
| --- | --- | --- |
| **Batch 1 (Complete)** | **100 / 500 (20%)** | 10 GTA VI Native Apps + 90 Core Debian Bookworm Power Tools (`vice-tool-hub`, `vice-run-tool`, 64x64 GTA VI icons) |
| **Batch 2 (Current)** | **250 / 500 (50%)** | +5 GTA VI Native Apps (Net Shield, Cyber Deck, Privacy Cloak, Office Studio, Clock Sync) + LibreOffice Suite + 140 Verified Bookworm Cybersecurity, VPN/Tor/DNS, and Standard Debian Tools |
| **Batch 3 (Planned)** | **375 / 500 (75%)** | +5 GTA VI Native Dev/Media Apps (JSON/Regex Studio, Theme Forge, Audio Mixer Pro, Container Deck, Backup Scheduler) + 120 Compilers, Language Toolchains, Container/VM, Database & Creative CLI/GUI Utilities |
| **Batch 4 (Planned)** | **500 / 500 (100%)** | +5 GTA VI Finale Suite Apps + 120 Hardware Diagnostics, Publishing, Accessibility, Science & Automation Tools completing full 500/500 catalog |
