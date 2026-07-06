#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) System Monitor
# Provides real-time monitoring of CPU, memory, disk, network, and temperature.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Source Shared Library ---
if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found. Cannot continue." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

# --- Configuration ---
REFRESH_INTERVAL="${1:-2}"
HISTORY_SIZE=60

# --- Cleanup Function ---
cleanup() {
    # Restore cursor and screen
    tput cnorm
    tput rmcup
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

# --- Helper Functions ---

check_monitor_deps() {
    check_dependencies "cat" "awk" "grep" "free" "df"
}

init_display() {
    # Save screen and hide cursor
    tput smcup
    tput civis
}

# --- Metric Collection Functions ---

get_cpu_usage() {
    # Calculate CPU usage percentage
    local idle
    idle=$(awk '/^cpu /{print $5}' /proc/stat)
    local total
    total=$(awk '/^cpu /{print $2+$3+$4+$5+$6+$7+$8}
    total=$((total - idle))
    
    if [ "$total" -eq 0 ]; then
        echo "0.0"
    else
        awk "BEGIN {printf \"%.1f\", 100 - ($idle / $total) * 100}"
    fi
}

get_memory_usage() {
    local total used pct
    total=$(awk '/MemTotal/{print $2}' /proc/meminfo)
    local available
    available=$(awk '/MemAvailable/{print $2}' /proc/meminfo)
    used=$((total - available))
    pct=$(awk "BEGIN {printf \"%.1f\", ($used / $total) * 100}")
    
    local used_gb total_gb
    used_gb=$(awk "BEGIN {printf \"%.2f\", $used / 1048576}")
    total_gb=$(awk "BEGIN {printf \"%.2f\", $total / 1048576}")
    
    echo "${pct}% (${used_gb}GB / ${total_gb}GB)"
}

get_disk_usage() {
    local root_info
    root_info=$(df -h / 2>/dev/null | awk 'NR==2{print $5, $2, $4}')
    local pct total avail
    pct=$(echo "$root_info" | awk '{print $1}')
    total=$(echo "$root_info" | awk '{print $2}')
    avail=$(echo "$root_info" | awk '{print $3}')
    echo "${pct} used (${avail} free)"
}

get_network_throughput() {
    local rx_bytes tx_bytes
    local main_iface
    main_iface=$(ip -o route get 1.1.1.1 2>/dev/null | awk '{print $5}' | head -n1)
    
    if [ -z "$main_iface" ]; then
        echo "N/A"
        return 0
    fi
    
    rx_bytes=$(cat "/sys/class/net/$main_iface/statistics/rx_bytes" 2>/dev/null || echo "0")
    tx_bytes=$(cat "/sys/class/net/$main_iface/statistics/tx_bytes" 2>/dev/null || echo "0")
    
    local rx_mb tx_mb
    rx_mb=$(awk "BEGIN {printf \"%.2f\", $rx_bytes / 1048576}")
    tx_mb=$(awk "BEGIN {printf \"%.2f\", $rx_bytes / 1048576}")
    
    echo "RX: ${rx_mb}MB  TX: ${tx_mb}MB ($main_iface)"
}

get_top_processes() {
    local count="${1:-5}"
    ps aux --sort=-%cpu | head -n $((count + 1)) | tail -n "$count" | awk '{printf "  %-8s %5s%% CPU  %s\n", $1, $3, $11}'
}

get_temperatures() {
    if ! command -v sensors > /dev/null 2>&1; then
        echo "  (lm-sensors not installed)"
        return 0
    fi
    
    local temps
    temps=$(sensors 2>/dev/null | grep -E "Core|Package|temp1" | head -n 5)
    
    if [ -z "$temps" ]; then
        echo "  (No thermal data)"
    else
        echo "$temps" | sed 's/^/  /'
    fi
}

# --- Display Functions ---

draw_dashboard() {
    local cpu mem disk net
    cpu=$(get_cpu_usage)
    mem=$(get_memory_usage)
    disk=$(get_disk_usage)
    net=$(get_network_throughput)
    
    # Clear screen
    clear
    
    echo -e "\033[1;36m==========================================="
    echo -e "   GTA VI OS - System Monitor"
    echo -e "===========================================\033[0m"
    echo ""
    echo -e "\033[1;33mSystem Resources:\033[0m"
    
    # CPU usage with bar
    local cpu_int=${cpu%.*}
    local cpu_bar=""
    local i=0
    while [ "$i" -lt 20 ]; do
        if [ "$i" -lt $((cpu_int / 5)); then
            cpu_bar="${cpu_bar}█"
        else
            cpu_bar="${cpu_bar} "
        fi
        i=$((i + 1))
    done
    printf "  CPU:  [${cpu_bar}] ${cpu}%%\n"
    
    # Memory usage with bar
    local mem_int=${mem%%%*}
    local mem_bar=""
    i=0
    while [ "$i" -lt 20 ]; do
        if [ "$i" -lt $((mem_int / 5))]; then
            mem_bar="${mem_bar}█"
        else
            mem_bar="${mem_bar} "
        fi
        i=$((i + 1))
    done
    printf "  RAM:  [${mem_bar}] ${mem}\n"
    
    echo ""
    echo -e "\033[1;33mStorage & Network:\033[0m"
    printf "  Disk: %s\n" "$disk"
    printf "  Net:  %s\n" "$net"
    
    echo ""
    echo -e "\033[1;33mTop Processes (by CPU):\033[0m"
    get_top_processes 5
    
    echo ""
    echo -e "\033[1;33mTemperatures:\033[0m"
    get_temperatures
    
    echo ""
    echo -e "\033[1;36m===========================================\033[0m"
    echo "Refresh: ${REFRESH_INTERVAL}s | Press Ctrl+C to exit"
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) System Monitor

Usage: $0 [interval]

Arguments:
  interval                   Refresh interval in seconds (default: 2)

Examples:
  $0 1
  $0 5
HELP
}

# --- Main ---

main() {
    check_monitor_deps
    
    # Handle help flag
    if [ "${1:-}" == "help" ] || [ "${1:-}" == "--help" ] || [ "${1:-}" == "-h" ]; then
        show_help
        exit 0
    fi
    
    # Validate interval
    if ! [[ "$REFRESH_INTERVAL" =~ ^[0-9]+$ ]] || [ "$REFRESH_INTERVAL" -lt 1 ]; then
        log_error "Interval must be a positive number."
        exit 1
    fi
    
    init_display
    
    while true; do
        draw_dashboard
        sleep "$REFRESH_INTERVAL"
    done
}

main "$@"