#!/usr/bin/env python3
"""
Vice Software Center.
A package management GUI for Vice OS with apt and flatpak support.
"""

import os
import re
import shutil
import signal
import subprocess
import sys

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QProgressBar
)
from PyQt5.QtCore import QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QBrush

sys.path.insert(0, "/opt/vice-os/lib")
sys.path.insert(0, "/opt/vice-os")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vice_theme import (  # noqa: E402
    COLORS,
    apply_app_theme,
    make_button,
    make_header,
)


class PackageWorkerThread(QThread):
    """Worker thread for running package management commands."""
    output_received = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self, command):
        super().__init__()
        self.command = command
        self._proc = None
        self._stopped = False

    def stop(self):
        self._stopped = True
        proc = self._proc
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass

    def run(self):
        try:
            self._proc = subprocess.Popen(
                self.command,
                shell=isinstance(self.command, str),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )

            while not self._stopped:
                output = self._proc.stdout.readline()
                if output == "" and self._proc.poll() is not None:
                    break
                if output:
                    self.output_received.emit(output.strip())

            if not self._stopped:
                stderr = self._proc.stderr.read()
                if stderr:
                    self.error_occurred.emit(stderr.strip())

            if self._stopped and self._proc.poll() is None:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            return_code = self._proc.wait()
            if not self._stopped:
                self.finished.emit(return_code == 0)

        except Exception as e:
            if not self._stopped:
                self.error_occurred.emit(str(e))
                self.finished.emit(False)


