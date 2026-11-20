#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Disk Manager
# Provides disk listing, formatting, mounting, unmounting, usage stats,
# and SMART health checks.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"
install_cleanup

# --- Helper Functions ---

check_disk_deps() {
    check_dependencies "lsblk" "mount" "umount" "blkid"
}

validate_block_device() {
    local device="$1"

    if [ ! -b "$device" ]; then
        log_error "'$device' is not a valid block device."
        return 1
    fi

    # Prevent formatting or mounting critical system partitions
    case "$device" in
        /dev/sda|/dev/nvme0n1|/dev/sda1|/dev/nvme0n1p1|/dev/nvme0n1p2)
            log_error "Operating on critical system device '$device' is blocked for safety."
            log_info "Use gparted or manual CLI tools for system partitions."
            return 1
            ;;
    esac
}

# --- Listing Functions ---

list_disks() {
    log_info "Block Devices:"
    echo "==================================="
    lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,MODEL
    echo "==================================="
}

list_partitions() {
    local disk="$1"

    if [ ! -b "$disk" ]; then
        log_error "'$disk' is not a valid block device."
        return 1
    fi

    log_info "Partitions on $disk:"
    echo "==================================="
    lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT "$disk"
    echo "==================================="
}

# --- Mounting Functions ---

mount_device() {
    local device="$1"
    local mount_point="${2:-}"

    validate_block_device "$device" || return 1

    # Check if already mounted
    if mountpoint -q "$device" 2>/dev/null || findmnt -rn -S "$device" | grep -q "$device"; then
        log_warn "$device is already mounted."
        findmnt -rn -S "$device"
        return 0
    fi

    if [ -z "$mount_point" ]; then
        # Auto-mount to /media/<basename>
        local basename
        basename=$(basename "$device")
        mount_point="/media/$basename"
    fi

    log_info "Mounting $device to $mount_point..."

    mkdir -p "$mount_point"

    if ! mount "$device" "$mount_point"; then
        log_error "Failed to mount $device."
        log_info "Filesystem type might be unsupported or partition is corrupt."
        return 1
    fi

    log_success "$device mounted successfully at $mount_point."
}

unmount_device() {
    local device="$1"

    # Allow unmounting by mount point or device
    if [ ! -b "$device" ] && ! mountpoint -q "$device"; then
        log_error "'$device' is neither a block device nor a valid mount point."
        return 1
    fi

    log_info "Unmounting $device..."

    if ! umount "$device"; then
        log_error "Failed to unmount $device."
        log_info "Device might be busy. Use 'lsof +D <mountpoint>' to find processes."
        return 1
    fi

    log_success "$device unmounted successfully."
}

# --- Formatting Functions ---

format_device() {
    local device="$1"
    local fs_type="${2:-ext4}"
    local force="${3:-no}"

    validate_block_device "$device" || return 1

    # Safety confirmation
    if [ "$force" != "yes" ] && [ "$force" != "--force" ]; then
        log_warn "WARNING: Formatting $device will destroy ALL data on it!"
        read -p "Type the device name ($device) to confirm: " confirm
        if [ "$confirm" != "$device" ]; then
            log_error "Confirmation failed. Aborting format."
            return 1
        fi
    fi

    # Unmount if mounted
    if findmnt -rn -S "$device" | grep -q "$device"; then
        log_info "Unmounting $device before formatting..."
        umount "$device" || { log_error "Cannot unmount. Aborting format."; return 1; }
    fi

    log_info "Formatting $device as $fs_type..."

    case "$fs_type" in
        ext4|ext3|ext2)
            if ! mkfs."$fs_type" -F "$device"; then
                log_error "Failed to format $device as $fs_type."
                return 1
            fi
            ;;
        fat32|vfat)
            if ! mkfs.vfat -F 32 "$device"; then
                log_error "Failed to format $device as fat32."
                return 1
            fi
            ;;
        exfat)
            if ! command -v mkfs.exfat > /dev/null 2>&1; then
                log_error "exfat support not found. Install 'exfatprogs'."
                return 1
            fi
            if ! mkfs.exfat "$device"; then
                log_error "Failed to format $device as exfat."
                return 1
            fi
            ;;
        ntfs)
            if ! command -v mkfs.ntfs > /dev/null 2>&1; then
                log_error "ntfs support not found. Install 'ntfs-3g'."
                return 1
            fi
            if ! mkfs.ntfs -F "$device"; then
                log_error "Failed to format $device as ntfs."
                return 1
            fi
            ;;
        *)
            log_error "Unsupported filesystem type: $fs_type"
            log_info "Supported types: ext4, ext3, ext2, fat32, exfat, ntfs"
            return 1
            ;;
    esac

    log_success "$device formatted successfully as $fs_type."
}

