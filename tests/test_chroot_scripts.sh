#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# Vice OS Chroot Scripts & System Configuration Test Suite
# Tests syntax, idempotency structure, package consistency, and configuration
# integrity across all 49 chroot scripts and declarative configuration files.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

CHROOT_SCRIPTS_DIR="$WORKDIR/chroot_scripts"
CONFIG_DIR="$WORKDIR/config"

PASSED=0
FAILED=0

record_result() {
    local test_name="$1"
    local result="$2"
    local details="${3:-}"

    if [ "$result" = "PASS" ]; then
        log_success "[PASS] $test_name"
        PASSED=$((PASSED + 1))
    else
        log_error "[FAIL] $test_name ($details)"
        FAILED=$((FAILED + 1))
    fi
}

main() {
    log_info "============================================================"
    log_info "  Running Chroot Scripts & Configuration Test Suite"
    log_info "============================================================"

    # --- Test 1: Exactly 49 Chroot Scripts Present ---
    local script_count
    script_count=$(find "$CHROOT_SCRIPTS_DIR" -maxdepth 1 -name "*.sh" | wc -l)
    if [ "$script_count" -eq 49 ]; then
        record_result "Chroot script count is exactly 49" "PASS"
    else
        record_result "Chroot script count is exactly 49" "FAIL" "Found $script_count scripts"
    fi

    # --- Test 2: Shebang in all 49 scripts ---
    local missing_shebang=0
    for s in "$CHROOT_SCRIPTS_DIR"/*.sh; do
        local line1
        line1=$(head -n 1 "$s")
        if [ "$line1" != "#!/bin/bash" ]; then
            missing_shebang=$((missing_shebang + 1))
        fi
    done
    if [ "$missing_shebang" -eq 0 ]; then
        record_result "All 49 chroot scripts have #!/bin/bash shebang" "PASS"
    else
        record_result "All 49 chroot scripts have #!/bin/bash shebang" "FAIL" "$missing_shebang scripts missing shebang"
    fi

    # --- Test 3: bash -n syntax check on all 49 scripts ---
    local syntax_errors=0
    for s in "$CHROOT_SCRIPTS_DIR"/*.sh; do
        if ! bash -n "$s" 2>/dev/null; then
            syntax_errors=$((syntax_errors + 1))
        fi
    done
    if [ "$syntax_errors" -eq 0 ]; then
        record_result "All 49 chroot scripts pass bash syntax check (bash -n)" "PASS"
    else
        record_result "All 49 chroot scripts pass bash syntax check (bash -n)" "FAIL" "$syntax_errors syntax errors"
    fi

    # --- Test 4: All scripts source /vice_payload/lib/common.sh ---
    local missing_common=0
    for s in "$CHROOT_SCRIPTS_DIR"/*.sh; do
        if ! grep -q "/vice_payload/lib/common.sh" "$s"; then
            missing_common=$((missing_common + 1))
        fi
    done
    if [ "$missing_common" -eq 0 ]; then
        record_result "All 49 scripts reference /vice_payload/lib/common.sh" "PASS"
    else
        record_result "All 49 scripts reference /vice_payload/lib/common.sh" "FAIL" "$missing_common missing reference"
    fi

    # --- Test 5: All scripts define main and invoke main \"$@\" ---
    local missing_main=0
    for s in "$CHROOT_SCRIPTS_DIR"/*.sh; do
        if ! grep -q 'main "$@"' "$s"; then
            missing_main=$((missing_main + 1))
        fi
    done
    if [ "$missing_main" -eq 0 ]; then
        record_result "All 49 scripts follow repository standard (main \"$@\")" "PASS"
    else
        record_result "All 49 scripts follow repository standard (main \"$@\")" "FAIL" "$missing_main missing main call"
    fi

    # --- Test 6: Package conflict check (no pulseaudio daemon with pipewire-audio) ---
    local pkg_file="$CONFIG_DIR/packages.list"
    if grep -q "^pulseaudio$" "$pkg_file"; then
        record_result "Package list audio conflict check (no conflicting pulseaudio daemon)" "FAIL" "pulseaudio found"
    else
        record_result "Package list audio conflict check (no conflicting pulseaudio daemon)" "PASS"
    fi

    # --- Test 7: PipeWire and tools present in packages.list ---
    local missing_audio=0
    for p in "pipewire" "pipewire-audio" "pipewire-pulse" "pipewire-alsa" "wireplumber" "alsa-utils" "alsa-ucm-conf" "rtkit" "pulseaudio-utils"; do
        if ! grep -q "^${p}$" "$pkg_file"; then
            missing_audio=$((missing_audio + 1))
        fi
    done
    if [ "$missing_audio" -eq 0 ]; then
        record_result "PipeWire modern audio + ALSA stack present in packages.list" "PASS"
    else
        record_result "PipeWire modern audio + ALSA stack present in packages.list" "FAIL" "$missing_audio missing audio packages"
    fi

    # --- Test 8: XML configuration validation (Openbox, Labwc, Thunar, Fontconfig) ---
    local xml_valid=true
    local python_bin="python"
    if python3 -c "import sys" >/dev/null 2>&1; then
        python_bin="python3"
    fi

    local target_dir
    target_dir=$(cygpath -w "$WORKDIR" 2>/dev/null || echo "$WORKDIR")

    if ! "$python_bin" -c "
import xml.etree.ElementTree as ET
import sys, os

root_dir = sys.argv[1]
files = [
    os.path.join(root_dir, 'config', 'openbox_rc.xml'),
    os.path.join(root_dir, 'config', 'skel', '.config', 'openbox', 'menu.xml'),
    os.path.join(root_dir, 'config', 'labwc', 'menu.xml'),
    os.path.join(root_dir, 'config', 'labwc', 'rc.xml'),
    os.path.join(root_dir, 'config', 'thunar', 'uca.xml'),
    os.path.join(root_dir, 'config', 'fontconfig', '99-vice-cjk.conf')
]

for f in files:
    try:
        ET.parse(f)
    except Exception as e:
        print(f'Error parsing {f}: {e}', file=sys.stderr)
        sys.exit(1)
" "$target_dir"; then
        xml_valid=false
    fi

    if [ "$xml_valid" = true ]; then
        record_result "All XML configuration files valid (Openbox, Labwc, Thunar, Fontconfig)" "PASS"
    else
        record_result "All XML configuration files valid (Openbox, Labwc, Thunar, Fontconfig)" "FAIL" "XML parser error"
    fi

    # --- Test 9: Desktop Autostart Notifications Exec target exists ---
    local notif_desktop="$CONFIG_DIR/skel/.config/autostart/vice-os-notifications.desktop"
    if grep -q "vice_notification_daemon.py" "$notif_desktop"; then
        record_result "Notification daemon autostart references vice_notification_daemon.py" "PASS"
    else
        record_result "Notification daemon autostart references vice_notification_daemon.py" "FAIL" "Wrong script name"
    fi

    # --- Test 10: Session config harmonization (session.conf & .profile) ---
    local session_conf="$CONFIG_DIR/vice-os-session.conf"
    local profile_file="$CONFIG_DIR/skel/.profile"
    if grep -q "SESSION_TYPE" "$session_conf" && grep -q 'SESSION_TYPE=.*SESSION' "$profile_file"; then
        record_result "Session type configuration harmonized between session.conf and .profile" "PASS"
    else
        record_result "Session type configuration harmonized between session.conf and .profile" "FAIL" "Variable mismatch"
    fi

    # --- Test 11: Declarative GRUB, Openbox, Labwc, APT, Polkit, Udev configs present ---
    local missing_configs=0
    local critical_configs=(
        "$CONFIG_DIR/grub.cfg"
        "$CONFIG_DIR/default/grub"
        "$CONFIG_DIR/openbox_rc.xml"
        "$CONFIG_DIR/labwc/rc.xml"
        "$CONFIG_DIR/labwc/autostart"
        "$CONFIG_DIR/labwc/environment"
        "$CONFIG_DIR/apt/sources.list"
        "$CONFIG_DIR/apt/apt.conf.d/99-no-recommends"
        "$CONFIG_DIR/polkit-1.preset"
        "$CONFIG_DIR/90-live-installer.rules"
        "$CONFIG_DIR/sudoers"
        "$CONFIG_DIR/systemd/zram-setup.conf"
        "$CONFIG_DIR/systemd/system/vp-autoupdate.service"
        "$CONFIG_DIR/systemd/system/vp-firewall.service"
        "$CONFIG_DIR/systemd/system/zram-setup.service"
        "$CONFIG_DIR/picom.conf"
        "$CONFIG_DIR/firefox/vice-os.js"
        "$CONFIG_DIR/firefox/policies.json"
        "$CONFIG_DIR/fontconfig/99-vice-cjk.conf"
    )
    for c in "${critical_configs[@]}"; do
        if [ ! -f "$c" ]; then
            missing_configs=$((missing_configs + 1))
        fi
    done
    if [ "$missing_configs" -eq 0 ]; then
        record_result "All critical system configuration files present" "PASS"
    else
        record_result "All critical system configuration files present" "FAIL" "$missing_configs missing files"
    fi

    # --- Test 12: ARM64 architecture handling (47_rpi_arm64_setup.sh & packages.arm64.list) ---
    if [ -f "$CHROOT_SCRIPTS_DIR/47_rpi_arm64_setup.sh" ] && [ -f "$CONFIG_DIR/packages.arm64.list" ]; then
        record_result "ARM64 / Raspberry Pi architecture support files present" "PASS"
    else
        record_result "ARM64 / Raspberry Pi architecture support files present" "FAIL" "Missing ARM64 support"
    fi

    # --- Test 13: Chroot media/Firefox/CJK/fail2ban/PipeWire/timer hardening ---
    local tuning_sh="$CHROOT_SCRIPTS_DIR/02_system_tuning.sh"
    local systemd_sh="$CHROOT_SCRIPTS_DIR/19_systemd_setup.sh"
    local opt_sh="$CHROOT_SCRIPTS_DIR/90_optimize.sh"
    local hard_ok=true
    grep -q '/etc/firefox-esr/vice-os.js' "$tuning_sh" || hard_ok=false
    grep -q 'backend = systemd' "$tuning_sh" || hard_ok=false
    grep -q '/etc/fonts/conf.avail' "$tuning_sh" || hard_ok=false
    grep -q 'rm -f /etc/pipewire/pipewire.conf' "$systemd_sh" || hard_ok=false
    grep -q '10-vice-audio.conf' "$systemd_sh" || hard_ok=false
    grep -q 'apt-daily.timer' "$opt_sh" || hard_ok=false
    grep -q 'apt-daily-upgrade.timer' "$opt_sh" || hard_ok=false
    "$python_bin" -c "import json, sys; json.load(open(sys.argv[1], encoding='utf-8'))" \
        "$target_dir/config/firefox/policies.json" 2>/dev/null || hard_ok=false
    if [ "$hard_ok" = true ]; then
        record_result "Chroot media, Firefox ESR, CJK fontconfig, PipeWire drop-in, fail2ban, and timer masking verified" "PASS"
    else
        record_result "Chroot media, Firefox ESR, CJK fontconfig, PipeWire drop-in, fail2ban, and timer masking verified" "FAIL" "Missing chroot hardening"
    fi

    echo ""
    log_info "============================================================"
    log_info "  Results: $PASSED passed, $FAILED failed"
    log_info "============================================================"

    if [ "$FAILED" -gt 0 ]; then
        exit 1
    fi
}

main "$@"
