#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Host Clock & Timezone Auto-Sync
# Installed to /usr/local/system_scripts/vice-timesync.sh
# Symlinked at /usr/local/bin/vice-timesync
# ============================================================================

VERSION="1.0.0"

case ":$PATH:" in
    *":/usr/sbin:"*) ;;
    *) PATH="$PATH:/usr/local/sbin:/usr/sbin:/sbin" ;;
esac
export PATH

ZONEINFO_DIR="${VICE_ZONEINFO_DIR:-/usr/share/zoneinfo}"
ETC_DIR="${VICE_ETC_DIR:-/etc}"
STATE_DIR="${VICE_TIMESYNC_STATE_DIR:-/etc/vice-os}"
MODE_FILE="${STATE_DIR}/timesync.mode"
LOCK_FILE="${VICE_TIMESYNC_LOCK_FILE:-/run/lock/vice-timesync.lock}"

log_info() {
    printf '[INFO] %s\n' "$1"
}

log_warn() {
    printf '[WARN] %s\n' "$1" >&2
}

log_error() {
    printf '[ERROR] %s\n' "$1" >&2
}

show_help() {
    cat <<'HELP'
GTA VI OS (Vice OS) Host Clock & Timezone Auto-Sync

Usage:
  vice-timesync --auto [--force]   Sync clock and auto-detect host local IANA timezone
  vice-timesync --sync-only        Sync system clock (VBoxService / Chrony) without changing timezone
  vice-timesync --set <IANA_TZ>    Validate and set a manual IANA timezone (locks against --auto)
  vice-timesync --status           Show current timezone, mode, clock, and sync service status
  vice-timesync --help             Show this help message and exit
  vice-timesync --version          Show version information and exit

Notes:
  - Manual selection via --set <IANA_TZ> sets manual mode so background timers and
    NetworkManager hooks do not overwrite your chosen timezone.
  - Pass --auto --force to clear manual mode and re-detect host local timezone.
HELP
}

show_version() {
    printf 'vice-timesync v%s (GTA VI OS Host Clock & Timezone Sync)\n' "$VERSION"
}

check_root() {
    if [ "${VICE_TESTING:-0}" = "1" ] || [ "${VICE_SKIP_ROOT_CHECK:-0}" = "1" ]; then
        return 0
    fi
    if [ "${EUID:-$(id -u)}" -ne 0 ]; then
        log_error "Root privileges are required for this operation (use sudo or pkexec)."
        exit 1
    fi
}

acquire_lock() {
    local lock_dir
    lock_dir=$(dirname "$LOCK_FILE")
    if ! mkdir -p "$lock_dir" 2>/dev/null; then
        return 0
    fi
    if command -v flock >/dev/null 2>&1; then
        exec 9>"$LOCK_FILE"
        if ! flock -w 10 9; then
            log_warn "Another vice-timesync instance is running; skipping."
            exit 0
        fi
    fi
}

get_mode() {
    if [ -f "$MODE_FILE" ]; then
        local mode_val
        mode_val=$(head -n 1 "$MODE_FILE" 2>/dev/null | tr -d '[:space:]' || true)
        if [ "$mode_val" = "manual" ]; then
            printf 'manual'
            return 0
        fi
    fi
    printf 'auto'
}

set_mode() {
    local new_mode="$1"
    if mkdir -p "$STATE_DIR" 2>/dev/null; then
        printf '%s\n' "$new_mode" > "$MODE_FILE"
        chmod 644 "$MODE_FILE" 2>/dev/null || true
    fi
}

