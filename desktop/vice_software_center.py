#!/usr/bin/env python3
"""
Vice Software Center
A package management GUI for Vice OS with apt and flatpak support.
"""

import sys
import subprocess
import json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QProgressBar, QComboBox, QCheckBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QBrush


class PackageWorkerThread(QThread):
    """Worker thread for running package management commands."""
    output_received = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self, command):
        super().__init__()
        self.command = command

    def run(self):
        try:
            process = subprocess.Popen(
                self.command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )

            # Read output in real-time
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    self.output_received.emit(output.strip())

            # Check for errors
            stderr = process.stderr.read()
            if stderr:
                self.error_occurred.emit(stderr.strip())

            # Wait for process to complete
            return_code = process.wait()
            self.finished.emit(return_code == 0)

        except Exception as e:
            self.error_occurred.emit(str(e))
            self.finished.emit(False)


class SoftwareCenter(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice Software Center")
        self.setGeometry(100, 100, 1000, 700)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0a0a0a;
                color: #00ffff;
            }
            QTabWidget::pane {
                border: 1px solid #00ffff;
                background-color: #0a0a0a;
            }
            QTabBar::tab {
                background-color: #1a1a1a;
                color: #00ffff;
                padding: 8px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #00ffff;
                color: #0a0a0a;
            }
            QLabel {
                color: #00ffff;
            }
            QLineEdit {
                background-color: #1a1a1a;
                color: #00ffff;
                border: 1px solid #00ffff;
                padding: 5px;
            }
            QPushButton {
                background-color: #1a1a1a;
                color: #00ffff;
                border: 1px solid #00ffff;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #00ffff;
                color: #0a0a0a;
            }
            QTableWidget {
                background-color: #1a1a1a;
                color: #00ffff;
                gridline-color: #00ffff;
                border: 1px solid #00ffff;
            }
            QHeaderView::section {
                background-color: #00ffff;
                color: #0a0a0a;
                padding: 5px;
            }
            QProgressBar {
                border: 1px solid #00ffff;
                background-color: #1a1a1a;
                color: #00ffff;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #00ffff;
            }
            QComboBox {
                background-color: #1a1a1a;
                color: #00ffff;
                border: 1px solid #00ffff;
                padding: 5px;
            }
            QCheckBox {
                color: #00ffff;
            }
            QCheckBox::indicator {
                width: 13px;
                height: 13px;
            }
            QCheckBox::indicator:unchecked {
                background-color: #1a1a1a;
                border: 1px solid #00ffff;
            }
            QCheckBox::indicator:checked {
                background-color: #00ffff;
                border: 1px solid #00ffff;
            }
        """)

        self.init_ui()
        self.refresh_packages()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Header
        header_label = QLabel("Vice Software Center")
        header_label.setAlignment(Qt.AlignCenter)
        header_label.setStyleSheet("font-size: 24px; font-weight: bold; margin: 10px;")
        layout.addWidget(header_label)

        # Tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # Create tabs
        self.apt_tab = self.create_package_tab("APT")
        self.flatpak_tab = self.create_package_tab("Flatpak")

        self.tab_widget.addTab(self.apt_tab, "APT Packages")
        self.tab_widget.addTab(self.flatpak_tab, "Flatpak Packages")

        # Status bar
        self.status_bar = self.statusBar()
        self.status_bar.setStyleSheet("background-color: #1a1a1a; color: #00ffff;")
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

    def create_package_tab(self, package_type):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Search and filter controls
        controls_layout = QHBoxLayout()

        search_label = QLabel("Search:")
        controls_layout.addWidget(search_label)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(f"Search {package_type} packages...")
        self.search_edit.textChanged.connect(self.filter_packages)
        controls_layout.addWidget(self.search_edit)

        # Refresh button
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_packages)
        controls_layout.addWidget(refresh_btn)

        layout.addLayout(controls_layout)

        # Package table
        self.package_table = QTableWidget()
        self.package_table.setColumnCount(4)
        self.package_table.setHorizontalHeaderLabels(["Name", "Version", "Description", "Status"])
        self.package_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.package_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.package_table)

        # Action buttons
        action_layout = QHBoxLayout()

        self.install_btn = QPushButton("Install")
        self.install_btn.clicked.connect(self.install_selected)
        action_layout.addWidget(self.install_btn)

        self.remove_btn = QPushButton("Remove")
        self.remove_btn.clicked.connect(self.remove_selected)
        action_layout.addWidget(self.remove_btn)

        self.update_btn = QPushButton("Update")
        self.update_btn.clicked.connect(self.update_selected)
        action_layout.addWidget(self.update_btn)

        layout.addLayout(action_layout)

        # Store reference to table based on package type
        if package_type == "APT":
            self.apt_table = self.package_table
        else:
            self.flatpak_table = self.package_table

        return tab

    def refresh_packages(self):
        """Refresh package lists for both APT and Flatpak."""
        self.status_bar.showMessage("Refreshing package lists...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress

        # Refresh APT packages
        apt_thread = PackageWorkerThread("apt list --installed 2>/dev/null")
        apt_thread.output_received.connect(lambda output: self.process_apt_output(output))
        apt_thread.error_occurred.connect(lambda error: self.handle_error(error, "APT"))
        apt_thread.finished.connect(lambda success: self.package_refresh_finished(success, "APT"))
        apt_thread.start()

        # Refresh Flatpak packages
        flatpak_thread = PackageWorkerThread("flatpak list --columns=application,version,branch,origin")
        flatpak_thread.output_received.connect(lambda output: self.process_flatpak_output(output))
        flatpak_thread.error_occurred.connect(lambda error: self.handle_error(error, "Flatpak"))
        flatpak_thread.finished.connect(lambda success: self.package_refresh_finished(success, "Flatpak"))
        flatpak_thread.start()

    def process_apt_output(self, output):
        """Process output from apt list command."""
        if output.startswith("Listing...") or output == "":
            return

        # Parse apt output: package/version,now arch [installed]
        parts = output.split('/')
        if len(parts) >= 2:
            name = parts[0]
            rest = parts[1].split()
            if rest:
                version = rest[0]
                description = self.get_apt_description(name)
                status = "Installed" if "installed" in output else "Available"
                self.add_apt_package(name, version, description, status)

    def process_flatpak_output(self, output):
        """Process output from flatpak list command."""
        if output == "" or "Application" in output:
            return

        parts = output.split('\t')
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
                f"apt show {package_name} 2>/dev/null | grep -E '^Description:' | head -1",
                shell=True, capture_output=True, text=True
            )
            if result.stdout:
                return result.stdout.replace("Description:", "").strip()
        except:
            pass
        return "No description available"

    def get_flatpak_description(self, app_id):
        """Get description for a Flatpak application."""
        try:
            result = subprocess.run(
                f"flatpak info {app_id} 2>/dev/null | grep -E '^Description:' | head -1",
                shell=True, capture_output=True, text=True
            )
            if result.stdout:
                return result.stdout.replace("Description:", "").strip()
        except:
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

        # Color coding based on status
        if status == "Installed":
            for col in range(4):
                item = self.apt_table.item(row_position, col)
                if item:
                    item.setBackground(QBrush(QColor(0, 255, 255, 30)))
                    item.setForeground(QBrush(QColor(0, 0, 0)))

    def add_flatpak_package(self, name, version, description, status):
        """Add a package to the Flatpak table."""
        row_position = self.flatpak_table.rowCount()
        self.flatpak_table.insertRow(row_position)
        self.flatpak_table.setItem(row_position, 0, QTableWidgetItem(name))
        self.flatpak_table.setItem(row_position, 1, QTableWidgetItem(version))
        self.flatpak_table.setItem(row_position, 2, QTableWidgetItem(description))
        self.flatpak_table.setItem(row_position, 3, QTableWidgetItem(status))

        # Color coding based on status
        if status == "Installed":
            for col in range(4):
                item = self.flatpak_table.item(row_position, col)
                if item:
                    item.setBackground(QBrush(QColor(0, 255, 255, 30)))
                    item.setForeground(QBrush(QColor(0, 0, 0)))

    def filter_packages(self):
        """Filter packages based on search text."""
        search_text = self.search_edit.text().lower()
        current_tab = self.tab_widget.currentIndex()

        if current_tab == 0:  # APT tab
            table = self.apt_table
        else:  # Flatpak tab
            table = self.flatpak_table

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

    def install_selected(self):
        """Install the selected package."""
        package_name = self.get_selected_package()
        if not package_name:
            QMessageBox.warning(self, "No Selection", "Please select a package to install.")
            return

        current_tab = self.tab_widget.currentIndex()
        if current_tab == 0:  # APT
            command = f"sudo apt install -y {package_name}"
            self.run_package_command(command, f"Installing APT package: {package_name}")
        else:  # Flatpak
            command = f"flatpak install -y flathub {package_name}"
            self.run_package_command(command, f"Installing Flatpak package: {package_name}")

    def remove_selected(self):
        """Remove the selected package."""
        package_name = self.get_selected_package()
        if not package_name:
            QMessageBox.warning(self, "No Selection", "Please select a package to remove.")
            return

        current_tab = self.tab_widget.currentIndex()
        if current_tab == 0:  # APT
            command = f"sudo apt remove -y {package_name}"
            self.run_package_command(command, f"Removing APT package: {package_name}")
        else:  # Flatpak
            command = f"flatpak uninstall -y {package_name}"
            self.run_package_command(command, f"Removing Flatpak package: {package_name}")

    def update_selected(self):
        """Update the selected package."""
        package_name = self.get_selected_package()
        if not package_name:
            QMessageBox.warning(self, "No Selection", "Please select a package to update.")
            return

        current_tab = self.tab_widget.currentIndex()
        if current_tab == 0:  # APT
            command = f"sudo apt install --only-upgrade -y {package_name}"
            self.run_package_command(command, f"Updating APT package: {package_name}")
        else:  # Flatpak
            command = f"flatpak update -y {package_name}"
            self.run_package_command(command, f"Updating Flatpak package: {package_name}")

    def run_package_command(self, command, operation_msg):
        """Run a package management command in a worker thread."""
        self.status_bar.showMessage(operation_msg)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate

        worker = PackageWorkerThread(command)
        worker.output_received.connect(lambda output: self.handle_command_output(output))
        worker.error_occurred.connect(lambda error: self.handle_command_error(error))
        worker.finished.connect(lambda success: self.command_finished(success))
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
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()