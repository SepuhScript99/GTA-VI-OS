#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Kernel Manager
# Provides utilities for kernel listing, safe old-kernel removal, initramfs
# regeneration, and kernel module management.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"
install_cleanup

# --- Helper Functions ---

check_kernel_deps() {
    check_dependencies "uname" "dpkg" "update-initramfs"
}

# --- Information Functions ---

show_running_kernel() {
    log_info "Running Kernel:"
    echo "==================================="
    echo "Version: $(uname -r)"
    echo "Arch: $(uname -m)"
    echo "==================================="
}

list_installed_kernels() {
    log_info "Installed Kernels:"
    echo "==================================="

    local running_kernel
    running_kernel=$(uname -r)

    dpkg -l | grep 'linux-image-[0-9]' | awk '{print $2, $3}' | while read -r pkg ver; do
        # Extract version from package name (e.g., linux-image-6.1.0-13-amd64 -> 6.1.0-13-amd64)
        local ver_name="${pkg#linux-image-}"

        if [ "$ver_name" == "$running_kernel" ]; then
            echo "  [Running] $ver_name"
        else
            echo "  [Old]    $ver_name"
        fi
    done

    echo "==================================="
}

show_cmdline() {
    log_info "Kernel Boot Parameters:"
    echo "==================================="
    cat /proc/cmdline
    echo ""
    echo "==================================="
}

# --- Maintenance Functions ---

update_initramfs() {
    local kernel="${1:-all}"

    log_info "Updating initramfs for kernel: $kernel..."

    if [ "$kernel" == "all" ]; then
        if ! update-initramfs -u -k all; then
            log_error "Failed to update initramfs for all kernels."
            return 1
        fi
    else
        if ! update-initramfs -u -k "$kernel"; then
            log_error "Failed to update initramfs for kernel $kernel."
            return 1
        fi
    fi

    log_success "Initramfs updated successfully."
}

remove_old_kernels() {
    log_info "Checking for old kernels to remove..."

    local running_kernel
    running_kernel=$(uname -r)

    # Find installed linux-image packages excluding the running one
    local old_kernels=()
    while IFS= read -r pkg; do
        local ver="${pkg#linux-image-}"
        if [ "$ver" != "$running_kernel" ]; then
            old_kernels+=("$pkg")
        fi
    done < <(dpkg -l | grep '^ii' | grep 'linux-image-[0-9]' | awk '{print $2}')

    if [ ${#old_kernels[@]} -eq 0 ]; then
        log_info "No old kernels found to remove."
        return 0
    fi

    log_info "Found old kernels:"
    for pkg in "${old_kernels[@]}"; do
        echo "  - $pkg"
    done
    echo ""

    read -p "Remove these old kernels? (y/N): " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        log_info "Aborted."
        return 1
    fi

    log_info "Removing old kernels..."

    # Add --no-install-recommends to prevent pulling in new packages
    if ! apt-get purge -y --no-install-recommends "${old_kernels[@]}"; then
        log_error "Failed to remove some old kernels."
        log_warn "You may need to manually run 'apt --fix-broken install'."
        return 1
    fi

    log_success "Old kernels removed successfully."

    # Optionally run autoremove to clean up dependencies
    log_info "Cleaning up unused dependencies..."
    apt-get autoremove -y --no-install-recommends || log_warn "Autoremove completed with warnings."
}

# --- Module Management Functions ---

list_modules() {
    log_info "Loaded Kernel Modules:"
    echo "==================================="
    lsmod
    echo "==================================="
}

load_module() {
    local module="$1"

    if [ -z "$module" ]; then
        log_error "Module name required."
        return 1
    fi

    log_info "Loading kernel module: $module..."

    if ! modprobe "$module"; then
        log_error "Failed to load module '$module'."
        log_info "Check if the module exists or if dependencies are missing."
        return 1
    fi

    log_success "Module '$module' loaded."
}

unload_module() {
    local module="$1"

    if [ -z "$module" ]; then
        log_error "Module name required."
        return 1
    fi

    log_info "Unloading kernel module: $module..."

    if ! modprobe -r "$module"; then
        log_error "Failed to unload module '$module'."
        log_info "The module might be in use by the system."
        return 1
    fi

    log_success "Module '$module' unloaded."
}

module_info() {
    local module="$1"

    if [ -z "$module" ]; then
        log_error "Module name required."
        return 1
    fi

    log_info "Information for module: $module"
    echo "==================================="

    if ! modinfo "$module"; then
        log_error "Module '$module' not found."
        return 1
    fi

    echo "==================================="
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Kernel Manager

Usage: $0 <command> [options]

Information:
  running                     Show currently running kernel version
  list                        List all installed kernels
  cmdline                     Show kernel boot parameters

Maintenance:
  update-initramfs [kernel]  Update initramfs (default: all)
  remove-old                  Remove old, non-running kernels (frees disk space)

Module Management:
  list-modules                List loaded kernel modules
  load <module>               Load a kernel module
  unload <module>             Unload a kernel module
  modinfo <module>            Show information about a module

Help:
  help                        Show this help message

Examples:
  $0 list
  $0 update-initramfs
  $0 update-initramfs 6.1.0-13-amd64
  $0 remove-old
  $0 load vfat
  $0 unload vfat
HELP
}

# --- Main ---

main() {
    check_kernel_deps

    local command="${1:-help}"
    shift || true

    case "$command" in
        running|current)
            show_running_kernel
            ;;
        list|installed)
            list_installed_kernels
            ;;
        cmdline|params)
            show_cmdline
            ;;
        update-initramfs|initramfs)
            local kernel="${1:-all}"
            update_initramfs "$kernel"
            ;;
        remove-old|purge-old)
            remove_old_kernels
            ;;
        list-modules|modules|lsmod)
            list_modules
            ;;
        load|modprobe)
            local module="${1:-}"
            if [ -z "$module" ]; then
                log_error "Module name required."
                exit 1
            fi
            load_module "$module"
            ;;
        unload|rmmod)
            local module="${1:-}"
            if [ -z "$module" ]; then
                log_error "Module name required."
                exit 1
            fi
            unload_module "$module"
            ;;
        modinfo|info)
            local module="${1:-}"
            if [ -z "$module" ]; then
                log_error "Module name required."
                exit 1
            fi
            module_info "$module"
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