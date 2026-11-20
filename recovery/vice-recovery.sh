#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# Vice OS Unified Recovery Menu
# Provides a TUI menu for all recovery operations:
#   - GRUB reinstallation
#   - Password reset
#   - Network configuration reset
#   - Filesystem check
#   - Package repair
#   - System diagnostics
#   - Emergency theme restoration (GRUB & Plymouth)
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"

LOCKFILE="/var/lock/vice-recovery.lock"
LOCKED=0

cleanup() {
    local exit_code=$?
    if [ "${LOCKED:-0}" -eq 1 ]; then
        flock -u 9 2>/dev/null || true
        exec 9>&- 2>/dev/null || true
        rm -f "$LOCKFILE" 2>/dev/null || true
    fi
    if [ $exit_code -ne 0 ] && [ "${LOCKED:-0}" -eq 1 ]; then
        log_error "Recovery operation aborted or terminated with exit code $exit_code."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

show_header() {
    clear
    echo "=============================================="
    echo "     Vice OS Unified Recovery Menu v1.1"
    echo "=============================================="
    echo ""
}

select_disk_partition() {
    local prompt="$1"
    local parts
    parts=$(lsblk -nlo NAME,SIZE,TYPE,MOUNTPOINT 2>/dev/null | grep "part" || true)

    if [ -z "$parts" ]; then
        log_error "No partitions found."
        return 1
    fi

    # Print selection prompts and list to stderr so caller capturing stdout
    # receives ONLY the partition device name.
    echo "$prompt" >&2
    echo "Available partitions:" >&2
    echo "$parts" | head -20 >&2
    echo "" >&2

    local part_name=""
    read -r -p "Enter partition (e.g., sda2, nvme0n1p2): " part_name
    part_name="$(echo "$part_name" | tr -d ' ')"
    part_name="${part_name#/dev/}"

    if [ -z "$part_name" ]; then
        log_error "No partition entered."
        return 1
    fi

    local part_dev="/dev/$part_name"

    if [ ! -b "$part_dev" ]; then
        log_error "Invalid partition: $part_dev"
        return 1
    fi

    echo "$part_dev"
    return 0
}

menu_rebuild_grub() {
    show_header
    echo ">> GRUB Recovery"
    echo ""

    local root_part
    if ! root_part=$(select_disk_partition "Select the root partition"); then
        read -r -p "Press Enter to return to menu..."
        return 1
    fi

    local efi_part=""
    if [ -d /sys/firmware/efi/efivars ]; then
        if ! efi_part=$(select_disk_partition "Select the EFI partition"); then
            read -r -p "Press Enter to return to menu..."
            return 1
        fi
    fi

    log_info "Running GRUB recovery on $root_part..."
    if [ -f "$WORKDIR/recovery/rebuild_grub.sh" ]; then
        if [ -n "$efi_part" ]; then
            if ! bash "$WORKDIR/recovery/rebuild_grub.sh" "$root_part" "$efi_part"; then
                log_error "GRUB recovery process reported errors."
            fi
        else
            if ! bash "$WORKDIR/recovery/rebuild_grub.sh" "$root_part"; then
                log_error "GRUB recovery process reported errors."
            fi
        fi
    else
        log_error "rebuild_grub.sh not found."
    fi

    echo ""
    read -r -p "Press Enter to return to menu..."
}

menu_reset_password() {
    show_header
    echo ">> Password Reset"
    echo ""

    local root_part
    if ! root_part=$(select_disk_partition "Select the root partition"); then
        read -r -p "Press Enter to return to menu..."
        return 1
    fi

    local username=""
    read -r -p "Enter username to reset password for (default: vice): " username
    username="${username:-vice}"

    log_info "Resetting password for '$username' on $root_part..."
    if [ -f "$WORKDIR/recovery/reset_password.sh" ]; then
        if ! bash "$WORKDIR/recovery/reset_password.sh" "$root_part" "$username"; then
            log_error "Password reset process reported errors."
        fi
    else
        log_error "reset_password.sh not found."
    fi

    echo ""
    read -r -p "Press Enter to return to menu..."
}

menu_reset_network() {
    show_header
    echo ">> Network Configuration Reset"
    echo ""

    log_warn "This will reset all network configurations to defaults."
    local confirm=""
    read -r -p "Continue? (y/N): " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        log_info "Cancelled."
        read -r -p "Press Enter to return to menu..."
        return 0
    fi

    if [ -f "$WORKDIR/recovery/reset_network.sh" ]; then
        if ! bash "$WORKDIR/recovery/reset_network.sh"; then
            log_error "Network reset process reported errors."
        fi
    else
        log_error "reset_network.sh not found."
    fi

    echo ""
    read -r -p "Press Enter to return to menu..."
}

menu_fsck() {
    show_header
    echo ">> Filesystem Check (fsck)"
    echo ""

    local root_part
    if ! root_part=$(select_disk_partition "Select the partition to check"); then
        read -r -p "Press Enter to return to menu..."
        return 1
    fi

    log_warn "Checking filesystem on $root_part..."
    log_info "Attempting to unmount $root_part if mounted..."

    if mountpoint -q "$root_part" 2>/dev/null; then
        umount "$root_part" 2>/dev/null || log_warn "Could not unmount. fsck on mounted filesystem is limited."
    fi

    if command -v fsck > /dev/null 2>&1; then
        local fsck_code=0
        fsck -y "$root_part" || fsck_code=$?
        case "$fsck_code" in
            0) log_success "Filesystem check completed: clean (no errors)." ;;
            1) log_success "Filesystem errors corrected successfully." ;;
            2) log_warn "System reboot recommended after filesystem repair." ;;
            *) log_error "fsck exited with status $fsck_code. Further manual intervention may be required." ;;
        esac
    else
        log_error "fsck not found. Install e2fsprogs."
    fi

    echo ""
    read -r -p "Press Enter to return to menu..."
}

