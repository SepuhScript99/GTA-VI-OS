#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Home Directory Backup Utility
# Creates a compressed tar.xz archive of /home/vice and rotates old backups.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Source Shared Library ---
if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found. Cannot continue." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

# --- Configuration ---
BACKUP_SOURCE="/home/vice"
BACKUP_DEST_DIR="${1:-/var/backups}"
TIMESTAMP=$(date +%Y%m%d%H%M%S)
BACKUP_FILE="$BACKUP_DEST_DIR/vice_home_backup_$TIMESTAMP.tar.xz"
KEEP_COUNT=3 # Number of recent backups to keep
LOCKFILE="/var/lock/vice-backup.lock"

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    if [ -f "$LOCKFILE" ]; then
        rm -f "$LOCKFILE"
    fi
    
    if [ $exit_code -ne 0 ] && [ -f "$BACKUP_FILE" ]; then
        log_warn "Backup failed. Removing partial archive..."
        rm -f "$BACKUP_FILE"
    fi
    
    if [ $exit_code -eq 0 ]; then
        log_success "=== Backup Process Complete ==="
    else
        log_error "=== Backup failed with exit code $exit_code ==="
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Main ---
main() {
    check_root
    check_dependencies "tar" "find"
    
    # Prevent concurrent execution
    exec 9>"$LOCKFILE"
    if ! flock -n 9; then
        log_warn "Another backup process is already running. Exiting."
        exit 0
    fi

    log_info "=== Starting Home Directory Backup ==="

    if [ ! -d "$BACKUP_SOURCE" ]; then
        log_error "Backup source directory not found: $BACKUP_SOURCE"
        exit 1
    fi

    log_info "Creating destination directory: $BACKUP_DEST_DIR"
    mkdir -p "$BACKUP_DEST_DIR"

    log_info "Creating compressed archive: $BACKUP_FILE"
    # Exclude caches, trash, and virtual filesystems to save space and avoid errors
    # We check the exit code explicitly to ensure the archive is valid.
    if ! tar --exclude="$BACKUP_SOURCE/.cache" \
             --exclude="$BACKUP_SOURCE/.local/share/Trash" \
             --exclude="$BACKUP_SOURCE/.gvfs" \
             -cJf "$BACKUP_FILE" \
             -C / home/vice; then
        log_error "Tar command failed. Archive may be corrupt."
        exit 1
    fi

    local size
    size=$(du -sh "$BACKUP_FILE" | awk '{print $1}')
    log_success "Backup created successfully (Size: $size)"

    log_info "Rotating old backups (keeping $KEEP_COUNT)..."
    
    # Use find to list files, sort by modification time (newest first), 
    # skip the first KEEP_COUNT, and safely delete the rest.
    # This is robust against filenames with spaces or special characters.
    find "$BACKUP_DEST_DIR" -name "vice_home_backup_*.tar.xz" -printf "%T@ %p\n" | \
    sort -rn | \
    tail -n +$((KEEP_COUNT + 1)) | \
    cut -d' ' -f2- | \
    while IFS= read -r old_file; do
        if [ -n "$old_file" ]; then
            rm -f "$old_file"
            log_info "Removed old backup: $(basename "$old_file")"
        fi
    done
}

main "$@"