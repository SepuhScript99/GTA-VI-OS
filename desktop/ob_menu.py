#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Openbox Pipe Menu Generator
Reads .desktop files and outputs an Openbox XML menu to stdout.
"""

import sys
import os
import glob
import re
import shutil
from xml.sax.saxutils import escape

APP_DIRS = [
    "/usr/share/applications",
    "/usr/local/share/applications",
    os.path.expanduser("~/.local/share/applications")
]

# Categories we care about for the menu, in display order
CATEGORY_MAP = {
    "Development": ["Development", "IDE", "Building"],
    "Graphics": ["Graphics", "Photography", "RasterGraphics"],
    "Internet": ["Network", "WebBrowser", "Email", "InstantMessaging"],
    "Multimedia": ["AudioVideo", "Audio", "Video", "Player"],
    "Office": ["Office", "WordProcessor", "Spreadsheet", "Presentation"],
    "Settings": ["Settings", "DesktopSettings", "HardwareSettings"],
    "System": ["System", "TerminalEmulator", "FileManager"],
    "Utilities": ["Utility", "TextTools", "Archiving"]
}

def parse_desktop_file(filepath: str) -> dict:
    """Parses a .desktop file and extracts Name, Exec, and Categories."""
    app_info = {}
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if line.startswith("Name="):
                    app_info["name"] = line.split("=", 1)[1]
                elif line.startswith("Exec="):
                    exec_cmd = line.split("=", 1)[1]
                    # Use regex to remove all Freedesktop field codes (e.g., %f, %u, %i, %c, %k)
                    # Then collapse multiple spaces and strip leading/trailing spaces
                    exec_cmd = re.sub(r'%[a-zA-Z]', '', exec_cmd)
                    exec_cmd = re.sub(r'\s+', ' ', exec_cmd).strip()
                    app_info["exec"] = exec_cmd
                elif line.startswith("Categories="):
                    app_info["categories"] = line.split("=", 1)[1].split(";")
                elif line.startswith("NoDisplay=") and line.split("=", 1)[1].lower() == "true":
                    return None # Skip hidden apps
                elif line.startswith("Terminal=") and line.split("=", 1)[1].lower() == "true":
                    app_info["terminal"] = "true"
                elif line.startswith("Type="):
                    if line.split("=", 1)[1] != "Application":
                        return None # Only show applications
                elif line.startswith("TryExec="):
                    try_exec_cmd = line.split("=", 1)[1]
                    if shutil.which(try_exec_cmd) is None:
                        return None # Skip if TryExec binary is missing
    except Exception as e:
        # Pipe menus must not pollute stdout with errors
        print(f"Error parsing {filepath}: {e}", file=sys.stderr)
        return None

    if "name" in app_info and "exec" in app_info:
        app_info.setdefault("categories", [])
        app_info.setdefault("terminal", "false")
        return app_info
    return None

def get_categorized_apps() -> dict:
    """Scans application directories and returns a categorized dict of apps."""
    apps_by_category = {cat: [] for cat in CATEGORY_MAP.keys()}
    seen_apps = set()

    for app_dir in APP_DIRS:
        for filepath in glob.glob(os.path.join(app_dir, "*.desktop")):
            app_info = parse_desktop_file(filepath)
            if not app_info:
                continue

            if app_info["name"] in seen_apps:
                continue
            seen_apps.add(app_info["name"])

            # Assign to the first matching category we support
            assigned = False
            for display_cat, keywords in CATEGORY_MAP.items():
                if any(keyword in app_info["categories"] for keyword in keywords):
                    apps_by_category[display_cat].append(app_info)
                    assigned = True
                    break

            # If no specific category matched, put in Utilities
            if not assigned:
                apps_by_category["Utilities"].append(app_info)

    # Sort apps alphabetically within each category
    for cat in apps_by_category:
        apps_by_category[cat].sort(key=lambda x: x["name"].lower())

    return apps_by_category

def generate_xml() -> str:
    """Generates the Openbox pipe menu XML."""
    categorized_apps = get_categorized_apps()
    term_bin = shutil.which("xfce4-terminal") or shutil.which("x-terminal-emulator") or "xterm"
    term_flag = "-x" if os.path.basename(term_bin) == "xfce4-terminal" else "-e"
    browser_bin = shutil.which("firefox-esr") or shutil.which("firefox") or "firefox-esr"

    xml_lines = ['<openbox_pipe_menu>']

    # Top level essentials
    xml_lines.append('  <item label="Applications Launcher">')
    xml_lines.append('    <action name="Execute"><command>python3 /opt/vice-os/vice_launcher.py</command></action>')
    xml_lines.append('  </item>')
    xml_lines.append('  <item label="Terminal">')
    xml_lines.append(f'    <action name="Execute"><command>{term_bin}</command></action>')
    xml_lines.append('  </item>')
    xml_lines.append('  <item label="File Manager">')
    xml_lines.append('    <action name="Execute"><command>thunar</command></action>')
    xml_lines.append('  </item>')
    xml_lines.append('  <item label="Web Browser">')
    xml_lines.append(f'    <action name="Execute"><command>{escape(browser_bin)}</command></action>')
    xml_lines.append('  </item>')
    xml_lines.append('  <separator />')

    for category, apps in categorized_apps.items():
        if not apps:
            continue

        xml_lines.append(f'  <menu id="apps-{category.lower()}" label="{category}">')
        for app in apps:
            safe_name = escape(app["name"])
            safe_exec = escape(app["exec"])

            # If the app requires a terminal, wrap the command cleanly for the detected terminal
            if app["terminal"] == "true":
                final_cmd = f"{escape(term_bin)} {term_flag} {safe_exec}"
            else:
                final_cmd = safe_exec

            xml_lines.append(f'    <item label="{safe_name}">')
            xml_lines.append(f'      <action name="Execute"><command>{final_cmd}</command></action>')
            xml_lines.append(f'    </item>')
        xml_lines.append('  </menu>')

    xml_lines.append('  <separator />')
    xml_lines.append('  <item label="Vice OS Settings">')
    xml_lines.append('    <action name="Execute"><command>python3 /opt/vice-os/vice_settings.py</command></action>')
    xml_lines.append('  </item>')
    xml_lines.append('  <item label="Restart Openbox">')
    xml_lines.append('    <action name="Reconfigure" />')
    xml_lines.append('  </item>')
    xml_lines.append('  <item label="Exit Openbox">')
    xml_lines.append('    <action name="Exit" />')
    xml_lines.append('  </item>')

    xml_lines.append('</openbox_pipe_menu>')
    return '\n'.join(xml_lines)

def main():
    # Ensure only XML is printed to stdout
    try:
        print(generate_xml())
    except Exception as e:
        # Fallback menu in case of catastrophic failure.
        # We do not include the exception string in the XML to prevent parsing errors.
        fallback_term = "xfce4-terminal" if os.path.exists("/usr/bin/xfce4-terminal") else "x-terminal-emulator"
        print(f"<openbox_pipe_menu><item label=\"Menu Error\"><action name=\"Execute\"><command>{fallback_term}</command></action></item></openbox_pipe_menu>", file=sys.stderr)
        print(f"<openbox_pipe_menu><item label=\"Menu Error (Check stderr)\"><action name=\"Execute\"><command>{fallback_term}</command></action></item></openbox_pipe_menu>")

if __name__ == "__main__":
    main()
