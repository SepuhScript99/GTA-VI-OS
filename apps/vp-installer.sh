#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# Vice OS Physical Installer
# Installs the running Live ISO environment to a physical disk.
# Supports BIOS (Legacy) and UEFI boot modes, optional LUKS2 disk encryption,
# zero data-loss safeguards, user account creation, and post-install hooks.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -f "$WORKDIR/lib/common.sh" ]; then
    source "$WORKDIR/lib/common.sh"
elif [ -f "/usr/local/lib/common.sh" ]; then
    source "/usr/local/lib/common.sh"
else
    echo "Error: common.sh library not found." >&2
    exit 1
fi
install_cleanup

LOCKFILE="/var/lock/vice-installer.lock"

# --- Cleanup Handler ---
cleanup() {
    local exit_code=$?

    # Release the flock lock
    if [ -f "$LOCKFILE" ]; then
        rm -f "$LOCKFILE" 2>/dev/null || true
    fi

    log_info "Cleaning up mounts..."
    # Ensure DNS resolv.conf inside target has fallback nameservers
    if mountpoint -q /mnt 2>/dev/null; then
        if [ ! -s /mnt/etc/resolv.conf ]; then
            cat <<'RESOLV' > /mnt/etc/resolv.conf 2>/dev/null || true
nameserver 1.1.1.1
nameserver 8.8.8.8
RESOLV
        fi
    fi

    # Unmount target partitions in reverse order
    if mountpoint -q /mnt/boot/efi 2>/dev/null; then
        umount /mnt/boot/efi 2>/dev/null || true
    fi
    if mountpoint -q /mnt/boot 2>/dev/null; then
        umount /mnt/boot 2>/dev/null || true
    fi
    if mountpoint -q /mnt 2>/dev/null; then
        umount -R /mnt 2>/dev/null || true
    fi

    # Close LUKS mapper if open to prevent device locks on subsequent runs
    if [ -e /dev/mapper/vice-root ]; then
        log_info "Closing LUKS device /dev/mapper/vice-root..."
        cryptsetup close vice-root 2>/dev/null || true
    fi

    if [ $exit_code -eq 0 ]; then
        log_success "Installation completed successfully."
    else
        log_error "Installation failed with exit code $exit_code."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Data-Loss Prevention Helpers ---

# Check if a device is the active Live boot media or holds system mounts
is_live_media() {
    local target_disk="$1"
    local dev_name
    dev_name=$(basename "$target_disk")

    # 1. Check known live mount points
    local live_mounts=("/run/live/medium" "/lib/live/mount/medium" "/run/live/rootfs/filesystem.squashfs" "/live/image" "/media/cdrom")
    for mp in "${live_mounts[@]}"; do
        if mountpoint -q "$mp" 2>/dev/null; then
            local live_src
            live_src=$(findmnt -n -o SOURCE "$mp" 2>/dev/null || true)
            if [ -n "$live_src" ]; then
                local live_parent
                live_parent=$(lsblk -no PKNAME "$live_src" 2>/dev/null || true)
                if [ "$live_parent" = "$dev_name" ] || [ "$live_src" = "$target_disk" ]; then
                    return 0
                fi
            fi
        fi
    done

    # 2. Check root filesystem parent disk
    local root_src
    root_src=$(findmnt -n -o SOURCE / 2>/dev/null || true)
    if [ -n "$root_src" ]; then
        local root_parent
        root_parent=$(lsblk -no PKNAME "$root_src" 2>/dev/null || true)
        if [ "$root_parent" = "$dev_name" ] || [ "$root_src" = "$target_disk" ]; then
            return 0
        fi
    fi

    # 3. Check for live ISO label
    if lsblk -no LABEL "$target_disk" 2>/dev/null | grep -qi "VICE_OS"; then
        return 0
    fi

    return 1
}

# Safely unmount all active filesystems and swap partitions on the target disk
safely_unmount_disk() {
    local target_disk="$1"
    log_info "Ensuring no active mounts or swap on $target_disk..."

    # Deactivate swap on all partitions of this disk
    local parts
    parts=$(lsblk -ln -o NAME "$target_disk" 2>/dev/null || true)
    for p in $parts; do
        if [ -b "/dev/$p" ]; then
            swapoff "/dev/$p" 2>/dev/null || true
        fi
    done

    # Unmount mounted partitions in reverse hierarchy order
    local active_mounts
    active_mounts=$(lsblk -ln -o MOUNTPOINT "$target_disk" 2>/dev/null | grep -v '^$' | sort -r || true)
    for mp in $active_mounts; do
        if mountpoint -q "$mp" 2>/dev/null; then
            log_info "Unmounting active mount $mp..."
            umount -f "$mp" 2>/dev/null || umount -l "$mp" 2>/dev/null || {
                log_error "Could not unmount $mp on $target_disk. Aborting to protect filesystem integrity."
                exit 1
            }
        fi
    done
}

# Validate that disk has sufficient capacity for Vice OS
check_disk_capacity() {
    local disk="$1"
    local size_bytes
    size_bytes=$(lsblk -bndo SIZE "$disk" 2>/dev/null || echo 0)
    local min_required_bytes=$((15 * 1024 * 1024 * 1024)) # 15 GiB recommended
    local min_strict_bytes=$((10 * 1024 * 1024 * 1024))   # 10 GiB strict floor

    if [ "$size_bytes" -lt "$min_strict_bytes" ]; then
        log_error "Disk size ($(numfmt --to=iec "$size_bytes" 2>/dev/null || echo "${size_bytes}B")) is below the strict minimum 10GB for Vice OS. Installation aborted."
        exit 1
    elif [ "$size_bytes" -lt "$min_required_bytes" ]; then
        log_warn "Disk size is smaller than recommended (15GB). Installation may run low on disk space."
    fi
}

# Execute custom post-install hooks if directories exist
run_post_install_hooks() {
    local hook_dirs=("/usr/local/apps/post-install.d" "$WORKDIR/apps/post-install.d")
    for hook_dir in "${hook_dirs[@]}"; do
        if [ -d "$hook_dir" ]; then
            log_info "Executing post-install hooks in $hook_dir..."
            for hook in "$hook_dir"/*; do
                if [ -x "$hook" ] && [ -f "$hook" ]; then
                    log_info "Running post-install hook: $(basename "$hook")..."
                    if "$hook" "/mnt" "$DISK"; then
                        log_success "Hook $(basename "$hook") completed successfully."
                    else
                        log_warn "Hook $(basename "$hook") exited with non-zero status."
                    fi
                fi
            done
        fi
    done
}

# --- Main Routine ---
main() {
    if [[ "${1:-}" == "--version" ]]; then
        echo "Vice OS Physical Installer v2.0"
        echo "Installs the live system to a physical disk with full LUKS2 and UEFI/BIOS support."
        exit 0
    fi
    if [[ "${1:-}" == "--help" ]] || [[ "${1:-}" == "-h" ]]; then
        echo "Vice OS Physical Installer v2.0"
        echo ""
        echo "Installs the running Live ISO environment to a physical disk."
        echo "Supports both BIOS (legacy) and UEFI boot modes."
        echo ""
        echo "Usage: sudo $0"
        echo ""
        echo "Features:"
        echo "  - Zero Data-Loss live media detection & protection"
        echo "  - Optional LUKS2 root volume encryption (dedicated /boot partition)"
        echo "  - Clean GPT partition table (ESP for UEFI, bios_grub for BIOS)"
        echo "  - Custom user account creation or 'vice' configuration"
        echo "  - Password-protected sudo configuration & root account locking"
        echo "  - Offline initramfs generation without network dependency"
        echo "  - Unique machine-id & SSH host keys generation"
        echo "  - Post-install hook runner (/usr/local/apps/post-install.d/)"
        exit 0
    fi

    check_root
    check_dependencies "rsync" "parted" "blkid" "chroot" "lsblk" "visudo" "grub-install" "update-grub" "mkfs.fat" "mkfs.ext4" "wipefs"

    # Prevent concurrent installer execution
    exec 9>"$LOCKFILE"
    if ! flock -n 9; then
        log_error "Another installer process is already running. Exiting."
        exit 1
    fi

    # Detect boot mode
    local is_uefi=false
    if [ -d /sys/firmware/efi/efivars ]; then
        is_uefi=true
        log_info "UEFI boot mode detected."
    else
        log_info "BIOS (Legacy) boot mode detected."
    fi

    # --- Disk Selection ---
    log_info "Scanning available disks..."
    echo ""
    printf "%-12s %-10s %-20s %-10s %s\n" "NAME" "SIZE" "MODEL" "TYPE" "STATUS"
    echo "----------------------------------------------------------------------"
    while IFS= read -r line; do
        local d_name d_size d_model d_type
        d_name=$(echo "$line" | awk '{print $1}')
        d_size=$(echo "$line" | awk '{print $2}')
        d_type=$(echo "$line" | awk '{print $NF}')
        d_model=$(echo "$line" | awk '{$1=""; $2=""; $NF=""; print $0}' | sed 's/^[ \t]*//;s/[ \t]*$//')

        local status=""
        if is_live_media "/dev/$d_name"; then
            status="[LIVE BOOT MEDIA - PROTECTED]"
        fi
        printf "%-12s %-10s %-20s %-10s %s\n" "$d_name" "$d_size" "$d_model" "$d_type" "$status"
    done < <(lsblk -d -n -o NAME,SIZE,MODEL,TYPE | grep -v loop)
    echo ""

    read -p "Enter the target disk (e.g., sda, nvme0n1): " DISK_NAME
    DISK="/dev/$DISK_NAME"

    if [ ! -b "$DISK" ]; then
        log_error "Disk $DISK does not exist!"
        exit 1
    fi

    # Validate that the input is a whole disk, not a partition
    local disk_type
    disk_type=$(lsblk -ndo TYPE "$DISK" 2>/dev/null || echo "unknown")
    if [ "$disk_type" != "disk" ]; then
        log_error "The selected device ($DISK) is not a whole disk (type: $disk_type). Please select a whole disk (e.g., sda, nvme0n1)."
        exit 1
    fi

    # ZERO DATA-LOSS CHECK: Refuse installation to the live media
    if is_live_media "$DISK"; then
        log_error "CRITICAL: The selected disk ($DISK) is the active Live boot media or contains active system filesystems!"
        log_error "Overwriting this disk would destroy the running live environment. Installation aborted."
        exit 1
    fi

    # Check disk capacity
    check_disk_capacity "$DISK"

    # Explicit destructive action confirmation
    log_warn "===================================================================="
    log_warn "WARNING: ALL DATA ON $DISK WILL BE PERMANENTLY DESTROYED!"
    log_warn "===================================================================="
    read -p "To confirm, please type the disk name ($DISK_NAME) exactly: " CONFIRM
    if [ "$CONFIRM" != "$DISK_NAME" ]; then
        log_error "Confirmation failed. Installation aborted."
        exit 1
    fi

    # --- Encryption Option ---
    local use_encryption=false
    local crypt_pass=""
    local crypt_pass_confirm=""

    read -p "Encrypt root partition with LUKS? (y/N): " enc_choice
    if [ "$enc_choice" = "y" ] || [ "$enc_choice" = "Y" ]; then
        if command -v cryptsetup > /dev/null 2>&1; then
            use_encryption=true
            log_info "LUKS2 disk encryption enabled."
        else
            log_warn "cryptsetup utility not found. Encryption disabled."
            use_encryption=false
        fi
    fi

    if $use_encryption; then
        while true; do
            read -s -p "Enter LUKS passphrase (minimum 8 characters): " crypt_pass
            echo ""
            read -s -p "Confirm LUKS passphrase: " crypt_pass_confirm
            echo ""
            if [ -z "$crypt_pass" ]; then
                log_error "Passphrase cannot be empty."
            elif [ "${#crypt_pass}" -lt 8 ]; then
                log_error "Passphrase must be at least 8 characters long."
            elif [ "$crypt_pass" != "$crypt_pass_confirm" ]; then
                log_error "Passphrases do not match. Please try again."
            else
                break
            fi
        done
    fi

    # Determine partition prefix (e.g. /dev/sda1 vs /dev/nvme0n1p1)
    if [[ "$DISK" =~ [0-9]$ ]]; then
        PART_PREFIX="${DISK}p"
    else
        PART_PREFIX="${DISK}"
    fi

    # Safely deactivate existing swap and unmount any mounted partitions
    safely_unmount_disk "$DISK"

    # --- Partitioning ---
    log_info "Creating partition table on $DISK..."
    parted -s "$DISK" mklabel gpt

    local PART_EFI=""
    local PART_BOOT=""
    local PART_ROOT=""

    if $is_uefi; then
        if $use_encryption; then
            # Layout: ESP (512MB), Boot (1024MB), Root (Rest)
            parted -s "$DISK" mkpart "Vice-ESP" fat32 1MiB 513MiB
            parted -s "$DISK" set 1 esp on
            parted -s "$DISK" mkpart "Vice-Boot" ext4 513MiB 1537MiB
            parted -s "$DISK" mkpart "Vice-Root" 1537MiB 100%

            PART_EFI="${PART_PREFIX}1"
            PART_BOOT="${PART_PREFIX}2"
            PART_ROOT="${PART_PREFIX}3"
        else
            # Layout: ESP (512MB), Root (Rest)
            parted -s "$DISK" mkpart "Vice-ESP" fat32 1MiB 513MiB
            parted -s "$DISK" set 1 esp on
            parted -s "$DISK" mkpart "Vice-Root" ext4 513MiB 100%

            PART_EFI="${PART_PREFIX}1"
            PART_ROOT="${PART_PREFIX}2"
        fi
    else
        if $use_encryption; then
            # Layout: BIOS Boot (2MB), Boot (1024MB), Root (Rest)
            parted -s "$DISK" mkpart "bios_boot" 1MiB 3MiB
            parted -s "$DISK" set 1 bios_grub on
            parted -s "$DISK" mkpart "Vice-Boot" ext4 3MiB 1027MiB
            parted -s "$DISK" mkpart "Vice-Root" 1027MiB 100%

            PART_BOOT="${PART_PREFIX}2"
            PART_ROOT="${PART_PREFIX}3"
        else
            # Layout: BIOS Boot (2MB), Root (Rest)
            parted -s "$DISK" mkpart "bios_boot" 1MiB 3MiB
            parted -s "$DISK" set 1 bios_grub on
            parted -s "$DISK" mkpart "Vice-Root" ext4 3MiB 100%

            PART_ROOT="${PART_PREFIX}2"
        fi
    fi

    # Synchronize partition table with kernel
    log_info "Synchronizing partition table with kernel..."
    partprobe "$DISK" 2>/dev/null || true
    udevadm settle --timeout=10 2>/dev/null || sleep 2

    if [ ! -b "$PART_ROOT" ]; then
        sleep 2
        udevadm settle --timeout=5 2>/dev/null || true
    fi
    if [ ! -b "$PART_ROOT" ]; then
        log_error "Target partition $PART_ROOT did not appear in /dev! Partitioning failed."
        exit 1
    fi

    # Wipe stale filesystem / RAID / LUKS signatures
    log_info "Wiping stale signatures on target partitions..."
    wipefs -a "$PART_ROOT" 2>/dev/null || true
    if [ -n "$PART_BOOT" ] && [ -b "$PART_BOOT" ]; then
        wipefs -a "$PART_BOOT" 2>/dev/null || true
    fi
    if $is_uefi && [ -b "$PART_EFI" ]; then
        wipefs -a "$PART_EFI" 2>/dev/null || true
    fi
    udevadm settle --timeout=5 2>/dev/null || true

    # --- Formatting & LUKS Setup ---
    if $is_uefi; then
        log_info "Formatting EFI System Partition (FAT32)..."
        mkfs.fat -F32 -n "VICE_ESP" "$PART_EFI"
    fi

    if [ -n "$PART_BOOT" ]; then
        log_info "Formatting dedicated boot partition (ext4)..."
        mkfs.ext4 -F -L "VICE_BOOT" "$PART_BOOT"
    fi

    local ROOT_MAPPER=""
    if $use_encryption; then
        ROOT_MAPPER="/dev/mapper/vice-root"
        log_info "Setting up LUKS2 container on $PART_ROOT..."
        echo -n "$crypt_pass" | cryptsetup luksFormat --type luks2 "$PART_ROOT" --batch-mode --key-file=-
        echo -n "$crypt_pass" | cryptsetup open "$PART_ROOT" vice-root --key-file=-
        crypt_pass=""
        crypt_pass_confirm=""

        log_info "Formatting LUKS encrypted root volume (ext4)..."
        mkfs.ext4 -F -L "VICE_ROOT" "$ROOT_MAPPER"
    else
        log_info "Formatting root partition (ext4)..."
        mkfs.ext4 -F -L "VICE_ROOT" "$PART_ROOT"
    fi

    # --- Mounting Filesystems ---
    log_info "Mounting target partitions..."
    if $use_encryption; then
        mount "$ROOT_MAPPER" /mnt
    else
        mount "$PART_ROOT" /mnt
    fi

    if [ -n "$PART_BOOT" ]; then
        mkdir -p /mnt/boot
        mount "$PART_BOOT" /mnt/boot
    fi

    if $is_uefi; then
        mkdir -p /mnt/boot/efi
        mount "$PART_EFI" /mnt/boot/efi
    fi

    # --- System File Copy ---
    log_info "Copying system files to target disk. This may take a while..."
    rsync -aAXv --info=progress2 \
        --exclude={"/dev/*","/proc/*","/sys/*","/tmp/*","/run/*","/mnt/*","/media/*","/lost+found","/live","/vice_payload*","/swapfile","/var/log/*","/var/cache/apt/*","/var/tmp/*","/root/.cache/*","/home/*/.cache/*"} \
        / /mnt/

    # --- Generating /etc/fstab ---
    log_info "Generating /etc/fstab..."
    local root_fs_uuid
    local luks_part_uuid

    if $use_encryption; then
        luks_part_uuid=$(blkid -s UUID -o value "$PART_ROOT")
        cat <<FSTAB > /mnt/etc/fstab
# Vice OS /etc/fstab (LUKS encrypted root)
/dev/mapper/vice-root  /            ext4    defaults,noatime,errors=remount-ro  0  1
tmpfs                  /tmp         tmpfs   defaults,noatime,size=512M          0  0
FSTAB
    else
        root_fs_uuid=$(blkid -s UUID -o value "$PART_ROOT")
        cat <<FSTAB > /mnt/etc/fstab
# Vice OS /etc/fstab
UUID=$root_fs_uuid  /            ext4    defaults,noatime,errors=remount-ro  0  1
tmpfs               /tmp         tmpfs   defaults,noatime,size=512M          0  0
FSTAB
    fi

    if [ -n "$PART_BOOT" ]; then
        local boot_fs_uuid
        boot_fs_uuid=$(blkid -s UUID -o value "$PART_BOOT")
        echo "UUID=$boot_fs_uuid  /boot        ext4    defaults,noatime                    0  2" >> /mnt/etc/fstab
    fi

    if $is_uefi; then
        local efi_uuid
        efi_uuid=$(blkid -s UUID -o value "$PART_EFI")
        echo "UUID=$efi_uuid  /boot/efi   vfat    umask=0077,defaults                 0  1" >> /mnt/etc/fstab
    fi

    # Write /etc/crypttab for LUKS
    if $use_encryption; then
        log_info "Generating /etc/crypttab..."
        echo "vice-root UUID=$luks_part_uuid none luks,discard" > /mnt/etc/crypttab
        chmod 600 /mnt/etc/crypttab
    fi

    # --- Chroot Virtual Filesystem Mounts ---
    log_info "Mounting virtual filesystems for chroot..."
    mount --bind /dev /mnt/dev
    mount --bind /dev/pts /mnt/dev/pts
    mount --bind /proc /mnt/proc
    mount --bind /sys /mnt/sys

    if $is_uefi; then
        mount -t efivarfs efivarfs /mnt/sys/firmware/efi/efivars 2>/dev/null || true
    fi

    # Copy resolv.conf for chroot network/DNS if available
    cp -L /etc/resolv.conf /mnt/etc/resolv.conf 2>/dev/null || true

    # Copy declarative GRUB default if available
    local grub_default_src="$WORKDIR/config/default/grub"
    if [ -f "$grub_default_src" ]; then
        mkdir -p /mnt/etc/default
        cp "$grub_default_src" /mnt/etc/default/grub
    fi

    # --- Bootloader & Initramfs Regeneration ---
    log_info "Configuring bootloader and building initramfs for physical hardware..."
    local arch
    arch=$(uname -m)

    chroot /mnt /bin/bash <<EOF
    export DEBIAN_FRONTEND=noninteractive

    echo "[*] Purging live-boot initramfs hooks to ensure standard physical hardware boot..."
    rm -f /etc/initramfs-tools/hooks/live* /usr/share/initramfs-tools/hooks/live* 2>/dev/null || true
    rm -f /etc/initramfs-tools/scripts/live* /usr/share/initramfs-tools/scripts/live* 2>/dev/null || true

    echo "[*] Ensuring GRUB default configuration exists..."
    if [ ! -f /etc/default/grub ]; then
        cat <<GRUBCFG > /etc/default/grub
GRUB_TIMEOUT=5
GRUB_DISTRIBUTOR="Vice OS"
GRUB_CMDLINE_LINUX_DEFAULT="quiet"
GRUB_CMDLINE_LINUX=""
GRUBCFG
    fi

    echo "[*] Installing GRUB bootloader..."
    if $is_uefi; then
        efi_target="x86_64-efi"
        if [ "$arch" = "aarch64" ] || [ "$arch" = "arm64" ]; then
            efi_target="arm64-efi"
        fi
        grub-install --target="\$efi_target" --efi-directory=/boot/efi --bootloader-id=VICE_OS --removable
    else
        grub-install --target=i386-pc "$DISK"
    fi

    echo "[*] Updating GRUB menu configuration..."
    update-grub

    echo "[*] Regenerating initramfs for physical hardware..."
    update-initramfs -u -k all || update-initramfs -c -k all
EOF

    # --- Post-Install Hardening & Cleanups ---
    log_info "Applying post-install security and configuration hooks..."

    # 1. Reset machine-id
    log_info "Initializing unique system machine-id..."
    rm -f /mnt/etc/machine-id /mnt/var/lib/dbus/machine-id 2>/dev/null || true
    chroot /mnt systemd-machine-id-setup 2>/dev/null || true

    # 2. Regenerate SSH host keys
    if [ -d /mnt/etc/ssh ]; then
        log_info "Regenerating unique SSH host keys..."
        rm -f /mnt/etc/ssh/ssh_host_*_key* 2>/dev/null || true
        chroot /mnt ssh-keygen -A 2>/dev/null || true
    fi

    # 3. Remove live-only udev rules
    log_info "Removing Live ISO specific udev rules..."
    rm -f /mnt/etc/udev/rules.d/90-live-installer.rules 2>/dev/null || true

    # 4. Hostname Configuration
    echo ""
    read -p "Enter system hostname [default: vice-os]: " NEW_HOSTNAME
    NEW_HOSTNAME="${NEW_HOSTNAME:-vice-os}"
    echo "$NEW_HOSTNAME" > /mnt/etc/hostname
    if grep -q "127.0.1.1" /mnt/etc/hosts 2>/dev/null; then
        sed -i "s|127.0.1.1.*|127.0.1.1\t$NEW_HOSTNAME|g" /mnt/etc/hosts
    else
        echo -e "127.0.1.1\t$NEW_HOSTNAME" >> /mnt/etc/hosts
    fi
    log_info "Configured hostname: $NEW_HOSTNAME"

    # 5. Autologin Configuration
    read -p "Enable automatic desktop login without password prompt? (y/N): " autologin_choice
    local enable_autologin=false
    if [[ "$autologin_choice" =~ ^[Yy]$ ]]; then
        enable_autologin=true
        log_info "Auto-login will be enabled."
    else
        log_info "Disabling automatic login (requiring password at login)..."
        rm -f /mnt/etc/systemd/system/getty@tty1.service.d/override.conf 2>/dev/null || true
    fi

    # 6. User Account Creation & Password Configuration
    echo ""
    log_info "--- User Account Setup ---"
    local TARGET_USER="vice"
    read -p "Install with default user 'vice' or create a custom user? [press Enter for 'vice']: " custom_user
    if [ -n "$custom_user" ] && [ "$custom_user" != "vice" ]; then
        if [[ "$custom_user" =~ ^[a-z_][a-z0-9_-]*$ ]]; then
            TARGET_USER="$custom_user"
            log_info "Creating user '$TARGET_USER'..."
            chroot /mnt useradd -m -s /bin/bash -G sudo,audio,video,plugdev,netdev,cdrom,dip "$TARGET_USER" 2>/dev/null || true
            if [ -d /mnt/home/vice/.config ]; then
                mkdir -p "/mnt/home/$TARGET_USER/.config"
                cp -r /mnt/home/vice/.config/* "/mnt/home/$TARGET_USER/.config/" 2>/dev/null || true
                chroot /mnt chown -R "$TARGET_USER:$TARGET_USER" "/home/$TARGET_USER"
            fi
            if $enable_autologin && [ -f /mnt/etc/systemd/system/getty@tty1.service.d/override.conf ]; then
                sed -i "s|--autologin vice|--autologin $TARGET_USER|g" /mnt/etc/systemd/system/getty@tty1.service.d/override.conf
            fi
        else
            log_warn "Invalid username '$custom_user'. Falling back to 'vice'."
            TARGET_USER="vice"
        fi
    fi

    # Set User Password (piped securely to chpasswd without shell injection)
    while true; do
        read -s -p "Enter password for '$TARGET_USER' (leave blank to keep 'vice' if user is vice): " USER_PASS
        echo ""
        if [ -n "$USER_PASS" ]; then
            read -s -p "Confirm password: " USER_PASS_CONFIRM
            echo ""
            if [ "$USER_PASS" = "$USER_PASS_CONFIRM" ]; then
                printf '%s\n' "$TARGET_USER:$USER_PASS" | chroot /mnt chpasswd
                USER_PASS=""
                USER_PASS_CONFIRM=""
                log_info "Password for '$TARGET_USER' set successfully."
                break
            else
                log_error "Passwords do not match. Please try again."
            fi
        elif [ "$TARGET_USER" = "vice" ]; then
            log_warn "Keeping default password 'vice'."
            break
        else
            log_error "Password cannot be empty for custom user '$TARGET_USER'."
        fi
    done

    # Secure sudoers configuration
    log_info "Configuring sudo privileges for '$TARGET_USER'..."
    cat <<SUDOERS > "/mnt/etc/sudoers.d/$TARGET_USER"
Defaults env_reset
Defaults env_keep += "LANG LC_*"
Defaults secure_path="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
$TARGET_USER ALL=(ALL:ALL) ALL
SUDOERS
    chown root:root "/mnt/etc/sudoers.d/$TARGET_USER"
    chmod 440 "/mnt/etc/sudoers.d/$TARGET_USER"

    if [ "$TARGET_USER" != "vice" ] && [ -f /mnt/etc/sudoers.d/vice ]; then
        rm -f /mnt/etc/sudoers.d/vice
    fi

    if ! chroot /mnt visudo -cf "/etc/sudoers.d/$TARGET_USER" > /dev/null 2>&1; then
        log_error "Syntax error in /etc/sudoers.d/$TARGET_USER! Aborting."
        exit 1
    fi

    # Set or lock Root password
    while true; do
        read -s -p "Enter a new root password (leave blank to lock root account): " ROOT_PASS
        echo ""
        if [ -n "$ROOT_PASS" ]; then
            read -s -p "Confirm root password: " ROOT_PASS_CONFIRM
            echo ""
            if [ "$ROOT_PASS" = "$ROOT_PASS_CONFIRM" ]; then
                printf '%s\n' "root:$ROOT_PASS" | chroot /mnt chpasswd
                ROOT_PASS=""
                ROOT_PASS_CONFIRM=""
                log_info "Root password set successfully."
                break
            else
                log_error "Passwords do not match. Please try again."
            fi
        else
            chroot /mnt passwd -l root > /dev/null 2>&1 || true
            log_info "Root account locked (sudo is configured for '$TARGET_USER')."
            break
        fi
    done

    # 7. Execute custom post-install hooks
    run_post_install_hooks

    # Cleanup is handled automatically by the trap handler
}

main "$@"
