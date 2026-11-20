#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) File Manager
# Provides CLI utilities for file analysis, cleanup, secure deletion, and archiving.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"
install_cleanup

# --- Helper Functions ---

check_file_deps() {
    check_dependencies "find" "du" "tar"
}

validate_path() {
    local path="$1"
    if [ ! -e "$path" ]; then
        log_error "Path '$path' does not exist."
        return 1
    fi
}

# --- Analysis Functions ---

dir_size() {
    local path="$1"

    validate_path "$path" || return 1

    log_info "Calculating size of: $path"
    echo "==================================="
    du -sh "$path" 2>/dev/null
    echo "==================================="
}

largest_files() {
    local path="$1"
    local count="${2:-10}"

    validate_path "$path" || return 1

    log_info "Top $count largest files in $path:"
    echo "==================================="

    # Use find to get files, du to get sizes, sort descending, head top N
    find "$path" -type f -exec du -h {} + 2>/dev/null | sort -rh | head -n "$count"

    echo "==================================="
}

empty_dirs() {
    local path="$1"

    validate_path "$path" || return 1

    log_info "Empty directories in $path:"
    echo "==================================="

    local empty
    empty=$(find "$path" -type d -empty 2>/dev/null)

    if [ -z "$empty" ]; then
        log_info "No empty directories found."
    else
        echo "$empty"
    fi

    echo "==================================="
}

# --- Cleanup Functions ---

clean_empty_dirs() {
    local path="$1"
    local dry_run="${2:-no}"

    validate_path "$path" || return 1

    if [ "$dry_run" == "yes" ] || [ "$dry_run" == "--dry-run" ]; then
        log_info "[Dry Run] Empty directories that would be removed:"
        find "$path" -type d -empty 2>/dev/null
    else
        log_info "Removing empty directories in $path..."
        find "$path" -type d -empty -delete 2>/dev/null
        log_success "Empty directories removed."
    fi
}

# --- Secure Deletion Functions ---

secure_delete() {
    local target="$1"

    validate_path "$target" || return 1

    check_dependencies "shred"

    if [ -d "$target" ]; then
        log_error "Target is a directory. secure-delete only works on files."
        log_info "To delete a directory securely, use 'find <dir> -type f -exec shred -u {} +'"
        return 1
    fi

    log_info "Securely deleting file: $target"
    log_info "Overwriting 3 times with random data, then zeroing..."

    # -u: truncate and remove file after shredding
    # -z: add a final overwrite with zeros to hide shredding
    # -n: number of passes (default is 3, but explicit is better)
    if ! shred -v -u -z -n 3 "$target"; then
        log_error "Failed to securely delete $target."
        return 1
    fi

    log_success "File securely deleted."
}

# --- Archive Functions ---

create_archive() {
    local source="$1"
    local archive_name="${2:-$(basename "$source").tar.gz}"

    validate_path "$source" || return 1

    local parent_dir
    parent_dir=$(dirname "$source")
    local base_name
    base_name=$(basename "$source")

    log_info "Creating archive: $archive_name from $source"

    if ! tar -czf "$archive_name" -C "$parent_dir" "$base_name"; then
        log_error "Failed to create archive."
        return 1
    fi

    log_success "Archive created: $archive_name"
    ls -lh "$archive_name"
}

extract_archive() {
    local archive="$1"
    local dest_dir="${2:-.}"

    validate_path "$archive" || return 1

    if [ ! -d "$dest_dir" ]; then
        mkdir -p "$dest_dir"
    fi

    log_info "Extracting $archive to $dest_dir..."

    case "$archive" in
        *.tar.gz|*.tgz)
            tar -xzf "$archive" -C "$dest_dir"
            ;;
        *.tar.bz2|*.tbz2)
            tar -xjf "$archive" -C "$dest_dir"
            ;;
        *.tar.xz|*.txz)
            tar -xJf "$archive" -C "$dest_dir"
            ;;
        *.tar)
            tar -xf "$archive" -C "$dest_dir"
            ;;
        *.zip)
            check_dependencies "unzip"
            unzip -q "$archive" -d "$dest_dir"
            ;;
        *)
            log_error "Unsupported archive format: $archive"
            log_info "Supported: .tar.gz, .tar.bz2, .tar.xz, .tar, .zip"
            return 1
            ;;
    esac

    if [ $? -ne 0 ]; then
        log_error "Failed to extract archive."
        return 1
    fi

    log_success "Archive extracted successfully."
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) File Manager

Usage: $0 <command> [options]

File Operations:
Analysis:
  size <path>                  Show total size of a file or directory
  largest <path> [count]       Show top N largest files (default: 10)
  empty-dirs <path>            Find empty directories

Cleanup:
  clean-empty <path> [--dry-run]  Remove empty directories

Secure Deletion:
  shred <file>                 Securely overwrite and delete a file

Archiving:
  archive <source> [archive.tar.gz]  Create a gzip tarball
  extract <archive> [dest_dir]       Extract tarball or zip to directory

Help:
  help                         Show this help message

Examples:
  $0 size /home/vice
  $0 largest /var/log 5
  $0 clean-empty /tmp
  $0 shred /home/vice/secret.txt
  $0 archive /home/vice/Documents docs_backup.tar.gz
  $0 extract project.tar.gz /opt/projects
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

    check_file_deps

    case "$command" in
        copy|cp)
            local src="${1:-}"
            local dst="${2:-}"
            if [ -z "$src" ] || [ -z "$dst" ]; then
                log_error "Path required."
                exit 1
            fi
            cp -r "$src" "$dst"
            ;;
        size|du)
            local path="${1:-}"
            if [ -z "$path" ]; then
                log_error "Path required."
                exit 1
            fi
            dir_size "$path"
            ;;
        largest|big)
            local path="${1:-}"
            if [ -z "$path" ]; then
                log_error "Path required."
                exit 1
            fi
            local count="${2:-10}"
            largest_files "$path" "$count"
            ;;
        empty-dirs|empty)
            local path="${1:-}"
            if [ -z "$path" ]; then
                log_error "Path required."
                exit 1
            fi
            empty_dirs "$path"
            ;;
        clean-empty|rmdir-empty)
            local path="${1:-}"
            if [ -z "$path" ]; then
                log_error "Path required."
                exit 1
            fi
            local dry_run="${2:-no}"
            clean_empty_dirs "$path" "$dry_run"
            ;;
        shred|secure-delete)
            local target="${1:-}"
            if [ -z "$target" ]; then
                log_error "Target file required."
                exit 1
            fi
            secure_delete "$target"
            ;;
        archive|tar)
            local source="${1:-}"
            if [ -z "$source" ]; then
                log_error "Source path required."
                exit 1
            fi
            local archive_name="${2:-}"
            create_archive "$source" "$archive_name"
            ;;
        extract|untar)
            local archive="${1:-}"
            if [ -z "$archive" ]; then
                log_error "Archive file required."
                exit 1
            fi
            local dest_dir="${2:-.}"
            extract_archive "$archive" "$dest_dir"
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