#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) USB Manager
# Manages USB device listing, mounting, unmounting, and safe power-off.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Source Shared Library ---
if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found. Cannot continue." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

# --- Configuration ---
LSUSB_CMD="lsusb"
UDISKSCTL_CMD="udisksctl"
FINDMNT_CMD="findmnt"

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "USB operation failed with exit code $exit_code."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Helper Functions ---

check_usb_deps() {
    check_dependencies "lsblk" "findmnt"
    
    if ! command -v "$LSUSB_CMD" > /dev/null 2>&1; then
        log_warn "lsusb not found. USB device listing will be limited."
    fi
    
    if ! command -v "$UDISKSCTL_CMD" > /dev/null 2>&1; then
        log_warn "udisksctl not found. Mount/unmount will use legacy commands."
    fi
}

# --- Listing Functions ---

list_devices() {
    log_info "Connected USB Devices (lsusb):"
    echo "==================================="
    
    if command -v "$LSUSB_CMD" > /dev/null 2>&1; then
        "$LSUSB_CMD"
    else
        log_warn "lsusb not installed. Cannot list USB devices."
    fi
    
    echo ""
    log_info "USB Block Devices (lsblk):"
    echo "==================================="
    
    # List only removable/USB block devices
    lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,TRAN,MODEL | grep -i "usb\|USB" || true
    
    echo "==================================="
}

list_partitions() {
    log_info "USB Partitions:"
    echo "==================================="
    
    # Find all USB block devices and their partitions
    for dev in /sys/block/sd* /sys/block/nvme*; do
        if [ -d "$dev" ]; then
            local dev_name
            dev_name=$(basename "$dev")
            local removable
            removable=$(cat "$dev/removable" 2>/dev/null || echo "0")
            
            # Check if it's a USB device (removable=1 or tran=usb)
            local tran
            tran=$(cat "$dev/device/transport" 2>/dev/null || echo "")
            
            if [ "$removable" == "1" ] || echo "$tran" | grep -qi "usb"; then
                echo "  Device: /dev/$dev_name"
                lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT "/dev/$dev_name" 2>/dev/null | tail -n +2 | while read -r line; do
                    echo "    $line"
                done
            fi
        fi
    done
    
    echo "==================================="
}

show_mounted() {
    log_info "Mounted USB Devices:"
    echo "==================================="
    
    "$FINDMNT_CMD" -o SOURCE,TARGET,FSTYPE,SIZE,OPTIONS | grep -E "/dev/sd|/dev/nvme" | while read -r line; do
        echo "  $line"
    done
    
    echo "==================================="
}

# --- Mount/Unmount Functions ---

mount_device() {
    local device="$1"
    local mount_point="${2:-}"
    
    if [ -z "$device" ]; then
        log_error "Device path required (e.g., /dev/sdb1)."
        return 1
    fi
    
    # Validate device exists
    if [ ! -b "$device" ]; then
        log_error "'$device' is not a valid block device."
        return 1
    fi
    
    # Check if already mounted
    if "$FINDMNT_CMD" -rn -S "$device" | grep -q "$device"; then
        log_warn "$device is already mounted."
        "$FINDMNT_CMD" -rn -S "$device" -o TARGET
        return 0
    fi
    
    # Try udisksctl first (no root needed)
    if command -v "$UDISKSCTL_CMD" > /dev/null 2>&1; then
        log_info "Mounting $device via udisksctl..."
        if "$UDISKSCTL_CMD" mount -b "$device" 2>/dev/null; then
            local mp
            mp=$("$FINDMNT_CMD" -rn -S "$device" -o TARGET)
            log_success "$device mounted at: $mp"
            return 0
        fi
    fi
    
    # Fallback to manual mount
    if [ -z "$mount_point" ]; then
        local basename
        basename=$(basename "$device")
        mount_point="/media/${basename}"
    fi
    
    log_info "Mounting $device to $mount_point..."
    mkdir -p "$mount_point"
    
    if mount "$device" "$mount_point"; then
        log_success "$device mounted at: $mount_point"
    else
        log_error "Failed to mount $device."
        log_info "Try running with sudo or check filesystem type."
        return 1
    fi
}

