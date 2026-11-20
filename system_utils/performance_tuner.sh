#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Performance Tuner
# Manages CPU governors, I/O schedulers, and kernel parameters for performance.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"
install_cleanup

# --- Configuration ---
CPU_DIR="/sys/devices/system/cpu"
BLOCK_DIR="/sys/block"
SYSCTL_CMD="sysctl"

# --- Helper Functions ---

check_tuner_deps() {
    check_dependencies "cat" "find" "sysctl"
}

# --- Status Functions ---

show_status() {
    log_info "Performance Status:"
    echo "==================================="

    # CPU Governors
    echo "CPU Governors:"
    for cpu in "$CPU_DIR"/cpu[0-9]*; do
        if [ -f "$cpu/cpufreq/scaling_governor" ]; then
            local cpu_num gov
            cpu_num=$(basename "$cpu")
            gov=$(cat "$cpu/cpufreq/scaling_governor" 2>/dev/null || echo "N/A")
            printf "  %-8s %s\n" "$cpu_num:" "$gov"
        fi
    done

    echo ""
    echo "I/O Schedulers:"
    for dev in sda sdb nvme0n1 nvme0n2; do
        if [ -f "$BLOCK_DIR/$dev/queue/scheduler" ]; then
            local sched
            sched=$(cat "$BLOCK_DIR/$dev/queue/scheduler" 2>/dev/null || echo "N/A")
            printf "  %-8s %s\n" "$dev:" "$sched"
        fi
    done

    echo ""
    echo "Kernel Parameters:"
    printf "  Swappiness:       %s\n" "$(cat /proc/sys/vm/swappiness)"
    printf "  Caches:          %s\n" "$(cat /proc/sys/vm/vfs_cache_pressure)"
    printf "  Max Map Count:   %s\n" "$(cat /proc/sys/vm/max_map_count)"

    echo "==================================="
}

# --- CPU Governor Functions ---

set_governor() {
    local governor="$1"

    if [ -z "$governor" ]; then
        log_error "Governor required (e.g., performance, powersave, schedutil)."
        return 1
    fi

    log_info "Setting CPU governor to: $governor"

    local set_count=0
    for cpu in "$CPU_DIR"/cpu[0-9]*; do
        if [ -f "$cpu/cpufreq/scaling_governor" ]; then
            if echo "$governor" > "$cpu/cpufreq/scaling_governor" 2>/dev/null; then
                set_count=$((set_count + 1))
            fi
        fi
    done

    if [ "$set_count" -gt 0 ]; then
        log_success "Governor set to '$governor' on $set_count CPU(s)."
    else
        log_error "Failed to set governor. Permission denied or unsupported."
        return 1
    fi
}

# --- I/O Scheduler Functions ---

set_io_scheduler() {
    local scheduler="$1"
    local device="${2:-all}"

    if [ -z "$scheduler" ]; then
        log_error "Scheduler required (e.g., mq-deadline, kyber, none)."
        return 1
    fi

    log_info "Setting I/O scheduler to: $scheduler"

    local set_count=0
    for dev in "$BLOCK_DIR"/*; do
        local dev_name
        dev_name=$(basename "$dev")

        # Skip loop/ram devices
        if [[ "$dev_name" == loop* ]] || [[ "$dev_name" == ram* ]]; then
            continue
        fi

        if [ -f "$dev/queue/scheduler" ]; then
            local current
            current=$(cat "$dev/queue/scheduler" 2>/dev/null || echo "")

            if echo "$scheduler" > "$dev/queue/scheduler" 2>/dev/null; then
                log_info "  $dev_name: $scheduler"
                set_count=$((set_count + 1))
            fi
        fi
    done

    if [ "$set_count" -gt 0 ]; then
        log_success "I/O scheduler set on $set_count device(s)."
    else
        log_error "Failed to set I/O scheduler."
        return 1
    fi
}

# --- Kernel Parameter Functions ---

set_swappiness() {
    local value="$1"

    if ! [[ "$value" =~ ^[0-9]+$ ]] || [ "$value" -lt 0 ] || [ "$value" -gt 200 ]; then
        log_error "Swappiness must be a number between 0 and 200."
        return 1
    fi

    log_info "Setting vm.swappiness to: $value"

    "$SYSCTL_CMD" -w vm.swappiness="$value" > /dev/null 2>&1
    log_success "Swappiness set to: $value"
}

# --- Profile Functions ---

apply_profile() {
    local profile="$1"

    if [ -z "$profile" ]; then
        log_error "Profile required (performance, balanced, powersave)."
        return 1
    fi

    log_info "Applying performance profile: $profile"

    case "$profile" in
        performance)
            set_governor "performance"
            set_io_scheduler "none"
            set_swappiness "10"
            log_success "Performance profile applied."
            ;;
        balanced)
            set_governor "schedutil"
            set_io_scheduler "mq-deadline"
            set_swappiness "50"
            log_success "Balanced profile applied."
            ;;
        powersave)
            set_governor "powersave"
            set_io_scheduler "mq-deadline"
            set_swappiness "100"
            log_success "Powersave profile applied."
            ;;
        *)
            log_error "Unknown profile: $profile"
            return 1
            ;;
    esac
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Performance Tuner

Usage: $0 <command> [options]

Status:
  status                     Show current performance settings

CPU Governor:
  set-governor <governor>   Set CPU governor (performance, powersave, schedutil)

I/O Scheduler:
  set-scheduler <scheduler>  Set I/O scheduler (mq-deadline, kyber, none)

Kernel Parameters:
  set-swappiness <value>     Set vm.swappiness (0-200)

Profiles:
  apply-profile <profile>   Apply a predefined profile
  Available profiles:
    performance: Max CPU, none I/O, swappiness=10
    balanced:    schedutil, mq-deadline, swappiness=50
    powersave:   powersave, mq-deadline, swappiness=100

Help:
  help                      Show this help message

Notes:
  - Setting governors requires root privileges (use sudo).
  - Not all governors/schedulers are available on all hardware.
  - Changes are not persistent across reboots unless saved to /etc/sysctl.conf.

Examples:
  $0 status
  $0 set-governor performance
  $0 apply-profile performance
HELP
}

# --- Main ---

main() {
    local command="${1:-help}"
    if [ "$command" = "help" ] || [ "$command" = "--help" ] || [ "$command" = "-h" ]; then
        show_help
        exit 0
    fi
    shift || true

    check_tuner_deps

    case "$command" in
        status|info)
            show_status
            ;;
        set-governor|governor)
            local gov="${1:-}"
            if [ -z "$gov" ]; then
                log_error "Governor required."
                exit 1
            fi
            set_governor "$gov"
            ;;
        set-scheduler|scheduler|io-scheduler)
            local sched="${1:-}"
            if [ -z "$sched" ]; then
                log_error "Scheduler required."
                exit 1
            fi
            set_io_scheduler "$sched"
            ;;
        set-swappiness|swappiness)
            local val="${1:-}"
            if [ -z "$val" ]; then
                log_error "Swappiness value required."
                exit 1
            fi
            set_swappiness "$val"
            ;;
        apply-profile|profile|set-profile)
            local prof="${1:-}"
            if [ -z "$prof" ]; then
                log_error "Profile name required."
                exit 1
            fi
            apply_profile "$prof"
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "Unknown command: $command"
            log_info "Run '$0 help' for usage information."
            exit 1
            ;;
    esac
}

main "$@"