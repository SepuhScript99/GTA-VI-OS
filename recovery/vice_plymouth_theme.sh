#!/bin/bash
# ============================================================================
# Vice OS — Plymouth Boot Splash Theme Installer
# Installs a cyberpunk-themed boot splash (Vice OS branding, cyan/magenta).
# Must be run as root.
# ============================================================================
set -Eeuo pipefail

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"

THEME_NAME="vice-cyberpunk"
PLYMOUTH_DIR="/usr/share/plymouth/themes/$THEME_NAME"
LOCKFILE="/var/lock/vice-plymouth-theme.lock"
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
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --version)
                echo "Vice OS Plymouth Boot Splash Installer v1.1"
                exit 0
                ;;
            --help|-h)
                echo "Vice OS Plymouth Boot Splash Installer"
                echo "Usage: sudo $0"
                echo "Installs cyberpunk-themed boot splash and updates initramfs."
                exit 0
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
        log_error "Another Plymouth theme operation is already running. Exiting."
        exit 1
    fi
    LOCKED=1

    log_info "============================================================"
    log_info "  Vice OS — Plymouth Boot Splash Installer"
    log_info "============================================================"

    # --- 1. Check plymouth is installed ---
    if ! command -v plymouth-set-default-theme >/dev/null 2>&1; then
        log_warn "plymouth-set-default-theme not found. Attempting to install plymouth..."
        if command -v apt-get >/dev/null 2>&1; then
            apt-get update 2>/dev/null || true
            apt-get install -y --no-install-recommends plymouth plymouth-themes 2>/dev/null || true
        fi
        if ! command -v plymouth-set-default-theme >/dev/null 2>&1; then
            log_error "Plymouth not installed. Install with: apt install plymouth plymouth-themes"
            exit 1
        fi
    fi

    # --- 2. Create theme directory ---
    mkdir -p "$PLYMOUTH_DIR"

    # --- 3. Generate splash background ---
    log_info "Generating splash background..."
    local convert_cmd=""
    if command -v magick >/dev/null 2>&1; then
        convert_cmd="magick"
    elif command -v convert >/dev/null 2>&1; then
        convert_cmd="convert"
    fi

    if [ -n "$convert_cmd" ]; then
        $convert_cmd -size 1920x1080 xc:"#0a0a0a" \
            -fill "#00ffff" -font "DejaVu-Sans-Mono-Bold" -pointsize 96 \
            -gravity center -annotate +0-150 "VICE OS" \
            -fill "#ff00ff" -font "DejaVu-Sans-Mono" -pointsize 36 \
            -gravity center -annotate +0-40 "BOOTING..." \
            "$PLYMOUTH_DIR/background.png" 2>/dev/null || \
        log_warn "ImageMagick generation failed, theme will use solid color"
    fi

    # --- 4. Create theme plugin config (script-based theme) ---
    cat > "$PLYMOUTH_DIR/vice-cyberpunk.plymouth" <<EOF
[Plymouth Theme]
Name=Vice OS Cyberpunk
Description=Vice OS cyberpunk boot splash — cyan/magenta on dark
ModuleName=two-step

[two-step]
Font=DejaVu Sans Mono 14
TitleFont=DejaVu Sans Mono Bold 36
TitleColor=0x00ffff
WatermarkVerticalAlignment=.5
WatermarkHorizontalAlignment=.5
ProgressBarHorizontalAlignment=.5
ProgressBarVerticalAlignment=.85
ProgressBarWidth=400
ProgressBarHeight=6
ProgressBarCornersRadius=3
DialogHorizontalAlignment=.5
DialogVerticalAlignment=.38
Transition=none
TransitionDuration=0.0
BackgroundStartColor=0x0a0a0a
BackgroundEndColor=0x0a0a0a
ProgressBarBackgroundColor=0x1a1a1a
ProgressBarForegroundColor=0x00ffff
MessageBelowAnimation=true
EOF

    # --- 5. Animated script theme (glow pulse) ---
    cat > "$PLYMOUTH_DIR/vice-glow.plymouth" <<EOF
[Plymouth Theme]
Name=Vice OS Glow
Description=Vice OS boot splash with pulsing glow animation
ModuleName=script

[script]
ImageDir=/usr/share/plymouth/themes/$THEME_NAME
ScriptFile=vice-glow.script
EOF

    cat > "$PLYMOUTH_DIR/vice-glow.script" <<'SCRIPT'
# Vice OS Glow — Plymouth script theme
# Cyan progress bar with magenta pulsing title

screen_width = Window.GetWidth();
screen_height = Window.GetHeight();

# Background
bg_color = [0.04, 0.04, 0.04];  # #0a0a0a

fun draw_background() {
    Window.SetBackgroundColor(bg_color[0], bg_color[1], bg_color[2]);
}

draw_background();

# Title "VICE OS"
title_image = Image.Text("VICE OS", 0.0, 1.0, 1.0, 1.0, "DejaVu Sans Mono Bold 48");
title_sprite = Sprite(title_image);
title_sprite.SetX((screen_width - title_image.GetWidth()) / 2);
title_sprite.SetY(screen_height * 0.35);

# Subtitle
sub_image = Image.Text("BOOTING", 1.0, 0.0, 1.0, 0.9, "DejaVu Sans Mono 20");
sub_sprite = Sprite(sub_image);
sub_sprite.SetX((screen_width - sub_image.GetWidth()) / 2);
sub_sprite.SetY(screen_height * 0.48);

# Progress bar
bar_width = 400;
bar_height = 6;
bar_x = (screen_width - bar_width) / 2;
bar_y = screen_height * 0.85;

# Background bar
bar_bg_image = Image(bar_width, bar_height);
bar_bg_image.SetBackgroundColor(0.1, 0.1, 0.1);
bar_bg_sprite = Sprite(bar_bg_image);
bar_bg_sprite.SetPosition(bar_x, bar_y, 0);

# Foreground progress
fun progress_callback(duration, progress) {
    if (progress > 1.0) progress = 1.0;
    fg_width = Math.Int(bar_width * progress);
    if (fg_width > 0) {
        fg_image = Image(fg_width, bar_height);
        fg_image.SetBackgroundColor(0.0, 1.0, 1.0);  # cyan
        fg_sprite = Sprite(fg_image);
        fg_sprite.SetPosition(bar_x, bar_y, 1);
    }
}

Plymouth.SetBootProgressFunction(progress_callback);

# Pulse animation for title glow
time = 0;
fun refresh() {
    time += 0.1;
    alpha = 0.6 + 0.4 * Math.Sin(time);
    title_sprite.SetOpacity(alpha);
}

Plymouth.SetRefreshFunction(refresh);
SCRIPT

    # --- 6. Register themes ---
    log_info "Registering themes with plymouth..."
    plymouth-set-default-theme -R "$THEME_NAME" 2>/dev/null || true

    # --- 7. Update initramfs so splash shows at boot ---
    log_info "Updating initramfs..."
    if command -v update-initramfs >/dev/null 2>&1; then
        update-initramfs -u 2>/dev/null || true
    fi

    # --- 8. Summary ---
    log_success "Plymouth Themes Installed!"
    log_info "Themes: $THEME_NAME, vice-glow"
}

main "$@"
