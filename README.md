# GTA VI OS (Vice OS) — 0.01 Alpha

[![Latest Release](https://img.shields.io/badge/Release-0.01%20Alpha%20(Latest)-FF5E7E?style=for-the-badge&logo=github)](https://github.com/SepuhScript99/GTA-VI-OS/releases/latest)
[![Debian 12 + Kernel 6.12 LTS](https://img.shields.io/badge/Debian%2012-Kernel%206.12%20LTS-36D6C3?style=for-the-badge&logo=debian&logoColor=white)](docs/ARCHITECTURE.md)
[![Tools 425 / 500 (85%)](https://img.shields.io/badge/Tools-425%20%2F%20500%20(85%25)-FF9A62?style=for-the-badge&logo=linux&logoColor=white)](docs/TOOLS_PROGRESS.md)
[![Architecture amd64 (64-bit)](https://img.shields.io/badge/Arch-amd64%20(64--bit)-6C63FF?style=for-the-badge)](docs/INSTALL.md)

**GTA VI OS (Vice OS)** adalah sistem operasi Linux siap pakai berbasis **Debian 12 Bookworm** dengan tema visual **GTA VI (Vice City / Leonida)**. OS ini menggunakan **kernel Linux 6.12 LTS (Debian Backports)**, hadir dengan tampilan modern bersudut melengkung ala Windows 11, dilengkapi **425/500 tools siap pakai** untuk **Coding, Cybersecurity/Kali, Office, dan Multimedia**, serta mendukung **deteksi hardware, audio, dan Wi-Fi secara otomatis**.

Anda bisa mencobanya dengan aman di **VirtualBox** atau **VMware** tanpa mengubah Windows di laptop/PC Anda, atau langsung memasangnya lewat **flashdisk** sebagai sistem operasi utama.

---

## 📥 Cara Download ISO (Untuk Pemula)

### **[⬇️ Download GTA-VI-OS 0.01 Alpha (Latest Release)](https://github.com/SepuhScript99/GTA-VI-OS/releases/latest)**

### Cara Menemukan Halaman Download di GitHub

Jika Anda membuka halaman utama repositori GitHub ini:

1. Lihat ke **panel sebelah kanan (sidebar kanan)** pada bagian **Releases**.
2. Klik **`GTA-VI-OS 0.01 Alpha`** yang memiliki label **`Latest`**.
3. Gulir ke bawah ke bagian **Assets** *(klik tulisan **Assets** jika daftarnya belum terbuka)* untuk mengunduh file ISO.

### Kenapa File ISO Dipecah Menjadi `.part1` dan `.part2`?

Ukuran utuh file ISO **GTA-VI-OS 0.01 Alpha (`Build #16`)** adalah **~2.56 GB** karena sudah berisi sistem operasi lengkap, kernel terbaru, Visual Studio Code + 11 bahasa pemrograman, LibreOffice, Firefox, dan 425 tools siap pakai. Karena GitHub membatasi ukuran maksimal **2 GB per file**, file ISO ini dipecah menjadi **`gta-vi-os-amd64.iso.part1`** dan **`gta-vi-os-amd64.iso.part2`** agar bisa diunduh dengan aman — Anda hanya perlu menggabungkannya kembali dalam 3 langkah mudah.

#### 🪟 Windows (Tanpa Install Aplikasi Tambahan)

1. Download **`gta-vi-os-amd64.iso.part1`**, **`gta-vi-os-amd64.iso.part2`**, dan **`GABUNG-ISO-WINDOWS.bat`** ke **1 folder yang sama** (misalnya semua di folder `Downloads`).
2. **Klik 2x** file **`GABUNG-ISO-WINDOWS.bat`** *(jika muncul peringatan Windows SmartScreen, klik **More info** -> **Run anyway**)*.
3. Tunggu **~15–30 detik** sampai muncul tulisan **`[OK] BERHASIL!`**, maka file **`gta-vi-os-amd64.iso`** sudah terbentuk dan terverifikasi siap dipakai!

*Alternatif cepat lewat Command Prompt (CMD) di folder tempat file tersimpan:*

```bat
copy /b gta-vi-os-amd64.iso.part1 + gta-vi-os-amd64.iso.part2 gta-vi-os-amd64.iso
```

#### 🐧 Linux / 🍎 macOS

1. Download **`gta-vi-os-amd64.iso.part1`**, **`gta-vi-os-amd64.iso.part2`**, dan **`gabung-iso-linux.sh`** ke **1 folder yang sama**.
2. Buka Terminal di folder tersebut, lalu jalankan:

```bash
bash gabung-iso-linux.sh
```

*Atau gabungkan langsung dengan satu perintah:*

```bash
cat gta-vi-os-amd64.iso.part* > gta-vi-os-amd64.iso
```

> **Catatan:** File `SHA256SUMS` dan `build_info.txt` di bagian *Assets* dipakai untuk mengecek keaslian dan info build ISO (skrip `GABUNG-ISO-WINDOWS.bat` dan `gabung-iso-linux.sh` sudah otomatis memverifikasi keutuhan file untuk Anda).

---

## 💻 Spesifikasi Minimum & Rekomendasi

| Komponen | Spesifikasi Minimum | Rekomendasi |
| --- | --- | --- |
| **Prosesor (CPU)** | 64-bit (`amd64` / `x86_64`), 2 Cores | 64-bit, 4 Cores atau lebih |
| **Memori (RAM)** | 4 GB | 8 GB atau lebih |
| **Penyimpanan (Storage)** | 20 GB kosong | 30 GB+ (SSD disarankan) |
| **Layar (Display)** | 1280×720+ | 1920×1080 (Full HD) |
| **Flashdisk (Install PC)** | 4 GB | 8 GB atau lebih |

---

## 🚀 Cara Menjalankan / Install Step-by-Step

### Opsi 1: Di VirtualBox (Paling Aman untuk Coba-Coba — Tidak Mengubah Windows)

1. Buka **Oracle VirtualBox**, klik **New / Baru**.
2. Isi nama VM (misalnya `GTA-VI-OS`), atur **Type:** `Linux`, **Version:** `Debian (64-bit)`. *(Jika muncul layar Unattended Install, centang **Skip Unattended Installation**).*
3. Atur **RAM minimal 4096 MB (4 GB)** dan **2–4 CPU**.
4. Buat **Virtual Hard Disk 30 GB (VDI)**.
5. Buka **Pengaturan / Settings** pada VM yang baru dibuat:
   - **Tampilan / Display**: atur **Video Memory** ke **128 MB**, Graphics Controller **VMSVGA**.
   - **Penyimpanan / Storage**: klik ikon CD (*Empty*) lalu pilih file **`gta-vi-os-amd64.iso`**.
   - **Jaringan / Network**: pilih **NAT** *(internet langsung jalan)* atau **Bridged**.
   - **Suara / Audio**: pastikan opsi **Audio diaktifkan** (*Enable Audio Output*).
6. Klik **Start!** dan tunggu sebentar hingga masuk ke desktop GTA VI OS.

### Opsi 2: Di VMware Workstation / Player

1. Klik **Create a New Virtual Machine**.
2. Pilih **Installer disc image file (iso)** dan arahkan ke file **`gta-vi-os-amd64.iso`**.
3. Pilih **Linux** -> **Debian 12 64-bit** *(atau Debian 64-bit)*.
4. Atur **RAM 4 GB (4096 MB)**, **2–4 CPU**, dan kapasitas disk **30 GB**.
5. Klik **Power On** (`open-vm-tools` otomatis aktif sehingga resolusi layar dan clipboard langsung menyesuaikan).

### Opsi 3: Install di PC / Laptop Pakai Flashdisk (Rufus / BalenaEtcher)

1. Siapkan **flashdisk minimal 4 GB / 8 GB** *(cadangkan dulu data di dalamnya karena isi flashdisk akan terhapus)*.
2. Tulis file **`gta-vi-os-amd64.iso`** ke flashdisk menggunakan **[Rufus](https://rufus.ie/)** (mode DD/ISO) atau **[BalenaEtcher](https://etcher.balena.io/)**.
3. Colokkan flashdisk, restart PC/laptop, lalu tekan tombol **Boot Menu** (`F12`, `F2`, `Del`, atau `Esc` tergantung merek perangkat) dan pilih flashdisk tersebut. ISO ini mendukung booting **UEFI & Legacy BIOS hybrid**.
4. Saat masuk Live session, **Wi-Fi, Audio, GPU, dan USB auto-mount** sudah berjalan otomatis.
5. Jika ingin **install permanen ke SSD/HDD** (mendukung partisi otomatis dan enkripsi **LUKS2** opsional), buka **Terminal** lalu jalankan:

```bash
sudo vp-installer.sh
```

---

## 🔑 Login Default & Tur Singkat Pertama Kali Masuk

Pada mode Live ISO, sistem langsung masuk ke desktop secara **auto-login** tanpa meminta password. Jika layar terkunci atau sistem meminta otorisasi admin:

- **Username:** `vice`
- **Password:** `vice`
- **Password `sudo` (Admin):** `vice`

### Aplikasi Utama yang Langsung Bisa Dicoba

| Aplikasi / Tombol | Kegunaan untuk Pengguna |
| --- | --- |
| **Tombol Menu / `Super`** | Membuka menu utama & **Applications Launcher** tampilan grid penuh yang lebar, rapi, dan mudah dicari. |
| **`Vice Tool Hub`** | Pusat **425 / 500 tools** siap pakai (Coding, Cybersecurity/Kali, Network, System, Office, Multimedia). |
| **`Vice OS Settings`** | **29 panel pengaturan langsung** (Display, Audio, Wi-Fi/VPN, Bluetooth, Firewall, Waktu, Storage/USB, Updates, Kernel, Power, Users, Printers, dll.). |
| **`Vice OS Fetch`** | Menampilkan informasi sistem, kernel, hardware, dan tema GTA VI secara ringkas di terminal. |
| **`Visual Studio Code`** | Sudah memakai tema **Leonida Dusk** tanpa layar welcome biru dan siap coding **C, C++, C# (.NET 8), Python, Rust, Node.js 22 + TypeScript, Go, Java 17, PHP, Ruby, dan Lua**. |
| **`LibreOffice`** | Paket aplikasi perkantoran (*Writer, Calc, Impress*) untuk membuka dan mengedit dokumen Word, Excel, serta presentasi. |
| **`Firefox`** | Browser web **Firefox ESR** siap pakai untuk internet dan riset harian. |
| **`Vice World Clock & Calendar`** | Jam dunia, kalender interaktif, dan sinkronisasi waktu otomatis dengan host/internet. |

---

## ✨ Ringkasan Fitur Utama GTA-VI-OS 0.01 Alpha

| Kategori | Ringkasan Kemampuan |
| --- | --- |
| **Basis OS & Kernel** | Berbasis **Debian 12 Bookworm** dengan kernel **Linux 6.12 LTS** dan firmware terbaru dari `bookworm-backports`, plus update keamanan otomatis via `unattended-upgrades`. |
| **Tampilan Desktop** | Dual-session **X11 (Openbox + `picom`)** & **Wayland (`labwc`)**, jendela sudut melengkung ala Windows 11, tema **Leonida Coastal Dusk**, taskbar modern, dan **Applications Launcher** full-width `AppCard` grid. |
| **Pengaturan Lengkap** | **Vice OS Settings** (`1080×680`) dengan **29 halaman kontrol langsung** (*real-time* ke sistem Linux, tanpa tombol stub), termasuk kontrol volume PipeWire `0–100%` dan pengaturan USB auto-mount. |
| **425 / 500 Tools Siap Pakai** | **18 aplikasi original Vice OS** (`Vice Tool Hub`, `Leonida FM Radio` 9 stasiun + pemutar folder lokal, `Vice Turbo Mode` telemetry & governor/ZRAM/renice asli, `Net Radar`, `Net Shield`, `Cyber Deck`, `Vault`, dll.) + **407 tools Debian/Kali/Dev** dengan ikon kustom 64×64. |
| **Stack Coding Lengkap** | **VS Code**, `gcc`/`g++`/`clang`, **.NET 8.0 SDK (C#)**, **Python 3.11** (`pip`, `pytest`, `flake8`), **Rust** (`rustc`, `cargo`), **Node.js 22 LTS + TypeScript (`tsc`)**, **Go**, **OpenJDK 17**, **PHP 8.2**, **Ruby**, dan **Lua 5.4**. |
| **Perkantoran & Media** | **LibreOffice** tema gelap yang nyaman dibaca, **Firefox ESR**, **mpv**, **Celluloid**, **Flameshot**, serta audio **PipeWire + WirePlumber**. |
| **Hardware & Auto-Mount** | Deteksi hardware native Linux (`systemd-udevd`, `udisks2`, `NetworkManager`, `rfkill`), auto-mount/auto-play via `thunar-volman` + `gvfs-fuse` + `mtp-tools` + `usbmuxd` + `fwupd` + `dkms`, serta dukungan VM otomatis (`open-vm-tools`, `qemu-guest-agent`, `spice-vdagent`). |
| **Keamanan & Pemulihan** | Installer disk **`vp-installer.sh`** dengan opsi enkripsi **LUKS2**, firewall **UFW**, **fail2ban**, dan menu recovery **`vice-recovery.sh`** (perbaikan GRUB, reset password, cek disk, dan restore tema). |

---

## ❓ FAQ Singkat Pemula

<details>
<summary><strong>1. Apakah aman menghapus file ISO lama setelah dipakai di VirtualBox?</strong></summary>

Ya, **100% aman**. Menghapus atau melepas file `.iso` lama setelah VM dimatikan (atau menggantinya di *Settings -> Storage* VirtualBox) tidak akan merusak sistem Windows di komputer Anda. Jika Anda sudah melakukan install permanen ke Virtual Hard Disk (VDI 30 GB), file ISO tidak lagi diperlukan untuk menyalakan VM. Jika Anda masih memakai mode Live CD, cukup arahkan *Storage* VirtualBox ke file `.iso` versi yang terbaru.

</details>

<details>
<summary><strong>2. Kenapa ukuran ISO sekitar 2,56 GB dan harus dipecah jadi <code>.part1</code> dan <code>.part2</code>?</strong></summary>

Karena ISO GTA VI OS langsung menyertakan sistem operasi Debian 12 lengkap, kernel Linux 6.12 LTS beserta driver Wi-Fi/GPU/Audio, Visual Studio Code + 11 bahasa pemrograman, LibreOffice, Firefox, dan 425 tools siap pakai tanpa mengharuskan Anda mengunduh ratusan paket manual setelah install. GitHub Releases memiliki batas maksimal ukuran **2 GB per file**, sehingga file `~2.56 GB` ini dipecah menjadi `.part1` dan `.part2` dengan skrip penggabung satu klik (`GABUNG-ISO-WINDOWS.bat` / `gabung-iso-linux.sh`) yang juga mengecek keaslian checksum `SHA256`.

</details>

<details>
<summary><strong>3. Bagaimana cara update kernel dan sistem di masa depan?</strong></summary>

GTA VI OS sudah dikonfigurasi menggunakan repositori **`bookworm-backports`** (diprioritaskan khusus untuk paket `linux-image-*`, `linux-headers-*`, `firmware-*`, dan CPU microcode dengan `Pin-Priority: 550`) serta **`unattended-upgrades`** untuk pembaruan keamanan otomatis. Setelah di-install, Anda bisa memperbarui kernel dan sistem kapan saja melalui menu **Vice OS Settings -> Updates** atau lewat Terminal:

```bash
sudo apt update && sudo apt upgrade
```

</details>

---

## 🛠️ Build Sendiri (Untuk Developer)

Jika Anda ingin membangun image ISO langsung dari source di host **Debian / Ubuntu**:

### Kebutuhan Paket Host

`debootstrap`, `debian-archive-keyring`, `grub-common`, `grub2-common`, `grub-pc-bin`, `grub-efi-amd64-bin`, `xorriso`, `squashfs-tools`, `mtools`, `dosfstools`, `curl`, `genisoimage`.

### Perintah Build & Pengujian

```bash
git clone https://github.com/SepuhScript99/GTA-VI-OS.git
cd GTA-VI-OS

sudo bash build_iso.sh          # Build normal (memanfaatkan cache/state jika tersedia)
sudo bash build_iso.sh --clean  # Build bersih dari awal (menghapus chroot cache)
```

Hasil build tersimpan di **`out/gta-vi-os-amd64.iso`** (beserta `out/SHA256SUMS` dan `out/build_info.txt`).

Untuk menjalankan validasi paket dan test suite secara lokal:

```bash
bash validation/validate_packages.sh
bash tests/run_all_tests.sh
python3 -m unittest discover -s tests -v
```

---

## 📁 Struktur Proyek

```text
apps/             Skrip installer aplikasi (vp-installer.sh dengan LUKS2, Docker, VS Code)
assets/           Generator aset visual, tema icon & launcher 425/500 tools (2 skrip Python)
build/            Pipeline pembuatan ISO (4 skrip modular: rootfs, bootloader, squashfs, pack)
chroot_scripts/   Skrip konfigurasi chroot Debian 12 (49 skrip bernomor urut)
config/           Konfigurasi deklaratif (apt backports, packages.list, tools_registry.json, libfm, polkit-1, skel, systemd, themes, X11, labwc)
desktop/          Lingkungan desktop PyQt5 (95 modul Python — shell, launcher, settings 29 panel, 16 native tools)
docs/             Dokumentasi lengkap proyek (20 dokumen, termasuk CHANGELOG.md & TOOLS_PROGRESS.md)
lib/              Library bersama untuk Bash dan Python
recovery/         Utilitas pemulihan sistem & watchdog (6 skrip)
scripts/          Otomasi rilis
system_scripts/   Skrip sistem & layanan inti (11 skrip, termasuk vice-run-tool.sh & vice-hw-autodetect.sh)
system_utils/     Utilitas manajemen sistem (47 skrip Bash + 1 utilitas Python)
tests/            Test suite terotomasi (unit, integrasi, build pipeline, chroot, validation, QEMU smoke test)
validation/       Skrip validasi artefak build (6 skrip termasuk validate_iso.sh berbasis xorriso)
```

Dokumentasi lanjutan untuk kontributor: [docs/CHANGELOG.md](docs/CHANGELOG.md) · [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [docs/INSTALL.md](docs/INSTALL.md) · [docs/TOOLS_PROGRESS.md](docs/TOOLS_PROGRESS.md) · [CONTRIBUTING.md](CONTRIBUTING.md)

---

## 📄 Lisensi

Proyek ini dirilis di bawah lisensi **GNU General Public License v2.0 (GPLv2)**. Lihat file [LICENSE](LICENSE) untuk detail lengkap.
