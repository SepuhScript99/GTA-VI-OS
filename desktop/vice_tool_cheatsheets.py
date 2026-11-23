#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) — Vice Command Deck.
Searchable interactive Linux and Vice OS command cheat-sheet covering Files,
Networking, Git, Permissions, Systemd, Archives, Security, and Shortcuts
with one-click Copy and Run-in-Terminal (xfce4-terminal).
Styled via vice_theme (Noto Sans CJK fallback).
"""

import os
import shutil
import signal
import sys

from PyQt5.QtCore import Qt, QProcess
from PyQt5.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit,
    QPushButton, QVBoxLayout, QWidget
)

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in ("/opt/vice-os", _HERE, "/opt/vice-os/lib"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from vice_theme import (  # noqa: E402
    COLORS,
    apply_app_theme,
    load_tool_icon,
    make_button,
    make_card,
    make_header,
)

try:
    from python.vice_utils import log_info  # noqa: E402
except ImportError:
    def log_info(msg: str) -> None:
        print(f"[INFO] {msg}")


CATEGORIES = [
    "All",
    "Files",
    "Networking",
    "Git",
    "Permissions",
    "Systemd",
    "Archives",
    "Security",
    "Shortcuts",
]

CHEATSHEETS = [
    ("Files", "Fast text search with ripgrep", "rg -n --hidden 'TODO' .", "Recursively search lines matching 'TODO' including hidden files (skipping .git).", True),
    ("Files", "Find files by name (Debian fd-find)", "fdfind -e py -e sh", "List all Python and shell scripts under the current directory using fdfind.", True),
    ("Files", "Syntax-highlighted file viewer (Debian bat)", "batcat --paging=always /etc/os-release", "View a file with line numbers and syntax highlighting via batcat.", True),
    ("Files", "Interactive disk usage analyzer", "ncdu ~", "Launch interactive ncurses disk usage explorer for your home directory.", True),
    ("Files", "Directory tree overview (depth 2)", "tree -L 2 -C", "Display colorized directory hierarchy up to 2 levels deep.", True),
    ("Files", "Show filesystem free space", "df -hT", "Display mounted filesystems with human-readable sizes and filesystem types.", True),
    ("Files", "Find largest files in current dir", "du -ah . | sort -rh | head -n 20", "List top 20 largest files and directories sorted by size.", True),
    ("Files", "Live log tailing with follow", "tail -n 50 -f ~/.xsession-errors", "Stream the last 50 lines and follow updates of your X session log.", True),

    ("Networking", "Show IP addresses concisely", "ip -br addr", "Compact brief summary of every network interface and assigned IP.", True),
    ("Networking", "Inspect listening & active sockets", "ss -tunap", "Show listening and established TCP/UDP sockets with process names.", True),
    ("Networking", "Show default gateway & routing table", "ip route", "Display kernel IP routing table and default gateway.", True),
    ("Networking", "Query DNS records with dig", "dig +short A debian.org", "Perform a concise DNS A-record lookup using dig.", True),
    ("Networking", "Scan local subnet ports (fast)", "nmap -sT -F 127.0.0.1", "TCP connect scan of top 100 common ports on localhost.", True),
    ("Networking", "Live traceroute with mtr report", "mtr -r -c 5 1.1.1.1", "Run 5-cycle ping+traceroute path quality report to 1.1.1.1.", True),
    ("Networking", "Inspect WireGuard tunnel status", "sudo wg show", "Display active WireGuard interfaces, endpoints, and handshakes.", True),
    ("Networking", "Check NetworkManager devices", "nmcli dev status", "Display status of Wi-Fi and Ethernet interfaces managed by NetworkManager.", True),

    ("Git", "Compact branch & commit graph", "git log --oneline --graph --decorate -n 20", "Show last 20 commits as a readable branch graph.", True),
    ("Git", "Short status & branch summary", "git status -sb", "Show current branch and concise modified/untracked file list.", True),
    ("Git", "Inspect unstaged + staged diff stats", "git diff --stat HEAD", "View changed file line counts compared to HEAD.", True),
    ("Git", "Stash work including untracked files", "git stash push -u -m 'wip'", "Temporarily shelve tracked and untracked edits cleanly.", True),
    ("Git", "Undo last commit keeping changes staged", "git reset --soft HEAD~1", "Move branch pointer back one commit without losing indexed edits.", True),
    ("Git", "Show remote tracking URLs", "git remote -v", "List configured Git fetch and push remote URLs.", True),

    ("Permissions", "Make script executable", "chmod +x script.sh", "Add execute bit to a script or binary.", True),
    ("Permissions", "Secure private SSH key permissions", "chmod 600 ~/.ssh/id_ed25519", "Restrict private key read/write solely to owner (required by OpenSSH).", True),
    ("Permissions", "Inspect file owner, mode, timestamps", "stat /etc/passwd", "Print detailed inode metadata, octal mode, UID/GID, and timestamps.", True),
    ("Permissions", "Check current user UID & groups", "id", "Display current user ID, primary group, and supplementary groups.", True),
    ("Permissions", "Change owner recursively (sudo)", "sudo chown -R vice:vice ~/Projects", "Update ownership of directory tree to user and group vice.", True),
    ("Permissions", "Verify sudoers syntax safely", "sudo visudo -c", "Check /etc/sudoers and /etc/sudoers.d/* for syntax errors.", True),

    ("Systemd", "List failed system services", "systemctl --failed", "Show any systemd units currently in failed state.", True),
    ("Systemd", "Check PipeWire & WirePlumber audio", "systemctl --user status pipewire pipewire-pulse wireplumber", "Inspect user audio daemon health on Vice OS.", True),
    ("Systemd", "Sync host clock & timezone status", "vice-timesync --status", "Check VirtualBox host time sync, Chrony status, and active timezone.", True),
    ("Systemd", "Tail system errors from current boot", "journalctl -p err -b -n 40 --no-pager", "Read the latest 40 error-priority kernel/system logs from this boot.", True),
    ("Systemd", "Analyze boot time bottlenecks", "systemd-analyze blame | head -n 20", "List the slowest units during system boot.", True),
    ("Systemd", "Check active timers", "systemctl list-timers --all", "Display scheduled systemd timers and next run timestamps.", True),

    ("Archives", "Create compressed tar.gz archive", "tar -czvf backup.tar.gz folder/", "Archive and gzip-compress a directory with progress output.", True),
    ("Archives", "Extract .tar.gz / .tar.xz archive", "tar -xvf archive.tar.gz", "Auto-detect compression and extract tarball into current folder.", True),
    ("Archives", "List contents of a 7z/zip archive", "7z l archive.7z", "Inspect files inside a 7z/zip archive without extracting.", True),
    ("Archives", "Fast resumable directory sync", "rsync -avh --progress src/ dst/", "Mirror src/ into dst/ preserving permissions and timestamps.", True),
    ("Archives", "Create ZIP archive recursively", "zip -r bundle.zip my_folder/", "Compress directory into standard ZIP archive.", True),

    ("Security", "Check UFW firewall rules", "sudo ufw status verbose", "Display Uncomplicated Firewall status, default policy, and active rules.", True),
    ("Security", "Encrypt a file with OpenSSL AES-256", "openssl enc -aes-256-cbc -pbkdf2 -salt -in secret.txt -out secret.txt.enc", "Encrypt file using AES-256-CBC and PBKDF2 key derivation.", True),
    ("Security", "Strip EXIF/GPS metadata from photo", "exiftool -all= photo.jpg", "Remove embedded EXIF, GPS, and camera metadata in place.", True),
    ("Security", "Compute SHA-256 checksum", "sha256sum file.iso", "Calculate SHA-256 digest of a file or ISO image.", True),
    ("Security", "Run Lynis quick system security audit", "sudo lynis audit system --quick", "Perform automated security hardening audit on Debian/Vice OS.", True),
    ("Security", "List GPG public & secret keys", "gpg --list-keys", "Show imported OpenPGP keys in your local keyring.", True),

    ("Shortcuts", "Open Vice OS Start Menu", "Super (Windows Key) / Alt+F1", "Instant Start Menu popup with categories, search, and Places.", False),
    ("Shortcuts", "Launch Vice Tool Hub (250 / 500)", "python3 /opt/vice-os/vice_tool_hub.py", "Open the Vice Tool Hub explorer for all 250 curated tools.", True),
    ("Shortcuts", "Launch interactive CLI tool wrapper", "vice-run-tool 'htop' htop", "Open any CLI/TUI tool with clean banner and hold-open prompt.", True),
    ("Shortcuts", "Close active window / Switch windows", "Alt+F4  |  Alt+Tab", "Openbox window close and switcher hotkeys.", False),
    ("Shortcuts", "Open Run Command / Terminal", "Alt+F2  |  Ctrl+Alt+T", "Quick launch Openbox run dialog or xfce4-terminal.", False),
    ("Shortcuts", "Check PipeWire audio status", "wpctl status", "Display WirePlumber sinks, sources, streams, and default volume.", True),
]


class ViceCommandDeckApp(QMainWindow):
    """Main window for Vice Command Deck."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice Command Deck — Vice OS")
        self.resize(960, 640)
        self.setMinimumSize(760, 520)
        icon = load_tool_icon("vice-tool-cheatsheets", "utilities-terminal")
        if not icon.isNull():
            self.setWindowIcon(icon)

        self._selected_cat = "All"
        self._cat_buttons = {}
        self._current_entry = None
        self._init_ui()
        self._populate_list()

    def _init_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("RootWidget")
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.setSpacing(12)

        header = make_header(
            title="Vice Command Deck",
            subtitle="Searchable Linux & Vice OS reference — edit flags, copy, or run in terminal",
            icon_name="vice-tool-cheatsheets",
            badge_text=f"{len(CHEATSHEETS)} RECIPES",
            badge_variant="neutral",
            parent=root,
        )
        layout.addWidget(header)

        self._search = QLineEdit(root)
        self._search.setPlaceholderText("Search commands, flags, packages, or keywords (e.g. 'rg', 'ufw', 'pipewire', 'tar')...")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._populate_list)
        layout.addWidget(self._search)

        cat_row = QHBoxLayout()
        cat_row.setSpacing(6)
        for cat in CATEGORIES:
            btn = QPushButton(cat, root)
            btn.setObjectName("CatTab")
            btn.setCheckable(True)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setChecked(cat == "All")
            btn.clicked.connect(lambda _=False, c=cat: self._set_category(c))
            self._cat_buttons[cat] = btn
            cat_row.addWidget(btn)
        cat_row.addStretch(1)
        layout.addLayout(cat_row)

        mid = QHBoxLayout()
        mid.setSpacing(12)

        self._list = QListWidget(root)
        self._list.currentItemChanged.connect(self._on_item_changed)
        mid.addWidget(self._list, 3)

        detail_card = make_card(title="Command Details", parent=root)
        self._detail_title = QLabel("Select a command", detail_card)
        self._detail_title.setStyleSheet(
            f"color: {COLORS['accent_peach']}; font-size: 15px; font-weight: bold;"
        )
        self._detail_title.setWordWrap(True)
        detail_card.body_layout.addWidget(self._detail_title)

        self._detail_desc = QLabel("", detail_card)
        self._detail_desc.setWordWrap(True)
        self._detail_desc.setStyleSheet(f"color: {COLORS['text_secondary']};")
        detail_card.body_layout.addWidget(self._detail_desc)

        cmd_hdr = QLabel("Editable Command", detail_card)
        cmd_hdr.setObjectName("SectionTitle")
        detail_card.body_layout.addWidget(cmd_hdr)

        self._cmd_edit = QPlainTextEdit(detail_card)
        self._cmd_edit.setMaximumHeight(110)
        detail_card.body_layout.addWidget(self._cmd_edit)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        copy_btn = make_button("Copy Command", variant="secondary", parent=detail_card)
        copy_btn.clicked.connect(self._copy_command)
        btn_row.addWidget(copy_btn)

        self._run_btn = make_button("Run in Terminal", variant="primary", parent=detail_card)
        self._run_btn.clicked.connect(self._run_in_terminal)
        btn_row.addWidget(self._run_btn)
        detail_card.body_layout.addLayout(btn_row)

        self._status_lbl = QLabel("Ready.", detail_card)
        self._status_lbl.setStyleSheet(f"color: {COLORS['accent_aqua']};")
        self._status_lbl.setWordWrap(True)
        detail_card.body_layout.addWidget(self._status_lbl)
        detail_card.body_layout.addStretch(1)

        mid.addWidget(detail_card, 2)
        layout.addLayout(mid, 1)

    def _set_category(self, cat: str) -> None:
        self._selected_cat = cat
        for name, btn in self._cat_buttons.items():
            btn.setChecked(name == cat)
        self._populate_list()

    def _populate_list(self) -> None:
        self._list.clear()
        query = self._search.text().strip().lower()
        for entry in CHEATSHEETS:
            cat, title, cmd, desc, _runnable = entry
            if self._selected_cat != "All" and cat != self._selected_cat:
                continue
            if query:
                hay = f"{cat} {title} {cmd} {desc}".lower()
                if query not in hay:
                    continue
            item = QListWidgetItem(f"[{cat}] {title}\n    {cmd}")
            item.setData(Qt.UserRole, entry)
            self._list.addItem(item)
        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    def _on_item_changed(self, current: QListWidgetItem, _prev) -> None:
        if current is None:
            return
        entry = current.data(Qt.UserRole)
        if not entry:
            return
        self._current_entry = entry
        cat, title, cmd, desc, runnable = entry
        self._detail_title.setText(f"[{cat}] {title}")
        self._detail_desc.setText(desc)
        self._cmd_edit.setPlainText(cmd)
        self._run_btn.setEnabled(bool(runnable))
        self._status_lbl.setText(
            "Editable — customize paths or flags before clicking Copy or Run."
            if runnable else "Desktop hotkey shortcut — press keys directly."
        )

    def _copy_command(self) -> None:
        cmd = self._cmd_edit.toPlainText().strip()
        if not cmd:
            return
        QApplication.clipboard().setText(cmd)
        self._status_lbl.setText("Copied command to clipboard.")

    def _run_in_terminal(self) -> None:
        cmd = self._cmd_edit.toPlainText().strip()
        if not cmd:
            return
        term = shutil.which("xfce4-terminal") or shutil.which("x-terminal-emulator") or shutil.which("xterm")
        if not term:
            QMessageBox.warning(self, "Terminal Missing", "Install xfce4-terminal or xterm to run commands.")
            return
        title = self._current_entry[1] if self._current_entry else "Command"
        wrapped = f"{cmd}; rc=$?; echo; read -r -p \"[EXIT $rc] Press [Enter] to close...\" _"
        if "xfce4-terminal" in os.path.basename(term):
            args = ["-T", f"Vice Command Deck — {title}", "-x", "bash", "-lc", wrapped]
        else:
            args = ["-T", f"Vice Command Deck — {title}", "-e", "bash", "-lc", wrapped]
        ok = QProcess.startDetached(term, args, os.path.expanduser("~"))
        if ok:
            self._status_lbl.setText(f"Launched in {os.path.basename(term)}.")
            log_info(f"Command Deck launched: {cmd}")
        else:
            self._status_lbl.setText("Failed to launch terminal.")

    def closeEvent(self, event) -> None:
        event.accept()


def main() -> None:
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    apply_app_theme(app)
    win = ViceCommandDeckApp()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
