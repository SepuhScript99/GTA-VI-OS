#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Log Manager
# Provides unified log viewing, filtering, real-time tailing, and cleanup
# using journalctl and dmesg.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Source Shared Library ---
if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found. Cannot continue." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "Log operation failed with exit code $exit_code."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Helper Functions ---

check_log_deps() {
    check_dependencies "journalctl"
}

# --- Viewing Functions ---

view_system_logs() {
    local lines="${1:-50}"
    log_info "Showing last $lines lines of system logs..."
    journalctl -n "$lines" --no-pager
}

view_kernel_logs() {
    local lines="${1:-50}"
    log_info "Showing last $lines lines of kernel logs..."
    if command -v dmesg > /dev/null 2>&1; then
        dmesg --color=always | tail -n "$lines"
    else
        journalctl -k -n "$lines" --no-pager
    fi
}

view_service_logs() {
    local service="$1"
    local lines="${2:-50}"
    
    if [ -z "$service" ]; then
        log_error "Service name required."
        return 1
    fi
    
    log_info "Showing last $lines lines of logs for service: $service"
    journalctl -u "$service" -n "$lines" --no-pager
}

view_errors() {
    local lines="${1:-50}"
    log_info "Showing last $lines error (and above) logs..."
    journalctl -p err -n "$lines" --no-pager
}

view_boot_logs() {
    local boot_id="${1:-0}"
    
    if [ "$boot_id" == "list" ]; then
        log_info "Available boots:"
        journalctl --list-boots
        return 0
    fi
    
    # 0 = current boot, -1 = previous boot, etc.
    if [ "$boot_id" == "0" ]; then
        log_info "Showing logs from current boot..."
        journalctl -b 0 --no-pager
    else
        log_info "Showing logs from boot $boot_id..."
        journalctl -b "$boot_id" --no-pager
    fi
}

# --- Tailing Functions ---

tail_system_logs() {
    log_info "Tailing system logs (Ctrl+C to exit)..."
    journalctl -f
}

tail_service_logs() {
    local service="$1"
    
    if [ -z "$service" ]; then
        log_error "Service name required."
        return 1
    fi
    
    log_info "Tailing logs for service: $service (Ctrl+C to exit)..."
    journalctl -u "$service" -f
}

# --- Maintenance Functions ---

clean_logs() {
    local time="${1:-7d}"
    local size="${2:-100M}"
    
    log_info "Cleaning up old logs (older than $time or exceeding $size)..."
    
    log_info "Vacuuming by time ($time)..."
    journalctl --vacuum-time="$time"
    
    log_info "Vacuuming by size ($size)..."
    journalctl --vacuum-size="$size"
    
    log_success "Log cleanup complete."
}

show_disk_usage() {
    log_info "Journal Disk Usage:"
    journalctl --disk-usage
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Log Manager

Usage: $0 <command> [options]

Viewing:
  system [lines]              View system logs (default: 50 lines)
  kernel [lines]              View kernel logs (default: 50 lines)
  service <name> [lines]     View logs for a specific service
  errors [lines]             View error and above logs
  boot [id|list]             View boot logs (0=current, -1=prev, list=show boots)

Tailing:
  tail                        Tail system logs in real-time
  tail-service <name>         Tail service logs in real-time

Maintenance:
  clean [time] [size]        Clean old logs (default: 7d, 100M)
  disk-usage                  Show disk usage of journal

Help:
  help                        Show this help message

Examples:
  $0 system 100
  $0 service NetworkManager 20
  $0 errors
  $0 boot list
  $0 boot -1
  $0 tail
  $0 clean 3d 50M
HELP
}

# --- Main ---

main() {
    check_log_deps
    
    local command="${1:-help}"
    shift || true
    
    case "$command" in
        system|all)
            local lines="${1:-50}"
            view_system_logs "$lines"
            ;;
        kernel|dmesg)
            local lines="${1:-50}"
            view_kernel_logs "$lines"
            ;;
        service|svc)
            local service="${1:-}"
            if [ -z "$service" ]; then
                log_error "Service name required."
                exit 1
            fi
            local lines="${2:-50}"
            view_service_logs "$service" "$lines"
            ;;
        errors|err)
            local lines="${1:-50}"
            view_errors "$lines"
            ;;
        boot)
            local boot_id="${1:-0}"
            view_boot_logs "$boot_id"
            ;;
        tail|follow)
            tail_system_logs
            ;;
        tail-service|follow-service)
            local service="${1:-}"
            if [ -z "$service" ]; then
                log_error "Service name required."
                exit 1
            fi
            tail_service_logs "$service"
            ;;
        clean|vacuum)
            local time="${1:-7d}"
            local size="${2:-100M}"
            clean_logs "$time" "$size"
            ;;
        disk-usage|usage)
            show_disk_usage
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