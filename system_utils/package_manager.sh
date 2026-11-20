#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Package Manager
# Provides safe package installation, removal, searching, listing, and
# repository management with built-in lock handling and logging.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"
install_cleanup

# --- Configuration ---
APT_CMD="apt-get"
DPKG_CMD="dpkg"
LOCK_TIMEOUT=60
LOG_FILE="/var/log/vice-os-package-manager.log"

# --- Helper Functions ---

check_package_deps() {
    check_dependencies "apt-get" "dpkg"
}

# APT options for safe, non-interactive operations
get_apt_opts() {
    echo "-o" "Acquire::Retries=3"
    echo "-o" "Dpkg::Lock::Timeout=${LOCK_TIMEOUT}"
    echo "-o" "Dpkg::Options::=--force-confold"
    echo "-o" "Dpkg::Options::=--force-confdef"
    echo "-y"
    echo "--no-install-recommends"
}

# --- Update Functions ---

update_package_lists() {
    log_info "Updating package lists..."

    local apt_opts
    apt_opts=$(get_apt_opts | tr '\n' ' ')

    if ! $APT_CMD $apt_opts update; then
        log_error "Failed to update package lists."
        log_info "Check your network connection and repository configuration."
        return 1
    fi

    log_success "Package lists updated successfully."
}

upgrade_packages() {
    log_info "Upgrading installed packages..."

    local apt_opts
    apt_opts=$(get_apt_opts | tr '\n' ' ')

    if ! $APT_CMD $apt_opts upgrade; then
        log_error "Failed to upgrade packages."
        log_info "Check network connection, held packages, or disk space."
        log_info "Try: sudo apt-get upgrade"
        return 1
    fi

    log_success "Package upgrade completed successfully."
}

full_update() {
    log_info "Performing full system update (update + upgrade + autoremove)..."

    update_package_lists || return 1
    upgrade_packages || return 1

    log_info "Cleaning up unused packages..."
    local apt_opts
    apt_opts=$(get_apt_opts | tr '\n' ' ')
    $APT_CMD $apt_opts autoremove || log_warn "Autoremove completed with warnings."

    log_success "Full system update completed."
}

# --- Install/Remove Functions ---

