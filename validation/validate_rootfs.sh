#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# Vice OS RootFS Validator
# Validates the built chroot filesystem for structural integrity.
# Run against a completed chroot directory.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"
install_cleanup

CHROOTDIR="${1:-$WORKDIR/chroot}"
EXIT_CODE=0

# Critical system directories that must exist
REQUIRED_DIRS=(
    "/bin" "/sbin" "/lib" "/lib64" "/usr" "/etc" "/var" "/tmp"
    "/usr/bin" "/usr/sbin" "/usr/lib" "/usr/share"
    "/etc/default" "/etc/systemd" "/etc/apt" "/etc/NetworkManager"
    "/etc/udev" "/etc/modprobe.d" "/etc/polkit-1"
    "/opt/vice-os" "/opt/vice-os/lib"
    "/home/vice" "/etc/skel"
)

# Critical system files that must exist
REQUIRED_FILES=(
    "/etc/passwd" "/etc/shadow" "/etc/group" "/etc/hostname"
    "/etc/hosts" "/etc/resolv.conf" "/etc/fstab"
    "/etc/os-release" "/etc/lsb-release"
    "/etc/apt/sources.list"
    "/etc/default/locale" "/etc/default/keyboard"
    "/bin/bash" "/bin/sh"
    "/usr/sbin/update-grub"
    "/opt/vice-os/vice_shell.py" "/opt/vice-os/login.py"
    "/opt/vice-os/style.qss" "/opt/vice-os/ob_menu.py"
    "/opt/vice-os/dbus_session.sh"
)

main() {
    log_info "=== Validating RootFS: $CHROOTDIR ==="

    if [ ! -d "$CHROOTDIR" ]; then
        log_error "Chroot directory does not exist: $CHROOTDIR"
        log_info "Run build_iso.sh first to create the chroot."
        exit 1
    fi

    # 1. Check required directories
    log_info "Checking required directories..."
    for dir in "${REQUIRED_DIRS[@]}"; do
        if [ ! -d "$CHROOTDIR$dir" ]; then
            log_error "Missing directory: $dir"
            EXIT_CODE=1
        fi
    done
    if [ "$EXIT_CODE" -eq 0 ]; then
        log_success "All required directories present."
    fi

    # 2. Check required files
    log_info "Checking required files..."
    local missing_files=0
    for file in "${REQUIRED_FILES[@]}"; do
        if [ ! -f "$CHROOTDIR$file" ] && [ ! -L "$CHROOTDIR$file" ]; then
            log_error "Missing file: $file"
            missing_files=$((missing_files + 1))
            EXIT_CODE=1
        fi
    done
    if [ "$missing_files" -eq 0 ]; then
        log_success "All required files present."
    else
        log_warn "$missing_files required files missing."
    fi

    # 3. Check essential directories are not empty
    log_info "Checking essential directories are non-empty..."
    local empty_dirs=0
    for dir in "/bin" "/sbin" "/lib" "/usr/bin" "/etc"; do
        if [ -d "$CHROOTDIR$dir" ]; then
            local count
            count=$(find "$CHROOTDIR$dir" -maxdepth 1 -type f 2>/dev/null | wc -l)
            if [ "$count" -eq 0 ]; then
                log_warn "Directory appears empty: $dir ($count files)"
                empty_dirs=$((empty_dirs + 1))
            fi
        fi
    done
    if [ "$empty_dirs" -eq 0 ]; then
        log_success "All essential directories are non-empty."
    fi

    # 4. Check vice user exists
    log_info "Checking vice user configuration..."
    if [ -f "$CHROOTDIR/etc/passwd" ]; then
        if grep -q "^vice:" "$CHROOTDIR/etc/passwd" 2>/dev/null; then
            log_success "User 'vice' exists in passwd."
        else
            log_error "User 'vice' not found in /etc/passwd"
            EXIT_CODE=1
        fi
    fi

    # 5. Check sudoers
    if [ -f "$CHROOTDIR/etc/sudoers.d/vice" ]; then
        log_success "Sudoers configuration present."
    else
        log_warn "Sudoers configuration not found at /etc/sudoers.d/vice"
    fi

    # 6. Check desktop files installed to /opt/vice-os/
    log_info "Checking Vice OS desktop installation..."
    local vice_os_files=0
    while IFS= read -r -d '' file; do
        vice_os_files=$((vice_os_files + 1))
    done < <(find "$CHROOTDIR/opt/vice-os" -type f -print0 2>/dev/null || true)
    if [ "$vice_os_files" -gt 0 ]; then
        log_success "Vice OS desktop: $vice_os_files files installed."
    else
        log_error "No files found in /opt/vice-os/"
        EXIT_CODE=1
    fi

    # 7. Report chroot size
    local size
    size=$(du -sh "$CHROOTDIR" 2>/dev/null | awk '{print $1}')
    log_info "Chroot size: $size"

    if [ "$EXIT_CODE" -eq 0 ]; then
        log_success "RootFS validation passed."
    else
        log_error "RootFS validation failed."
    fi

    exit $EXIT_CODE
}

main "$@"
