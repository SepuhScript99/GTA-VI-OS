#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: Build Optimization
# Reduces ISO size, optimizes boot time, rebuilds font/desktop caches, and
# tunes memory management. Runs before 99_cleanup.sh.
# ============================================================================

if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "=== Starting build optimization ==="

    # ── 1. Remove unnecessary documentation ──
    log_info "Removing unnecessary documentation..."
    rm -rf /usr/share/doc/* 2>/dev/null || true
    rm -rf /usr/share/man/* 2>/dev/null || true
    rm -rf /usr/share/info/* 2>/dev/null || true
    rm -rf /usr/share/lintian/* 2>/dev/null || true

    # ── 2. Keep only en_US locale ──
    log_info "Optimizing locales..."
    local locale_archive="/usr/lib/locale/locale-archive"
    if [ -f "$locale_archive" ]; then
        local locale_dir
        locale_dir=$(dirname "$locale_archive")
        find "$locale_dir" -type f ! -name "en_US*" ! -name "locale-archive" -delete 2>/dev/null || true
    fi
    # Remove unused locale definitions
    find /usr/share/locale -maxdepth 1 -type d ! -name "locale" ! -name "en_US" ! -name "en@boldquot" ! -name "en@quot" -exec rm -rf {} + 2>/dev/null || true

    # ── 3. Clean apt cache aggressively ──
    log_info "Cleaning apt cache..."
    apt-get clean -qq 2>/dev/null || true
    rm -rf /var/lib/apt/lists/* 2>/dev/null || true
    rm -rf /var/cache/apt/*.bin 2>/dev/null || true
    rm -rf /var/cache/apt/archives/partial/* 2>/dev/null || true

    # ── 4. Remove unnecessary kernel modules (keep common drivers & sound/GPU) ──
    log_info "Removing unnecessary kernel modules..."
    local modules_dir="/lib/modules"
    if [ -d "$modules_dir" ]; then
        for kv in "$modules_dir"/*/; do
            if [ -d "$kv/kernel/drivers/net/ethernet/amd" ]; then
                rm -rf "$kv/kernel/drivers/net/ethernet/amd" 2>/dev/null || true
            fi
            if [ -d "$kv/kernel/drivers/net/ethernet/atheros" ]; then
                rm -rf "$kv/kernel/drivers/net/ethernet/atheros" 2>/dev/null || true
            fi
            if [ -d "$kv/kernel/drivers/infiniband" ]; then
                rm -rf "$kv/kernel/drivers/infiniband" 2>/dev/null || true
            fi
            # Regenerate module dependency tree after stripping modules
            local kver
            kver=$(basename "$kv")
            if command -v depmod >/dev/null 2>&1 && [ -n "$kver" ]; then
                depmod -a "$kver" 2>/dev/null || true
            fi
        done
    fi

    # ── 5. Keep firmware lean — remove only floppy/obsolete ──
    log_info "Cleaning obsolete firmware..."
    local firmware_dir="/lib/firmware"
    if [ -d "$firmware_dir" ]; then
        rm -rf "$firmware_dir/ql2400"* "$firmware_dir/ql2500"* 2>/dev/null || true
        rm -rf "$firmware_dir/liquidio" 2>/dev/null || true
    fi

    # ── 6. Mask slow-starting or unnecessary systemd services and their timers ──
    log_info "Masking non-essential systemd services and timers for faster boot..."
    local services_to_mask=(
        "apt-daily.service" "apt-daily.timer"
        "apt-daily-upgrade.service" "apt-daily-upgrade.timer"
        "man-db.service" "man-db.timer"
    )
    for svc in "${services_to_mask[@]}"; do
        systemctl mask "$svc" 2>/dev/null || true
    done

    # ── 7. Enable early OOM killer for low-memory responsiveness ──
    log_info "Enabling early OOM killer configuration..."
    mkdir -p /etc/systemd/system.conf.d
    cat <<SYSTEMD > /etc/systemd/system.conf.d/99-vice-oom.conf
[Manager]
DefaultOOMPolicy=continue
SYSTEMD

    # ── 8. Tune kernel parameters for desktop responsiveness (ZRAM-compatible) ──
    log_info "Tuning kernel parameters..."
    mkdir -p /etc/sysctl.d
    cat <<SYSCTL > /etc/sysctl.d/99-vice-desktop.conf
# Vice OS desktop responsiveness tuning
vm.swappiness=100
vm.vfs_cache_pressure=50
vm.dirty_ratio=15
vm.dirty_background_ratio=5
kernel.numa_balancing=0
SYSCTL

    # ── 9. Safeguard PipeWire drop-in & rebuild font/desktop/icon/MIME caches ──
    if [ -f /etc/pipewire/pipewire.conf.d/10-vice-audio.conf ]; then
        rm -f /etc/pipewire/pipewire.conf
    fi
    if command -v fc-cache >/dev/null 2>&1; then
        log_info "Refreshing system fontconfig cache..."
        fc-cache -f 2>/dev/null || true
    fi
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database -q /usr/share/applications 2>/dev/null || true
    fi
    if command -v update-mime-database >/dev/null 2>&1 && [ -d /usr/share/mime ]; then
        update-mime-database /usr/share/mime 2>/dev/null || true
    fi
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        for theme_dir in /usr/share/icons/Papirus-Dark /usr/share/icons/hicolor; do
            if [ -d "$theme_dir" ]; then
                gtk-update-icon-cache -q -f "$theme_dir" 2>/dev/null || true
            fi
        done
    fi

    log_success "Build optimization completed."
}

main "$@"