install_packages() {
    local packages=("$@")

    if [ ${#packages[@]} -eq 0 ]; then
        log_error "No packages specified for installation."
        return 1
    fi

    log_info "Installing package(s): ${packages[*]}"

    local apt_opts
    apt_opts=$(get_apt_opts | tr '\n' ' ')

    if ! $APT_CMD $apt_opts install "${packages[@]}"; then
        log_error "Failed to install package(s): ${packages[*]}"
        log_info "Check that the package names are correct and repositories are up to date."
        log_info "Try: sudo apt-get update && sudo apt-get install ${packages[*]}"
        return 1
    fi

    log_success "Package(s) installed successfully: ${packages[*]}"
}

remove_packages() {
    local packages=("$@")
    local purge="${PURGE:-no}"

    if [ ${#packages[@]} -eq 0 ]; then
        log_error "No packages specified for removal."
        return 1
    fi

    log_info "Removing package(s): ${packages[*]}"

    local apt_opts
    apt_opts=$(get_apt_opts | tr '\n' ' ')

    local action="remove"
    if [ "$purge" == "yes" ]; then
        action="purge"
        log_info "Purging configuration files as well."
    fi

    if ! $APT_CMD $apt_opts $action "${packages[@]}"; then
        log_error "Failed to remove package(s): ${packages[*]}"
        log_info "The package may be a dependency of another package."
        log_info "Try: sudo apt-get remove ${packages[*]}"
        return 1
    fi

    log_success "Package(s) removed successfully: ${packages[*]}"
}

purge_packages() {
    PURGE=yes
    remove_packages "$@"
}

# --- Search Functions ---

search_packages() {
    local query="$1"

    if [ -z "$query" ]; then
        log_error "Search query required."
        return 1
    fi

    log_info "Searching for packages matching: $query"
    echo "==================================="

    # Use apt-cache for searching (doesn't require root)
    apt-cache search "$query" | sort

    echo "==================================="
}

show_package_info() {
    local package="$1"

    if [ -z "$package" ]; then
        log_error "Package name required."
        return 1
    fi

    log_info "Package Information: $package"
    echo "==================================="

    apt-cache show "$package" 2>/dev/null | head -n 30

    if [ $? -ne 0 ]; then
        log_error "Package '$package' not found."
        return 1
    fi

    echo "==================================="
}

# --- Listing Functions ---

list_installed() {
    log_info "Installed Packages (count: $($DPKG_CMD -l | grep -c '^ii') ):"
    echo "==================================="
    $DPKG_CMD -l | grep '^ii' | awk '{printf "  %-30s %s\n", $2, $3}'
    echo "==================================="
}

list_upgradable() {
    log_info "Checking for upgradable packages..."

    # Update lists first to get accurate results
    $APT_CMD -qq update > /dev/null 2>&1 || true

    local upgradable
    upgradable=$($APT_CMD -qq list --upgradable 2>/dev/null | grep -v "Listing")

    if [ -z "$upgradable" ]; then
        log_info "All packages are up to date."
        return 0
    fi

    log_info "Upgradable Packages:"
    echo "==================================="
    echo "$upgradable"
    echo "==================================="
}

list_recently_installed() {
    local count="${1:-20}"

    log_info "Recently Installed Packages (last $count):"
    echo "==================================="
    grep " install " /var/log/dpkg.log 2>/dev/null | tail -n "$count" | awk '{print $4}'
    echo "==================================="
}

# --- Repository Functions ---

list_repositories() {
    log_info "Configured APT Repositories:"
    echo "==================================="

    # Show main sources.list
    if [ -f /etc/apt/sources.list ]; then
        echo "--- /etc/apt/sources.list ---"
        grep -v "^#" /etc/apt/sources.list | grep -v "^$"
    fi

    # Show sources.list.d
    for file in /etc/apt/sources.list.d/*.list; do
        if [ -f "$file" ]; then
            echo "--- $(basename "$file") ---"
            grep -v "^#" "$file" | grep -v "^$"
        fi
    done

    echo "==================================="
}

add_repository() {
    local repo_line="$1"
    local name="${2:-custom}"

    if [ -z "$repo_line" ]; then
        log_error "Repository line required."
        log_info "Example: deb http://deb.debian.org/debian bookworm main"
        return 1
    fi

    local repo_file="/etc/apt/sources.list.d/${name}.list"

    if [ -f "$repo_file" ]; then
        log_warn "Repository file '$repo_file' already exists."
        read -p "Overwrite? (y/N): " confirm
        if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
            log_info "Aborted."
            return 1
        fi
    fi

    log_info "Adding repository to $repo_file..."
    echo "$repo_line" > "$repo_file"

    log_success "Repository added."
    log_info "Run '$0 update' to refresh package lists."
}

remove_repository() {
    local name="$1"

    if [ -z "$name" ]; then
        log_error "Repository name required."
        return 1
    fi

    local repo_file="/etc/apt/sources.list.d/${name}.list"

    if [ ! -f "$repo_file" ]; then
        log_error "Repository file '$repo_file' not found."
        return 1
    fi

    log_info "Removing repository: $repo_file"
    rm -f "$repo_file"
    log_success "Repository removed."
    log_info "Run '$0 update' to refresh package lists."
}

# --- Cache Functions ---

clean_cache() {
    log_info "Cleaning APT cache..."

    local apt_opts
    apt_opts=$(get_apt_opts | tr '\n' ' ')

    $APT_CMD $apt_opts clean
    $APT_CMD $apt_opts autoremove

    log_success "APT cache cleaned."
}

# --- Dependency Functions ---

check_dependencies() {
    local package="$1"

    if [ -z "$package" ]; then
        log_error "Package name required."
        return 1
    fi

    log_info "Checking dependencies for: $package"
    echo "==================================="
    apt-cache depends "$package" 2>/dev/null || log_error "Package '$package' not found."
    echo "==================================="
}

show_reverse_dependencies() {
    local package="$1"

    if [ -z "$package" ]; then
        log_error "Package name required."
        return 1
    fi

    log_info "Packages that depend on: $package"
    echo "==================================="
    apt-cache rdepends "$package" 2>/dev/null || log_error "Package '$package' not found."
    echo "==================================="
}

# --- Download Functions ---

download_package() {
    local package="$1"
    local target_dir="${2:-.}"

    if [ -z "$package" ]; then
        log_error "Package name required."
        return 1
    fi

    log_info "Downloading package: $package to $target_dir"

    cd "$target_dir"

    if ! apt-get download "$package"; then
        log_error "Failed to download package '$package'."
        return 1
    fi

    log_success "Package downloaded to: $(pwd)/${package}_*.deb"
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Package Manager

Usage: $0 <command> [options]

Update:
  update                       Update package lists
  upgrade                      Upgrade installed packages
  full-update                  Update + upgrade + autoremove

Install/Remove:
  install <pkg1> [pkg2...]     Install package(s)
  remove <pkg1> [pkg2...]      Remove package(s)
  purge <pkg1> [pkg2...]       Remove package(s) and config files

Search:
  search <query>               Search for packages
  info <package>               Show package information
  depends <package>            Show package dependencies
  rdepends <package>           Show reverse dependencies

Listing:
  list-installed               List all installed packages
  list-upgradable              List upgradable packages
  list-recent [count]          List recently installed packages (default: 20)

Repositories:
  list-repos                   List configured repositories
  add-repo <line> [name]       Add a repository
  remove-repo <name>           Remove a repository

Cache:
  clean                        Clean APT cache and autoremove

Download:
  download <package> [dir]     Download .deb file without installing

Help:
  help                         Show this help message

Examples:
  $0 install firefox-esr vlc
  $0 remove firefox-esr
  $0 search "text editor"
  $0 info firefox-esr
  $0 list-upgradable
  $0 add-repo "deb http://deb.debian.org/debian bookworm main" custom
HELP
}

# --- Main ---

main() {
    check_package_deps

    local command="${1:-help}"
    shift || true

    case "$command" in
        update)
            update_package_lists
            ;;
        upgrade)
            upgrade_packages
            ;;
        full-update)
            full_update
            ;;
        install)
            if [ $# -eq 0 ]; then
                log_error "Package name(s) required."
                exit 1
            fi
            install_packages "$@"
            ;;
        remove|uninstall)
            if [ $# -eq 0 ]; then
                log_error "Package name(s) required."
                exit 1
            fi
            remove_packages "$@"
            ;;
        purge)
            if [ $# -eq 0 ]; then
                log_error "Package name(s) required."
                exit 1
            fi
            purge_packages "$@"
            ;;
        search)
            local query="${1:-}"
            if [ -z "$query" ]; then
                log_error "Search query required."
                exit 1
            fi
            search_packages "$query"
            ;;
        info|show)
            local package="${1:-}"
            if [ -z "$package" ]; then
                log_error "Package name required."
                exit 1
            fi
            show_package_info "$package"
            ;;
        list-installed|installed)
            list_installed
            ;;
        list-upgradable|upgradable)
            list_upgradable
            ;;
        list-recent|recent)
            local count="${1:-20}"
            list_recently_installed "$count"
            ;;
        list-repos|repos)
            list_repositories
            ;;
        add-repo)
            local repo_line="${1:-}"
            local name="${2:-custom}"
            if [ -z "$repo_line" ]; then
                log_error "Repository line required."
                exit 1
            fi
            add_repository "$repo_line" "$name"
            ;;
        remove-repo)
            local name="${1:-}"
            if [ -z "$name" ]; then
                log_error "Repository name required."
                exit 1
            fi
            remove_repository "$name"
            ;;
        clean|clean-cache)
            clean_cache
            ;;
        depends)
            local package="${1:-}"
            if [ -z "$package" ]; then
                log_error "Package name required."
                exit 1
            fi
            check_dependencies "$package"
            ;;
        rdepends)
            local package="${1:-}"
            if [ -z "$package" ]; then
                log_error "Package name required."
                exit 1
            fi
            show_reverse_dependencies "$package"
            ;;
        download)
            local package="${1:-}"
            local dir="${2:-.}"
            if [ -z "$package" ]; then
                log_error "Package name required."
                exit 1
            fi
            download_package "$package" "$dir"
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