#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Backup Manager
# Provides general-purpose backup creation, verification, restoration,
# listing, and rotation for any system directory.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Source Shared Library ---
if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found. Cannot continue." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

# --- Configuration ---
BACKUP_DIR="/var/backups/vice-os"
TIMESTAMP=$(date +%Y%m%d%H%M%S)

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "Backup operation failed with exit code $exit_code."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Helper Functions ---

check_backup_deps() {
    check_dependencies "tar" "sha256sum" "find"
}

ensure_backup_dir() {
    if [ ! -d "$BACKUP_DIR" ]; then
        mkdir -p "$BACKUP_DIR"
        chmod 750 "$BACKUP_DIR"
    fi
}

validate_source_path() {
    local path="$1"
    if [ ! -e "$path" ]; then
        log_error "Source path '$path' does not exist."
        return 1
    fi
}

# --- Core Functions ---

create_backup() {
    local source_path="$1"
    local backup_name="${2:-}"
    
    validate_source_path "$source_path" || return 1
    ensure_backup_dir
    
    local parent_dir
    parent_dir=$(dirname "$source_path")
    local base_name
    base_name=$(basename "$source_path")
    
    if [ -z "$backup_name" ]; then
        # Sanitize name for filename safety
        local safe_name
        safe_name=$(echo "$base_name" | tr '/ ' '__')
        backup_name="${safe_name}_backup_${TIMESTAMP}.tar.gz"
    fi
    
    local backup_path="${BACKUP_DIR}/${backup_name}"
    local checksum_path="${backup_path}.sha256"
    
    log_info "Creating backup of '$source_path'..."
    log_info "Backup file: $backup_path"
    
    # Create tarball
    # --absolute-names is not used to prevent security issues; we cd to parent
    if ! tar -czpf "$backup_path" -C "$parent_dir" "$base_name"; then
        log_error "Failed to create backup archive."
        rm -f "$backup_path"
        return 1
    fi
    
    # Generate checksum
    log_info "Generating checksum..."
    if ! sha256sum "$backup_path" > "$checksum_path"; then
        log_error "Failed to generate checksum."
        rm -f "$backup_path" "$checksum_path"
        return 1
    fi
    
    local size
    size=$(du -h "$backup_path" | awk '{print $1}')
    
    log_success "Backup created successfully."
    log_info "Size: $size"
    log_info "Checksum: $checksum_path"
}

restore_backup() {
    local backup_name="$1"
    local dest_dir="${2:-/}"
    
    local backup_path="${BACKUP_DIR}/${backup_name}"
    local checksum_path="${backup_path}.sha256"
    
    if [ ! -f "$backup_path" ]; then
        log_error "Backup file '$backup_name' not found in $BACKUP_DIR."
        return 1
    fi
    
    if [ ! -d "$dest_dir" ]; then
        log_info "Destination directory does not exist. Creating: $dest_dir"
        mkdir -p "$dest_dir"
    fi
    
    log_info "Restoring backup '$backup_name' to '$dest_dir'..."
    
    # Verify checksum if it exists
    if [ -f "$checksum_path" ]; then
        log_info "Verifying backup integrity..."
        if ! sha256sum -c "$checksum_path" --quiet 2>/dev/null; then
            log_error "Checksum verification failed! Backup may be corrupted."
            log_warn "Aborting restore to prevent data damage."
            return 1
        fi
        log_success "Checksum verified."
    else
        log_warn "No checksum file found. Proceeding without integrity check."
    fi
    
    # Extract tarball
    if ! tar -xzpf "$backup_path" -C "$dest_dir"; then
        log_error "Failed to extract backup."
        return 1
    fi
    
    log_success "Backup restored successfully to: $dest_dir"
}

list_backups() {
    ensure_backup_dir
    
    log_info "Available Backups in $BACKUP_DIR:"
    echo "==================================="
    
    local backups
    backups=$(find "$BACKUP_DIR" -name "*.tar.gz" -type f | sort)
    
    if [ -z "$backups" ]; then
        log_info "No backups found."
        return 0
    fi
    
    for file in $backups; do
        local name size
        name=$(basename "$file")
        size=$(du -h "$file" | awk '{print $1}')
        local has_checksum="No"
        if [ -f "${file}.sha256" ]; then
            has_checksum="Yes"
        fi
        
        printf "  %-45s %8s  Checksum: %s\n" "$name" "$size" "$has_checksum"
    done
    
    echo "==================================="
}