menu_repair_packages() {
    show_header
    echo ">> Package Repair"
    echo ""

    log_warn "This will attempt to repair the package system."
    log_info "Options:"
    echo "  1. Fix broken packages (dpkg --configure -a & apt-get -f install)"
    echo "  2. Reinstall all Vice OS packages"
    echo "  3. Back"
    echo ""

    local pkg_opt=""
    read -r -p "Select option (1-3): " pkg_opt

    case "$pkg_opt" in
        1)
            log_info "Configuring unconfigured packages..."
            dpkg --configure -a || log_warn "dpkg configure reported warnings."
            log_info "Resolving broken dependencies..."
            apt-get install -f -y || log_warn "apt-get install -f reported warnings."
            log_success "Package repair completed."
            ;;
        2)
            log_warn "This will reinstall all packages from config/packages.list"
            local confirm=""
            read -r -p "Continue? (y/N): " confirm
            if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
                local pkg_file="$WORKDIR/config/packages.list"
                if [ -f "$pkg_file" ]; then
                    local pkgs
                    pkgs=$(grep -v '^\s*#' "$pkg_file" | grep -v '^\s*$' | tr '\n' ' ')
                    if [ -n "$pkgs" ]; then
                        log_info "Reinstalling packages: $pkgs"
                        apt-get install --reinstall -y $pkgs || log_warn "Some packages could not be reinstalled."
                        log_success "Package reinstallation completed."
                    else
                        log_warn "Package list is empty."
                    fi
                else
                    log_error "Package list not found at $pkg_file"
                fi
            fi
            ;;
        3|*)
            return 0
            ;;
    esac

    echo ""
    read -r -p "Press Enter to return to menu..."
}

menu_diagnostics() {
    show_header
    echo ">> System Diagnostics"
    echo "=============================================="
    echo ""

    echo "--- System Information ---"
    echo "Kernel: $(uname -a 2>/dev/null || echo 'N/A')"
    echo "Uptime: $(uptime -p 2>/dev/null || echo 'N/A')"
    echo ""

    echo "--- Memory ---"
    free -h 2>/dev/null || echo "free: N/A"
    echo ""

    echo "--- Disk Usage ---"
    df -h / 2>/dev/null || echo "df: N/A"
    echo ""

    echo "--- Mounted Filesystems ---"
    mount | grep -E "^/dev" 2>/dev/null || echo "mount: N/A"
    echo ""

    echo "--- Active Services ---"
    systemctl list-units --type=service --state=running --no-legend 2>/dev/null | head -10 || echo "systemctl: N/A"
    echo ""

    echo "--- Failed Services ---"
    systemctl --failed --no-legend 2>/dev/null || echo "systemctl: N/A"
    echo ""

    echo "--- Network Interfaces ---"
    ip addr show 2>/dev/null | grep -E "^[0-9]|inet " || echo "ip: N/A"
    echo ""

    echo "--- Bootloader ---"
    if [ -d /sys/firmware/efi/efivars ]; then
        echo "Boot mode: UEFI"
        efibootmgr -v 2>/dev/null | head -5 || echo "efibootmgr: N/A"
    else
        echo "Boot mode: BIOS (Legacy)"
    fi

    echo ""
    read -r -p "Press Enter to return to menu..."
}

