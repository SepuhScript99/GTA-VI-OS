# Vice OS Tools Progress (`100 / 500`)

**Overall Progress:** **100 / 500 (20%)** — Batch 1 Complete
**Theme:** GTA VI Leonida Neon (`config/tools_registry.json`)
**Target Suite:** Debian 12 (Bookworm) + Native PyQt5 Vice OS Originals

```text
Progress: [####................] 100 / 500 (20%)
Batch 1 : [####################] 100 / 100 (Complete)
```

---

## Category Breakdown (Batch 1)

| Category | Count | Native / Curated | Notes |
| --- | ---: | --- | --- |
| GTA VI Originals | 10 | 10 `vice-native` GUI apps | Bespoke Leonida Neon PyQt5 suite (`vice_tool_*.py`) |
| System | 16 | 16 Debian Bookworm tools | Process, I/O, hardware, sensors, and cleanup tools |
| Network | 16 | 16 Debian Bookworm tools | Scanners, packet capture, DNS, HTTP, and throughput tools |
| Security | 12 | 12 Debian Bookworm tools | Crypto, rootkit/audit scanners, firewall, and password safes |
| Developer | 15 | 15 Debian Bookworm tools | Editors, search, Git, debuggers, profilers, and linters |
| Files & Disk | 13 | 13 Debian Bookworm tools | Disk usage, partitioning, S.M.A.R.T., recovery, and file managers |
| Media | 10 | 10 Debian Bookworm tools | Audio/video transcoders, players, codecs, and EXIF tools |
| Productivity | 8 | 8 Debian Bookworm tools | QR generator, editors, calculator, PDF, diff, and archivers |
| **Total** | **100** | **10 Native + 90 Debian** | **All 100 receive custom 64x64 GTA VI icons** |

---

## Batch 1 Full Tool Catalog (`100 / 500`)

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
| 97 | `qpdfview` | qpdfview Document Viewer | Productivity | `qpdfview` | `qpdfview` | GUI | `vice-tool-qpdfview` |
| 98 | `file-roller` | File Roller Archive GUI | Productivity | `file-roller` | `file-roller` | GUI | `vice-tool-file-roller` |
| 99 | `p7zip-full` | 7-Zip CLI Archiver (7z) | Productivity | `p7zip-full` | `7z` | Terminal | `vice-tool-p7zip-full` |
| 100 | `meld` | Meld Visual Diff & Merge | Productivity | `meld` | `meld` | GUI | `vice-tool-meld` |

---

## Batches 2–5 Roadmap (`200 / 500` -> `500 / 500`)

| Batch | Cumulative Target | Planned Focus |
| --- | --- | --- |
| **Batch 1 (Current)** | **100 / 500 (20%)** | 10 GTA VI Leonida Neon Native Apps + 90 Core Debian Bookworm Power Tools (`vice-tool-hub`, `vice-run-tool`, custom 64x64 GTA VI icons) |
| **Batch 2** | **200 / 500 (40%)** | +10 GTA VI Native Utilities (Wi-Fi/VPN Deck, Port Guard, Log Sentinel, Snapshot Vault, Disk Benchmark Pro) + 90 Networking, Forensics, Container & Observability CLI/GUI tools (`bmon`/`ethtool`/`arp-scan`/`fping`/`aria2`/`cloc`/`hyperfine`/`entr`/`pv`) |
| **Batch 3** | **300 / 500 (60%)** | +10 GTA VI Native Dev/Media Apps (JSON/Regex Studio, Shader/Theme Forge, Audio Mixer Pro, Shortcut Deck) + 90 Compiler, Language Runtime, Database & Reverse-Engineering utilities |
| **Batch 4** | **400 / 500 (80%)** | +10 GTA VI Native Cloud/Automation Apps + 90 Hardware Diagnostics, Filesystem Recovery, Encryption, Virtualization & Documentation tools |
| **Batch 5** | **500 / 500 (100%)** | +10 GTA VI Finale Suite + 90 Productivity, Accessibility, Office/Publishing, and Creative Pipeline tools completing full 500/500 catalog |