unmount_device() {
    local device="$1"
    
    if [ -z "$device" ]; then
        log_error "Device path or mount point required."
        return 1
    fi
    
    # Check if it's mounted
    if ! "$FINDMNT_CMD" -rn -S "$device" 2>/dev/null | grep -q "$device"; then
        # Check if it's a mount point
        if ! "$FINDMNT_CMD" -rn -T "$device" 2>/dev/null | grep -q "$device"; then
            log_warn "$device is not mounted."
            return 0
        fi
    fi
    
    # Try udisksctl first
    if command -v "$UDISKSCTL_CMD" > /dev/null 2>&1; then
        log_info "Unmounting $device via udisksctl..."
        if "$UDISKSCTL_CMD" unmount -b "$device" 2>/dev/null; then
            log_success "$device unmounted."
            return 0
        fi
    fi
    
    # Fallback to umount
    log_info "Unmounting $device..."
    if umount "$device"; then
        log_success "$device unmounted."
    else
        log_error "Failed to unmount $device."
        log_info "Device might be busy. Use 'lsof +D <mountpoint>' to find processes."
        return 1
    fi
}

eject_device() {
    local device="$1"
    
    if [ -z "$device" ]; then
        log_error "Device path required (e.g., /dev/sdb)."
        return 1
    fi
    
    # Extract the base device (e.g., /dev/sdb1 -> /dev/sdb)
    local base_device
    base_device=$(echo "$device" | sed 's/[0-9]*$//')
    
    # First unmount all partitions on this device
    log_info "Unmounting all partitions on $base_device..."
    
    for part in /dev/"$(basename "$base_device")"*; do
        if [ -b "$part" ] && "$FINDMNT_CMD" -rn -S "$part" 2>/dev/null | grep -q "$part"; then
            unmount_device "$part" || true
        fi
    done
    
    # Power off the device
    if command -v "$UDISKSCTL_CMD" > /dev/null 2>&1; then
        log_info "Powering off $base_device..."
        if "$UDISKSCTL_CMD" power-off -b "$base_device" 2>/dev/null; then
            log_success "Device $base_device powered off. Safe to remove."
            return 0
        fi
    fi
    
    # Fallback: use eject
    if command -v eject > /dev/null 2>&1; then
        log_info "Ejecting $base_device..."
        if eject "$base_device" 2>/dev/null; then
            log_success "Device $base_device ejected. Safe to remove."
            return 0
        fi
    fi
    
    log_warn "Could not power off device automatically."
    log_info "It should be safe to remove the device if all partitions are unmounted."
}

# --- Information Functions ---

device_info() {
    local device="$1"
    
    if [ -z "$device" ]; then
        log_error "Device path required."
        return 1
    fi
    
    if [ ! -b "$device" ]; then
        log_error "'$device' is not a valid block device."
        return 1
    fi
    
    log_info "Device Information: $device"
    echo "==================================="
    
    # Basic info
    lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,MODEL,VENDOR,TRAN "$device"
    
    echo ""
    echo "UUIDs:"
    blkid "$device"* 2>/dev/null || true
    
    echo "==================================="
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) USB Manager

Usage: $0 <command> [options]

Listing:
  list                        List all USB devices and block devices
  partitions                  List USB partitions
  mounted                     Show currently mounted USB devices

Mount/Unmount:
  mount <device> [mountpoint]  Mount a USB partition (auto-mounts to /media/<dev>)
  unmount <device|mountpoint>  Unmount a USB partition
  eject <device>              Safely power off and eject entire USB drive

Information:
  info <device>               Show detailed device information

Help:
  help                        Show this help message

Notes:
  - Uses udisksctl if available (no root required for most operations).
  - Falls back to mount/umount/eject if udisksctl is not installed.
  - Device paths: /dev/sdb, /dev/sdb1, /dev/nvme0n1p1, etc.

Examples:
  $0 list
  $0 mount /dev/sdb1
  $0 unmount /dev/sdb1
  $0 eject /dev/sdb
  $0 info /dev/sdb
HELP
}

# --- Main ---

main() {
    check_usb_deps
    
    local command="${1:-help}"
    shift || true
    
    case "$command" in
        list|ls|devices)
            list_devices
            ;;
        partitions|parts)
            list_partitions
            ;;
        mounted|mounts)
            show_mounted
            ;;
        mount)
            local device="${1:-}"
            if [ -z "$device" ]; then
                log_error "Device path required."
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
        eject|safe-remove|power-off)
            local device="${1:-}"
            if [ -z "$device" ]; then
                log_error "Device path required."
                exit 1
            fi
            eject_device "$device"
            ;;
        info|show)
            local device="${1:-}"
            if [ -z "$device" ]; then
                log_error "Device path required."
                exit 1
            fi
            device_info "$device"
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