get_current_timezone() {
    if [ -f "${ETC_DIR}/timezone" ]; then
        local tz_file_val
        tz_file_val=$(head -n 1 "${ETC_DIR}/timezone" 2>/dev/null | tr -d '[:space:]' || true)
        if [ -n "$tz_file_val" ]; then
            printf '%s' "$tz_file_val"
            return 0
        fi
    fi
    if [ -L "${ETC_DIR}/localtime" ]; then
        local target
        target=$(readlink -f "${ETC_DIR}/localtime" 2>/dev/null || true)
        local real_root
        real_root=$(readlink -f "$ZONEINFO_DIR" 2>/dev/null || printf '%s' "$ZONEINFO_DIR")
        case "$target" in
            "${real_root}/"*)
                printf '%s' "${target#"${real_root}/"}"
                return 0
                ;;
        esac
    fi
    if command -v timedatectl >/dev/null 2>&1 && [ -d /run/systemd/system ]; then
        local td_tz
        td_tz=$(timedatectl show -p Timezone --value 2>/dev/null || true)
        if [ -n "$td_tz" ]; then
            printf '%s' "$td_tz"
            return 0
        fi
    fi
    printf 'UTC'
}

validate_timezone() {
    local tz="${1:-}"
    if [ -z "$tz" ]; then
        return 1
    fi

    case "$tz" in
        /*|.*|*..*|*//*|*/)
            return 1
            ;;
        posix|posix/*|right|right/*|localtime|Factory|leapseconds|*.tab|*.zi|*.list)
            return 1
            ;;
    esac

    if [[ ! "$tz" =~ ^[A-Za-z0-9_+-]+(/[A-Za-z0-9_+-]+){0,2}$ ]]; then
        return 1
    fi

    local candidate="${ZONEINFO_DIR}/${tz}"
    if [ ! -f "$candidate" ] || [ ! -r "$candidate" ]; then
        return 1
    fi

    local real_root real_target
    real_root=$(readlink -f "$ZONEINFO_DIR" 2>/dev/null || printf '%s' "$ZONEINFO_DIR")
    real_target=$(readlink -f "$candidate" 2>/dev/null || printf '%s' "$candidate")
    case "$real_target" in
        "${real_root}/"*)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

apply_timezone() {
    local tz="$1"
    if ! validate_timezone "$tz"; then
        log_error "Invalid or unsafe IANA timezone: '$tz'"
        return 1
    fi

    local current_tz
    current_tz=$(get_current_timezone)
    if [ "$current_tz" = "$tz" ] && [ -L "${ETC_DIR}/localtime" ]; then
        log_info "Timezone already set to $tz."
        return 0
    fi

    if command -v timedatectl >/dev/null 2>&1 && [ -d /run/systemd/system ]; then
        if timedatectl set-timezone "$tz" >/dev/null 2>&1; then
            log_info "Timezone updated to $tz via timedatectl."
            return 0
        fi
    fi

    mkdir -p "$ETC_DIR"
    printf '%s\n' "$tz" > "${ETC_DIR}/timezone"
    chmod 644 "${ETC_DIR}/timezone"
    ln -snf "${ZONEINFO_DIR}/${tz}" "${ETC_DIR}/localtime"
    log_info "Timezone updated to $tz via ${ETC_DIR}/timezone and ${ETC_DIR}/localtime."
    return 0
}

is_virtualbox_guest() {
    if [ -e /dev/vboxguest ]; then
        return 0
    fi
    if command -v systemd-detect-virt >/dev/null 2>&1; then
        local virt
        virt=$(systemd-detect-virt 2>/dev/null || true)
        if [ "$virt" = "oracle" ]; then
            return 0
        fi
    fi
    if [ -r /sys/class/dmi/id/product_name ] && grep -qi "VirtualBox" /sys/class/dmi/id/product_name 2>/dev/null; then
        return 0
    fi
    if [ -r /sys/class/dmi/id/sys_vendor ] && grep -qiE "VirtualBox|innotek|Oracle" /sys/class/dmi/id/sys_vendor 2>/dev/null; then
        return 0
    fi
    return 1
}

sync_clock() {
    local synced=0

    if command -v VBoxService >/dev/null 2>&1 && is_virtualbox_guest; then
        if timeout 8 VBoxService --timesync-set-start >/dev/null 2>&1; then
            log_info "Synced clock with VirtualBox host (VBoxService --timesync-set-start)."
            synced=1
        else
            log_warn "VBoxService --timesync-set-start returned non-zero status."
        fi
    fi

    if command -v chronyc >/dev/null 2>&1; then
        local chrony_running=0
        if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet chrony 2>/dev/null; then
            chrony_running=1
        elif chronyc tracking >/dev/null 2>&1; then
            chrony_running=1
        fi

        if [ "$chrony_running" -eq 1 ]; then
            if timeout 8 chronyc -a makestep >/dev/null 2>&1; then
                log_info "Stepped system clock via Chrony (chronyc -a makestep)."
                synced=1
            else
                log_warn "chronyc -a makestep failed or timed out."
            fi
        fi
    fi

    if [ "$synced" -eq 0 ]; then
        log_info "Clock step skipped (no active VirtualBox guest or Chrony daemon detected)."
    fi
    return 0
}

has_default_route() {
    if [ "${VICE_TESTING:-0}" = "1" ]; then
        return 0
    fi
    if ! command -v ip >/dev/null 2>&1; then
        return 0
    fi
    if [ -n "$(ip -4 route show default 2>/dev/null || true)" ] || \
       [ -n "$(ip -6 route show default 2>/dev/null || true)" ]; then
        return 0
    fi
    return 1
}

parse_worldtimeapi_tz() {
    local json="$1"
    if command -v python3 >/dev/null 2>&1; then
        printf '%s' "$json" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
    tz = data.get("timezone", "")
    if isinstance(tz, str):
        print(tz.strip())
except Exception:
    pass
' 2>/dev/null || true
        return 0
    fi
    printf '%s' "$json" | sed -n 's/.*"timezone"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1
}

detect_ip_timezone() {
    if ! command -v curl >/dev/null 2>&1; then
        log_warn "curl not installed; cannot auto-detect host local timezone."
        return 1
    fi
    if ! has_default_route; then
        log_info "No active default network route; deferring timezone auto-detection."
        return 1
    fi

    local raw=""
    local tz=""

    # 1. Primary provider: ipinfo.io (HTTPS plain text, verified in Debian Live VMs)
    raw=$(curl -fsSL --max-time 4 "https://ipinfo.io/timezone" 2>/dev/null || true)
    tz=$(printf '%s' "$raw" | tr -d '[:space:]')
    if validate_timezone "$tz"; then
        printf '%s' "$tz"
        return 0
    fi

    # 2. Secondary provider: ip-api.com (verified reliable fallback in Live VMs)
    raw=$(curl -fsSL --max-time 4 "http://ip-api.com/line/?fields=timezone" 2>/dev/null || true)
    tz=$(printf '%s' "$raw" | tr -d '[:space:]')
    if validate_timezone "$tz"; then
        printf '%s' "$tz"
        return 0
    fi

    # 3. Tertiary provider: ipapi.co
    raw=$(curl -fsSL --max-time 4 "https://ipapi.co/timezone" 2>/dev/null || true)
    tz=$(printf '%s' "$raw" | tr -d '[:space:]')
    if validate_timezone "$tz"; then
        printf '%s' "$tz"
        return 0
    fi

    # 4. Quaternary provider: worldtimeapi.org
    raw=$(curl -fsSL --max-time 4 "https://worldtimeapi.org/api/ip" 2>/dev/null || true)
    if [ -n "$raw" ]; then
        tz=$(parse_worldtimeapi_tz "$raw" | tr -d '[:space:]')
        if validate_timezone "$tz"; then
            printf '%s' "$tz"
            return 0
        fi
    fi

    return 1
}

run_auto() {
    local force="${1:-0}"
    sync_clock

    if [ "$force" -eq 1 ]; then
        set_mode "auto"
    fi

    local mode
    mode=$(get_mode)
    if [ "$mode" = "manual" ] && [ "$force" -ne 1 ]; then
        local current_tz
        current_tz=$(get_current_timezone)
        log_info "Manual timezone mode active ($current_tz); skipping auto-detection (pass --auto --force to override)."
        return 0
    fi

    local detected_tz=""
    if detected_tz=$(detect_ip_timezone); then
        apply_timezone "$detected_tz"
        set_mode "auto"
    else
        log_warn "Could not auto-detect host local timezone (offline or providers unreachable); keeping $(get_current_timezone)."
    fi
    return 0
}

run_set() {
    local tz="${1:-}"
    if [ -z "$tz" ]; then
        log_error "--set requires an IANA timezone (e.g. America/New_York or Asia/Jakarta)."
        exit 1
    fi
    if ! validate_timezone "$tz"; then
        log_error "Invalid or unknown IANA timezone: '$tz'"
        exit 1
    fi
    apply_timezone "$tz"
    set_mode "manual"
    sync_clock
}

run_status() {
    local current_tz mode local_time utc_time virt vbox_state chrony_state
    current_tz=$(get_current_timezone)
    mode=$(get_mode)
    local_time=$(date '+%Y-%m-%d %H:%M:%S %Z (%z)' 2>/dev/null || date)
    utc_time=$(date -u '+%Y-%m-%d %H:%M:%S UTC' 2>/dev/null || date -u)

    if command -v systemd-detect-virt >/dev/null 2>&1; then
        virt=$(systemd-detect-virt 2>/dev/null || printf 'none')
    else
        virt="unknown"
    fi

    if command -v VBoxService >/dev/null 2>&1; then
        if pgrep -x VBoxService >/dev/null 2>&1; then
            vbox_state="available (running)"
        else
            vbox_state="available (stopped)"
        fi
    else
        vbox_state="not-installed"
    fi

    if command -v chronyc >/dev/null 2>&1; then
        if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet chrony 2>/dev/null; then
            chrony_state="active"
        elif chronyc tracking >/dev/null 2>&1; then
            chrony_state="active"
        else
            chrony_state="inactive"
        fi
    else
        chrony_state="not-installed"
    fi

    printf 'Timezone: %s\n' "$current_tz"
    printf 'Mode: %s\n' "$mode"
    printf 'LocalTime: %s\n' "$local_time"
    printf 'UTCTime: %s\n' "$utc_time"
    printf 'Virtualization: %s\n' "$virt"
    printf 'VBoxService: %s\n' "$vbox_state"
    printf 'Chrony: %s\n' "$chrony_state"

    if [ "$chrony_state" = "active" ]; then
        local offset_line
        offset_line=$(chronyc tracking 2>/dev/null | awk -F: '/Last offset/ {gsub(/^[[:space:]]+/, "", $2); print $2; exit}' || true)
        if [ -n "$offset_line" ]; then
            printf 'ChronyOffset: %s\n' "$offset_line"
        fi
    fi
}

main() {
    if [ "$#" -eq 0 ]; then
        show_help
        exit 0
    fi

    local action=""
    local target_tz=""
    local force=0

    while [ "$#" -gt 0 ]; do
        case "$1" in
            --auto)
                action="auto"
                ;;
            --force)
                force=1
                ;;
            --sync-only)
                action="sync-only"
                ;;
            --set)
                action="set"
                shift
                if [ "$#" -eq 0 ]; then
                    log_error "--set requires an IANA timezone argument."
                    exit 1
                fi
                target_tz="$1"
                ;;
            --set=*)
                action="set"
                target_tz="${1#--set=}"
                ;;
            --status)
                action="status"
                ;;
            --help|-h|help)
                show_help
                exit 0
                ;;
            --version|-v|-V)
                show_version
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help >&2
                exit 1
                ;;
        esac
        shift
    done

    case "$action" in
        auto)
            check_root
            acquire_lock
            run_auto "$force"
            ;;
        sync-only)
            check_root
            acquire_lock
            sync_clock
            ;;
        set)
            check_root
            acquire_lock
            run_set "$target_tz"
            ;;
        status)
            run_status
            ;;
        *)
            log_error "No action specified (use --auto, --sync-only, --set <IANA_TZ>, or --status)."
            exit 1
            ;;
    esac
}

main "$@"
