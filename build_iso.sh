#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) ISO Build Orchestrator
# Version: 1.0 Stable
#
# This script orchestrates the build phases by calling modular scripts
# located in the build/ directory. It uses lib/state_manager.sh for
# robust resumability.
# ============================================================================

# --- Configuration ---
WORKDIR="$PWD"
CHROOTDIR="$WORKDIR/chroot"
IMAGEDIR="$WORKDIR/image"
SCRATCHDIR="$WORKDIR/scratch"
OUTDIR="$WORKDIR/out"
ISO_LABEL="VICE_OS"
ARCH="${DEBIAN_ARCH:-amd64}"
ISO_NAME="gta-vi-os-${ARCH}.iso"
REQUIRED_SPACE_GB=10
LOG_FILE="$WORKDIR/build.log"

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

# Set the state file path for this build
export STATE_FILE="$WORKDIR/state/build.state"

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    log_info "Cleaning up orchestrator..."
    # Unmount any leftover bind mounts from chroot_setup in reverse order
    umount "$CHROOTDIR/dev/pts" 2>/dev/null || umount -l "$CHROOTDIR/dev/pts" 2>/dev/null || true
    umount "$CHROOTDIR/dev" 2>/dev/null || umount -l "$CHROOTDIR/dev" 2>/dev/null || true
    umount "$CHROOTDIR/proc" 2>/dev/null || umount -l "$CHROOTDIR/proc" 2>/dev/null || true
    umount "$CHROOTDIR/sys" 2>/dev/null || umount -l "$CHROOTDIR/sys" 2>/dev/null || true

    if [ $exit_code -eq 0 ]; then
        log_success "Build pipeline completed successfully."
        state_mark_complete "BUILD"
    else
        log_error "Build pipeline failed with exit code $exit_code."
        log_warn "You can resume the build by running this script again without --clean."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Main Build Process ---
