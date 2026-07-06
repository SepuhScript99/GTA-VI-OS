#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Log Cleaner Utility
# Safely removes old system logs and vacuums the systemd journal.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Source Shared Library ---
if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found. Cannot continue." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

LOCKFILE="/var/lock/vice-clean-logs.lock"

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    if [ -f "$LOCKFILE" ]; then
        rm -f "$LOCKFILE"
    fi
    if [ $exit_code -eq 0 ]; then
        log_success "=== Log Cleanup Complete ==="
    else
        log_error "=== Log Cleanup failed with exit code $exit_code ==="
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Main ---
main() {
    check_root
    check_dependencies "systemctl" "find" "stat" "truncate"
    
    # Prevent concurrent execution
    exec 9>"$LOCKFILE"
    if ! flock -n 9; then
        log_warn "Another log cleanup process is already running. Exiting."
        exit 0
    fi

    log_info "=== Starting System Log Cleanup ==="

    log_info "Vacuuming systemd journal (keeping last 7 days)..."
    # This removes all journal entries older than 7 days
    journalctl --vacuum-time=7d 2>/dev/null || log_warn "journalctl vacuum-time failed."

    log_info "Vacuuming systemd journal (keeping max 100MB)..."
    # This ensures the journal doesn't exceed 100MB in size
    journalctl --vacuum-size=100M 2>/dev/null || log_warn "journalctl vacuum-size failed."

    log_info "Removing rotated and old log files in /var/log..."
    # Remove rotated logs (e.g., .gz, .1, .old)
    find /var/log -type f \( -name "*.gz" -o -name "*.1" -o -name "*.old" \) -delete 2>/dev/null || true

    # Truncate large active log files to free space without breaking the daemon
    log_info "Truncating active log files larger than 50MB..."
    local max_size_bytes=$((50 * 1024 * 1024)) # 50MB in bytes
    
    while IFS= read -r -d '' logfile; do
        local size
        size=$(stat -c%s "$logfile" 2>/dev/null || echo 0)
        if [ "$size" -gt "$max_size_bytes" ]; then
            log_info "Truncating $logfile (was $((size / 1024 / 1024))MB)..."
            truncate -s 0 "$logfile"
        fi
    done < <(find /var/log -type f -name "*.log" -print0 2>/dev/null)

    log_success "=== Log Cleanup Complete ==="
}

main "$@"