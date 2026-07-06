#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) System Info
# Provides a consolidated overview of OS, kernel, uptime, CPU, memory, disk,
# and network interfaces for troubleshooting and diagnostics.
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
        log_error "System info retrieval failed with exit code $exit_code."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Helper Functions ---

print_header() {
    local title="$1"
    echo ""
    echo "=== $title ==="
}

# --- Information Functions ---

show_os_info() {
    print_header "Operating System"
    if [ -f /etc/os-release ]; then
        grep -E "^(NAME|VERSION|PRETTY_NAME|ID|BUILD_ID)=" /etc/os-release | sed 's/=/: /' | sed 's/"//g'
    else
        echo "OS Release file not found."
    fi
}

show_kernel_info() {
    print_header "Kernel"
    echo "Kernel: $(uname -r)"
    echo "Arch: $(uname -m)"
    echo "Hostname: $(uname -n)"
}

show_uptime() {
    print_header "Uptime"
    uptime -p
    echo "Current Time: $(date)"
}

show_cpu_info() {
    print_header "CPU"
    
    if ! command -v lscpu > /dev/null 2>&1; then
        log_warn "lscpu not found. Basic CPU info only."
        echo "Model: $(grep "model name" /proc/cpuinfo | head -n 1 | cut -d: -f2 | xargs)
        echo "Cores: $(nproc 2>/dev/null || echo 'N/A')"
        return 0
    fi
    
    lscpu | grep -E "^(Model name|CPU\(s\)|Thread|Core|Socket|CPU max MHz|Virtualization)"
}

show_memory_info() {
    print_header "Memory"
    if command -v free > /dev/null 2>&1; then
        free -h
    else
        echo "free command not found."
        echo "MemTotal: $(grep MemTotal /proc/meminfo | awk '{print $2 " kB"}')"
    fi
}

show_disk_info() {
    print_header "Disk Usage"
    if command -v df > /dev/null 2>&1; then
        df -h | grep -v "tmpfs\|loop\|udev"
    else
        echo "df command not found."
    fi
}

show_network_info() {
    print_header "Network Interfaces"
    if command -v ip > /dev/null 2>&1; then
        ip -br addr
    else
        echo "ip command not found."
    fi
}

show_gpu_info() {
    print_header "Graphics (GPU)"
    if command -v lspci > /dev/null 2>&1; then
        lspci | grep -i "vga\|3d\|display"
    else
        echo "lspci not found. Cannot determine GPU info."
    fi
}

show_audio_info() {
    print_header "Audio"
    if command -v pactl > /dev/null 2>&1; then
        if pactl info > /dev/null 2>&1; then
            pactl info | grep -E "Server Name|Default Sink|Default Source"
        else
            echo "Audio server (PulseAudio/PipeWire) not running."
        fi
    else
        echo "pactl not found."
    fi
}

show_all() {
    show_os_info
    show_kernel_info
    show_uptime
    show_cpu_info
    show_memory_info
    show_disk_info
    show_network_info
    show_gpu_info
    show_audio_info
    echo ""
    echo "==================================="
    echo "    System Info Retrieval Complete   "
    echo "==================================="
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) System Info

Usage: $0 <command>

Commands:
  all            Show all system information (default)
  os             Show operating system info
  kernel         Show kernel and architecture info
  uptime         Show system uptime and time
  cpu            Show CPU information
  memory         Show memory (RAM/Swap) usage
  disk           Show disk space usage
  network        Show network interfaces and IPs
  gpu            Show graphics controller info
  audio          Show audio server info
  help           Show this help message

Examples:
  $0 all
  $0 cpu
  $0 network
HELP
}

# --- Main ---

main() {
    local command="${1:-all}"
    shift || true
    
    case "$command" in
        all)
            show_all
            ;;
        os)
            show_os_info
            ;;
        kernel)
            show_kernel_info
            ;;
        uptime)
            show_uptime
            ;;
        cpu)
            show_cpu_info
            ;;
        memory|ram)
            show_memory_info
            ;;
        disk|storage)
            show_disk_info
            ;;
        network|net)
            show_network_info
            ;;
        gpu|graphics)
            show_gpu_info
            ;;
        audio|sound)
            show_audio_info
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