class SoftwareCenter(QMainWindow):
    def __init__(self):
        super().__init__()
        self._workers = []
        self.setWindowTitle("Vice Software Center")
        self.resize(1020, 700)
        self.setMinimumSize(780, 520)
        apply_app_theme(self)

        self.init_ui()
        self.refresh_packages()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        header = make_header(
            title="Vice Software Center",
            subtitle="Inspect, update, install, and remove Debian APT & Flatpak packages",
            icon_name="system-software-install",
            badge_text="APT & FLATPAK",
            badge_variant="aqua",
            parent=central_widget,
        )
        layout.addWidget(header)

        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget, 1)

        self.apt_tab = self.create_package_tab("APT")
        self.flatpak_tab = self.create_package_tab("Flatpak")

        self.tab_widget.addTab(self.apt_tab, "APT Packages")
        self.tab_widget.addTab(self.flatpak_tab, "Flatpak Packages")

        self.status_bar = self.statusBar()
        self.status_bar.setStyleSheet(
            f"background-color: {COLORS['bg_surface']}; color: {COLORS['text_secondary']};"
        )
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

    def create_package_tab(self, package_type):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QLabel("Search:"))

        search_edit = QLineEdit()
        search_edit.setPlaceholderText(f"Search {package_type} packages...")
        search_edit.setClearButtonEnabled(True)
        search_edit.textChanged.connect(self.filter_packages)
        controls_layout.addWidget(search_edit)

        refresh_btn = make_button("Refresh", variant="secondary", parent=tab)
        refresh_btn.clicked.connect(self.refresh_packages)
        controls_layout.addWidget(refresh_btn)

        layout.addLayout(controls_layout)

        package_table = QTableWidget()
        package_table.setColumnCount(4)
        package_table.setHorizontalHeaderLabels(["Name", "Version", "Description", "Status"])
        package_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        package_table.setSelectionBehavior(QTableWidget.SelectRows)
        package_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(package_table, 1)

        action_layout = QHBoxLayout()

        install_btn = make_button("Install", variant="primary", parent=tab)
        install_btn.clicked.connect(self.install_selected)
        action_layout.addWidget(install_btn)

        remove_btn = make_button("Remove", variant="danger", parent=tab)
        remove_btn.clicked.connect(self.remove_selected)
        action_layout.addWidget(remove_btn)

        update_btn = make_button("Update", variant="secondary", parent=tab)
        update_btn.clicked.connect(self.update_selected)
        action_layout.addWidget(update_btn)
        action_layout.addStretch()

        layout.addLayout(action_layout)

        if package_type == "APT":
            self.apt_search_edit = search_edit
            self.apt_table = package_table
        else:
            self.flatpak_search_edit = search_edit
            self.flatpak_table = package_table

        return tab

    def _cleanup_worker(self, w):
        if w in self._workers:
            self._workers.remove(w)

    def _start_worker(self, command):
        worker = PackageWorkerThread(command)
        self._workers.append(worker)
        worker.finished.connect(lambda _ok, w=worker: self._cleanup_worker(w))
        return worker

    def shutdown_workers(self):
        for w in list(self._workers):
            if w.isRunning():
                w.stop()
                if not w.wait(1500):
                    w.terminate()
                    w.wait(500)
        self._workers.clear()

    def closeEvent(self, event):
        self.shutdown_workers()
        super().closeEvent(event)

    def refresh_packages(self):
        """Refresh package lists for both APT and Flatpak."""
        self.shutdown_workers()
        self.status_bar.showMessage("Refreshing package lists...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)

        self.apt_table.setRowCount(0)
        self.flatpak_table.setRowCount(0)

        apt_thread = self._start_worker(
            ["dpkg-query", "-W", "-f=${Package}\t${Version}\t${binary:Summary}\n"]
        )
        apt_thread.output_received.connect(self.process_apt_output)
        apt_thread.error_occurred.connect(lambda error: self.handle_error(error, "APT"))
        apt_thread.finished.connect(lambda success: self.package_refresh_finished(success, "APT"))
        apt_thread.start()

        if shutil.which("flatpak"):
            flatpak_thread = self._start_worker(
                ["flatpak", "list", "--columns=application,version,branch,origin"]
            )
            flatpak_thread.output_received.connect(self.process_flatpak_output)
            flatpak_thread.error_occurred.connect(lambda error: self.handle_error(error, "Flatpak"))
            flatpak_thread.finished.connect(lambda success: self.package_refresh_finished(success, "Flatpak"))
            flatpak_thread.start()

    def process_apt_output(self, output):
        """Process output from dpkg-query command."""
        if not output or output.startswith("Listing..."):
            return

        parts = output.split("\t")
        if len(parts) >= 2:
            name = parts[0].strip()
            version = parts[1].strip()
            description = parts[2].strip() if len(parts) > 2 else ""
            if name:
                self.add_apt_package(name, version, description or "Installed package", "Installed")

    def process_flatpak_output(self, output):
        """Process output from flatpak list command."""
        if output == "" or "Application" in output:
            return

        parts = output.split("\t")
        if len(parts) >= 3:
            name = parts[0]
            version = parts[1]
            description = self.get_flatpak_description(name)
            status = "Installed"
            self.add_flatpak_package(name, version, description, status)

    def get_apt_description(self, package_name):
        """Get description for an APT package."""
        try:
            result = subprocess.run(
                ["apt-cache", "show", package_name],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.splitlines():
                if line.startswith("Description:") or line.startswith("Description-en:"):
                    return line.split(":", 1)[1].strip()
        except Exception:
            pass
        return "No description available"

    def get_flatpak_description(self, app_id):
        """Get description for a Flatpak application."""
        try:
            result = subprocess.run(
                ["flatpak", "info", app_id],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.splitlines():
                if line.strip().startswith("Description:"):
                    return line.split(":", 1)[1].strip()
        except Exception:
            pass
        return "No description available"

    def add_apt_package(self, name, version, description, status):
        """Add a package to the APT table."""
        row_position = self.apt_table.rowCount()
        self.apt_table.insertRow(row_position)
        self.apt_table.setItem(row_position, 0, QTableWidgetItem(name))
        self.apt_table.setItem(row_position, 1, QTableWidgetItem(version))
        self.apt_table.setItem(row_position, 2, QTableWidgetItem(description))
        self.apt_table.setItem(row_position, 3, QTableWidgetItem(status))

        if status == "Installed":
            for col in range(4):
                item = self.apt_table.item(row_position, col)
                if item:
                    item.setBackground(QBrush(QColor(54, 214, 195, 22)))
                    item.setForeground(QBrush(QColor(COLORS["text_primary"])))

    def add_flatpak_package(self, name, version, description, status):
        """Add a package to the Flatpak table."""
        row_position = self.flatpak_table.rowCount()
        self.flatpak_table.insertRow(row_position)
        self.flatpak_table.setItem(row_position, 0, QTableWidgetItem(name))
        self.flatpak_table.setItem(row_position, 1, QTableWidgetItem(version))
        self.flatpak_table.setItem(row_position, 2, QTableWidgetItem(description))
        self.flatpak_table.setItem(row_position, 3, QTableWidgetItem(status))

        if status == "Installed":
            for col in range(4):
                item = self.flatpak_table.item(row_position, col)
                if item:
                    item.setBackground(QBrush(QColor(54, 214, 195, 22)))
                    item.setForeground(QBrush(QColor(COLORS["text_primary"])))

    def filter_packages(self):
        """Filter packages based on search text."""
        current_tab = self.tab_widget.currentIndex()

        if current_tab == 0:  # APT tab
            table = self.apt_table
            search_text = self.apt_search_edit.text().lower()
        else:  # Flatpak tab
            table = self.flatpak_table
            search_text = self.flatpak_search_edit.text().lower()

        for row in range(table.rowCount()):
            item = table.item(row, 0)  # Name column
            if item:
                matches = search_text in item.text().lower()
                table.setRowHidden(row, not matches)

    def package_refresh_finished(self, success, package_type):
        """Handle completion of package refresh."""
        if success:
            self.status_bar.showMessage(f"{package_type} package list refreshed successfully")
        else:
            self.status_bar.showMessage(f"Failed to refresh {package_type} package list")
        self.progress_bar.setVisible(False)

    def handle_error(self, error, package_type):
        """Handle errors from package operations."""
        self.status_bar.showMessage(f"Error with {package_type}: {error}")
        print(f"Error with {package_type}: {error}")

    def get_selected_package(self):
        """Get the currently selected package from the active tab."""
        current_tab = self.tab_widget.currentIndex()
        if current_tab == 0:  # APT tab
            table = self.apt_table
        else:  # Flatpak tab
            table = self.flatpak_table

        selected_items = table.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            name_item = table.item(row, 0)
            if name_item:
                return name_item.text()
        return None

    @staticmethod
    def _priv_apt_cmd(apt_args):
        cmd = ["env", "DEBIAN_FRONTEND=noninteractive", "apt-get"] + list(apt_args)
        if shutil.which("pkexec") and (os.geteuid() != 0 if hasattr(os, "geteuid") else True):
            return ["pkexec"] + cmd
        return cmd

    def install_selected(self):
        """Install the selected package."""
        package_name = self.get_selected_package()
        if not package_name or not re.match(r"^[a-zA-Z0-9.+_:-]+$", package_name):
            QMessageBox.warning(self, "No Selection", "Please select a valid package to install.")
            return

        current_tab = self.tab_widget.currentIndex()
        if current_tab == 0:
            command = self._priv_apt_cmd(["install", "-y", package_name])
            self.run_package_command(command, f"Installing APT package: {package_name}")
        else:
            command = ["flatpak", "install", "-y", "flathub", package_name]
            self.run_package_command(command, f"Installing Flatpak package: {package_name}")

    def remove_selected(self):
        """Remove the selected package."""
        package_name = self.get_selected_package()
        if not package_name or not re.match(r"^[a-zA-Z0-9.+_:-]+$", package_name):
            QMessageBox.warning(self, "No Selection", "Please select a valid package to remove.")
            return

        current_tab = self.tab_widget.currentIndex()
        if current_tab == 0:
            command = self._priv_apt_cmd(["remove", "-y", package_name])
            self.run_package_command(command, f"Removing APT package: {package_name}")
        else:
            command = ["flatpak", "uninstall", "-y", package_name]
            self.run_package_command(command, f"Removing Flatpak package: {package_name}")

    def update_selected(self):
        """Update the selected package."""
        package_name = self.get_selected_package()
        if not package_name or not re.match(r"^[a-zA-Z0-9.+_:-]+$", package_name):
            QMessageBox.warning(self, "No Selection", "Please select a valid package to update.")
            return

        current_tab = self.tab_widget.currentIndex()
        if current_tab == 0:
            command = self._priv_apt_cmd(["install", "--only-upgrade", "-y", package_name])
            self.run_package_command(command, f"Updating APT package: {package_name}")
        else:
            command = ["flatpak", "update", "-y", package_name]
            self.run_package_command(command, f"Updating Flatpak package: {package_name}")

    def run_package_command(self, command, operation_msg):
        """Run a package management command in a worker thread."""
        self.status_bar.showMessage(operation_msg)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate

        worker = self._start_worker(command)
        worker.output_received.connect(self.handle_command_output)
        worker.error_occurred.connect(self.handle_command_error)
        worker.finished.connect(self.command_finished)
        worker.start()

    def handle_command_output(self, output):
        """Handle output from package commands."""
        self.status_bar.showMessage(output)

    def handle_command_error(self, error):
        """Handle errors from package commands."""
        self.status_bar.showMessage(f"Error: {error}")
        QMessageBox.critical(self, "Command Error", f"An error occurred:\n{error}")

    def command_finished(self, success):
        """Handle completion of package commands."""
        self.progress_bar.setVisible(False)
        if success:
            self.status_bar.showMessage("Operation completed successfully")
            # Refresh package list after operation
            self.refresh_packages()
        else:
            self.status_bar.showMessage("Operation failed")


def main():
    app = QApplication(sys.argv)
    window = SoftwareCenter()
    app.aboutToQuit.connect(window.shutdown_workers)

    def _handle_sig(_signum, _frame):
        QTimer.singleShot(0, app.quit)

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, _handle_sig)
        except Exception:
            pass
    # Keep Python signal handlers responsive during Qt event loop
    sig_pump = QTimer()
    sig_pump.start(250)
    sig_pump.timeout.connect(lambda: None)

    window.show()
    rc = app.exec_()
    window.shutdown_workers()
    sys.exit(rc)


if __name__ == "__main__":
    main()
