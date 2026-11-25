#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# Vice OS Validation Integration Test
# Runs all validation scripts against the current state and reports results.
# Can run without a built chroot (skips chroot-dependent tests).
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

PASSED=0
FAILED=0
SKIPPED=0

record_result() {
    local test_name="$1"
    local result="$2"

    case "$result" in
        PASS)
            log_success "[PASS] $test_name"
            PASSED=$((PASSED + 1))
            ;;
        FAIL)
            log_error "[FAIL] $test_name"
            FAILED=$((FAILED + 1))
            ;;
        SKIP)
            log_info "[SKIP] $test_name"
            SKIPPED=$((SKIPPED + 1))
            ;;
    esac
}

# Test 1: Package list validation (can run without chroot)
test_package_list() {
    log_info "--- Test: Package list validation ---"

    if [ ! -f "$WORKDIR/validation/validate_packages.sh" ]; then
        record_result "Package list validation script exists" FAIL
        return
    fi
    record_result "Package list validation script exists" PASS

    if bash "$WORKDIR/validation/validate_packages.sh" 2>&1; then
        record_result "Package list validation passes" PASS
    else
        record_result "Package list validation passes" FAIL
    fi
}

# Test 2: Package list contains critical packages
test_critical_packages() {
    log_info "--- Test: Critical packages present ---"
    local pkg_list="$WORKDIR/config/packages.list"
    local missing=0

    for pkg in thunar stalonetray firefox-esr xorg openbox python3-pyqt5 pipewire pipewire-pulse wireplumber alsa-utils ffmpeg libavcodec-extra fonts-noto-cjk polkitd librsvg2-common; do
        if grep -q "^$pkg$" "$pkg_list"; then
            :
        else
            log_error "Missing critical package: $pkg"
            missing=$((missing + 1))
        fi
    done

    if [ "$missing" -eq 0 ]; then
        record_result "All critical packages present in packages.list" PASS
    else
        record_result "All critical packages present in packages.list" FAIL
    fi
}

# Test 3: Desktop files exist
test_desktop_files() {
    log_info "--- Test: Desktop configuration files ---"
    local missing=0

    for f in vice-os-compositor.desktop vice-os-wallpaper.desktop vice-os-shell.desktop vice-os-settings.desktop; do
        if [ ! -f "$WORKDIR/config/$f" ]; then
            log_error "Missing desktop file: $f"
            missing=$((missing + 1))
        fi
    done

    if [ "$missing" -eq 0 ]; then
        record_result "All desktop files present" PASS
    else
        record_result "All desktop files present" FAIL
    fi
}

# Test 4: New desktop helper modules exist
test_desktop_modules() {
    log_info "--- Test: Desktop helper modules ---"
    local missing=0

    for mod in systray_manager.py power_manager.py wallpaper_manager.py session_watchdog.py panel_config.py vice_settings.py vice_settings_pages.py vice_launcher.py welcome_wizard.py; do
        if [ ! -f "$WORKDIR/desktop/$mod" ]; then
            log_error "Missing desktop module: $mod"
            missing=$((missing + 1))
        fi
    done

    if [ "$missing" -eq 0 ]; then
        record_result "All desktop helper modules present" PASS
    else
        record_result "All desktop helper modules present" FAIL
    fi
}

# Test 5: Shared library functions exist (Python)
test_shared_library() {
    log_info "--- Test: Shared Python library exports ---"

    local lib="$WORKDIR/lib/python/vice_utils.py"
    if [ ! -f "$lib" ]; then
        record_result "vice_utils.py exists" FAIL
        return
    fi
    record_result "vice_utils.py exists" PASS

    local missing=0
    for func in get_battery_status is_process_running get_disk_usage get_cpu_usage get_ram_usage launch_command; do
        if grep -q "def $func" "$lib"; then
            :
        else
            log_error "Missing function: $func"
            missing=$((missing + 1))
        fi
    done

    if [ "$missing" -eq 0 ]; then
        record_result "All shared library functions present" PASS
    else
        record_result "All shared library functions present" FAIL
    fi
}

# Test 6: Shared library functions exist (Bash)
test_shared_bash_library() {
    log_info "--- Test: Shared bash library exports ---"

    local lib="$WORKDIR/lib/common.sh"
    if [ ! -f "$lib" ]; then
        record_result "common.sh exists" FAIL
        return
    fi
    record_result "common.sh exists" PASS

    local missing=0
    for func in bootstrap_script init_script install_cleanup retry_command get_timestamp log_info log_error check_root check_dependencies; do
        if ! grep -qE "^${func}\b" "$lib" 2>/dev/null; then
            log_error "Missing bash function: $func"
            missing=$((missing + 1))
        fi
    done

    if [ "$missing" -eq 0 ]; then
        record_result "All bash library functions present" PASS
    else
        record_result "All bash library functions present" FAIL
    fi
}

