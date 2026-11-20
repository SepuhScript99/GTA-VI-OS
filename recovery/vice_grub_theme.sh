#!/bin/bash
# ============================================================================
# Vice OS — GRUB Theme Installer
# Installs a cyberpunk-themed GRUB boot menu with Vice OS branding.
# Must be run as root.
# ============================================================================
set -Eeuo pipefail

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"

THEME_NAME="vice-cyberpunk"
GRUB_THEME_DIR="/boot/grub/themes/$THEME_NAME"
LOCKFILE="/var/lock/vice-grub-theme.lock"
LOCKED=0

cleanup() {
    local exit_code=$?
    if [ "${LOCKED:-0}" -eq 1 ]; then
        flock -u 9 2>/dev/null || true
        exec 9>&- 2>/dev/null || true
        rm -f "$LOCKFILE" 2>/dev/null || true
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

main() {
    local do_activate=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --version)
                echo "Vice OS GRUB Theme Installer v1.1"
                exit 0
                ;;
            --help|-h)
                echo "Vice OS GRUB Theme Installer"
                echo "Usage: sudo $0 [--install]"
                echo "  --install, -i   Install theme files and activate immediately in /etc/default/grub"
                exit 0
                ;;
            --install|-i)
                do_activate=true
                shift
                ;;
            *)
                shift
                ;;
        esac
    done

    check_root

    mkdir -p /var/lock 2>/dev/null || true
    exec 9>"$LOCKFILE"
    if ! flock -n 9; then
        log_error "Another GRUB theme operation is already running. Exiting."
        exit 1
    fi
    LOCKED=1

    log_info "============================================================"
    log_info "  Vice OS — GRUB Theme Installer"
    log_info "============================================================"

    # --- 1. Create theme directory ---
    mkdir -p "$GRUB_THEME_DIR/background"

    # --- 2. Generate boot background using ImageMagick or ffmpeg ---
    log_info "Generating boot background..."
    local convert_cmd=""
    if command -v magick >/dev/null 2>&1; then
        convert_cmd="magick"
    elif command -v convert >/dev/null 2>&1; then
        convert_cmd="convert"
    fi

    if [ -n "$convert_cmd" ]; then
        $convert_cmd -size 1920x1080 xc:"#0a0a0a" \
            -fill "#00ffff" -font "DejaVu-Sans-Mono-Bold" -pointsize 72 \
            -gravity center -annotate +0-200 "VICE OS" \
            -fill "#ff00ff" -font "DejaVu-Sans-Mono" -pointsize 32 \
            -gravity center -annotate +0-120 "GTA VI EDITION" \
            -fill "#555555" -pointsize 18 \
            -gravity south -annotate +0+60 "http://vice-os.dev" \
            -fill "#333333" -strokewidth 1 -stroke "#00ffff" \
            -draw "line 0,530 1920,530" \
            -draw "line 0,550 1920,550" \
            -fill "#00ffff" -font "DejaVu-Sans-Mono" -pointsize 20 \
            -gravity center -annotate +0+80 "Select boot entry  |  Use arrow keys to navigate" \
            "$GRUB_THEME_DIR/background/background.png" 2>/dev/null || log_warn "ImageMagick render warning, checking fallback"
    fi

    # Fallback if background wasn't created
    if [ ! -f "$GRUB_THEME_DIR/background/background.png" ]; then
        if command -v ffmpeg >/dev/null 2>&1; then
            ffmpeg -f lavfi -i "color=c=0x0a0a0a:s=1920x1080:d=0.1,format=rgba" \
                -frames:v 1 "$GRUB_THEME_DIR/background/background.png" -y 2>/dev/null || true
        fi
    fi

    # --- 3. Create GRUB theme.txt ---
    log_info "Creating theme configuration..."
    cat > "$GRUB_THEME_DIR/theme.txt" <<'THEME'
# Vice OS — Cyberpunk GRUB Theme
# Boot menu color scheme: cyan/magenta on dark background

title-text: "VICE OS"
title-font: "DejaVu Sans Mono Bold 20"
title-color: "#ff00ff"

