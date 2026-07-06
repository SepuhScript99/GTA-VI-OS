#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Orchestrator
# Version: 1.0 Stable
# 
# Mounts virtual filesystems, stages the payload, and executes modular 
# configuration scripts located in the chroot_scripts/ directory.
# Utilizes lib/state_manager.sh for granular resumability.
# ============================================================================

WORKDIR="$PWD"
CHROOTDIR="${1:-$WORKDIR/chroot}"

# --- Source Shared Libraries ---
if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found. Cannot continue." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

if [ ! -f "$WORKDIR/lib/state_manager.sh" ]; then
    log_error "lib/state_manager.sh not found. Cannot continue."
    exit 1
fi
source "$WORKDIR/lib/state_manager.sh"

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    log_info "Cleaning up chroot mounts..."
    
    # Prevent apt from keeping locks if we exit early
    rm -f "$CHROOTDIR/var/lib/dpkg/lock-frontend" 2>/dev/null || true
    rm -f "$CHROOTDIR/var/lib/apt/lists/lock" 2>/dev/null || true
    
    umount "$CHROOTDIR/dev" 2>/dev/null || true
    umount "$CHROOTDIR/proc" 2>/dev/null || true
    umount "$CHROOTDIR/sys" 2>/dev/null || true
    
    if [ $exit_code -eq 0 ]; then
        log_success "Chroot orchestration completed successfully."
    else
        log_error "Chroot orchestration failed with exit code $exit_code."
        log_warn "You can resume by re-running build_iso.sh. Completed scripts will be skipped."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Main Setup Process ---
main() {
    check_root
    log_info "=== Configuring chroot environment ==="

    if [ ! -d "$CHROOTDIR" ] || [ ! -d "$WORKDIR/chroot_scripts" ]; then
        log_error "Chroot directory or chroot_scripts directory not found!"
        exit 1
    fi

    log_info "Mounting virtual filesystems..."
    mount --bind /dev "$CHROOTDIR/dev"
    mount --bind /proc "$CHROOTDIR/proc"
    mount --bind /sys "$CHROOTDIR/sys"

    # Safely configure DNS for the chroot
    log_info "Configuring DNS for chroot..."
    if ! cp -L /etc/resolv.conf "$CHROOTDIR/etc/resolv.conf" 2>/dev/null; then
        log_warn "Failed to copy host resolv.conf. Creating fallback DNS (1.1.1.1)..."
        echo "nameserver 1.1.1.1" > "$CHROOTDIR/etc/resolv.conf"
    fi

    log_info "Copying project files into chroot payload..."
    # Create a temporary payload directory inside the chroot
    mkdir -p "$CHROOTDIR/vice_payload"
    cp -r "$WORKDIR/config" "$CHROOTDIR/vice_payload/"
    cp -r "$WORKDIR/assets" "$CHROOTDIR/vice_payload/"
    cp -r "$WORKDIR/desktop" "$CHROOTDIR/vice_payload/"
    cp -r "$WORKDIR/system_scripts" "$CHROOTDIR/vice_payload/"
    cp -r "$WORKDIR/lib" "$CHROOTDIR/vice_payload/"
    cp -r "$WORKDIR/chroot_scripts" "$CHROOTDIR/vice_payload/"

    # Ensure all scripts in the payload are executable
    chmod +x "$CHROOTDIR"/vice_payload/chroot_scripts/*.sh 2>/dev/null || true
    chmod +x "$CHROOTDIR"/vice_payload/system_scripts/*.sh 2>/dev/null || true
    chmod +x "$CHROOTDIR"/vice_payload/desktop/*.sh 2>/dev/null || true
    chmod +x "$CHROOTDIR"/vice_payload/desktop/*.py 2>/dev/null || true

    # Execute modular scripts inside the chroot in alphabetical order
    # The payload (including chroot_scripts) is already staged by create_rootfs.sh
    for script in "$WORKDIR"/chroot_scripts/*.sh; do
        local script_name=$(basename "$script")
        # Create a state key based on the script name (e.g., CHROOT_00_base_config)
        local state_key="CHROOT_${script_name%.sh}"
        
        if state_is_complete "$state_key"; then
            log_warn "Skipping completed chroot script: $script_name"
            continue
        fi
        
        log_info "Executing chroot script: $script_name"
        if chroot "$CHROOTDIR" /bin/bash "/vice_payload/chroot_scripts/$script_name"; then
            state_mark_complete "$state_key"
        else
            log_error "Chroot script failed: $script_name"
            exit 1
        fi
    done

    log_info "Chroot scripts completed. Final cleanup will be handled by trap."
}

main "$@"