menu_restore_themes() {
    show_header
    echo ">> Restore Boot Themes (Emergency Theme Repair)"
    echo ""

    log_info "Available theme restoration options:"
    echo "  1. Reinstall Cyberpunk GRUB theme"
    echo "  2. Reinstall Vice OS Plymouth boot splash"
    echo "  3. Reinstall both GRUB & Plymouth themes"
    echo "  4. Back"
    echo ""

    local theme_opt=""
    read -r -p "Select option (1-4): " theme_opt

    case "$theme_opt" in
        1)
            if [ -f "$WORKDIR/recovery/vice_grub_theme.sh" ]; then
                log_info "Applying Cyberpunk GRUB theme..."
                if ! bash "$WORKDIR/recovery/vice_grub_theme.sh" --install; then
                    log_error "GRUB theme installation failed."
                fi
            else
                log_error "vice_grub_theme.sh not found."
            fi
            ;;
        2)
            if [ -f "$WORKDIR/recovery/vice_plymouth_theme.sh" ]; then
                log_info "Applying Plymouth boot splash theme..."
                if ! bash "$WORKDIR/recovery/vice_plymouth_theme.sh"; then
                    log_error "Plymouth theme installation failed."
                fi
            else
                log_error "vice_plymouth_theme.sh not found."
            fi
            ;;
        3)
            if [ -f "$WORKDIR/recovery/vice_grub_theme.sh" ]; then
                log_info "Applying Cyberpunk GRUB theme..."
                if ! bash "$WORKDIR/recovery/vice_grub_theme.sh" --install; then
                    log_error "GRUB theme installation failed."
                fi
            fi
            if [ -f "$WORKDIR/recovery/vice_plymouth_theme.sh" ]; then
                log_info "Applying Plymouth boot splash theme..."
                if ! bash "$WORKDIR/recovery/vice_plymouth_theme.sh"; then
                    log_error "Plymouth theme installation failed."
                fi
            fi
            ;;
        4|*)
            return 0
            ;;
    esac

    echo ""
    read -r -p "Press Enter to return to menu..."
}

main() {
    if [[ "${1:-}" == "--version" ]]; then
        echo "Vice OS Unified Recovery Menu v1.1"
        exit 0
    fi
    if [[ "${1:-}" == "--help" ]] || [[ "${1:-}" == "-h" ]]; then
        echo "Vice OS Unified Recovery Menu"
        echo ""
        echo "Usage: sudo $0"
        echo "Provides a TUI menu for GRUB repair, password reset, network reset,"
        echo "filesystem checks, package repairs, and boot theme restorations."
        exit 0
    fi

    check_root

    mkdir -p /var/lock 2>/dev/null || true
    exec 9>"$LOCKFILE"
    if ! flock -n 9; then
        log_error "Another recovery process is already running."
        exit 1
    fi
    LOCKED=1

    while true; do
        show_header
        echo "  1.  Rebuild GRUB Bootloader"
        echo "  2.  Reset User Password"
        echo "  3.  Reset Network Configuration"
        echo "  4.  Filesystem Check (fsck)"
        echo "  5.  Repair Package System"
        echo "  6.  System Diagnostics"
        echo "  7.  Restore Boot Themes (GRUB & Plymouth)"
        echo ""
        echo "  0.  Exit"
        echo ""
        local option=""
        read -r -p "Select option (0-7): " option

        case "$option" in
            1) menu_rebuild_grub ;;
            2) menu_reset_password ;;
            3) menu_reset_network ;;
            4) menu_fsck ;;
            5) menu_repair_packages ;;
            6) menu_diagnostics ;;
            7) menu_restore_themes ;;
            0)
                log_info "Exiting recovery menu."
                exit 0
                ;;
            *)
                log_warn "Invalid option: $option"
                sleep 1
                ;;
        esac
    done
}

main "$@"