delete_backup() {
    local backup_name="$1"
    
    local backup_path="${BACKUP_DIR}/${backup_name}"
    local checksum_path="${backup_path}.sha256"
    
    if [ ! -f "$backup_path" ]; then
        log_error "Backup file '$backup_name' not found."
        return 1
    fi
    
    log_info "Deleting backup: $backup_name"
    rm -f "$backup_path" "$checksum_path"
    
    log_success "Backup deleted."
}

rotate_backups() {
    local keep_count="${1:-5}"
    
    if ! [[ "$keep_count" =~ ^[0-9]+$ ]]; then
        log_error "Keep count must be a number."
        return 1
    fi
    
    ensure_backup_dir
    
    log_info "Rotating backups. Keeping last $keep_count..."
    
    # List backups by modification time (newest first), skip the first N, delete the rest
    local deleted_count=0
    while IFS= read -r file; do
        local name
        name=$(basename "$file")
        log_info "Deleting old backup: $name"
        rm -f "$file" "${file}.sha256"
        deleted_count=$((deleted_count + 1))
    done < <(find "$BACKUP_DIR" -name "*.tar.gz" -type f -printf '%T@ %p\n' | sort -rn | tail -n +$((keep_count + 1)) | awk '{print $2}')
    
    if [ "$deleted_count" -eq 0 ]; then
        log_info "No old backups to delete."
    else
        log_success "Deleted $deleted_count old backup(s)."
    fi
}

verify_backup() {
    local backup_name="$1"
    
    local backup_path="${BACKUP_DIR}/${backup_name}"
    local checksum_path="${backup_path}.sha256"
    
    if [ ! -f "$backup_path" ]; then
        log_error "Backup file '$backup_name' not found."
        return 1
    fi
    
    if [ ! -f "$checksum_path" ]; then
        log_error "Checksum file not found for '$backup_name'. Cannot verify."
        return 1
    fi
    
    log_info "Verifying integrity of '$backup_name'..."
    
    if sha256sum -c "$checksum_path" --quiet 2>/dev/null; then
        log_success "Backup integrity verified successfully."
    else
        log_error "Backup verification FAILED! The archive may be corrupted."
        return 1
    fi
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Backup Manager

Usage: $0 <command> [options]

Commands:
  create <source_path> [backup_name]   Create a backup of a file or directory
  restore <backup_name> [dest_dir]     Restore a backup to a directory (default: /)
  list                                 List all available backups
  delete <backup_name>                 Delete a specific backup
  rotate [keep_count]                  Keep only the newest N backups (default: 5)
  verify <backup_name>                 Verify backup integrity using SHA256

Notes:
  - Backups are stored in: $BACKUP_DIR
  - Backups are compressed with gzip (.tar.gz)
  - SHA256 checksums are generated automatically for integrity verification

Examples:
  $0 create /etc
  $0 create /home/vice my_home_backup.tar.gz
  $0 list
  $0 verify etc_backup_20231027_120000.tar.gz
  $0 restore my_home_backup.tar.gz /tmp/restore_test
  $0 rotate 3
HELP
}

# --- Main ---

main() {
    check_backup_deps
    
    local command="${1:-help}"
    shift || true
    
    case "$command" in
        create|backup)
            local source_path="${1:-}"
            if [ -z "$source_path" ]; then
                log_error "Source path required."
                exit 1
            fi
            local backup_name="${2:-}"
            create_backup "$source_path" "$backup_name"
            ;;
        restore|extract)
            local backup_name="${1:-}"
            if [ -z "$backup_name" ]; then
                log_error "Backup name required."
                exit 1
            fi
            local dest_dir="${2:-/}"
            restore_backup "$backup_name" "$dest_dir"
            ;;
        list|ls)
            list_backups
            ;;
        delete|rm)
            local backup_name="${1:-}"
            if [ -z "$backup_name" ]; then
                log_error "Backup name required."
                exit 1
            fi
            delete_backup "$backup_name"
            ;;
        rotate|cleanup)
            local keep_count="${1:-5}"
            rotate_backups "$keep_count"
            ;;
        verify|check)
            local backup_name="${1:-}"
            if [ -z "$backup_name" ]; then
                log_error "Backup name required."
                exit 1
            fi
            verify_backup "$backup_name"
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