#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) GRUB Recovery Tool
# Reinstalls and reconfigures GRUB on a target root partition.
# Can be run from a Live CD or a rescue shell.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Source Shared Library ---
if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found. Cannot continue." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

LOCKFILE="/var/lock/vice-rebuild-grub.lock"

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    
    # Release the lock
    if [ -f "$LOCKFILE" ]; then
        rm -f "$LOCKFILE"
    fi
    
    log_info "Cleaning up recovery mounts..."
    # Use recursive unmount to safely catch all bind mounts and prevent "target is busy"
    if mountpoint -q /mnt; then
        umount -R /mnt 2>/dev/null || true
    fi
    
    if [ $exit_code -eq 0 ]; then
        log_success "GRUB recovery completed successfully."
    else
        log_error "GRUB recovery failed with exit code $exit_code."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Main ---
main() {
    check_root
    check_dependencies "mount" "umount" "chroot" "grub-install" "update-grub" "lsblk"

    # Prevent concurrent execution
    exec 9>"$LOCKFILE"
    if ! flock -n 9; then
        log_error "Another GRUB recovery process is already running. Exiting."
        exit 1
    fi

    log_info "=== Starting GRUB Recovery Tool ==="

    if [ $# -lt 1 ]; then
        log_error "Usage: sudo $0 <root_partition> [efi_partition]"
        log_error "Example (BIOS): sudo $0 /dev/sda2"
        log_error "Example (UEFI): sudo $0 /dev/sda2 /dev/sda1"
        exit 1
    fi

    local root_part="$1"
    local efi_part="${2:-}"

    if [ ! -b "$root_part" ]; then
        log_error "Root partition $root_part is not a valid block device."
        exit 1
    fi

    # Detect boot mode
    local is_uefi=false
    if [ -d /sys/firmware/efi/efivars ]; then
        is_uefi=true
        log_info "UEFI boot mode detected."
        if [ -z "$efi_part" ]; then
            log_error "UEFI mode requires an EFI partition argument."
            exit 1
        fi
        if [ ! -b "$efi_part" ]; then
            log_error "EFI partition $efi_part is not a valid block device."
            exit 1
        fi
    else
        log_info "BIOS (Legacy) boot mode detected."
    fi

    log_info "Mounting root partition ($root_part) to /mnt..."
    mount "$root_part" /mnt

    if $is_uefi; then
        log_info "Mounting EFI partition ($efi_part) to /mnt/boot/efi..."
        mkdir -p /mnt/boot/efi
        mount "$efi_part" /mnt/boot/efi
    fi

    log_info "Mounting virtual filesystems for chroot..."
    mount --bind /dev /mnt/dev
    mount --bind /proc /mnt/proc
    mount --bind /sys /mnt/sys

    if $is_uefi; then
        mount -t efivarfs efivarfs /mnt/sys/firmware/efi/efivars 2>/dev/null || log_warn "Could not mount efivarfs. NVRAM might not be updated."
    fi

    # Ensure DNS resolution works inside chroot
    if ! cp -L /etc/resolv.conf /mnt/etc/resolv.conf 2>/dev/null; then
        log_warn "Failed to copy host resolv.conf. Creating fallback DNS (1.1.1.1)..."
        echo "nameserver 1.1.1.1" > /mnt/etc/resolv.conf
    fi

    log_info "Entering chroot to reinstall GRUB..."
    
    # Safely determine parent disk for BIOS installation using lsblk
    local disk_dev=""
    if ! $is_uefi; then
        disk_dev=$(lsblk -ndo PKNAME "$root_part" 2>/dev/null | head -n1)
        if [ -z "$disk_dev" ]; then
            log_error "Could not determine parent disk for $root_part via lsblk."
            log_error "Please ensure util-linux is up to date."
            exit 1
        fi
        disk_dev="/dev/$disk_dev"
        log_info "Detected parent disk for BIOS install: $disk_dev"
    fi

    chroot /mnt /bin/bash <<EOF
    export DEBIAN_FRONTEND=noninteractive

    echo "[*] Reinstalling GRUB..."
    if $is_uefi; then
        grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=VICE_OS --removable
    else
        grub-install --target=i386-pc $disk_dev
    fi

    echo "[*] Updating GRUB configuration..."
    update-grub
EOF

    # Cleanup is handled by the trap
}

main "$@"