#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Process Manager
# Provides utilities for listing, finding, killing, and monitoring processes.
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
        log_error "Process operation failed with exit code $exit_code."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Helper Functions ---

check_process_deps() {
    check_dependencies "ps" "pgrep" "pkill"
}

validate_pid() {
    local pid="$1"
    if ! [[ "$pid" =~ ^[0-9]+$ ]]; then
        log_error "Invalid PID: $pid. Must be a number."
        return 1
    fi
    if ! ps -p "$pid" > /dev/null 2>&1; then
        log_error "Process with PID $pid does not exist."
        return 1
    fi
    return 0
}

# --- Listing Functions ---

list_all() {
    log_info "All Running Processes:"
    echo "==================================="
    ps aux --sort=-%cpu
    echo "==================================="
}

list_by_user() {
    local user="$1"
    
    if [ -z "$user" ]; then
        log_error "Username required."
        return 1
    fi
    
    log_info "Processes for user: $user"
    echo "==================================="
    ps -u "$user" -f
    echo "==================================="
}

# --- Finding Functions ---

find_by_name() {
    local name="$1"
    
    if [ -z "$name" ]; then
        log_error "Process name required."
        return 1
    fi
    
    log_info "Processes matching: $name"
    echo "==================================="
    
    local results
    results=$(pgrep -a "$name")
    
    if [ -z "$results" ]; then
        log_info "No processes found matching '$name'."
    else
        echo "$results"
    fi
    
    echo "==================================="
}

# --- Kill Functions ---

kill_pid() {
    local pid="$1"
    local signal="${2:-TERM}"
    
    validate_pid "$pid" || return 1
    
    log_info "Sending $signal signal to PID $pid..."
    
    if ! kill -"$signal" "$pid"; then
        log_error "Failed to send signal to PID $pid."
        log_info "Try running with sudo or use signal KILL."
        return 1
    fi
    
    log_success "Signal $signal sent to PID $pid."
}

kill_by_name() {
    local name="$1"
    local signal="${2:-TERM}"
    
    if [ -z "$name" ]; then
        log_error "Process name required."
        return 1
    fi
    
    log_info "Sending $signal signal to processes matching: $name..."
    
    if ! pkill -"$signal" "$name"; then
        log_error "Failed to send signal. No processes matched or permission denied."
        return 1
    fi
    
    log_success "Signal $signal sent to matching processes."
}

force_kill_pid() {
    local pid="$1"
    log_warn "Force killing (SIGKILL) PID $pid. Unsaved data may be lost."
    kill_pid "$pid" "KILL"
}

force_kill_name() {
    local name="$1"
    log_warn "Force killing (SIGKILL) processes matching: $name. Unsaved data may be lost."
    kill_by_name "$name" "KILL"
}

# --- Resource Monitoring Functions ---

top_cpu() {
    local count="${1:-10}"
    
    if ! [[ "$count" =~ ^[0-9]+$ ]]; then
        log_error "Count must be a number."
        return 1
    fi
    
    log_info "Top $count processes by CPU usage:"
    echo "==================================="
    ps -eo pid,ppid,user,%cpu,%mem,cmd --sort=-%cpu | head -n $((count + 1))
    echo "==================================="
}

top_mem() {
    local count="${1:-10}"
    
    if ! [[ "$count" =~ ^[0-9]+$ ]]; then
        log_error "Count must be a number."
        return 1
    fi
    
    log_info "Top $count processes by Memory usage:"
    echo "==================================="
    ps -eo pid,ppid,user,%cpu,%mem,cmd --sort=-%mem | head -n $((count + 1))
    echo "==================================="
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Process Manager

Usage: $0 <command> [options]

Listing:
  list                        List all running processes
  list-user <username>        List processes for a specific user

Finding:
  find <name>                 Find processes by name (uses pgrep)

Killing:
  kill <pid> [signal]         Send signal to PID (default: TERM)
  kill-name <name> [signal]   Send signal to processes by name (default: TERM)
  force-kill <pid>            Force kill (SIGKILL) a specific PID
  force-kill-name <name>      Force kill (SIGKILL) processes by name

Monitoring:
  top-cpu [count]             Show top N processes by CPU usage (default: 10)
  top-mem [count]             Show top N processes by Memory usage (default: 10)

Help:
  help                        Show this help message

Notes:
  - Signals can be specified by name (e.g., TERM, KILL, HUP) or number.
  - Killing processes may require root privileges (use sudo).

Examples:
  $0 list
  $0 find firefox
  $0 top-cpu 5
  $0 kill 1234 HUP
  $0 force-kill-name chromium
HELP
}

# --- Main ---

main() {
    check_process_deps
    
    local command="${1:-help}"
    shift || true
    
    case "$command" in
        list|all)
            list_all
            ;;
        list-user|user)
            local user="${1:-}"
            if [ -z "$user" ]; then
                log_error "Username required."
                exit 1
            fi
            list_by_user "$user"
            ;;
        find|grep|search)
            local name="${1:-}"
            if [ -z "$name" ]; then
                log_error "Process name required."
                exit 1
            fi
            find_by_name "$name"
            ;;
        kill)
            local pid="${1:-}"
            if [ -z "$pid" ]; then
                log_error "PID required."
                exit 1
            fi
            local signal="${2:-TERM}"
            kill_pid "$pid" "$signal"
            ;;
        kill-name|pkill)
            local name="${1:-}"
            if [ -z "$name" ]; then
                log_error "Process name required."
                exit 1
            fi
            local signal="${2:-TERM}"
            kill_by_name "$name" "$signal"
            ;;
        force-kill|kill-9)
            local pid="${1:-}"
            if [ -z "$pid" ]; then
                log_error "PID required."
                exit 1
            fi
            force_kill_pid "$pid"
            ;;
        force-kill-name|pkill-9)
            local name="${1:-}"
            if [ -z "$name" ]; then
                log_error "Process name required."
                exit 1
            fi
            force_kill_name "$name"
            ;;
        top-cpu|cpu)
            local count="${1:-10}"
            top_cpu "$count"
            ;;
        top-mem|mem)
            local count="${1:-10}"
            top_mem "$count"
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