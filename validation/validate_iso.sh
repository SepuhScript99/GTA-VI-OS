#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# Vice OS ISO Validator
# Validates the generated ISO image for structural integrity, bootability,
# and live-boot compatibility. Run against out/*.iso after build_iso.sh completes.
# Uses xorriso exclusively (safe for >2 GB ISOs; avoids isoinfo 2 GB limits).
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"

ISO_PATH="${1:-$WORKDIR/out/gta-vi-os-amd64.iso}"
EXIT_CODE=0

TEMP_FILES=()
TEMP_DIRS=()
cleanup() {
    local code=$?
    for f in "${TEMP_FILES[@]}"; do
        rm -f "$f" 2>/dev/null || true
    done
    for d in "${TEMP_DIRS[@]}"; do
        chmod -R u+w "$d" 2>/dev/null || true
        rm -rf "$d" 2>/dev/null || true
    done
    if [ $code -ne 0 ]; then
        log_error "Operation failed with exit code $code."
    fi
    exit $code
}
install_cleanup

main() {
    log_info "=== Validating ISO: $ISO_PATH ==="

    check_dependencies "xorriso"

    if [ ! -f "$ISO_PATH" ]; then
        log_error "ISO not found: $ISO_PATH"
        log_info "Run build_iso.sh first to generate the ISO."
        exit 1
    fi

    # 1. Check ISO size is non-zero and within reasonable bounds
    local iso_size_bytes
    iso_size_bytes=$(stat -c%s "$ISO_PATH" 2>/dev/null || stat -f%z "$ISO_PATH" 2>/dev/null || echo "0")
    local iso_size_human
    iso_size_human=$(du -h "$ISO_PATH" | awk '{print $1}')

    if [ "$iso_size_bytes" -eq 0 ]; then
        log_error "ISO is zero bytes. Build may have failed."
        EXIT_CODE=1
    elif [ "$iso_size_bytes" -lt 104857600 ]; then
        log_warn "ISO is unusually small (${iso_size_human}). May be truncated."
    else
        log_success "ISO size: $iso_size_human ($iso_size_bytes bytes)"
    fi

    # 2. Check ISO is a valid ISO9660 image
    if command -v file >/dev/null 2>&1; then
        local iso_type
        iso_type=$(file "$ISO_PATH" 2>/dev/null || true)
        if printf '%s\n' "$iso_type" | grep -iE "iso 9660|bootable|x86 boot|dos/mbr" >/dev/null; then
            log_success "ISO format is valid: $iso_type"
        else
            log_warn "ISO format may be invalid: $iso_type"
        fi
    fi

    # 3. Check El Torito boot records (BIOS & UEFI) and Hybrid MBR via xorriso
    local xorriso_report
    xorriso_report=$(xorriso -indev "$ISO_PATH" -report_el_torito plain -report_system_area plain 2>&1 || true)

    if printf '%s\n' "$xorriso_report" | grep -iE "El Torito (boot catalog|cat path|boot img)" >/dev/null; then
        log_success "El Torito boot record present."
    else
        log_error "No El Torito boot record detected."
        EXIT_CODE=1
    fi

    if printf '%s\n' "$xorriso_report" | grep -iE "EFI boot|UEFI|efiboot\.img" >/dev/null; then
        log_success "UEFI boot image detected."
    else
        log_warn "No UEFI boot image detected in El Torito report."
    fi

    if printf '%s\n' "$xorriso_report" | grep -i "System area summary:.*MBR" >/dev/null; then
        log_success "Hybrid MBR detected (USB bootable)."
    fi

    # 4. Check ISO contains required live-boot artifacts via xorriso -find /
    log_info "Checking live-boot artifacts inside ISO..."
    local iso_listing
    iso_listing=$(xorriso -indev "$ISO_PATH" -find / 2>/dev/null || true)

    local required_iso_files=(
        "boot/grub/grub.cfg"
        "vmlinuz"
        "initrd.img"
        "live/filesystem.squashfs"
    )

    local missing_iso_files=0
    local f
    for f in "${required_iso_files[@]}"; do
        if printf '%s\n' "$iso_listing" | grep -E "^'?/${f}'?$" >/dev/null; then
            log_info "  $f: present"
        else
            log_error "  $f: missing from ISO"
            missing_iso_files=$((missing_iso_files + 1))
            EXIT_CODE=1
        fi
    done

    if [ "$missing_iso_files" -eq 0 ]; then
        log_success "All required live-boot artifacts present in ISO."
    fi

    # 5. Validate SquashFS metadata inside ISO without extracting (>2 GB safe)
    log_info "Validating SquashFS metadata inside ISO (without extracting)..."
    local squashfs_lsl squashfs_size_bytes
    squashfs_lsl=$(xorriso -indev "$ISO_PATH" -lsl /live/filesystem.squashfs 2>/dev/null || true)
    squashfs_size_bytes=$(printf '%s\n' "$squashfs_lsl" | awk '/filesystem\.squashfs/{print $5; exit}')
    if [ -z "$squashfs_size_bytes" ] || [[ ! "$squashfs_size_bytes" =~ ^[0-9]+$ ]] || [ "$squashfs_size_bytes" -le 0 ]; then
        log_error "SquashFS not found or zero bytes in ISO (${squashfs_size_bytes:-0} bytes)."
        EXIT_CODE=1
    elif [ "$squashfs_size_bytes" -le 1000000 ]; then
        log_error "SquashFS is unusually small (${squashfs_size_bytes} bytes)."
        EXIT_CODE=1
    else
        local sqfs_size_mb
        sqfs_size_mb=$(awk "BEGIN {printf \"%.1fM\", $squashfs_size_bytes / 1048576}")
        log_success "SquashFS verified inside ISO ($sqfs_size_mb, $squashfs_size_bytes bytes)."
    fi

    # 6. Extract ONLY small boot artifacts (/vmlinuz, /initrd.img, /boot/grub/grub.cfg)
    local extract_dir
    extract_dir=$(mktemp -d)
    TEMP_DIRS+=("$extract_dir")

    local vmlinuz_tmp="$extract_dir/vmlinuz"
    local initrd_tmp="$extract_dir/initrd.img"
    local grub_tmp="$extract_dir/grub.cfg"

    log_info "Extracting small boot artifacts (/vmlinuz, /initrd.img, /boot/grub/grub.cfg)..."
    if ! xorriso -indev "$ISO_PATH" -osirrox on \
        -extract /vmlinuz "$vmlinuz_tmp" \
        -extract /initrd.img "$initrd_tmp" \
        -extract /boot/grub/grub.cfg "$grub_tmp" >/dev/null 2>&1; then
        log_warn "Batch xorriso extraction returned non-zero; retrying per-file extraction..."
        xorriso -indev "$ISO_PATH" -osirrox on -extract /vmlinuz "$vmlinuz_tmp" >/dev/null 2>&1 || true
        xorriso -indev "$ISO_PATH" -osirrox on -extract /initrd.img "$initrd_tmp" >/dev/null 2>&1 || true
        xorriso -indev "$ISO_PATH" -osirrox on -extract /boot/grub/grub.cfg "$grub_tmp" >/dev/null 2>&1 || true
    fi

    # 7. Validate kernel (vmlinuz) inside ISO
    log_info "Validating kernel inside ISO..."
    if [ -s "$vmlinuz_tmp" ]; then
        if command -v file >/dev/null 2>&1; then
            local vmlinuz_type
            vmlinuz_type=$(file "$vmlinuz_tmp" 2>/dev/null || true)
            if printf '%s\n' "$vmlinuz_type" | grep -iE "linux kernel|elf|x86-64|aarch64|arm64|pe32|efi" >/dev/null; then
                log_success "Kernel image is valid: $vmlinuz_type"
            else
                log_warn "Kernel image format may be invalid: $vmlinuz_type"
            fi
        else
            log_success "Kernel image extracted ($(stat -c%s "$vmlinuz_tmp" 2>/dev/null || echo "?") bytes)."
        fi
    else
        log_error "Failed to extract kernel (/vmlinuz) from ISO."
        EXIT_CODE=1
    fi

    # 8. Validate initramfs inside ISO
    log_info "Validating initramfs inside ISO..."
    if [ -s "$initrd_tmp" ]; then
        if command -v file >/dev/null 2>&1; then
            local initrd_type
            initrd_type=$(file "$initrd_tmp" 2>/dev/null || true)
            if printf '%s\n' "$initrd_type" | grep -iE "gzip|lz4|xz|zstd|cpio|ascii cpio" >/dev/null; then
                log_success "Initramfs format is valid: $initrd_type"
            else
                log_warn "Initramfs format may be invalid: $initrd_type"
            fi
        fi

        local initrd_bytes
        initrd_bytes=$(stat -c%s "$initrd_tmp" 2>/dev/null || stat -f%z "$initrd_tmp" 2>/dev/null || echo "0")
        if [ "$initrd_bytes" -lt 1000000 ]; then
            log_warn "Initramfs is unusually small (${initrd_bytes} bytes). May be truncated."
        else
            log_success "Initramfs size valid (${initrd_bytes} bytes)."
        fi
    else
        log_error "Failed to extract initramfs (/initrd.img) from ISO."
        EXIT_CODE=1
    fi

    # 9. Validate GRUB configuration
    log_info "Validating GRUB configuration..."
    if [ -s "$grub_tmp" ]; then
        if grep -F "linux /vmlinuz" "$grub_tmp" >/dev/null; then
            log_success "GRUB configuration contains kernel boot entry."
        else
            log_error "GRUB configuration missing kernel boot entry."
            EXIT_CODE=1
        fi

        if grep -F "initrd /initrd.img" "$grub_tmp" >/dev/null; then
            log_success "GRUB configuration contains initramfs entry."
        else
            log_error "GRUB configuration missing initramfs entry."
            EXIT_CODE=1
        fi
    else
        log_error "Failed to extract GRUB config (/boot/grub/grub.cfg) from ISO."
        EXIT_CODE=1
    fi

    # 10. Check SHA256 checksum file exists
    local sha256_file="${ISO_PATH%.iso}.sha256"
    if [ ! -f "$sha256_file" ] && [ ! -f "${ISO_PATH}.sha256" ]; then
        sha256_file="$WORKDIR/out/SHA256SUMS"
        if [ ! -f "$sha256_file" ]; then
            log_warn "SHA256SUMS not found alongside ISO."
        fi
    fi

    if [ -f "$sha256_file" ]; then
        log_success "SHA256 checksum file present: $sha256_file"
    fi

    # 11. Check build_info.txt exists
    local build_info="$WORKDIR/out/build_info.txt"
    if [ -f "$build_info" ]; then
        log_success "Build metadata present."
    else
        log_warn "Build metadata not found: $build_info"
    fi

    echo ""
    if [ "$EXIT_CODE" -eq 0 ]; then
        log_success "ISO validation passed."
    else
        log_error "ISO validation failed."
    fi

    exit $EXIT_CODE
}

main "$@"
