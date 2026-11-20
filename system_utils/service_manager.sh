#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Service Manager
# Provides a simplified interface for managing systemd services.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"
install_cleanup

# --- Configuration ---
SYSTEMCTL_CMD="systemctl"

# --- Helper Functions ---

check_service_deps() {
    check_dependencies "systemctl"
}

validate_service_name() {
    local service="$1"
    if [ -z "$service" ]; then
        log_error "Service name required."
        return 1
    fi

    # Basic validation to prevent command injection
    if ! [[ "$service" =~ ^[a-zA-Z0-9@_-]+(\.service)?$ ]]; then
        log_error "Invalid service name: $service"
        return 1
    fi

    # Automatically append .service if not present
    if [[ "$service" != *.service ]]; then
        echo "${service}.service"
    else
        echo "$service"
    fi
}

# --- Status Functions ---

show_status() {
    local service
    service=$(validate_service_name "$1") || return 1

    log_info "Status for service: $service"
    $SYSTEMCTL_CMD status "$service" --no-pager
}

is_active() {
    local service
    service=$(validate_service_name "$1") || return 1

    if $SYSTEMCTL_CMD is-active --quiet "$service"; then
        log_success "Service '$service' is active (running)."
        return 0
    else
        log_warn "Service '$service' is inactive or failed."
        return 1
    fi
}

is_enabled() {
    local service
    service=$(validate_service_name "$1") || return 1

    if $SYSTEMCTL_CMD is-enabled --quiet "$service" 2>/dev/null; then
        log_success "Service '$service' is enabled (starts on boot)."
        return 0
    else
        log_warn "Service '$service' is disabled."
        return 1
    fi
}

# --- Listing Functions ---

list_running() {
    log_info "Running Services:"
    echo "==================================="
    $SYSTEMCTL_CMD list-units --type=service --state=running --no-pager --no-legend | awk '{print $1, $4}'
    echo "==================================="
}

list_failed() {
    log_info "Failed Services:"
    echo "==================================="
    local failed
    failed=$($SYSTEMCTL_CMD list-units --type=service --state=failed --no-pager --no-legend | awk '{print $1}')

    if [ -z "$failed" ]; then
        log_success "No failed services found."
    else
        echo "$failed"
    fi
    echo "==================================="
}

list_all() {
    log_info "All Loaded Services:"
    echo "==================================="
    $SYSTEMCTL_CMD list-units --type=service --all --no-pager --no-legend | awk '{printf "%-40s %s\n", $1, $4}'
    echo "==================================="
}

# --- Control Functions ---

start_service() {
    local service
    service=$(validate_service_name "$1") || return 1

    log_info "Starting service: $service"
    if ! $SYSTEMCTL_CMD start "$service"; then
        log_error "Failed to start '$service'."
        return 1
    fi
    log_success "Service '$service' started."
}

stop_service() {
    local service
    service=$(validate_service_name "$1") || return 1

    log_info "Stopping service: $service"
    if ! $SYSTEMCTL_CMD stop "$service"; then
        log_error "Failed to stop '$service'."
        return 1
    fi
    log_success "Service '$service' stopped."
}

restart_service() {
    local service
    service=$(validate_service_name "$1") || return 1

    log_info "Restarting service: $service"
    if ! $SYSTEMCTL_CMD restart "$service"; then
        log_error "Failed to restart '$service'."
        return 1
    fi
    log_success "Service '$service' restarted."
}

reload_service() {
    local service
    service=$(validate_service_name "$1") || return 1

    log_info "Reloading service configuration: $service"
    if ! $SYSTEMCTL_CMD reload "$service"; then
        log_error "Failed to reload '$service'."
        log_info "The service might not support reload. Try 'restart' instead."
        return 1
    fi
    log_success "Service '$service' reloaded."
}

enable_service() {
    local service
    service=$(validate_service_name "$1") || return 1

    log_info "Enabling service (start on boot): $service"
    if ! $SYSTEMCTL_CMD enable "$service"; then
        log_error "Failed to enable '$service'."
        return 1
    fi
    log_success "Service '$service' enabled."
}

disable_service() {
    local service
    service=$(validate_service_name "$1") || return 1

    log_info "Disabling service (won't start on boot): $service"
    if ! $SYSTEMCTL_CMD disable "$service"; then
        log_error "Failed to disable '$service'."
        return 1
    fi
    log_success "Service '$service' disabled."
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Service Manager

Usage: $0 <command> [service_name]

Status:
  status <service>            Show detailed status of a service
  is-active <service>         Check if service is running (exit 0=yes, 1=no)
  is-enabled <service>        Check if service starts on boot

Listing:
  list-running                List all currently running services
  list-failed                 List all failed services
  list-all                    List all loaded services

Control:
  start <service>             Start a service
  stop <service>              Stop a service
  restart <service>           Restart a service
  reload <service>            Reload service configuration (if supported)
  enable <service>            Enable service to start on boot
  disable <service>           Disable service from starting on boot

Help:
  help                        Show this help message

Notes:
  - The '.service' suffix is automatically appended if omitted.
  - Most operations require root privileges (use sudo).

Examples:
  $0 status NetworkManager
  $0 restart bluetooth
  $0 enable ssh
  $0 list-failed
HELP
}

# --- Main ---

main() {
    check_service_deps

    local command="${1:-help}"
    shift || true

    case "$command" in
        status)
            local service="${1:-}"
            if [ -z "$service" ]; then
                log_error "Service name required."
                exit 1
            fi
            show_status "$service"
            ;;
        is-active)
            local service="${1:-}"
            if [ -z "$service" ]; then
                log_error "Service name required."
                exit 1
            fi
            is_active "$service"
            ;;
        is-enabled)
            local service="${1:-}"
            if [ -z "$service" ]; then
                log_error "Service name required."
                exit 1
            fi
            is_enabled "$service"
            ;;
        list-running|running)
            list_running
            ;;
        list-failed|failed)
            list_failed
            ;;
        list-all|all)
            list_all
            ;;
        start)
            local service="${1:-}"
            if [ -z "$service" ]; then
                log_error "Service name required."
                exit 1
            fi
            start_service "$service"
            ;;
        stop)
            local service="${1:-}"
            if [ -z "$service" ]; then
                log_error "Service name required."
                exit 1
            fi
            stop_service "$service"
            ;;
        restart)
            local service="${1:-}"
            if [ -z "$service" ]; then
                log_error "Service name required."
                exit 1
            fi
            restart_service "$service"
            ;;
        reload)
            local service="${1:-}"
            if [ -z "$service" ]; then
                log_error "Service name required."
                exit 1
            fi
            reload_service "$service"
            ;;
        enable)
            local service="${1:-}"
            if [ -z "$service" ]; then
                log_error "Service name required."
                exit 1
            fi
            enable_service "$service"
            ;;
        disable)
            local service="${1:-}"
            if [ -z "$service" ]; then
                log_error "Service name required."
                exit 1
            fi
            disable_service "$service"
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