# Test 7: Recovery scripts exist
test_recovery_scripts() {
    log_info "--- Test: Recovery scripts ---"
    local missing=0

    for s in rebuild_grub.sh reset_password.sh reset_network.sh vice-recovery.sh; do
        if [ ! -f "$WORKDIR/recovery/$s" ]; then
            log_error "Missing recovery script: $s"
            missing=$((missing + 1))
        fi
    done

    if [ "$missing" -eq 0 ]; then
        record_result "All recovery scripts present" PASS
    else
        record_result "All recovery scripts present" FAIL
    fi
}

# Test 8: Chroot scripts count and ordering
test_chroot_scripts() {
    log_info "--- Test: Chroot scripts ---"

    local count
    count=$(ls "$WORKDIR/chroot_scripts"/*.sh 2>/dev/null | wc -l)
    if [ "$count" -eq 49 ]; then
        record_result "49 chroot scripts present ($count found)" PASS
    else
        record_result "49 chroot scripts present ($count found)" FAIL
    fi

    # Check cleanup runs last
    if [ -f "$WORKDIR/chroot_scripts/99_cleanup.sh" ]; then
        record_result "Cleanup script runs last (99_cleanup.sh)" PASS
    else
        record_result "Cleanup script runs last (99_cleanup.sh)" FAIL
    fi
}

# Test 9: CI pipeline exists
test_ci_pipeline() {
    log_info "--- Test: CI pipeline ---"

    if [ -f "$WORKDIR/.github/workflows/ci.yml" ]; then
        record_result "CI pipeline exists" PASS

        local jobs
        jobs=$(grep -c "name:" "$WORKDIR/.github/workflows/ci.yml" || true)
        if [ "$jobs" -ge 5 ]; then
            record_result "CI pipeline has 5+ jobs ($jobs found)" PASS
        else
            record_result "CI pipeline has 5+ jobs ($jobs found)" FAIL
        fi
    else
        record_result "CI pipeline exists" FAIL
    fi
}

# Test 10: Validation scripts exist
test_validation_scripts() {
    log_info "--- Test: Validation scripts ---"
    local missing=0

    for s in validate_packages.sh validate_rootfs.sh validate_kernel.sh validate_initramfs.sh validate_iso.sh run_all.sh; do
        if [ ! -f "$WORKDIR/validation/$s" ]; then
            log_error "Missing validation script: $s"
            missing=$((missing + 1))
        fi
    done

    if [ "$missing" -eq 0 ]; then
        record_result "All validation scripts present (6 scripts)" PASS
    else
        record_result "All validation scripts present (6 scripts)" FAIL
    fi
}

# Test 11: Documentation files exist
test_documentation() {
    log_info "--- Test: Documentation ---"

    local files=(
        "$WORKDIR/README.md" "$WORKDIR/PROJECT_STATUS.md" "$WORKDIR/ROADMAP.md"
        "$WORKDIR/TODO.md" "$WORKDIR/ARCHITECTURE.md"
        "$WORKDIR/AI/Constitution.md" "$WORKDIR/AI/Context.md"
        "$WORKDIR/AI/Principles.md" "$WORKDIR/AI/DecisionMaking.md"
        "$WORKDIR/AI/Architecture.md" "$WORKDIR/AI/Workflow.md"
        "$WORKDIR/AI/Coding.md" "$WORKDIR/AI/Quality.md"
        "$WORKDIR/AI/Mission.md" "$WORKDIR/AI/Decision_Log.md"
    )
    local missing=0

    for f in "${files[@]}"; do
        if [ ! -f "$f" ]; then
            log_error "Missing documentation: $f"
            missing=$((missing + 1))
        fi
    done

    if [ "$missing" -eq 0 ]; then
        record_result "All documentation files present" PASS
    else
        record_result "All documentation files present" FAIL
    fi
}

# Test 12: Config files integrity
test_config_integrity() {
    log_info "--- Test: Configuration files ---"

    local missing=0
    for f in grub.cfg fstab packages.list os-release openbox_rc.xml picom.conf firefox/vice-os.js firefox/policies.json fontconfig/99-vice-cjk.conf apt/preferences.d/90-vice-backports-kernel apt/apt.conf.d/20auto-upgrades apt/apt.conf.d/50unattended-upgrades libfm/libfm.conf polkit-1/rules.d/50-vice-udisks-automount.rules skel/.config/xfce4/xfconf/xfce-perchannel-xml/thunar-volman.xml; do
        if [ ! -f "$WORKDIR/config/$f" ]; then
            log_error "Missing config: $f"
            missing=$((missing + 1))
        fi
    done

    if [ "$missing" -eq 0 ]; then
        record_result "All critical config files present" PASS
    else
        record_result "All critical config files present" FAIL
    fi
}

# Test 13: Wayland session support files
test_wayland_session() {
    log_info "--- Test: Wayland session support ---"
    local missing=0

    # Wayland packages present in packages.list
    for pkg in labwc xwayland qtwayland5 swaybg swaylock swayidle; do
        if grep -q "^$pkg$" "$WORKDIR/config/packages.list"; then
            :
        else
            log_error "Missing Wayland package: $pkg"
            missing=$((missing + 1))
        fi
    done

    # Wayland session launcher script
    if [ ! -f "$WORKDIR/desktop/wayland_session.sh" ]; then
        log_error "Missing: desktop/wayland_session.sh"
        missing=$((missing + 1))
    fi

    # Session configuration file
    if [ ! -f "$WORKDIR/config/vice-os-session.conf" ]; then
        log_error "Missing: config/vice-os-session.conf"
        missing=$((missing + 1))
    fi

    # Labwc compositor config files
    for f in rc.xml autostart environment menu.xml; do
        if [ ! -f "$WORKDIR/config/labwc/$f" ]; then
            log_error "Missing labwc config: config/labwc/$f"
            missing=$((missing + 1))
        fi
    done

    # .profile must contain session selection logic
    if ! grep -q "wayland_session.sh" "$WORKDIR/config/skel/.profile"; then
        log_error "Missing Wayland session selection in .profile"
        missing=$((missing + 1))
    fi

    # vice_shell.py must be session-aware (logout)
    if ! grep -q "WAYLAND_DISPLAY" "$WORKDIR/desktop/vice_shell.py"; then
        log_error "vice_shell.py missing Wayland-aware logout"
        missing=$((missing + 1))
    fi

    if [ "$missing" -eq 0 ]; then
        record_result "Wayland session support files present" PASS
    else
        record_result "Wayland session support files present" FAIL
    fi
}

# Test 14: ARM64 & Raspberry Pi boot support files
test_arm64_rpi_boot() {
    log_info "--- Test: ARM64 & Raspberry Pi boot support ---"
    local missing=0

    # ARM64 package list
    if [ ! -f "$WORKDIR/config/packages.arm64.list" ]; then
        log_error "Missing: config/packages.arm64.list"
        missing=$((missing + 1))
    fi

    # Raspberry Pi firmware configs
    for f in config.txt cmdline.txt boot.cmd; do
        if [ ! -f "$WORKDIR/config/rpi/$f" ]; then
            log_error "Missing RPi config: config/rpi/$f"
            missing=$((missing + 1))
        fi
    done

    # ARM64 / RPi chroot setup script
    if [ ! -f "$WORKDIR/chroot_scripts/47_rpi_arm64_setup.sh" ]; then
        log_error "Missing: chroot_scripts/47_rpi_arm64_setup.sh"
        missing=$((missing + 1))
    fi

    # Bootloader script must support ARM64 EFI and RPi
    if ! grep -q "arm64-efi" "$WORKDIR/build/create_bootloader.sh"; then
        log_error "build/create_bootloader.sh missing arm64-efi support"
        missing=$((missing + 1))
    fi

    if [ "$missing" -eq 0 ]; then
        record_result "ARM64 and Raspberry Pi boot support files present" PASS
    else
        record_result "ARM64 and Raspberry Pi boot support files present" FAIL
    fi
}

# Test 15: Session-aware login greeter
test_login_greeter() {
    log_info "--- Test: Session-aware login greeter ---"
    local login_script="$WORKDIR/desktop/login.py"

    if [ ! -f "$login_script" ]; then
        record_result "desktop/login.py exists" FAIL
        return
    fi

    local missing=0
    for keyword in "session_combo" "wayland_session.sh" "dbus_session.sh" "load_default_session"; do
        if ! grep -q "$keyword" "$login_script"; then
            log_error "login.py missing keyword: $keyword"
            missing=$((missing + 1))
        fi
    done

    if [ "$missing" -eq 0 ]; then
        record_result "Login greeter is session-aware with X11/Wayland switcher" PASS
    else
        record_result "Login greeter is session-aware with X11/Wayland switcher" FAIL
    fi
}

main() {
    log_info "============================================"
    log_info "  Vice OS Validation Integration Test Suite"
    log_info "============================================"
    echo ""

    test_package_list
    test_critical_packages
    test_desktop_files
    test_desktop_modules
    test_shared_library
    test_shared_bash_library
    test_recovery_scripts
    test_chroot_scripts
    test_ci_pipeline
    test_validation_scripts
    test_documentation
    test_config_integrity
    test_wayland_session
    test_arm64_rpi_boot
    test_login_greeter

    echo ""
    log_info "============================================"
    log_info "  Results: $PASSED passed, $FAILED failed, $SKIPPED skipped"
    log_info "============================================"

    if [ "$FAILED" -gt 0 ]; then
        exit 1
    fi
}

main "$@"