# --- Information Functions ---

disk_usage() {
    local path="${1:-/}"

    if [ ! -e "$path" ]; then
        log_error "Path '$path' does not exist."
        return 1
    fi

    log_info "Disk Usage for $path:"
    echo "==================================="
    df -h "$path"
    echo "==================================="
}

show_uuids() {
    log_info "Block Device UUIDs:"
    echo "==================================="
    blkid
    echo "==================================="
}

# --- SMART Functions ---

smart_status() {
    local device="$1"

    validate_block_device "$device" || return 1

    if ! command -v smartctl > /dev/null 2>&1; then
        log_error "smartctl not found. Install 'smartmontools'."
        return 1
    fi

    log_info "SMART Health Status for $device:"
    echo "==================================="

    # Check if SMART is available
    if ! smartctl -i "$device" 2>/dev/null | grep -q "SMART support is: Available"; then
        log_warn "SMART support is not available for $device."
        log_info "This might be a USB drive, SD card, or virtual disk."
        return 1
    fi

    smartctl -H "$device"
    echo "==================================="
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Disk Manager

Usage: $0 <command> [options]

Partition & Storage Management:
Listing:
  list                        List all block devices
  partitions <disk>           List partitions on a specific disk

Mounting:
  mount <device> [mountpoint] Mount a device (auto-mounts to /media/<dev> if omitted)
  unmount <device|mountpoint> Unmount a device or mount point

Formatting:
  format <device> <fstype> [--force]  Format a device (fstype: ext4, fat32, exfat, ntfs)

Information:
  usage [path]                Show disk usage for a path (default: /)
  uuids                       Show UUIDs for all block devices

SMART:
  smart <device>              Show SMART health status for a device

Help:
  help                        Show this help message

Examples:
  $0 list
  $0 partitions /dev/sdb
  $0 mount /dev/sdb1
  $0 format /dev/sdb1 ext4 --force
  $0 unmount /media/sdb1
  $0 smart /dev/sda
HELP
}

# --- Main ---

main() {
    local command="${1:-help}"
    if [ "$command" = "help" ] || [ "$command" = "--help" ] || [ "$command" = "-h" ]; then
        show_help
        exit 0
    fi
    shift || true

    check_disk_deps

    case "$command" in
        list|disks)
            list_disks
            ;;
        partitions|parts)
            local disk="${1:-}"
            if [ -z "$disk" ]; then
                log_error "Disk device required."
                exit 1
            fi
            list_partitions "$disk"
            ;;
        mount)
            local device="${1:-}"
            if [ -z "$device" ]; then
                log_error "Device required."
                exit 1
            fi
            local mount_point="${2:-}"
            mount_device "$device" "$mount_point"
            ;;
        unmount|umount)
            local device="${1:-}"
            if [ -z "$device" ]; then
                log_error "Device or mount point required."
                exit 1
            fi
            unmount_device "$device"
            ;;
        format)
            local device="${1:-}"
            local fs_type="${2:-ext4}"
            local force="${3:-no}"
            if [ -z "$device" ]; then
                log_error "Device required."
                exit 1
            fi
            format_device "$device" "$fs_type" "$force"
            ;;
        usage|df)
            local path="${1:-/}"
            disk_usage "$path"
            ;;
        uuids|blkid)
            show_uuids
            ;;
        smart|health)
            local device="${1:-}"
            if [ -z "$device" ]; then
                log_error "Device required."
                exit 1
            fi
            smart_status "$device"
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "Unknown command: $command"
            log_info "Run '$0 help' for usage information."
            exit 1
            ;;
    esac
}

main "$@"