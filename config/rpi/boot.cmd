# ============================================================================
# GTA VI OS (Vice OS) U-Boot Boot Script for ARM64 / Raspberry Pi
# Compile with: mkimage -C none -A arm64 -T script -d boot.cmd boot.scr
# ============================================================================

setenv bootargs "console=serial0,115200 console=tty1 root=live:LABEL=VICE_OS boot=live components quiet loglevel=3 systemd.show_status=0 fsck.mode=skip"

echo "=== Booting GTA VI OS (Vice OS) ARM64 ==="

# Search for kernel and initramfs on current boot device
if test -e ${devtype} ${devnum}:${distro_bootpart} /vmlinuz; then
    echo "Loading kernel..."
    load ${devtype} ${devnum}:${distro_bootpart} ${kernel_addr_r} /vmlinuz
    echo "Loading initrd..."
    load ${devtype} ${devnum}:${distro_bootpart} ${ramdisk_addr_r} /initrd.img
    echo "Starting kernel via booti..."
    booti ${kernel_addr_r} ${ramdisk_addr_r}:${filesize} ${fdt_addr}
fi
