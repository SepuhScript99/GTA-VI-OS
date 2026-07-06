#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Configuration Backup Manager
# Manages backup and restoration of system and user configuration files.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Source Shared Library ---
if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found. Cannot continue." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

# --- Configuration ---
BACKUP_DIR="/var/backups/vice-os/config-backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/config_backup_${TIMESTAMP}.tar.gz"
KEEP_COUNT=5

# Directories to backup
ETC_DIRS=(
    "/etc/vice-os"
    "/etc/default"
    "/etc/modprobe.d"
    "/etc/sysctl.d"
    "/etc/xdg"
    "/etc/X11/xorg.conf.d"
    "/etc/ufw"
    "/etc/ssh"
    "/etc/NetworkManager/conf.d"
    "/etc/apt/sources.list.d"
    "/etc/apt/apt.conf.d"
    "/etc/polkit-1/rules.d"
)
USER_CONFIG_DIRS=(
    "${HOME}/.config"
    "${HOME}/.local/share/applications"
    "${HOME}/.bashrc"
    "${HOME}/.profile"
    "${HOME}/.Xresources"
)

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "Config backup operation failed with exit code $exit_code."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Helper Functions ---

check_backup_deps() {
    check_dependencies "tar" "find"
}

ensure_backup_dir() {
    if [ ! -d "$BACKUP_DIR" ]; then
        mkdir -p "$BACKUP_DIR"
    fi
}

validate_path() {
    local path="$1"
    if [ ! -e "$path" ]; then
        return 1
    fi
    return 0
}

# --- Backup Function ---

create_backup() {
    ensure_backup_dir
    
    log_info "Creating configuration backup..."
    log_info "Target: $BACKUP_FILE"
    
    local tmp_file
    tmp_file=$(mktemp)
    
    # Build list of files to backup
    {
        # Add /etc paths
        for dir in "${ETC_DIRS[@]}"; do
            if validate_path "$dir"; then
                echo "$dir"
            fi
        done
        
        # Add user config paths
        for dir in "${USER_CONFIG_DIRS[@]}"; do
            if validate_path "$dir"; then
                echo "$dir"
            fi
        done
    } > "$tmp_file"
    
    # Create tarball
    if ! tar czf "$BACKUP_FILE" -T "$tmp_file" 2>/dev/null; then
        log_error "Failed to create backup archive."
        rm -f "$tmp_file"
        return 1
    fi
    
    rm -f "$tmp_file"
    
    local size
    size=$(du -h "$BACKUP_FILE" | awk '{print $1}')
    log_success "Backup created: $BACKUP_FILE (Size: $size)"
}

# --- Restore Function ---

restore_backup() {
    local backup_name="$1"
    local backup_path="${BACKUP_DIR}/${backup_name}"
    
    if [ ! -f "$backup_path" ]; then
        log_error "Backup file '$backup_name' not found."
        return 1
    fi
    
    log_warn "This will overwrite current configurations."
    read -p "Type 'YES' to confirm restore: " confirm
    if [ "$confirm" != "YES" ]; then
        log_info "Restore aborted."
        return 1
    fi
    
    log_info "Restoring from: $backup_path"
    
    # Extract to root
    if ! tar xzf "$backup_path" -C / 2>/dev/null; then
        log_error "Failed to extract backup."
        return 1
    fi
    
    log_success "Configuration restored successfully."
}

# --- List Function ---

list_backups() {
    ensure_backup_dir
    
    log_info "Available Configuration Backups:"
    echo "==================================="
    
    local backups
    backups=$(find "$BACKUP_DIR" -name "config_backup_*.tar.gz" -type f | sort)
    
    if [ -z "$backups" ]; then
        log_info "No configuration backups found."
        return 0
    fi
    
    for file in $backups; do
        local name size
        name=$(basename "$file")
        size=$(du -h "$file" | awk '{print $1}')
        printf "  %-40s %8s\n" "$name" "$size"
    done
    
    echo "==================================="
}

# --- Delete Function ---

delete_backup() {
    local backup_name="$1"
    local backup_path="${BACKUP_DIR}/${backup_name}"
    
    if [ ! -f "$backup_path" ]; then
        log_error "Backup file '$backup_name' not found."
        return 1
    fi
    
    log_info "Deleting backup: $backup_name"
    rm -f "$backup_path"
    log_success "Backup deleted."
}

# --- Rotate Function ---

rotate_backups() {
    local keep="${1:-$KEEP_COUNT}"
    
    if ! [[ "$keep" =~ ^[0-9]+$ ]]; then
        log_error "Keep count must be a number."
        return 1
    fi
    
    ensure_backup_dir
    
    log_info "Rotating backups. Keeping last $keep..."
    
    local deleted_count=0
    while IFS= read -r file; do
        local name
        name=$(basename "$file")
        log_info "Deleting old backup: $name"
        rm -f "$file"
        deleted_count=$((deleted_count + 1))
    done < <(find "$BACKUP_DIR" -name "config_backup_*.tar.gz" -type f -printf '%T@ %p\n' | sort -rn | tail -n +$((keep + 1)) | awk '{print $2}')
    
    if [ "$deleted_count" -eq 0 ]; then
        log_info "No old backups to delete."
    else
        log_success "Deleted $deleted_count old backup(s)."
    fi
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Configuration Backup Manager

Usage: $0 <command> [options]

Commands:
  create                     Create a new configuration backup
  restore <backup_name>      Restore from a backup file
  list                       List all available backups
  delete <backup_name>       Delete a specific backup
  rotate [keep_count]       Keep only the newest N backups (default: 5)

Notes:
  - Backups are stored in: $BACKUP_DIR
  - Backups include: /etc configs, user configs, and application settings.
  - Restore requires root privileges (use sudo).

Examples:
  $0 create
  $0 list
  $0 restore config_backup_20231027_143000.tar.gz
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
            create_backup
            ;;
        restore|extract)
            local name="${1:-}"
            if [ -z "$name" ]; then
                log_error "Backup name required."
                exit 1
            fi
            restore_backup "$name"
            ;;
        list|ls)
            list_backups
            ;;
        delete|rm)
            local name="${1:-}"
            if [ -z "$name" ]; then
                log_error "Backup name required."
                exit 1
            fi
            delete_backup "$name"
            ;;
        rotate|cleanup)
            local keep="${1:-$KEEP_COUNT}"
            rotate_backups "$keep"
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