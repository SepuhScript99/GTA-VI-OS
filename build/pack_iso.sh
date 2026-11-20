#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) ISO Packer
# Assembles the final hybrid BIOS/UEFI bootable ISO using xorriso.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"
install_cleanup

# --- Arguments ---
IMAGEDIR="${1:?Error: IMAGEDIR argument required}"
SCRATCHDIR="${2:?Error: SCRATCHDIR argument required}"
OUTDIR="${3:?Error: OUTDIR argument required}"
ISO_NAME="${4:?Error: ISO_NAME argument required}"
ISO_LABEL="${5:?Error: ISO_LABEL argument required}"
ARCH="${6:-${DEBIAN_ARCH:-amd64}}"

ISO_OUTPUT="$OUTDIR/$ISO_NAME"

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ] && [ -f "$ISO_OUTPUT" ]; then
        log_warn "ISO packing failed. Removing partial ISO artifact..."
        rm -f "$ISO_OUTPUT"
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Main ---
main() {
    check_dependencies "xorriso"

    log_info "Target architecture: ${ARCH}"

    log_info "Validating boot artifacts..."
    local required_files=(
        "$IMAGEDIR/vmlinuz"
        "$IMAGEDIR/initrd.img"
        "$IMAGEDIR/VICE_OS"
        "$IMAGEDIR/live/filesystem.squashfs"
        "$IMAGEDIR/boot/grub/grub.cfg"
        "$SCRATCHDIR/efiboot.img"
    )

    # BIOS boot image is only required for x86_64
    if [ "${ARCH}" != "arm64" ]; then
        required_files+=("$SCRATCHDIR/bios.img")
    fi

    for file in "${required_files[@]}"; do
        if [ ! -f "$file" ]; then
            log_error "Required artifact not found: $file"
            exit 1
        fi
    done

    log_info "Packing final ISO with xorriso..."
    mkdir -p "$OUTDIR"

    rm -f "$ISO_OUTPUT"

    # Export SOURCE_DATE_EPOCH for reproducible ISO timestamps
    export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(date +%s)}"

    local xorriso_args=(
        "-as" "mkisofs" "-r" "-J" "-joliet-long" "-iso-level" "3"
        "-full-iso9660-filenames" "-volid" "$ISO_LABEL"
        "--eltorito-catalog" "boot/grub/boot.cat"
    )

    if [ "${ARCH}" != "arm64" ]; then
        # BIOS/El Torito boot (x86_64: Hybrid BIOS MBR + UEFI)
        local mbr_img="/usr/lib/grub/i386-pc/boot_hybrid.img"
        if [ ! -f "$mbr_img" ]; then
            log_error "MBR template $mbr_img not found. Is grub-pc-bin installed?"
            exit 1
        fi

        xorriso_args+=(
            "--grub2-boot-info" "--grub2-mbr" "$mbr_img"
            "-eltorito-boot" "boot/grub/bios.img" "-no-emul-boot" "-boot-load-size" "4" "-boot-info-table"
            "-eltorito-alt-boot" "-e" "EFI/efiboot.img" "-no-emul-boot"
            "-isohybrid-gpt-basdat"
        )
    else
        # ARM64: Pure UEFI (EFI is the primary El Torito boot entry)
        xorriso_args+=(
            "-eltorito-boot" "EFI/efiboot.img" "-no-emul-boot"
            "-isohybrid-gpt-basdat"
        )
    fi

    xorriso_args+=(
        "--append_partition" "2" "0xef" "$SCRATCHDIR/efiboot.img"
        "-output" "$ISO_OUTPUT"
        "-graft-points"
        "$IMAGEDIR"=
        "/EFI/efiboot.img=$SCRATCHDIR/efiboot.img"
    )

    # BIOS boot image graft (x86_64 only)
    if [ "${ARCH}" != "arm64" ]; then
        xorriso_args+=(
            "/boot/grub/bios.img=$SCRATCHDIR/bios.img"
        )
    fi

    if ! xorriso "${xorriso_args[@]}"; then

        log_error "xorriso failed to create the ISO image."
        exit 1
    fi

    if [ ! -s "$ISO_OUTPUT" ]; then
        log_error "xorriso completed but ISO file is missing or zero bytes."
        exit 1
    fi

    local size
    size=$(du -sh "$ISO_OUTPUT" | awk '{print $1}')
    log_success "ISO packed successfully at $ISO_OUTPUT (Size: $size)"
}

main "$@"