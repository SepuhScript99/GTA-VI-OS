#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) — Vice Command Deck.
Searchable interactive Linux and Vice OS command cheat-sheet covering Files,
Networking, Git, Permissions, Systemd, Archives, Security, and Shortcuts
with one-click Copy and Run-in-Terminal (xfce4-terminal).
"""

import os
import shutil
import signal
import sys

from PyQt5.QtCore import Qt, QProcess
from PyQt5.QtGui import QFont, QIcon, QPixmap
from PyQt5.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton,
    QVBoxLayout, QWidget
)

sys.path.insert(0, "/opt/vice-os/lib")

try:
    from python.vice_utils import log_info  # noqa: E402
except ImportError:
    def log_info(msg: str) -> None:
        print(f"[INFO] {msg}")


CJK_FONTS = [
    "Noto Sans",
    "Noto Sans CJK JP",
    "Noto Sans CJK SC",
    "Noto Sans CJK TC",
    "Noto Sans CJK KR",
    "DejaVu Sans",
]

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

    ("Networking", "Show IP addresses concisely", "ip -br addr", "Compact color/brief summary of every network interface and assigned IP.", True),
    ("Networking", "Inspect listening TCP/UDP sockets", "ss -tulnp", "Show listening TCP/UDP ports and bound process info.", True),
    ("Networking", "Show default gateway & routing table", "ip route", "Display kernel IP routing table and default gateway.", True),
    ("Networking", "Query DNS records with dig", "dig +short A debian.org", "Perform a concise DNS A-record lookup using dig.", True),
    ("Networking", "Scan local subnet ports (fast)", "nmap -sT -F 127.0.0.1", "TCP connect scan of top 100 common ports on localhost.", True),
    ("Networking", "Live traceroute with mtr report", "mtr -r -c 5 1.1.1.1", "Run 5-cycle ping+traceroute path quality report to 1.1.1.1.", True),
    ("Networking", "Fetch HTTP response headers", "curl -ILs https://example.com | head -n 20", "Inspect HTTP status and response headers following redirects.", True),
    ("Networking", "Check NetworkManager devices", "nmcli dev status", "Display status of Wi-Fi and Ethernet interfaces managed by NetworkManager.", True),

    ("Git", "Compact branch & commit graph", "git log --oneline --graph --decorate -n 20", "Show last 20 commits as a readable branch graph.", True),
    ("Git", "Short status & branch summary", "git status -sb", "Show current branch and concise modified/untracked file list.", True),
    ("Git", "Inspect unstaged + staged diff stats", "git diff --stat HEAD", "View changed file line counts compared to HEAD.", True),
    ("Git", "Stash work including untracked files", "git stash push -u -m 'wip'", "Temporarily shelve tracked and untracked edits cleanly.", True),
    ("Git", "Undo last commit keeping changes staged", "git reset --soft HEAD~1", "Move branch pointer back one commit without losing indexed edits.", True),
    ("Git", "Show remote tracking URLs", "git remote -v", "List configured Git fetch and push remote URLs.", True),

    ("Permissions", "Make script executable (user/group/other)", "chmod +x script.sh", "Add execute bit to a script or binary.", True),
    ("Permissions", "Secure private SSH key permissions", "chmod 600 ~/.ssh/id_ed25519", "Restrict private key read/write solely to owner (required by OpenSSH).", True),
    ("Permissions", "Inspect file owner, mode, timestamps", "stat /etc/passwd", "Print detailed inode metadata, octal mode, UID/GID, and timestamps.", True),
    ("Permissions", "Check current user UID & groups", "id", "Display current user ID, primary group, and supplementary groups.", True),
    ("Permissions", "Change owner recursively (sudo)", "sudo chown -R vice:vice ~/Projects", "Update ownership of directory tree to user and group vice.", True),
    ("Permissions", "Verify sudoers syntax safely", "sudo visudo -c", "Check /etc/sudoers and /etc/sudoers.d/* for syntax errors.", True),

    ("Systemd", "List failed system services", "systemctl --failed", "Show any systemd units currently in failed state.", True),
    ("Systemd", "Check PipeWire & WirePlumber user audio", "systemctl --user status pipewire pipewire-pulse wireplumber", "Inspect user audio daemon health on Vice OS.", True),
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
    ("Security", "Decrypt an OpenSSL AES-256 file", "openssl enc -d -aes-256-cbc -pbkdf2 -in secret.txt.enc -out secret.txt", "Decrypt an encrypted file created with Vice Vault or OpenSSL.", True),
    ("Security", "Compute SHA-256 checksum", "sha256sum file.iso", "Calculate SHA-256 digest of a file or ISO image.", True),
    ("Security", "Run Lynis quick system security audit", "sudo lynis audit system --quick", "Perform automated security hardening audit on Debian/Vice OS.", True),
    ("Security", "List GPG public & secret keys", "gpg --list-keys", "Show imported OpenPGP keys in your local keyring.", True),

    ("Shortcuts", "Open Vice OS Start Menu", "Super (Windows Key) / Alt+F1", "Instant Start Menu popup with categories, search, and Places.", False),
    ("Shortcuts", "Launch Vice Tool Hub (X / 500)", "python3 /opt/vice-os/vice_tool_hub.py", "Open the Leonida Arsenal explorer for all 100+ tools.", True),
    ("Shortcuts", "Launch interactive CLI tool wrapper", "vice-run-tool 'htop' htop", "Open any CLI/TUI tool with GTA VI banner and hold-open behavior.", True),
    ("Shortcuts", "Close active window / Switch windows", "Alt+F4  |  Alt+Tab", "Openbox window close and switcher hotkeys.", False),
    ("Shortcuts", "Open Run Command / Terminal", "Alt+F2  |  Ctrl+Alt+T", "Quick launch Openbox run dialog or xfce4-terminal.", False),
    ("Shortcuts", "Check PipeWire audio status", "wpctl status", "Display WirePlumber sinks, sources, streams, and default volume.", True),
]

STYLE = """
QMainWindow, QWidget#RootWidget {
    background-color: #120e1e;
    color: #f4f1fa;
    font-family: "Noto Sans", "Noto Sans CJK JP", "Noto Sans CJK SC", "Noto Sans CJK TC", "Noto Sans CJK KR", "DejaVu Sans", sans-serif;
    font-size: 13px;
}
QFrame#Banner {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #1d1433, stop:0.6 #2e153d, stop:1 #16223a);
    border: 1px solid #ff4da6;
    border-radius: 12px;
}
QLineEdit {
    background-color: #1b152e;
    color: #f4f1fa;
    border: 1px solid #3c2e5e;
    border-radius: 8px;
    padding: 8px 12px;
}
QLineEdit:focus {
    border-color: #00e5ff;
}
QPushButton#CatBtn {
    background-color: #1b152e;
    color: #cfc6e6;
    border: 1px solid #322650;
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 12px;
    font-weight: bold;
}
QPushButton#CatBtn:checked {
    background-color: #361f47;
    color: #ffd166;
    border-color: #ff4da6;
}
QListWidget {
    background-color: #161126;
    color: #f4f1fa;
    border: 1px solid #382b57;
    border-radius: 10px;
    padding: 6px;
}
QListWidget::item {
    padding: 8px 10px;
    border-radius: 6px;
}
QListWidget::item:selected {
    background-color: #311d46;
    color: #ffd166;
    border: 1px solid #ff4da6;
}
QPlainTextEdit {
    background-color: #0d0a18;
    color: #00e5ff;
    border: 1px solid #382b57;
    border-radius: 8px;
    font-family: "Noto Sans Mono CJK JP", "Noto Sans Mono CJK SC", "DejaVu Sans Mono", monospace;
    font-size: 13px;
    padding: 10px;
}
QPushButton {
    background-color: #1f1836;
    color: #00e5ff;
    border: 1px solid #00e5ff;
    border-radius: 8px;
    padding: 8px 14px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #00e5ff;
    color: #120e1e;
}
QPushButton#RunBtn {
    color: #ffd166;
    border-color: #ff8a5b;
    background-color: #341b42;
}
QPushButton#RunBtn:hover {
    background-color: #ff8a5b;
    color: #120e1e;
}
"""


def _configure_cjk_fonts(app: QApplication) -> None:
    for fam in ("Noto Sans", "DejaVu Sans", "Sans", "sans-serif"):
        QFont.insertSubstitutions(fam, CJK_FONTS)
    font = QFont("Noto Sans", 10)
    if hasattr(font, "setFamilies"):
        font.setFamilies(CJK_FONTS)
    app.setFont(font)


def _load_app_icon() -> QIcon:
    for path in (
        "/usr/share/icons/hicolor/64x64/apps/vice-tool-cheatsheets.png",
        "/usr/share/pixmaps/vice-tool-cheatsheets.png",
    ):
        if os.path.isfile(path):
            pm = QPixmap(path)
            if not pm.isNull():
                return QIcon(pm)
    return QIcon.fromTheme("utilities-terminal")


class ViceCommandDeckApp(QMainWindow):
    """Main window for Vice Command Deck."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice Command Deck — Linux & Vice OS Cheatsheets")
        self.resize(940, 620)
        self.setMinimumSize(740, 500)
        icon = _load_app_icon()
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

        banner = QFrame(root)
        banner.setObjectName("Banner")
        bl = QVBoxLayout(banner)
        bl.setContentsMargins(16, 12, 16, 12)
        title = QLabel("VICE COMMAND DECK · INTERACTIVE CHEATSHEETS", banner)
        title.setStyleSheet("color: #ffd166; font-size: 18px; font-weight: bold; background: transparent;")
        bl.addWidget(title)
        sub = QLabel("Searchable Linux & Vice OS reference — edit command args, Copy, or Run in xfce4-terminal", banner)
        sub.setStyleSheet("color: #cfc6e6; font-size: 12px; background: transparent;")
        bl.addWidget(sub)
        layout.addWidget(banner)

        self._search = QLineEdit(root)
        self._search.setPlaceholderText("Search commands, flags, packages, or keywords (e.g. 'rg', 'docker', 'pipewire', 'tar')...")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._populate_list)
        layout.addWidget(self._search)

        cat_row = QHBoxLayout()
        cat_row.setSpacing(6)
        for cat in CATEGORIES:
            btn = QPushButton(cat, root)
            btn.setObjectName("CatBtn")
            btn.setCheckable(True)
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

        detail_col = QVBoxLayout()
        detail_col.setSpacing(10)

        self._detail_title = QLabel("Select a command", root)
        self._detail_title.setStyleSheet("color: #ff8a5b; font-size: 16px; font-weight: bold;")
        self._detail_title.setWordWrap(True)
        detail_col.addWidget(self._detail_title)

        self._detail_desc = QLabel("", root)
        self._detail_desc.setWordWrap(True)
        self._detail_desc.setStyleSheet("color: #d6cee8;")
        detail_col.addWidget(self._detail_desc)

        cmd_hdr = QLabel("Editable Command:", root)
        cmd_hdr.setStyleSheet("color: #cfc6e6; font-weight: bold;")
        detail_col.addWidget(cmd_hdr)

        self._cmd_edit = QPlainTextEdit(root)
        self._cmd_edit.setMaximumHeight(110)
        detail_col.addWidget(self._cmd_edit)

        btn_row = QHBoxLayout()
        copy_btn = QPushButton("Copy Command", root)
        copy_btn.clicked.connect(self._copy_command)
        btn_row.addWidget(copy_btn)

        self._run_btn = QPushButton("Run in Terminal", root)
        self._run_btn.setObjectName("RunBtn")
        self._run_btn.clicked.connect(self._run_in_terminal)
        btn_row.addWidget(self._run_btn)
        detail_col.addLayout(btn_row)

        self._status_lbl = QLabel("Ready.", root)
        self._status_lbl.setStyleSheet("color: #64ffda;")
        self._status_lbl.setWordWrap(True)
        detail_col.addWidget(self._status_lbl)
        detail_col.addStretch(1)

        mid.addLayout(detail_col, 2)
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
            "Editable — customize paths/flags before clicking Copy or Run."
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
    _configure_cjk_fonts(app)
    app.setStyleSheet(STYLE)
    win = ViceCommandDeckApp()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
