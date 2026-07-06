#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# Vice OS Physical Installer
# Installs the live system to a physical disk, supporting BIOS and UEFI.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Source Shared Library ---
if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found. Cannot continue." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

LOCKFILE="/var/lock/vice-installer.lock"

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    
    # Release the lock
    if [ -f "$LOCKFILE" ]; then
        rm -f "$LOCKFILE"
    fi
    
    log_info "Cleaning up mounts..."
    # Remove temporary resolv.conf to prevent host DNS leakage
    if mountpoint -q /mnt; then
        rm -f /mnt/etc/resolv.conf 2>/dev/null || true
    fi
    
    # Use recursive unmount to catch any stragglers and prevent "target is busy"
    if mountpoint -q /mnt; then
        umount -R /mnt 2>/dev/null || true
    fi
    
    if [ $exit_code -eq 0 ]; then
        log_success "Installation completed successfully."
    else
        log_error "Installation failed with exit code $exit_code."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Main ---
main() {
    check_root
    # Added grub-common for update-grub
    check_dependencies "rsync" "parted" "blkid" "chroot" "lsblk" "visudo" "grub-install" "update-grub"

    # Prevent concurrent execution
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
    log_info "Available disks:"
    lsblk -d -o NAME,SIZE,MODEL,TYPE | grep -v loop
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

    # Safety confirmation: require typing the disk name
    log_warn "WARNING: This will DESTROY ALL DATA on $DISK!"
    read -p "To confirm, type the disk name ($DISK_NAME) again: " CONFIRM
    if [ "$CONFIRM" != "$DISK_NAME" ]; then
        log_error "Confirmation failed. Installation aborted."
        exit 1
    fi

    # Determine partition prefix
    if echo "$DISK_NAME" | grep -qE "nvme|mmcblk"; then
        PART_PREFIX="${DISK}p"
    else
        PART_PREFIX="${DISK}"
    fi

    # --- Partitioning ---
    log_info "Partitioning $DISK..."
    
    if $is_uefi; then
        # UEFI: GPT with ESP
        parted -s "$DISK" mklabel gpt
        parted -s "$DISK" mkpart primary 1MiB 513MiB
        parted -s "$DISK" set 1 esp on
        parted -s "$DISK" mkpart primary 513MiB 100%
        
        PART_EFI="${PART_PREFIX}1"
        PART_ROOT="${PART_PREFIX}2"
        
        log_info "Formatting partitions (UEFI)..."
        mkfs.fat -F32 "$PART_EFI"
        mkfs.ext4 -F "$PART_ROOT"
    else
        # BIOS: GPT with BIOS Boot partition (2MB for safe alignment)
        parted -s "$DISK" mklabel gpt
        parted -s "$DISK" mkpart primary 1MiB 3MiB
        parted -s "$DISK" set 1 bios_grub on
        parted -s "$DISK" mkpart primary 3MiB 100%
        
        PART_ROOT="${PART_PREFIX}2"
        
        log_info "Formatting partitions (BIOS)..."
        mkfs.ext4 -F "$PART_ROOT"
    fi

    log_info "Mounting partitions..."
    mount "$PART_ROOT" /mnt
    if $is_uefi; then
        mkdir -p /mnt/boot/efi
        mount "$PART_EFI" /mnt/boot/efi
    fi

    # --- File Copy ---
    log_info "Copying system files to disk. This may take a while..."
    # Exclude live-specific and volatile directories to save time and space
    rsync -aAXv --progress \
        --exclude={"/dev/*","/proc/*","/sys/*","/tmp/*","/run/*","/mnt/*","/media/*","/lost+found","/live","/var/log/*","/var/cache/apt/*","/var/tmp/*"} \
        / /mnt/

    # --- System Configuration ---
    log_info "Generating /etc/fstab..."
    local root_uuid
    root_uuid=$(blkid -s UUID -o value "$PART_ROOT")
    cat <<FSTAB > /mnt/etc/fstab
# Vice OS /etc/fstab
UUID=$root_uuid  /            ext4    defaults,noatime,errors=remount-ro  0  1
tmpfs            /tmp         tmpfs   defaults,noatime,size=512M          0  0
FSTAB

    if $is_uefi; then
        local efi_uuid
        efi_uuid=$(blkid -s UUID -o value "$PART_EFI")
        echo "UUID=$efi_uuid  /boot/efi   vfat    umask=0077,defaults  0  1" >> /mnt/etc/fstab
    fi

    # --- Chroot Setup ---
    log_info "Mounting virtual filesystems for chroot..."
    mount --bind /dev /mnt/dev
    mount --bind /proc /mnt/proc
    mount --bind /sys /mnt/sys

    if $is_uefi; then
        mount -t efivarfs efivarfs /mnt/sys/firmware/efi/efivars 2>/dev/null || true
    fi

    # Safely copy resolv.conf (dereference symlinks for systemd-resolved hosts)
    cp -L /etc/resolv.conf /mnt/etc/resolv.conf || log_warn "Failed to copy resolv.conf. Network might fail in chroot."

    # Copy declarative GRUB defaults config if it exists in the payload
    local grub_default_src="$WORKDIR/config/default/grub"
    if [ -f "$grub_default_src" ]; then
        log_info "Installing GRUB defaults configuration..."
        mkdir -p /mnt/etc/default
        cp "$grub_default_src" /mnt/etc/default/grub
    fi

    log_info "Installing GRUB and regenerating initramfs..."
    # GRUB packages are already copied via rsync from the Live ISO.
    # We bypass apt-get to allow completely offline installation.
    chroot /mnt /bin/bash <<EOF
    export DEBIAN_FRONTEND=noninteractive

    echo "[*] Ensuring GRUB default config exists..."
    if [ ! -f /etc/default/grub ]; then
        cat <<GRUBCFG > /etc/default/grub
GRUB_TIMEOUT=5
GRUB_DISTRIBUTOR="Vice OS"
GRUB_CMDLINE_LINUX_DEFAULT="quiet"
GRUB_CMDLINE_LINUX=""
GRUBCFG
    fi

    echo "[*] Installing GRUB..."
    if $is_uefi; then
        grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=VICE_OS --removable
    else
        grub-install --target=i386-pc $DISK
    fi

    echo "[*] Updating GRUB config..."
    update-grub

    echo "[*] Regenerating initramfs for physical hardware..."
    # Reinstalling the kernel ensures all hardware modules are built and live-boot is dropped if present
    apt-get -o Acquire::Retries=3 -o Dpkg::Lock::Timeout=300 install -y --no-install-recommends --reinstall linux-image-amd64 || echo "Warning: Kernel reinstall failed. Initramfs might be stale."
    update-initramfs -u -k all

    apt-get clean
EOF

    # --- User Password Setup ---
    log_info "Setting up user passwords for the installed system..."
    echo ""
    
    while true; do
        read -s -p "Enter a new password for user 'vice' (leave blank to keep 'vice'): " VICE_PASS
        if [ -n "$VICE_PASS" ]; then
            read -s -p "Confirm password: " VICE_PASS_CONFIRM
            if [ "$VICE_PASS" == "$VICE_PASS_CONFIRM" ]; then
                chroot /mnt /bin/bash -c "echo 'vice:$VICE_PASS' | chpasswd"
                # Remove passwordless sudo for security on installed system
                echo "vice ALL=(ALL) ALL" > /mnt/etc/sudoers.d/vice
                chown root:root /mnt/etc/sudoers.d/vice
                chmod 440 /mnt/etc/sudoers.d/vice
                # Validate sudoers syntax to prevent lockout
                if ! chroot /mnt /usr/sbin/visudo -cf /etc/sudoers.d/vice > /dev/null 2>&1; then
                    log_error "Syntax error in sudoers file! Aborting to prevent lockout."
                    exit 1
                fi
                break
            else
                log_error "Passwords do not match. Please try again."
            fi
        else
            log_warn "Keeping default password 'vice'."
            break
        fi
    done

    while true; do
        read -s -p "Enter a new root password (leave blank to disable root login): " ROOT_PASS
        if [ -n "$ROOT_PASS" ]; then
            read -s -p "Confirm root password: " ROOT_PASS_CONFIRM
            if [ "$ROOT_PASS" == "$ROOT_PASS_CONFIRM" ]; then
                chroot /mnt /bin/bash -c "echo 'root:$ROOT_PASS' | chpasswd"
                break
            else
                log_error "Passwords do not match. Please try again."
            fi
        else
            chroot /mnt /bin/bash -c "passwd -l root"
            log_info "Root login disabled."
            break
        fi
    done

    # Cleanup is handled by the trap
}

main "$@"