#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Archive Manager
# Provides creation, extraction, and listing of various archive formats
# (tar.gz, tar.bz2, tar.xz, zip) with automatic format detection.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"
install_cleanup

# --- Helper Functions ---

check_archive_deps() {
    check_dependencies "tar"
    # zip/unzip are checked dynamically when needed
}

validate_path() {
    local path="$1"
    if [ ! -e "$path" ]; then
        log_error "Path '$path' does not exist."
        return 1
    fi
}

# --- Create Function ---

create_archive() {
    local source_path="$1"
    local archive_name="${2:-}"
    local compression="${3:-gz}" # gz, bz2, xz, zip

    validate_path "$source_path" || return 1

    local parent_dir
    parent_dir=$(dirname "$source_path")
    local base_name
    base_name=$(basename "$source_path")

    # Auto-generate archive name if not provided
    if [ -z "$archive_name" ]; then
        case "$compression" in
            gz)  archive_name="${base_name}.tar.gz" ;;
            bz2) archive_name="${base_name}.tar.bz2" ;;
            xz)  archive_name="${base_name}.tar.xz" ;;
            zip) archive_name="${base_name}.zip" ;;
            *)   log_error "Unsupported compression: $compression"; return 1 ;;
        esac
    fi

    log_info "Creating archive: $archive_name from $source_path"

    case "$compression" in
        gz)
            if ! tar -czf "$archive_name" -C "$parent_dir" "$base_name"; then
                log_error "Failed to create gzip tarball."
                return 1
            fi
            ;;
        bz2)
            if ! tar -cjf "$archive_name" -C "$parent_dir" "$base_name"; then
                log_error "Failed to create bzip2 tarball."
                return 1
            fi
            ;;
        xz)
            if ! tar -cJf "$archive_name" -C "$parent_dir" "$base_name"; then
                log_error "Failed to create xz tarball."
                return 1
            fi
            ;;
        zip)
            if ! command -v zip > /dev/null 2>&1; then
                log_error "zip command not found. Install 'zip'."
                return 1
            fi
            # zip requires a different approach: cd to parent, then zip
            if ! (cd "$parent_dir" && zip -r "$OLDPWD/$archive_name" "$base_name" > /dev/null); then
                log_error "Failed to create zip archive."
                return 1
            fi
            ;;
        *)
            log_error "Unsupported compression format: $compression"
            return 1
            ;;
    esac

    log_success "Archive created: $archive_name"
    ls -lh "$archive_name" | awk '{print "Size:", $5}'
}

# --- Extract Function ---

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
            if ! command -v unzip > /dev/null 2>&1; then
                log_error "unzip command not found. Install 'unzip'."
                return 1
            fi
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

    log_success "Archive extracted successfully to: $dest_dir"
}

# --- List Function ---

list_archive() {
    local archive="$1"

    validate_path "$archive" || return 1

    log_info "Contents of $archive:"
    echo "==================================="

    case "$archive" in
        *.tar.gz|*.tgz|*.tar.bz2|*.tbz2|*.tar.xz|*.txz|*.tar)
            tar -tf "$archive"
            ;;
        *.zip)
            if ! command -v unzip > /dev/null 2>&1; then
                log_error "unzip command not found."
                return 1
            fi
            unzip -l "$archive"
            ;;
        *)
            log_error "Unsupported archive format: $archive"
            return 1
            ;;
    esac

    echo "==================================="
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Archive Manager

Usage: $0 <command> [options]

Commands:
  create <source> [archive_name] [compression]
                              Create an archive (compression: gz, bz2, xz, zip; default: gz)
  extract <archive> [dest_dir]
                              Extract archive to directory (default: current dir)
  list <archive>              List contents of an archive
  help                        Show this help message

Supported Formats:
  - .tar.gz / .tgz
  - .tar.bz2 / .tbz2
  - .tar.xz / .txz
  - .tar
  - .zip

Examples:
  $0 create /home/vice/Documents docs_backup.tar.gz gz
  $0 create /etc etc_backup.tar.xz xz
  $0 extract project.tar.gz /opt/projects
  $0 list backup.tar.bz2
HELP
}

# --- Main ---

main() {
    check_archive_deps

    local command="${1:-help}"
    shift || true

    case "$command" in
        create|archive)
            local source="${1:-}"
            if [ -z "$source" ]; then
                log_error "Source path required."
                exit 1
            fi
            local archive_name="${2:-}"
            local compression="${3:-gz}"
            create_archive "$source" "$archive_name" "$compression"
            ;;
        extract|unarchive)
            local archive="${1:-}"
            if [ -z "$archive" ]; then
                log_error "Archive file required."
                exit 1
            fi
            local dest_dir="${2:-.}"
            extract_archive "$archive" "$dest_dir"
            ;;
        list|ls)
            local archive="${1:-}"
            if [ -z "$archive" ]; then
                log_error "Archive file required."
                exit 1
            fi
            list_archive "$archive"
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