message-font: "DejaVu Sans Mono 14"
message-color: "#00ffff"
message-bg-color: "#0a0a0a"

desktop-image: "background/background.png"
desktop-color: "#0a0a0a"

# Terminal font and colors
terminal-font: "DejaVu Sans Mono 14"
terminal-color: "#00ffff"

# Boot menu layout
+ boot_menu {
    left = 25%
    top = 35%
    width = 50%
    height = 35%
    item_font: "DejaVu Sans Mono 14"
    item_color: "#00ffff"
    selected_item_font: "DejaVu Sans Mono Bold 16"
    selected_item_color: "#0a0a0a"
    selected_item_bg_color: "#00ffff"
    selected_item_highlight_color: "#ff00ff"
    menu_pixmap_style = "menu"
    menu_rectangle = true
    menu_height = 36
    menu_width = 500
    menu_spacing = 4
    item_spacing = 2
    title_margin = 12
    item_margin = 8
    item_padding = 12 4
    scrollbar = false
}

# Boot entries
+ label {
    top = 92%
    left = 50%
    align = "center"
    text = "Use ↑/↓ to select  |  Enter to boot  |  'e' to edit  |  'c' for GRUB command line"
    font = "DejaVu Sans Mono 12"
    color = "#555555"
}
THEME

    # --- 4. Create progress bar style ---
    cat > "$GRUB_THEME_DIR/progress.txt" <<'PROGRESS'
# Progress bar for GRUB theme
+ progress_bar {
    left = 30%
    top = 72%
    width = 40%
    height = 3
    bg_color = "#1a1a1a"
    fg_color = "#00ffff"
    highlight_color = "#ff00ff"
    text_color = "#00ffff"
    font = "DejaVu Sans Mono 10"
    text = "Loading %d%%"
}
PROGRESS

    # --- 5. Create install script ---
    cat > "$GRUB_THEME_DIR/install.sh" <<'INSTALL'
#!/bin/bash
# One-time GRUB theme installer for Vice OS
set -euo pipefail
THEME_NAME="vice-cyberpunk"
GRUB_CFG="/etc/default/grub"

if [ ! -d "/boot/grub/themes/$THEME_NAME" ]; then
    echo "[ERROR] Theme not found at /boot/grub/themes/$THEME_NAME"
    exit 1
fi

if [ -f "$GRUB_CFG" ]; then
    # Backup original GRUB config
    cp "$GRUB_CFG" "$GRUB_CFG.bak.$(date +%s)" 2>/dev/null || true

    # Set theme in GRUB config
    if grep -q "^GRUB_THEME=" "$GRUB_CFG"; then
        sed -i "s|^GRUB_THEME=.*|GRUB_THEME=/boot/grub/themes/$THEME_NAME/theme.txt|" "$GRUB_CFG"
    else
        echo "GRUB_THEME=/boot/grub/themes/$THEME_NAME/theme.txt" >> "$GRUB_CFG"
    fi

    # Also set timeout if not present
    if ! grep -q "^GRUB_TIMEOUT=" "$GRUB_CFG"; then
        echo "GRUB_TIMEOUT=5" >> "$GRUB_CFG"
    fi
fi

# Update GRUB
echo "[*] Updating GRUB..."
if command -v update-grub >/dev/null 2>&1; then
    update-grub 2>/dev/null || true
elif command -v grub-mkconfig >/dev/null 2>&1; then
    grub-mkconfig -o /boot/grub/grub.cfg 2>/dev/null || true
fi

echo "[+] Vice OS GRUB theme activated!"
INSTALL
    chmod +x "$GRUB_THEME_DIR/install.sh"

    if [ "$do_activate" = true ]; then
        log_info "Activating GRUB theme..."
        bash "$GRUB_THEME_DIR/install.sh"
        log_success "Vice OS Cyberpunk GRUB theme installed and activated!"
    else
        log_success "Vice OS Cyberpunk GRUB theme files installed to $GRUB_THEME_DIR."
        log_info "To activate manually, run: sudo bash $GRUB_THEME_DIR/install.sh"
    fi
}

main "$@"
