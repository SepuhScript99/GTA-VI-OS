#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# Vice OS ISO Validator
# Validates the generated ISO image for structural integrity, bootability,
# and live-boot compatibility. Run against out/*.iso after build_iso.sh completes.
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
    local iso_type
    iso_type=$(file "$ISO_PATH")
    if echo "$iso_type" | grep -qi "iso 9660\|bootable\|x86 boot"; then
        log_success "ISO format is valid: $iso_type"
    else
        log_warn "ISO format may be invalid: $iso_type"
    fi

    # 3. Check El Torito boot record (BIOS boot)
    local has_bios_boot=false
    if isoinfo -d -i "$ISO_PATH" 2>/dev/null | grep -q "Booting from CD-ROM"; then
        log_success "El Torito BIOS boot record present."
        has_bios_boot=true
    else
        log_info "No El Torito BIOS boot record detected."
    fi

    # 4. Check UEFI boot image
    if isoinfo -d -i "$ISO_PATH" 2>/dev/null | grep -q "UDF"; then
        log_success "UDF filesystem detected (UEFI compatible)."
    fi

    # 5. Check ISO contains required live-boot artifacts
    log_info "Checking live-boot artifacts inside ISO..."
    local required_iso_files=(
        "boot/grub/grub.cfg"
        "vmlinuz"
        "initrd.img"
        "live/filesystem.squashfs"
    )

    local missing_iso_files=0
    for f in "${required_iso_files[@]}"; do
        if isoinfo -J -i "$ISO_PATH" -f 2>/dev/null | grep -q "^/$f$"; then
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

    # 6. Validate SquashFS integrity inside ISO
    log_info "Validating SquashFS integrity..."
    local squashfs_file
    squashfs_file=$(isoinfo -J -i "$ISO_PATH" -f 2>/dev/null | grep "live/filesystem.squashfs$" | head -n 1)
    if [ -z "$squashfs_file" ]; then
        log_error "SquashFS not found in ISO"
        EXIT_CODE=1
    else
        local squashfs_tmp
        squashfs_tmp=$(mktemp)
        TEMP_FILES+=("$squashfs_tmp")

        if isoinfo -J -i "$ISO_PATH" -x "$squashfs_file" > "$squashfs_tmp" 2>/dev/null; then
            local squashfs_type
            squashfs_type=$(file "$squashfs_tmp")
            if echo "$squashfs_type" | grep -qi "squashfs"; then
                local sqfs_size
                sqfs_size=$(du -h "$squashfs_tmp" | awk '{print $1}')
                log_success "SquashFS integrity valid (Size: $sqfs_size)."

                # Additional check: verify squashfs superblock and listing without extracting
                if command -v unsquashfs >/dev/null 2>&1; then
                    if unsquashfs -s "$squashfs_tmp" >/dev/null 2>&1; then
                        local sqfs_count
                        sqfs_count=$(unsquashfs -l "$squashfs_tmp" 2>/dev/null | wc -l || echo "0")
                        log_success "SquashFS superblock valid and listable ($sqfs_count entries)."
                    else
                        log_warn "SquashFS superblock check failed. May be corrupted."
                    fi
                fi
            else
                log_error "SquashFS format invalid: $squashfs_type"
                EXIT_CODE=1
            fi
        else
            log_error "Failed to extract SquashFS from ISO for validation."
            EXIT_CODE=1
        fi
    fi

    # 7. Validate kernel (vmlinuz) inside ISO
    log_info "Validating kernel inside ISO..."
    local vmlinuz_tmp
    vmlinuz_tmp=$(mktemp)
    TEMP_FILES+=("$vmlinuz_tmp")

    if isoinfo -J -i "$ISO_PATH" -x "/vmlinuz" > "$vmlinuz_tmp" 2>/dev/null; then
        local vmlinuz_type
        vmlinuz_type=$(file "$vmlinuz_tmp")
        if echo "$vmlinuz_type" | grep -qi "linux kernel\|elf\|x86-64"; then
            log_success "Kernel image is valid: $vmlinuz_type"
        else
            log_warn "Kernel image format may be invalid: $vmlinuz_type"
        fi
    else
        log_error "Failed to extract kernel from ISO."
        EXIT_CODE=1
    fi

    # 8. Validate initramfs inside ISO
    log_info "Validating initramfs inside ISO..."
    local initrd_tmp
    initrd_tmp=$(mktemp)
    TEMP_FILES+=("$initrd_tmp")

    if isoinfo -J -i "$ISO_PATH" -x "/initrd.img" > "$initrd_tmp" 2>/dev/null; then
        local initrd_type
        initrd_type=$(file "$initrd_tmp")
        if echo "$initrd_type" | grep -qi "gzip\|LZ4\|XZ\|cpio\|ASCII cpio"; then
            log_success "Initramfs format is valid: $initrd_type"
        else
            log_warn "Initramfs format may be invalid: $initrd_type"
        fi

        # Check size
        local initrd_bytes
        initrd_bytes=$(stat -c%s "$initrd_tmp" 2>/dev/null || stat -f%z "$initrd_tmp" 2>/dev/null || echo "0")
        if [ "$initrd_bytes" -lt 1000000 ]; then
            log_warn "Initramfs is unusually small (${initrd_bytes} bytes). May be truncated."
        fi
    else
        log_error "Failed to extract initramfs from ISO."
        EXIT_CODE=1
    fi

    # 9. Validate GRUB configuration
    log_info "Validating GRUB configuration..."
    local grub_tmp
    grub_tmp=$(mktemp)
    TEMP_FILES+=("$grub_tmp")

    if isoinfo -J -i "$ISO_PATH" -x "/boot/grub/grub.cfg" > "$grub_tmp" 2>/dev/null; then
        if grep -q "linux /vmlinuz" "$grub_tmp"; then
            log_success "GRUB configuration contains kernel boot entry."
        else
            log_error "GRUB configuration missing kernel boot entry."
            EXIT_CODE=1
        fi

        if grep -q "initrd /initrd.img" "$grub_tmp"; then
            log_success "GRUB configuration contains initramfs entry."
        else
            log_error "GRUB configuration missing initramfs entry."
            EXIT_CODE=1
        fi
    else
        log_error "Failed to extract GRUB config from ISO."
        EXIT_CODE=1
    fi

    # 10. Check SHA256 checksum file exists
    local sha256_file="${ISO_PATH%.iso}.sha256"
    if [ ! -f "$sha256_file" ] && [ ! -f "${ISO_PATH}.sha256" ]; then
        # Check in out/ directory
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