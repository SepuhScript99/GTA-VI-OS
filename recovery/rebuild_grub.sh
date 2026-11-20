#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) GRUB Recovery Tool
# Reinstalls and reconfigures GRUB on a target root partition.
# Can be run from a Live CD or a rescue shell.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"

LOCKFILE="/var/lock/vice-rebuild-grub.lock"
LOCKED=0
MOUNTED=0

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?

    if [ "${MOUNTED:-0}" -eq 1 ]; then
        log_info "Cleaning up recovery mounts..."
        # Safely unmount virtual mounts first, then root
        if mountpoint -q /mnt; then
            umount -R /mnt 2>/dev/null || umount -l -R /mnt 2>/dev/null || true
        fi
    fi

    # Release the lock only if acquired by this process
    if [ "${LOCKED:-0}" -eq 1 ]; then
        flock -u 9 2>/dev/null || true
        exec 9>&- 2>/dev/null || true
        rm -f "$LOCKFILE" 2>/dev/null || true
    fi

    if [ "${LOCKED:-0}" -eq 1 ]; then
        if [ $exit_code -eq 0 ]; then
            log_success "GRUB recovery completed successfully."
        else
            log_error "GRUB recovery failed with exit code $exit_code."
        fi
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Main ---
main() {
    # Handle flags
    if [[ "${1:-}" == "--version" ]]; then
        echo "Vice OS GRUB Recovery Tool v1.1"
        echo "Usage: sudo $0 <root_partition> [efi_partition]"
        exit 0
    fi
    if [[ "${1:-}" == "--help" ]] || [[ "${1:-}" == "-h" ]]; then
        echo "Vice OS GRUB Recovery Tool"
        echo ""
        echo "Reinstalls GRUB on a target root partition from a Live CD or rescue shell."
        echo ""
        echo "Usage: sudo $0 <root_partition> [efi_partition]"
        echo ""
        echo "Examples:"
        echo "  sudo $0 /dev/sda2              (BIOS)"
        echo "  sudo $0 /dev/sda2 /dev/sda1    (UEFI)"
        echo ""
        echo "The tool auto-detects UEFI vs BIOS mode from /sys/firmware/efi."
        exit 0
    fi

    check_root
    check_dependencies "mount" "umount" "chroot" "lsblk"

    mkdir -p /var/lock 2>/dev/null || true
    # Prevent concurrent execution
    exec 9>"$LOCKFILE"
    if ! flock -n 9; then
        log_error "Another GRUB recovery process is already running. Exiting."
        exit 1
    fi
    LOCKED=1

    log_info "=== Starting GRUB Recovery Tool ==="

    if [ $# -lt 1 ]; then
        log_error "Usage: sudo $0 <root_partition> [efi_partition]"
        log_error "Example (BIOS): sudo $0 /dev/sda2"
        log_error "Example (UEFI): sudo $0 /dev/sda2 /dev/sda1"
        log_error "Run '$0 --help' for more information."
        exit 1
    fi

    local root_part="$1"
    local efi_part="${2:-}"

    if [ ! -b "$root_part" ]; then
        log_error "Root partition $root_part is not a valid block device."
        exit 1
    fi

    if mountpoint -q /mnt; then
        log_error "/mnt is already mounted. Please unmount /mnt before running GRUB recovery."
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
    MOUNTED=1

    if $is_uefi; then
        log_info "Mounting EFI partition ($efi_part) to /mnt/boot/efi..."
        mkdir -p /mnt/boot/efi
        mount "$efi_part" /mnt/boot/efi
    fi

    log_info "Mounting virtual filesystems for chroot..."
    mount --rbind /dev /mnt/dev
    mount --make-rslave /mnt/dev
    mount --bind /proc /mnt/proc
    mount --rbind /sys /mnt/sys
    mount --make-rslave /mnt/sys

    if $is_uefi; then
        mount -t efivarfs efivarfs /mnt/sys/firmware/efi/efivars 2>/dev/null || log_warn "Could not mount efivarfs. NVRAM might not be updated."
    fi

    # Ensure DNS resolution works inside chroot if resolv.conf exists
    if [ -f /etc/resolv.conf ]; then
        cp -L /etc/resolv.conf /mnt/etc/resolv.conf 2>/dev/null || true
    fi

    log_info "Entering chroot to reinstall GRUB..."

    # Safely determine parent disk for BIOS installation using lsblk
    local disk_dev=""
    if ! $is_uefi; then
        disk_dev=$(lsblk -ndo PKNAME "$root_part" 2>/dev/null | head -n1 || true)
        if [ -z "$disk_dev" ]; then
            log_error "Could not determine parent disk for $root_part via lsblk."
            exit 1
        fi
        disk_dev="/dev/$disk_dev"
        log_info "Detected parent disk for BIOS install: $disk_dev"
    fi

    # Determine UEFI target architecture
    local target_efi="x86_64-efi"
    local host_arch
    host_arch=$(uname -m 2>/dev/null || echo "x86_64")
    if [ "$host_arch" = "aarch64" ] || [ "$host_arch" = "arm64" ]; then
        target_efi="arm64-efi"
    fi

    chroot /mnt /bin/bash <<EOF
    set -Eeuo pipefail
    export DEBIAN_FRONTEND=noninteractive

    if ! command -v grub-install >/dev/null 2>&1; then
        echo "[ERROR] grub-install utility not found in target system." >&2
        exit 1
    fi

    echo "[*] Reinstalling GRUB..."
    if $is_uefi; then
        grub-install --target=$target_efi --efi-directory=/boot/efi --bootloader-id=VICE_OS --removable
    else
        grub-install --target=i386-pc $disk_dev
    fi

    echo "[*] Updating GRUB configuration..."
    if command -v update-grub >/dev/null 2>&1; then
        update-grub
    elif command -v grub-mkconfig >/dev/null 2>&1; then
        grub-mkconfig -o /boot/grub/grub.cfg
    else
        echo "[WARN] Neither update-grub nor grub-mkconfig found." >&2
    fi
EOF

    # Cleanup is handled by the trap
}

main "$@"
