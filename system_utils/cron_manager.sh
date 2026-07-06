#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Cron Manager
# Provides safe, non-interactive management of user crontab entries.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Source Shared Library ---
if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found. Cannot continue." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

# --- Configuration ---
SYSTEMCTL_CMD="systemctl"
CRONTAB_CMD="crontab"

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "Cron operation failed with exit code $exit_code."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Helper Functions ---

check_cron_deps() {
    check_dependencies "crontab"
    
    # Check if cron service is running
    if ! $SYSTEMCTL_CMD is-active --quiet cron 2>/dev/null; then
        log_warn "Cron service is not running. Attempting to start..."
        $SYSTEMCTL_CMD enable --now cron 2>/dev/null || log_warn "Could not start cron service."
    fi
}

validate_schedule() {
    local schedule="$1"
    local field_count
    
    # Count fields in the schedule string
    field_count=$(echo "$schedule" | wc -w)
    
    if [ "$field_count" -ne 5 ]; then
        log_error "Invalid cron schedule format."
        log_info "Expected 5 fields: minute hour day-of-month month day-of-week"
        log_info "Example: '0 2 * * *' (Runs at 2:00 AM every day)"
        return 1
    fi
    
    return 0
}

# --- Listing Functions ---

list_jobs() {
    log_info "Current Cron Jobs for user '$USER':"
    echo "==================================="
    
    local jobs
    jobs=$($CRONTAB_CMD -l 2>/dev/null)
    
    if [ -z "$jobs" ]; then
        log_info "No cron jobs configured."
    else
        echo "$jobs"
    fi
    
    echo "==================================="
}

# --- Job Management Functions ---

add_job() {
    local schedule="$1"
    shift
    local command="$*"
    
    validate_schedule "$schedule" || return 1
    
    if [ -z "$command" ]; then
        log_error "Command to execute is required."
        return 1
    fi
    
    local entry="$schedule $command"
    
    log_info "Adding cron job: $entry"
    
    # Safely append to crontab without removing existing entries
    # Create a temp file to hold the combined crontab
    local tmp_crontab
    tmp_crontab=$(mktemp)
    
    # Dump existing crontab (ignore errors if none exists)
    $CRONTAB_CMD -l > "$tmp_crontab" 2>/dev/null || true
    
    # Ensure the file ends with a newline before appending
    if [ -s "$tmp_crontab" ] && [ "$(tail -c1 "$tmp_crontab" | wc -l)" -eq 0 ]; then
        echo "" >> "$tmp_crontab"
    fi
    
    echo "$entry" >> "$tmp_crontab"
    
    # Install the new crontab
    if ! $CRONTAB_CMD "$tmp_crontab"; then
        log_error "Failed to install new crontab."
        rm -f "$tmp_crontab"
        return 1
    fi
    
    rm -f "$tmp_crontab"
    log_success "Cron job added successfully."
}

remove_job() {
    local pattern="$1"
    
    if [ -z "$pattern" ]; then
        log_error "Pattern required to identify job(s) for removal."
        log_info "Example: $0 remove '/usr/local/bin/backup.sh'"
        return 1
    fi
    
    log_info "Removing cron jobs matching: $pattern"
    
    local tmp_crontab
    tmp_crontab=$(mktemp)
    
    # Dump existing crontab, filtering out matching lines
    $CRONTAB_CMD -l 2>/dev/null | grep -v "$pattern" > "$tmp_crontab" || true
    
    # Check if anything changed
    local original_count new_count
    original_count=$($CRONTAB_CMD -l 2>/dev/null | wc -l)
    new_count=$(wc -l < "$tmp_crontab")
    
    if [ "$original_count" -eq "$new_count" ]; then
        log_warn "No matching cron jobs found."
        rm -f "$tmp_crontab"
        return 0
    fi
    
    # Install the filtered crontab
    if ! $CRONTAB_CMD "$tmp_crontab"; then
        log_error "Failed to update crontab."
        rm -f "$tmp_crontab"
        return 1
    fi
    
    rm -f "$tmp_crontab"
    log_success "Matching cron job(s) removed."
}

clear_all_jobs() {
    log_warn "WARNING: This will permanently delete ALL cron jobs for user '$USER'."
    read -p "Type 'YES' to confirm: " confirm
    
    if [ "$confirm" != "YES" ]; then
        log_info "Operation aborted."
        return 1
    fi
    
    log_info "Clearing all cron jobs..."
    $CRONTAB_CMD -r
    log_success "All cron jobs cleared."
}

# --- Service Management Functions ---

start_service() {
    log_info "Starting and enabling cron service..."
    $SYSTEMCTL_CMD enable --now cron
    log_success "Cron service enabled and started."
}

stop_service() {
    log_info "Stopping and disabling cron service..."
    $SYSTEMCTL_CMD disable --now cron
    log_success "Cron service stopped and disabled."
}

restart_service() {
    log_info "Restarting cron service..."
    $SYSTEMCTL_CMD restart cron
    log_success "Cron service restarted."
}

status_service() {
    log_info "Cron Service Status:"
    echo "==================================="
    $SYSTEMCTL_CMD status cron --no-pager
    echo "==================================="
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Cron Manager

Usage: $0 <command> [options]

Job Management:
  list                        List all current cron jobs
  add <schedule> <command>    Add a new cron job
  remove <pattern>            Remove cron jobs matching a pattern (e.g., a script name)
  clear                       Clear ALL cron jobs (requires confirmation)

Service Control:
  start                       Enable and start the cron daemon
  stop                        Disable and stop the cron daemon
  restart                     Restart the cron daemon
  status                      Show cron daemon status

Help:
  help                        Show this help message

Schedule Format:
  The schedule consists of 5 fields:
  1. Minute (0-59)
  2. Hour (0-23)
  3. Day of month (1-31)
  4. Month (1-12)
  5. Day of week (0-7) (0 or 7 is Sunday, or use names like Mon, Tue)

  Examples:
    "0 * * * *"        - Every hour on the hour
    "*/15 * * * *"     - Every 15 minutes
    "0 2 * * *"         - Every day at 2:00 AM
    "0 0 * * 0"         - Every Sunday at midnight

Examples:
  $0 list
  $0 add "0 2 * * *" /usr/local/bin/backup.sh
  $0 remove "backup.sh"
  $0 status
HELP
}

# --- Main ---

main() {
    check_cron_deps
    
    local command="${1:-help}"
    shift || true
    
    case "$command" in
        list|ls)
            list_jobs
            ;;
        add)
            local schedule="${1:-}"
            if [ -z "$schedule" ]; then
                log_error "Schedule required."
                exit 1
            fi
            shift
            if [ $# -eq 0 ]; then
                log_error "Command required."
                exit 1
            fi
            add_job "$schedule" "$@"
            ;;
        remove|rm)
            local pattern="${1:-}"
            if [ -z "$pattern" ]; then
                log_error "Pattern required."
                exit 1
            fi
            remove_job "$pattern"
            ;;
        clear|wipe)
            clear_all_jobs
            ;;
        start|enable)
            start_service
            ;;
        stop|disable)
            stop_service
            ;;
        restart)
            restart_service
            ;;
        status)
            status_service
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