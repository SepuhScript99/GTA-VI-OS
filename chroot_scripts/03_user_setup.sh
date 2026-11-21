#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: User & Desktop Setup
# Creates the default user, installs the desktop shell, and configures auto-login.
# Note: .profile and .bashrc are installed by 22_skel_setup.sh
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Installing useradd defaults..."
    if [ -f /vice_payload/config/default/useradd ]; then
        mkdir -p /etc/default
        cp /vice_payload/config/default/useradd /etc/default/useradd
        chown root:root /etc/default/useradd
        chmod 644 /etc/default/useradd
    else
        log_error "config/default/useradd not found in payload!"
        exit 1
    fi

    log_info "Setting up user account..."
    if ! id -u vice >/dev/null 2>&1; then
        # useradd reads /etc/default/useradd for the shell (SHELL=/bin/bash)
        useradd -m vice
        echo "vice:vice" | chpasswd
    else
        log_warn "User 'vice' already exists. Skipping creation."
    fi

    # Ensure vice has correct shell and groups regardless of creation path
    usermod -s /bin/bash vice
    usermod -aG sudo vice

    log_info "Configuring sudo for 'vice' user..."
    if [ -f /vice_payload/config/sudoers ]; then
        cp /vice_payload/config/sudoers /etc/sudoers.d/vice
        chown root:root /etc/sudoers.d/vice
        chmod 440 /etc/sudoers.d/vice

        # Validate sudoers syntax to prevent locking out root access
        if ! visudo -cf /etc/sudoers.d/vice > /dev/null 2>&1; then
            log_error "Syntax error in /etc/sudoers.d/vice! Aborting."
            exit 1
        fi
        log_info "Sudoers configuration installed and validated."
    else
        log_error "config/sudoers not found in payload!"
        exit 1
    fi

    log_info "Generating original assets..."
    python3 /vice_payload/assets/generate_assets.py

    log_info "Installing Desktop Environment files..."
    mkdir -p /opt/vice-os
    cp -r /vice_payload/desktop/* /opt/vice-os/

    # Ensure all desktop scripts and helpers are executable
    chmod +x /opt/vice-os/*.sh /opt/vice-os/*.py 2>/dev/null || true

    # Copy shared Python libraries so the desktop shell can import them at runtime
    mkdir -p /opt/vice-os/lib
    cp -r /vice_payload/lib/python /opt/vice-os/lib/

    # Use picom config syntax, but keep filename as compton.conf for legacy compatibility
    cp /vice_payload/config/compton.conf /etc/xdg/compton.conf

    # Copy Openbox configuration to system skeleton and vice user
    # (22_skel_setup.sh handles .bashrc and .profile, but Openbox config is handled here)
    mkdir -p /etc/skel/.config/openbox
    cp /vice_payload/config/openbox_rc.xml /etc/skel/.config/openbox/rc.xml

    mkdir -p /home/vice/.config/openbox
    cp /vice_payload/config/openbox_rc.xml /home/vice/.config/openbox/rc.xml
    chown -R vice:vice /home/vice/.config

    # Install Vice-Dark Openbox window theme
    if [ -d /vice_payload/config/themes/Vice-Dark ]; then
        mkdir -p /usr/share/themes
        rm -rf /usr/share/themes/Vice-Dark
        cp -r /vice_payload/config/themes/Vice-Dark /usr/share/themes/
        find /usr/share/themes/Vice-Dark -type d -exec chmod 755 {} \;
        find /usr/share/themes/Vice-Dark -type f -exec chmod 644 {} \;
        log_info "Installed Vice-Dark Openbox theme."
    fi

    # Install default xfce4-terminal dark configuration
    if [ -f /vice_payload/config/xfce4/terminal/terminalrc ]; then
        mkdir -p /etc/skel/.config/xfce4/terminal /home/vice/.config/xfce4/terminal
        cp /vice_payload/config/xfce4/terminal/terminalrc /etc/skel/.config/xfce4/terminal/terminalrc
        cp /vice_payload/config/xfce4/terminal/terminalrc /home/vice/.config/xfce4/terminal/terminalrc
        chmod 644 /etc/skel/.config/xfce4/terminal/terminalrc /home/vice/.config/xfce4/terminal/terminalrc
        chown -R vice:vice /home/vice/.config
        log_info "Installed default xfce4-terminal configuration."
    fi

    # Install Qt5 (qt5ct) icon/font configuration (enables Papirus-Dark icons in Qt5 apps)
    if [ -f /vice_payload/config/qt5ct/qt5ct.conf ]; then
        mkdir -p /etc/skel/.config/qt5ct /home/vice/.config/qt5ct
        cp /vice_payload/config/qt5ct/qt5ct.conf /etc/skel/.config/qt5ct/qt5ct.conf
        cp /vice_payload/config/qt5ct/qt5ct.conf /home/vice/.config/qt5ct/qt5ct.conf
        chmod 644 /etc/skel/.config/qt5ct/qt5ct.conf /home/vice/.config/qt5ct/qt5ct.conf
        log_info "Installed qt5ct Papirus-Dark configuration."
    fi

    # Install LibFM & PCManFM desktop icon manager configurations
    if [ -f /vice_payload/config/libfm/libfm.conf ]; then
        mkdir -p /etc/skel/.config/libfm /home/vice/.config/libfm
        cp /vice_payload/config/libfm/libfm.conf /etc/skel/.config/libfm/libfm.conf
        cp /vice_payload/config/libfm/libfm.conf /home/vice/.config/libfm/libfm.conf
        chmod 644 /etc/skel/.config/libfm/libfm.conf /home/vice/.config/libfm/libfm.conf
    fi
    if [ -f /vice_payload/config/pcmanfm/vice/desktop-items-0.conf ]; then
        mkdir -p /etc/skel/.config/pcmanfm/vice /home/vice/.config/pcmanfm/vice
        cp /vice_payload/config/pcmanfm/vice/desktop-items-0.conf /etc/skel/.config/pcmanfm/vice/desktop-items-0.conf
        cp /vice_payload/config/pcmanfm/vice/desktop-items-0.conf /home/vice/.config/pcmanfm/vice/desktop-items-0.conf
        chmod 644 /etc/skel/.config/pcmanfm/vice/desktop-items-0.conf /home/vice/.config/pcmanfm/vice/desktop-items-0.conf
        log_info "Installed pcmanfm desktop icons configuration."
    fi
    chown -R vice:vice /home/vice/.config

    # Pre-create standard XDG user directories
    for d in Desktop Documents Downloads Music Pictures Videos; do
        mkdir -p "/etc/skel/$d" "/home/vice/$d"
    done
    chown -R vice:vice /home/vice

    # Copy Labwc (Wayland compositor) configuration to system skeleton and vice user
    # Labwc reads config from ~/.config/labwc/ — mirrors the Openbox config structure.
    if [ -d /vice_payload/config/labwc ]; then
        log_info "Installing Labwc Wayland compositor configuration..."
        mkdir -p /etc/skel/.config/labwc
        cp /vice_payload/config/labwc/* /etc/skel/.config/labwc/
        chmod +x /etc/skel/.config/labwc/autostart 2>/dev/null || true

        mkdir -p /home/vice/.config/labwc
        cp /vice_payload/config/labwc/* /home/vice/.config/labwc/
        chmod +x /home/vice/.config/labwc/autostart 2>/dev/null || true
        chown -R vice:vice /home/vice/.config/labwc

        # Also install labwc config system-wide as fallback (/etc/xdg/labwc/)
        mkdir -p /etc/xdg/labwc
        cp /vice_payload/config/labwc/* /etc/xdg/labwc/
        chmod +x /etc/xdg/labwc/autostart 2>/dev/null || true
        log_info "Labwc configuration installed to /etc/skel, /home/vice, and /etc/xdg."
    else
        log_warn "Labwc config directory not found in payload. Wayland session config skipped."
    fi

    # Install session type configuration (x11 default, wayland opt-in)
    if [ -f /vice_payload/config/vice-os-session.conf ]; then
        mkdir -p /etc/vice-os
        cp /vice_payload/config/vice-os-session.conf /etc/vice-os/session.conf
        chmod 644 /etc/vice-os/session.conf
        log_info "Installed session configuration (/etc/vice-os/session.conf)."
    fi

    # Install GUI Application Entries (Settings Menu)
    log_info "Installing XDG application entries..."
    mkdir -p /usr/share/applications
    if [ -f /vice_payload/config/vice-os-settings.desktop ]; then
        cp /vice_payload/config/vice-os-settings.desktop /usr/share/applications/
        chmod 644 /usr/share/applications/vice-os-settings.desktop
    fi

    log_info "Configuring Auto-login via getty..."
    mkdir -p /etc/systemd/system/getty@tty1.service.d
    cat <<'GETTY' > /etc/systemd/system/getty@tty1.service.d/override.conf
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin vice --noclear %I $TERM
GETTY

    log_info "Configuring live-config to prevent tty1/xinit override..."
    mkdir -p /etc/live/config.conf.d
    cat <<'LIVECONF' > /etc/live/config.conf.d/vice-os.conf
# Prevent live-config from overriding Vice OS user/sudo/xinit startup
LIVE_CONFIG_NOX11AUTOLOGIN="true"
LIVE_CONFIG_NOCOMPONENTS="xinit,user-setup,sudo"
LIVECONF
    chmod 644 /etc/live/config.conf.d/vice-os.conf

    log_success "User and desktop setup completed."
}

main "$@"
