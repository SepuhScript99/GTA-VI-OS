#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: Raspberry Pi & ARM64 Boot Configuration
# Configures Raspberry Pi firmware (config.txt, cmdline.txt), U-Boot boot script,
# hardware overlays, and serial console when building for ARM64 targets.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    # 1. Check build architecture
    local build_arch="amd64"
    if [ -f /etc/vice-build.conf ]; then
        # shellcheck disable=SC1091
        source /etc/vice-build.conf
        build_arch="${DEBIAN_ARCH:-amd64}"
    fi

    if [ "${build_arch}" != "arm64" ]; then
        log_info "Skipping Raspberry Pi / ARM64 configuration (build arch: ${build_arch})."
        return 0
    fi

    log_info "=== Configuring Raspberry Pi & ARM64 Boot Subsystem ==="

    # 2. Ensure target boot directories exist
    mkdir -p /boot/firmware /boot/firmware/overlays

    # 3. Install config.txt and cmdline.txt
    if [ -d /vice_payload/config/rpi ]; then
        log_info "Installing Raspberry Pi firmware configuration..."
        if [ -f /vice_payload/config/rpi/config.txt ]; then
            cp /vice_payload/config/rpi/config.txt /boot/firmware/config.txt
            cp /vice_payload/config/rpi/config.txt /boot/config.txt 2>/dev/null || true
            chmod 644 /boot/firmware/config.txt
            log_info "Installed: /boot/firmware/config.txt"
        fi

        if [ -f /vice_payload/config/rpi/cmdline.txt ]; then
            cp /vice_payload/config/rpi/cmdline.txt /boot/firmware/cmdline.txt
            cp /vice_payload/config/rpi/cmdline.txt /boot/cmdline.txt 2>/dev/null || true
            chmod 644 /boot/firmware/cmdline.txt
            log_info "Installed: /boot/firmware/cmdline.txt"
        fi

        # 4. Install U-Boot boot script
        if [ -f /vice_payload/config/rpi/boot.cmd ]; then
            cp /vice_payload/config/rpi/boot.cmd /boot/boot.cmd
            if command -v mkimage > /dev/null 2>&1; then
                log_info "Compiling U-Boot boot script (boot.scr)..."
                mkimage -C none -A arm64 -T script -d /boot/boot.cmd /boot/boot.scr > /dev/null 2>&1 || true
                cp /boot/boot.scr /boot/firmware/boot.scr 2>/dev/null || true
            else
                log_info "Installing plain boot script..."
                cp /vice_payload/config/rpi/boot.cmd /boot/firmware/boot.cmd 2>/dev/null || true
            fi
        fi
    fi

    # 5. Configure raspi-firmware defaults
    log_info "Configuring raspi-firmware defaults..."
    mkdir -p /etc/default
    cat <<'RPI_DEF' > /etc/default/raspi-firmware
# /etc/default/raspi-firmware
# Configuration for Debian raspi-firmware package on Vice OS
CONSOLENAME="serial0"
BAUDRATE="115200"
ROOTPART="/dev/mmcblk0p2"
KERNEL="vmlinuz"
INITRAMFS="initrd.img"
RPI_DEF
    chmod 644 /etc/default/raspi-firmware

    # 6. Configure Raspberry Pi hardware kernel modules
    log_info "Configuring hardware kernel modules for ARM64..."
    mkdir -p /etc/modules-load.d
    cat <<'RPI_MODS' > /etc/modules-load.d/rpi-hardware.conf
# Raspberry Pi hardware kernel modules
vc4
v3d
snd_bcm2835
i2c-dev
spidev
bcm2835-gpiomem
RPI_MODS
    chmod 644 /etc/modules-load.d/rpi-hardware.conf

    # 7. Configure serial console for headless debugging
    log_info "Enabling serial console for debugging..."
    if command -v systemctl > /dev/null 2>&1; then
        systemctl enable serial-getty@serial0.service 2>/dev/null || true
        systemctl enable serial-getty@ttyAMA0.service 2>/dev/null || true
    fi

    log_success "Raspberry Pi & ARM64 boot configuration completed."
}

main "$@"
