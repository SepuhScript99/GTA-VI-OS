#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Interactive Settings Menu
# Provides a text-based UI to launch system configuration and recovery tools.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Source Shared Library ---
if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found. Cannot continue." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

# Ensure the script is running as root
if [ "$EUID" -ne 0 ]; then
    log_warn "This menu requires root privileges. Re-running with sudo..."
    exec sudo "$0" "$@"
fi

# --- Trap for Terminal Sanity ---
# If the user presses Ctrl+C, restore terminal state before exiting
trap 'echo ""; log_warn "Menu interrupted. Exiting."; stty sane; exit 1' SIGINT SIGTERM

# --- Helper Functions ---
pause() {
    read -r -p "Press [Enter] key to continue..."
}

# Helper function to run tools safely without crashing the menu on failure
run_tool() {
    local script_path="$1"
    local script_name
    script_name=$(basename "$script_path")
    
    log_info "Executing: $script_name"
    # We use 'if bash ...; then' to prevent 'set -e' from exiting the menu
    # if the sub-script returns a non-zero (failure) exit code.
    if bash "$script_path"; then
        log_success "$script_name completed successfully."
    else
        local exit_code=$?
        log_error "$script_name exited with error code $exit_code."
    fi
    pause
}

show_status() {
    clear
    echo "==================================="
    echo "      GTA VI OS (Vice OS)          "
    echo "          System Status            "
    echo "==================================="
    echo -e "OS: $(cat /etc/os-release | grep PRETTY_NAME | cut -d'"' -f2)"
    echo -e "Kernel: $(uname -r)"
    echo -e "Uptime: $(uptime -p | sed 's/up //')"
    echo -e "CPU Load: $(awk '{print $1*100"%"}' /proc/loadavg)"
    echo -e "Memory: $(free -h | awk '/Mem:/ {print $3 " / " $2}')"
    echo -e "Disk Usage (/): $(df -h / | awk 'NR==2 {print $3 " / " $2 " (" $5 ")"}')"
    echo "==================================="
    pause
}

show_menu() {
    clear
    echo "==================================="
    echo "      GTA VI OS (Vice OS)          "
    echo "          Settings Menu            "
    echo "==================================="
    echo "1. Install Vice OS to Disk"
    echo "2. Install Visual Studio Code"
    echo "3. Install Docker Engine"
    echo "4. Backup Home Directory"
    echo "5. Manual System Update"
    echo "-----------------------------------"
    echo "6. Reset Network Configuration"
    echo "7. Reset User Password"
    echo "8. Reinstall GRUB Bootloader"
    echo "-----------------------------------"
    echo "9. Clean System Logs"
    echo "10. Repair Broken Packages"
    echo "-----------------------------------"
    echo "11. View System Status"
    echo "12. Exit"
    echo "==================================="
}

# --- Main Loop ---
main() {
    check_root
    while true; do
        show_menu
        read -r -p "Enter your choice [1-12]: " choice
        
        case $choice in
            1) run_tool "$WORKDIR/apps/vp-installer.sh" ;;
            2) run_tool "$WORKDIR/apps/vp-code.sh" ;;
            3) run_tool "$WORKDIR/apps/vp-docker.sh" ;;
            4) run_tool "$WORKDIR/system_scripts/backup_home.sh" ;;
            5) run_tool "$WORKDIR/system_scripts/vp-autoupdate.sh" ;;
            6) run_tool "$WORKDIR/recovery/reset_network.sh" ;;
            7) run_tool "$WORKDIR/recovery/reset_password.sh" ;;
            8) run_tool "$WORKDIR/recovery/rebuild_grub.sh" ;;
            9) run_tool "$WORKDIR/system_scripts/clean_logs.sh" ;;
            10) run_tool "$WORKDIR/system_scripts/repair_packages.sh" ;;
            11) show_status ;;
            12)
                log_info "Exiting Settings Menu..."
                break
                ;;
            *)
                log_error "Invalid option. Please choose a number between 1 and 12."
                pause
                ;;
        esac
    done
}

main "$@"