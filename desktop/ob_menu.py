#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) Openbox Pipe Menu Generator.
Reads .desktop files and outputs an Openbox XML menu to stdout.
"""

import glob
import os
import re
import shlex
import shutil
import sys
from xml.sax.saxutils import escape, quoteattr

APP_DIRS = [
    "/usr/share/applications",
    "/usr/local/share/applications",
    os.path.expanduser("~/.local/share/applications"),
]

# Categories we care about for the menu, in display order
CATEGORY_MAP = {
    "Development": ["Development", "IDE", "Building"],
    "Graphics": ["Graphics", "Photography", "RasterGraphics"],
    "Internet": ["Network", "WebBrowser", "Email", "InstantMessaging"],
    "Multimedia": ["AudioVideo", "Audio", "Video", "Player"],
    "Office": ["Office", "WordProcessor", "Spreadsheet", "Presentation"],
    "Security": ["Security", "Forensics", "SystemSecurity"],
    "Settings": ["Settings", "DesktopSettings", "HardwareSettings"],
    "System": ["System", "TerminalEmulator", "FileManager"],
    "Utilities": ["Utility", "TextTools", "Archiving"],
}


def parse_desktop_file(filepath: str) -> dict:
    """Parse a .desktop file's [Desktop Entry] section and extract Name, Exec, Categories."""
    app_info = {}
    in_desktop_entry = False
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("["):
                    if line == "[Desktop Entry]":
                        in_desktop_entry = True
                        continue
                    if in_desktop_entry:
                        break
                    continue
                if not in_desktop_entry or "=" not in line:
                    continue

                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()

                if key == "Name":
                    app_info["name"] = val
                elif key == "Exec":
                    exec_cmd = re.sub(r"%[a-zA-Z]", "", val)
                    exec_cmd = re.sub(r"\s+", " ", exec_cmd).strip()
                    app_info["exec"] = exec_cmd
                elif key == "Categories":
                    app_info["categories"] = [c.strip() for c in val.split(";") if c.strip()]
                elif key in ("NoDisplay", "Hidden") and val.lower() == "true":
                    return None
                elif key == "OnlyShowIn":
                    envs = {e.strip().upper() for e in val.split(";") if e.strip()}
                    if envs and not (envs & {"OPENBOX", "XFCE", "LXDE", "GTK"}):
                        return None
                elif key == "NotShowIn":
                    envs = {e.strip().upper() for e in val.split(";") if e.strip()}
                    if "OPENBOX" in envs:
                        return None
                elif key == "Terminal" and val.lower() == "true":
                    app_info["terminal"] = "true"
                elif key == "Type" and val != "Application":
                    return None
                elif key == "TryExec" and val and shutil.which(val) is None:
                    return None
    except Exception as e:
        # Pipe menus must not pollute stdout with errors
        print(f"Error parsing {filepath}: {e}", file=sys.stderr)
        return None

    if "name" in app_info and "exec" in app_info and app_info["exec"]:
        try:
            tokens = shlex.split(app_info["exec"])
        except ValueError:
            tokens = app_info["exec"].split()
        if not tokens:
            return None
        if tokens[0] == "su-to-root" and shutil.which("su-to-root") is None:
            return None
        app_info.setdefault("categories", [])
        app_info.setdefault("terminal", "false")
        return app_info
    return None


def get_categorized_apps() -> dict:
    """Scan application directories and return a categorized dict of apps."""
    apps_by_category = {cat: [] for cat in CATEGORY_MAP.keys()}
    seen_apps = set()

    for app_dir in APP_DIRS:
        if not os.path.isdir(app_dir):
            continue
        for filepath in sorted(glob.glob(os.path.join(app_dir, "*.desktop"))):
            app_info = parse_desktop_file(filepath)
            if not app_info:
                continue

            if app_info["name"] in seen_apps:
                continue
            seen_apps.add(app_info["name"])

            assigned = False
            for display_cat, keywords in CATEGORY_MAP.items():
                if any(keyword in app_info["categories"] for keyword in keywords):
                    apps_by_category[display_cat].append(app_info)
                    assigned = True
                    break

            if not assigned:
                apps_by_category["Utilities"].append(app_info)

    for cat in apps_by_category:
        apps_by_category[cat].sort(key=lambda x: x["name"].lower())

    return apps_by_category