main() {
    # Handle flags before any processing
    if [[ "${1:-}" == "--version" ]]; then
        echo "GTA VI OS (Vice OS) ISO Build Orchestrator"
        echo "Version: 1.0 Stable"
        echo "Build Pipeline: 10 phases (state-managed, resumable)"
        echo ""
        echo "Environment variables:"
        echo "  DEBIAN_ARCH=arm64    Target architecture (default: amd64)"
        echo "  DEBIAN_MIRROR=...    Custom Debian mirror URL"
        exit 0
    fi

    # Initialize log file
    echo "Build started at $(date)" > "$LOG_FILE"

    # Export architecture for all child build scripts
    export DEBIAN_ARCH="$ARCH"

    # Set SOURCE_DATE_EPOCH for reproducible builds across all phases
    if [ -z "${SOURCE_DATE_EPOCH:-}" ]; then
        if command -v git > /dev/null 2>&1 && git rev-parse --git-dir > /dev/null 2>&1; then
            export SOURCE_DATE_EPOCH=$(git log -1 --pretty=%ct 2>/dev/null || date +%s)
        else
            export SOURCE_DATE_EPOCH=$(date +%s)
        fi
    fi
    log_info "Build timestamp (SOURCE_DATE_EPOCH): $SOURCE_DATE_EPOCH"

    check_root
    check_host
    check_internet "deb.debian.org"
    check_disk_space "$WORKDIR" "$REQUIRED_SPACE_GB"
    check_dependencies "debootstrap" "grub-mkstandalone" "xorriso" "mksquashfs" "mcopy" "mmd" "mkfs.vfat" "curl"

    # Handle --clean flag
    if [[ "${1:-}" == "--clean" ]]; then
        log_info "Clean build requested. Removing existing chroot and state..."
        rm -rf "$CHROOTDIR"
        state_clear
        state_init
    else
        # If state file doesn't exist, initialize it
        if [ ! -f "$STATE_FILE" ]; then
            state_init
        fi
    fi

    log_info "=== Starting GTA VI OS (Vice OS) ISO Build Pipeline ==="

    # Step 1: Create RootFS (Delegates to build module)
    if ! state_is_complete "ROOTFS"; then
        bash "$WORKDIR/build/create_rootfs.sh" "$CHROOTDIR"
        state_mark_complete "ROOTFS"
    else
        log_warn "RootFS phase already complete. Skipping."
    fi

    # Step 2: Configure chroot (Delegates to orchestrator)
    if ! state_is_complete "CHROOT_CONFIG"; then
        bash "$WORKDIR/chroot_setup.sh" "$CHROOTDIR"
        state_mark_complete "CHROOT_CONFIG"
    else
        log_warn "Chroot configuration phase already complete. Skipping."
    fi

    # Step 3: Ensure initramfs exists and clean up old images
    if ! state_is_complete "INITRAMFS"; then
        log_info "Generating initramfs..."
        # Mount virtual filesystems needed by update-initramfs
        mount --bind /dev "$CHROOTDIR/dev" 2>/dev/null || true
        mount --bind /proc "$CHROOTDIR/proc" 2>/dev/null || true
        mount --bind /sys "$CHROOTDIR/sys" 2>/dev/null || true

        chroot "$CHROOTDIR" update-initramfs -u -k all

        # Unmount after initramfs generation
        umount "$CHROOTDIR/sys" 2>/dev/null || true
        umount "$CHROOTDIR/proc" 2>/dev/null || true
        umount "$CHROOTDIR/dev" 2>/dev/null || true

        log_info "Cleaning up old initramfs images..."
        local initrd_img
        initrd_img=$(find "$CHROOTDIR/boot/" -name 'initrd.img-*' -type f 2>/dev/null | sort -V | tail -n 1 || true)
        if [ -n "$initrd_img" ]; then
            find "$CHROOTDIR/boot/" -name 'initrd.img-*' -type f ! -name "$(basename "$initrd_img")" -delete 2>/dev/null || true
        fi
        state_mark_complete "INITRAMFS"
    else
        log_warn "Initramfs phase already complete. Skipping."
    fi

    # Step 4: Prepare ISO directory structure & Backup existing ISO
    if ! state_is_complete "ISO_PREP"; then
        log_info "Preparing ISO directory structure..."
        if [ -f "$OUTDIR/$ISO_NAME" ]; then
            mkdir -p "$OUTDIR/backups"
            local ts
            ts=$(get_timestamp)
            mv "$OUTDIR/$ISO_NAME" "$OUTDIR/backups/${ISO_NAME%.iso}_$ts.iso"
            log_warn "Existing ISO backed up to $OUTDIR/backups/"
            # Rotate backups: keep only the 3 most recent
            local keep=3
            (cd "$OUTDIR/backups" && ls -1t *.iso 2>/dev/null | tail -n +$((keep + 1)) | xargs -r rm -f) || true
            log_info "Backup rotation: keeping last $keep ISOs."
        fi

        rm -rf "$IMAGEDIR" "$SCRATCHDIR"
        mkdir -p "$IMAGEDIR/live" "$SCRATCHDIR" "$IMAGEDIR/boot/grub" "$OUTDIR"
        state_mark_complete "ISO_PREP"
    else
        log_warn "ISO Prep phase already complete. Skipping."
    fi

    # Step 5: Create SquashFS (Delegated to build module)
    if ! state_is_complete "SQUASHFS"; then
        bash "$WORKDIR/build/create_squashfs.sh" "$CHROOTDIR" "$IMAGEDIR"
        state_mark_complete "SQUASHFS"
    else
        log_warn "SquashFS phase already complete. Skipping."
    fi

    # Step 6: Copy kernel and initrd to ISO root
    if ! state_is_complete "KERNEL_COPY"; then
        log_info "Copying kernel and initrd..."
        local kernel_img
        local initrd_img
        kernel_img=$(find "$CHROOTDIR/boot/" -name 'vmlinuz-*' -type f | sort -V | tail -n 1)
        initrd_img=$(find "$CHROOTDIR/boot/" -name 'initrd.img-*' -type f | sort -V | tail -n 1)

        if [ -z "$kernel_img" ] || [ -z "$initrd_img" ]; then
            log_error "Kernel or initrd not found in chroot/boot!"
            exit 1
        fi

        cp "$kernel_img" "$IMAGEDIR/vmlinuz"
        cp "$initrd_img" "$IMAGEDIR/initrd.img"

        log_info "Creating GRUB marker file..."
        touch "$IMAGEDIR/VICE_OS"

        log_info "Copying GRUB configuration..."
        if [ ! -f "config/grub.cfg" ]; then
            log_error "config/grub.cfg not found!"
            exit 1
        fi
        cp config/grub.cfg "$IMAGEDIR/boot/grub/grub.cfg"

        state_mark_complete "KERNEL_COPY"
    else
        log_warn "Kernel copy phase already complete. Skipping."
    fi

    # Step 7: Create Bootloader Images (Delegated to build module)
    if ! state_is_complete "BOOTLOADER"; then
        bash "$WORKDIR/build/create_bootloader.sh" "$IMAGEDIR" "$SCRATCHDIR" "$ARCH"
        state_mark_complete "BOOTLOADER"
    else
        log_warn "Bootloader phase already complete. Skipping."
    fi

    # Step 8: Pack ISO (Delegated to build module)
    if ! state_is_complete "ISO_PACK"; then
        bash "$WORKDIR/build/pack_iso.sh" "$IMAGEDIR" "$SCRATCHDIR" "$OUTDIR" "$ISO_NAME" "$ISO_LABEL" "$ARCH"
        state_mark_complete "ISO_PACK"
    else
        log_warn "ISO Packing phase already complete. Skipping."
    fi

    # Step 9: Generate Build Metadata
    log_info "Generating build metadata..."
    local git_hash="unknown"
    if command -v git > /dev/null 2>&1; then
        git_hash=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
    fi

    # Safely retrieve kernel version even on resumed builds
    local kernel_ver="unknown"
    local kf
    kf=$(find "$CHROOTDIR/boot/" -name 'vmlinuz-*' -type f 2>/dev/null | sort -V | tail -n 1 || true)
    if [ -n "$kf" ]; then
        kernel_ver=$(basename "$kf" | sed 's/vmlinuz-//')
    elif [ -f "$IMAGEDIR/vmlinuz" ]; then
        kernel_ver="vmlinuz"
    fi

    local iso_size="0"
    if [ -f "$OUTDIR/$ISO_NAME" ]; then
        iso_size=$(du -sh "$OUTDIR/$ISO_NAME" | awk '{print $1}')
    fi

    cat <<METADATA > "$OUTDIR/build_info.txt"
Build Date: $(date)
Git Commit: $git_hash
Kernel Version: $kernel_ver
ISO Size: $iso_size
METADATA

    # Step 10: Generate SHA256 Checksum
    if [ ! -f "$OUTDIR/$ISO_NAME" ]; then
        log_error "ISO generation failed. Output file not found."
        exit 1
    fi

    log_info "Generating SHA256 checksum..."
    (cd "$OUTDIR" && sha256sum "$ISO_NAME" > SHA256SUMS)

    log_success "=== ISO build pipeline complete: $OUTDIR/$ISO_NAME ==="
}

main "$@"