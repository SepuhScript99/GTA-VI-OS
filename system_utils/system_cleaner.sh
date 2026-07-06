#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) System Cleaner
# Provides deep cleaning of caches, temporary files, and orphaned packages.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Source Shared Library ---
if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found. Cannot continue." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

# --- Configuration ---
DRY_RUN=false

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "System cleanup failed with exit code $exit_code."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Helper Functions ---

check_cleaner_deps() {
    check_dependencies "apt-get" "journalctl" "find" "du"
}

# Prints dry-run prefix if active
dr() {
    if [ "$DRY_RUN" == true ]; then
        echo "[Dry Run]"
    fi
}

# --- Cleaning Functions ---

clean_apt_cache() {
    log_info "Cleaning APT Cache..."
    
    if [ "$DRY_RUN" == true ]; then
        log_warn "Would run: apt-get clean, apt-get autoremove --purge"
        return 0
    fi
    
    apt-get clean
    apt-get autoremove -y --purge
    log_success "APT cache cleaned."
}

clean_journal() {
    log_info "Vacuuming Systemd Journal (keeping last 7 days, max 100M)..."
    
    if [ "$DRY_RUN" == true ]; then
        log_warn "Would run: journalctl --vacuum-time=7d, --vacuum-size=100M"
        return 0
    fi
    
    journalctl --vacuum-time=7d
    journalctl --vacuum-size=100M
    log_success "Journal vacuumed."
}

clean_thumbnail_cache() {
    local user_home="${1:-/home/vice}"
    local thumb_dir="${user_home}/.cache/thumbnails"
    
    if [ ! -d "$thumb_dir" ]; then
        log_info "No thumbnail cache found in $user_home."
        return 0
    fi
    
    local size_before
    size_before=$(du -sh "$thumb_dir" 2>/dev/null | awk '{print $1}')
    
    log_info "Cleaning Thumbnail Cache in $user_home (Size: $size_before)..."
    
    if [ "$DRY_RUN" == true ]; then
        log_warn "Would remove: $thumb_dir/*"
        return 0
    fi
    
    find "$thumb_dir" -type f -delete
    log_success "Thumbnail cache cleaned."
}

clean_tmp() {
    log_info "Cleaning /tmp (files older than 1 day not in use)..."
    
    if [ "$DRY_RUN" == true ]; then
        log_warn "Would remove files in /tmp older than 1 day"
        return 0
    fi
    
    # -not -path "*/systemd-*" to avoid breaking systemd private tmp dirs
    find /tmp -depth -mindepth 1 -mtime +1 -not -path "*/systemd-*" -delete 2>/dev/null || true
    log_success "/tmp cleaned."
}

remove_orphans() {
    log_info "Removing Orphaned Packages..."
    
    if [ "$DRY_RUN" == true ]; then
        local orphans
        orphans=$(apt-get autoremove --dry-run 2>/dev/null | grep "将被删除" || apt-get autoremove --dry-run 2>/dev/null | grep "will be REMOVED")
        if [ -n "$orphans" ]; then
            log_warn "Would remove orphaned packages:"
            echo "$orphans"
        else
            log_info "No orphaned packages found."
        fi
        return 0
    fi
    
    apt-get autoremove -y --purge
    log_success "Orphaned packages removed."
}

clean_all() {
    log_info "=== Starting Full System Cleanup ==="
    
    clean_apt_cache
    clean_journal
    
    # Clean for all users with home directories
    while IFS=: read -r user _ home_dir _; do
        if [[ "$home_dir" == /home/* ]]; then
            clean_thumbnail_cache "$home_dir"
        fi
    done < /etc/passwd
    
    clean_tmp
    remove_orphans
    
    log_info "=== Full System Cleanup Complete ==="
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) System Cleaner

Usage: $0 <command> [--dry-run]

Commands:
  all                  Run all cleaning operations
  apt                  Clean APT cache and autoremove
  journal              Vacuum systemd journal (7 days / 100M)
  thumbnails           Clean user thumbnail caches
  tmp                  Clean /tmp (files older than 1 day)
  orphans             Remove orphaned packages (autoremove --purge)

Options:
  --dry-run           Show what would be cleaned without actually deleting

Help:
  help                 Show this help message

Examples:
  $0 all --dry-run
  $0 apt
  $0 thumbnails
HELP
}

# --- Main ---

main() {
    check_cleaner_deps
    check_root
    
    local command="${1:-help}"
    shift || true
    
    # Check for --dry-run flag
    for arg in "$@"; do
        if [ "$arg" == "--dry-run" ]; then
            DRY_RUN=true
            log_warn "Dry Run Mode Active. No files will be deleted."
        fi
    done
    
    case "$command" in
        all|full)
            clean_all
            ;;
        apt|apt-cache)
            clean_apt_cache
            ;;
        journal|logs)
            clean_journal
            ;;
        thumbnails|thumbs)
            clean_thumbnail_cache
            ;;
        tmp|temp)
            clean_tmp
            ;;
        orphans|autoremove)
            remove_orphans
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