def generate_xml() -> str:
    """Generate the Openbox pipe menu XML."""
    categorized_apps = get_categorized_apps()
    term_bin = shutil.which("xfce4-terminal") or shutil.which("x-terminal-emulator") or "xterm"
    term_flag = "-x" if os.path.basename(term_bin) == "xfce4-terminal" else "-e"
    browser_bin = shutil.which("firefox-esr") or shutil.which("firefox") or "firefox-esr"

    xml_lines = ["<openbox_pipe_menu>"]

    xml_lines.append('  <item label="Applications Launcher">')
    xml_lines.append('    <action name="Execute"><command>python3 /opt/vice-os/vice_launcher.py</command></action>')
    xml_lines.append("  </item>")
    xml_lines.append('  <item label="Terminal">')
    xml_lines.append(f'    <action name="Execute"><command>{escape(term_bin)}</command></action>')
    xml_lines.append("  </item>")
    xml_lines.append('  <item label="File Manager">')
    xml_lines.append('    <action name="Execute"><command>thunar</command></action>')
    xml_lines.append("  </item>")
    xml_lines.append('  <item label="Web Browser">')
    xml_lines.append(f'    <action name="Execute"><command>{escape(browser_bin)}</command></action>')
    xml_lines.append("  </item>")
    xml_lines.append("  <separator />")

    for category, apps in categorized_apps.items():
        if not apps:
            continue

        xml_lines.append(f'  <menu id={quoteattr(f"apps-{category.lower()}")} label={quoteattr(category)}>')
        for app in apps:
            safe_name_attr = quoteattr(app["name"])
            safe_exec = escape(app["exec"])

            if app["terminal"] == "true":
                final_cmd = f"{escape(term_bin)} {term_flag} {safe_exec}"
            else:
                final_cmd = safe_exec

            xml_lines.append(f"    <item label={safe_name_attr}>")
            xml_lines.append(f'      <action name="Execute"><command>{final_cmd}</command></action>')
            xml_lines.append("    </item>")
        xml_lines.append("  </menu>")

    xml_lines.append("  <separator />")
    xml_lines.append('  <item label="Vice OS Settings">')
    xml_lines.append('    <action name="Execute"><command>python3 /opt/vice-os/vice_settings.py</command></action>')
    xml_lines.append("  </item>")
    xml_lines.append('  <item label="Restart Openbox">')
    xml_lines.append('    <action name="Reconfigure" />')
    xml_lines.append("  </item>")
    xml_lines.append('  <item label="Exit Openbox">')
    xml_lines.append('    <action name="Exit" />')
    xml_lines.append("  </item>")

    xml_lines.append("</openbox_pipe_menu>")
    return "\n".join(xml_lines)


def main():
    # Ensure only XML is printed to stdout
    try:
        print(generate_xml())
    except Exception:
        # Fallback menu must remain valid XML without leaking exception details.
        fallback_term = "xfce4-terminal" if os.path.exists("/usr/bin/xfce4-terminal") else "x-terminal-emulator"
        print(
            f'<openbox_pipe_menu><item label="Menu Error"><action name="Execute"><command>{fallback_term}</command></action></item></openbox_pipe_menu>',
            file=sys.stderr,
        )
        print(
            f'<openbox_pipe_menu><item label="Menu Error (Check stderr)"><action name="Execute"><command>{fallback_term}</command></action></item></openbox_pipe_menu>'
        )


if __name__ == "__main__":
    main()
