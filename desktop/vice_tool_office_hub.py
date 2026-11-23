#!/usr/bin/env python3
"""
GTA VI OS (Vice OS) — Vice Office Studio.
Cohesive GTA VI Office workspace hub launching LibreOffice Writer, Calc,
Impress, Draw, Math, and PDF Viewer (qpdfview), indexing recent documents
from ~/Documents and LibreOffice history, creating blank or starter template
files, and toggling LibreOffice GTA VI Dark / Paper Light UI themes.
Styled via vice_theme (Noto Sans CJK fallback).
"""

from datetime import datetime
import os
import shutil
import signal
import sys
import tempfile
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile

from PyQt5.QtCore import QProcess, QSize, Qt
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QPushButton, QVBoxLayout, QWidget
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
    from python.vice_utils import log_error, log_info  # noqa: E402
except ImportError:
    def log_info(msg: str) -> None:
        print(f"[INFO] {msg}")

    def log_error(msg: str) -> None:
        print(f"[ERROR] {msg}", file=sys.stderr)


OOR_NS = "http://openoffice.org/2001/registry"
XS_NS = "http://www.w3.org/2001/XMLSchema"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

LO_USER_XCU = os.path.expanduser("~/.config/libreoffice/4/user/registrymodifications.xcu")
LO_SKEL_XCU = "/etc/skel/.config/libreoffice/4/user/registrymodifications.xcu"

OFFICE_APPS = [
    {
        "id": "libreoffice-writer",
        "title": "Writer",
        "subtitle": "Documents & reports",
        "icon": "vice-tool-libreoffice-writer",
        "fallback": "libreoffice-writer",
        "cmd": ["libreoffice", "--writer"],
        "alt_bins": ["lowriter"],
    },
    {
        "id": "libreoffice-calc",
        "title": "Calc",
        "subtitle": "Spreadsheets & data",
        "icon": "vice-tool-libreoffice-calc",
        "fallback": "libreoffice-calc",
        "cmd": ["libreoffice", "--calc"],
        "alt_bins": ["localc"],
    },
    {
        "id": "libreoffice-impress",
        "title": "Impress",
        "subtitle": "Slide decks",
        "icon": "vice-tool-libreoffice-impress",
        "fallback": "libreoffice-impress",
        "cmd": ["libreoffice", "--impress"],
        "alt_bins": ["loimpress"],
    },
    {
        "id": "libreoffice-draw",
        "title": "Draw",
        "subtitle": "Diagrams & vectors",
        "icon": "vice-tool-libreoffice-draw",
        "fallback": "libreoffice-draw",
        "cmd": ["libreoffice", "--draw"],
        "alt_bins": ["lodraw"],
    },
    {
        "id": "libreoffice-math",
        "title": "Math",
        "subtitle": "Equation editor",
        "icon": "vice-tool-libreoffice-math",
        "fallback": "libreoffice-math",
        "cmd": ["libreoffice", "--math"],
        "alt_bins": ["lomath"],
    },
    {
        "id": "qpdfview",
        "title": "PDF Viewer",
        "subtitle": "Read & inspect PDFs",
        "icon": "vice-tool-qpdfview",
        "fallback": "qpdfview",
        "cmd": ["qpdfview"],
        "alt_bins": ["evince", "okular"],
    },
]

DOC_EXTENSIONS = {
    ".odt", ".ods", ".odp", ".odg", ".odf",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".pdf", ".rtf", ".csv", ".md", ".txt",
}

TEMPLATE_SPECS = [
    ("Writer Document (.odt)", ".odt", "writer", "application/vnd.oasis.opendocument.text"),
    ("Calc Spreadsheet (.ods)", ".ods", "calc", "application/vnd.oasis.opendocument.spreadsheet"),
    ("Impress Deck (.odp)", ".odp", "impress", "application/vnd.oasis.opendocument.presentation"),
    ("CSV Ledger (.csv)", ".csv", "calc", "text/csv"),
    ("Markdown Notes (.md)", ".md", "editor", "text/markdown"),
]


def _create_minimal_odf(dest_path: str, mime: str, kind: str, title_text: str) -> None:
    """Create a valid minimal OpenDocument (.odt/.ods/.odp) archive."""
    safe_title = (
        title_text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    manifest = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" '
        'manifest:version="1.2">\n'
        f'  <manifest:file-entry manifest:full-path="/" manifest:media-type="{mime}"/>\n'
        '  <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>\n'
        '</manifest:manifest>\n'
    )
    if kind == "writer":
        body = (
            "<office:text>"
            f'<text:h text:outline-level="1">{safe_title}</text:h>'
            "<text:p></text:p>"
            "</office:text>"
        )
    elif kind == "calc":
        body = (
            "<office:spreadsheet>"
            '<table:table table:name="Sheet1">'
            "<table:table-column/>"
            "<table:table-row>"
            f'<table:table-cell office:value-type="string"><text:p>{safe_title}</text:p></table:table-cell>'
            "</table:table-row>"
            "</table:table>"
            "</office:spreadsheet>"
        )
    else:
        body = (
            "<office:presentation>"
            '<draw:page draw:name="Slide1">'
            '<draw:frame svg:width="20cm" svg:height="3cm" svg:x="2cm" svg:y="2cm">'
            f"<draw:text-box><text:p>{safe_title}</text:p></draw:text-box>"
            "</draw:frame>"
            "</draw:page>"
            "</office:presentation>"
        )

    content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<office:document-content '
        'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
        'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
        'xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" '
        'xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0" '
        'office:version="1.2">\n'
        f"  <office:body>{body}</office:body>\n"
        "</office:document-content>\n"
    )
    with zipfile.ZipFile(dest_path, "w") as zf:
        zf.writestr("mimetype", mime.encode("utf-8"), compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/manifest.xml", manifest.encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("content.xml", content.encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED)


def _iter_xcu_items(root) -> list:
    return [el for el in root if el.tag in ("item", f"{{{OOR_NS}}}item")]


def _xcu_theme_entries(dark: bool) -> list:
    scheme = "/org.openoffice.Office.UI/ColorScheme/ColorSchemes/org.openoffice.Office.UI:ColorScheme['LibreOffice']"
    return [
        ("/org.openoffice.Office.Common/Misc", "SymbolStyle", "xs:string", "sifr_dark" if dark else "sifr"),
        ("/org.openoffice.Office.Common/View", "DarkMode", "xs:string", "true" if dark else "false"),
        ("/org.openoffice.Office.UI/ColorScheme", "CurrentColorScheme", "xs:string", "LibreOffice"),
        (f"{scheme}/AppBackground", "Color", "xs:int", "855573" if dark else "15593458"),
        (f"{scheme}/DocColor", "Color", "xs:int", "16777215"),
        (f"{scheme}/FontColor", "Color", "xs:int", "0"),
    ]


def _read_xcu_dark_state(path: str) -> bool:
    for cand in (path, LO_SKEL_XCU):
        if not os.path.isfile(cand):
            continue
        try:
            tree = ET.parse(cand)
            root = tree.getroot()
            for item in _iter_xcu_items(root):
                if item.attrib.get(f"{{{OOR_NS}}}path") == "/org.openoffice.Office.Common/View":
                    for prop in item.findall("prop"):
                        if prop.attrib.get(f"{{{OOR_NS}}}name") == "DarkMode":
                            val = prop.findtext("value", "").strip().lower()
                            return val == "true"
        except Exception:
            continue
    return True


def _apply_lo_theme(path: str, dark: bool) -> None:
    ET.register_namespace("oor", OOR_NS)
    ET.register_namespace("xs", XS_NS)
    ET.register_namespace("xsi", XSI_NS)

    parent = os.path.dirname(path)
    os.makedirs(parent, exist_ok=True)

    root = None
    for cand in (path, LO_SKEL_XCU):
        if os.path.isfile(cand):
            try:
                root = ET.parse(cand).getroot()
                break
            except Exception:
                root = None
    if root is None:
        root = ET.Element(f"{{{OOR_NS}}}items")

    for oor_path, prop_name, prop_type, value in _xcu_theme_entries(dark):
        target_item = None
        for item in _iter_xcu_items(root):
            if item.attrib.get(f"{{{OOR_NS}}}path") == oor_path:
                for prop in item.findall("prop"):
                    if prop.attrib.get(f"{{{OOR_NS}}}name") == prop_name:
                        target_item = item
                        break
            if target_item is not None:
                break

        if target_item is None:
            target_item = ET.SubElement(root, "item")
            target_item.set(f"{{{OOR_NS}}}path", oor_path)
            prop_el = ET.SubElement(target_item, "prop")
            prop_el.set(f"{{{OOR_NS}}}name", prop_name)
            prop_el.set(f"{{{OOR_NS}}}op", "fuse")
            if prop_type == "xs:int":
                prop_el.set(f"{{{OOR_NS}}}type", prop_type)
            val_el = ET.SubElement(prop_el, "value")
            val_el.text = value
        else:
            for prop in target_item.findall("prop"):
                if prop.attrib.get(f"{{{OOR_NS}}}name") == prop_name:
                    val_el = prop.find("value")
                    if val_el is None:
                        val_el = ET.SubElement(prop, "value")
                    val_el.text = value

    tree = ET.ElementTree(root)
    fd, tmp_path = tempfile.mkstemp(prefix="lo_xcu_", suffix=".tmp", dir=parent)
    os.close(fd)
    try:
        tree.write(tmp_path, encoding="utf-8", xml_declaration=True)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        raise


def _parse_lo_history(xcu_path: str) -> list:
    """Extract recent local file paths from LibreOffice PickList/OrderList."""
    if not os.path.isfile(xcu_path):
        return []
    found = []
    try:
        root = ET.parse(xcu_path).getroot()
        for item in _iter_xcu_items(root):
            oor_path = item.attrib.get(f"{{{OOR_NS}}}path", "")
            if "History" not in oor_path and "PickList" not in oor_path:
                continue
            for val in item.iter("value"):
                raw = (val.text or "").strip()
                if raw.startswith("file://"):
                    parsed = urllib.parse.urlparse(raw)
                    local = urllib.parse.unquote(parsed.path)
                    if os.path.isfile(local):
                        found.append(local)
    except Exception:
        pass
    return found


class ViceOfficeStudioApp(QMainWindow):
    """Main window for Vice Office Studio."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vice Office Studio — Vice OS")
        self.resize(960, 660)
        self.setMinimumSize(760, 520)
        icon = load_tool_icon("vice-tool-office-hub", "libreoffice-startcenter")
        if not icon.isNull():
            self.setWindowIcon(icon)

        self._dark_theme = _read_xcu_dark_state(LO_USER_XCU)
        self._init_ui()
        self._refresh_recent()
        self._sync_theme_controls()

    def _init_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("RootWidget")
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.setSpacing(12)

        self._header = make_header(
            title="Vice Office Studio",
            subtitle="LibreOffice suite launcher, quick document forge, and recent workspace files",
            icon_name="vice-tool-office-hub",
            badge_text="GTK3 SUITE",
            badge_variant="coral",
            parent=root,
        )
        self._theme_btn = make_button("Theme: Dark", variant="secondary", parent=self._header)
        self._theme_btn.clicked.connect(self._toggle_lo_theme)
        self._header.right_layout.insertWidget(0, self._theme_btn)
        layout.addWidget(self._header)

        # Suite Launcher Grid
        suite_card = make_card(
            title="Office Applications",
            subtitle="Launch LibreOffice apps with GTK3 GTA VI styling and crisp white document paper",
            parent=root,
        )
        app_grid = QGridLayout()
        app_grid.setSpacing(10)
        for idx, spec in enumerate(OFFICE_APPS):
            subtitle = spec["subtitle"].replace("&", "&&")
            btn = QPushButton(f"{spec['title']}\n{subtitle}", suite_card)
            btn.setMinimumHeight(64)
            btn.setCursor(Qt.PointingHandCursor)
            ic = load_tool_icon(spec["icon"], spec["fallback"])
            if not ic.isNull():
                btn.setIcon(ic)
                btn.setIconSize(QSize(32, 32))
            btn.clicked.connect(lambda _=False, s=spec: self._launch_suite_app(s))
            row, col = divmod(idx, 3)
            app_grid.addWidget(btn, row, col)
        suite_card.body_layout.addLayout(app_grid)
        layout.addWidget(suite_card)

        # Quick Blank / Template Document Creator
        create_card = make_card(title="Quick New Document", parent=root)
        crow = QHBoxLayout()
        crow.setSpacing(8)
        self._tpl_combo = QComboBox(create_card)
        for label, _ext, _kind, _mime in TEMPLATE_SPECS:
            self._tpl_combo.addItem(label)
        crow.addWidget(self._tpl_combo)

        self._doc_name = QLineEdit(create_card)
        self._doc_name.setPlaceholderText("Document name (e.g. Project_Brief)...")
        self._doc_name.returnPressed.connect(self._create_and_open_doc)
        crow.addWidget(self._doc_name, 1)

        create_btn = make_button("Create && Open", variant="primary", parent=create_card)
        create_btn.clicked.connect(self._create_and_open_doc)
        crow.addWidget(create_btn)
        create_card.body_layout.addLayout(crow)
        layout.addWidget(create_card)

        # Recent Documents Card
        recent_card = make_card(title="Recent Documents (~/Documents & LibreOffice History)", parent=root)
        r_top = QHBoxLayout()
        r_top.setSpacing(8)
        open_any_btn = make_button("Open File...", variant="secondary", parent=recent_card)
        open_any_btn.clicked.connect(self._browse_open_doc)
        r_top.addWidget(open_any_btn)

        open_dir_btn = make_button("Open ~/Documents", variant="secondary", parent=recent_card)
        open_dir_btn.clicked.connect(self._open_documents_dir)
        r_top.addWidget(open_dir_btn)

        r_top.addStretch(1)
        ref_btn = make_button("Refresh", variant="secondary", icon_name="view-refresh", parent=recent_card)
        ref_btn.clicked.connect(self._refresh_recent)
        r_top.addWidget(ref_btn)
        recent_card.body_layout.addLayout(r_top)

        self._recent_list = QListWidget(recent_card)
        self._recent_list.itemDoubleClicked.connect(self._open_recent_item)
        recent_card.body_layout.addWidget(self._recent_list, 1)

        open_sel_row = QHBoxLayout()
        self._status_lbl = QLabel("Ready.", recent_card)
        self._status_lbl.setObjectName("MutedLabel")
        open_sel_row.addWidget(self._status_lbl, 1)

        open_sel_btn = make_button("Open Selected", variant="primary", parent=recent_card)
        open_sel_btn.clicked.connect(self._open_selected_recent)
        open_sel_row.addWidget(open_sel_btn)
        recent_card.body_layout.addLayout(open_sel_row)
        layout.addWidget(recent_card, 1)

    def _sync_theme_controls(self) -> None:
        if self._dark_theme:
            self._theme_btn.setText("UI: GTA VI Dark")
            self._header.set_badge("DARK CHROME · WHITE PAPER", "coral")
        else:
            self._theme_btn.setText("UI: Paper Light")
            self._header.set_badge("LIGHT CHROME · WHITE PAPER", "aqua")

    def _toggle_lo_theme(self) -> None:
        new_dark = not self._dark_theme
        try:
            _apply_lo_theme(LO_USER_XCU, new_dark)
            self._dark_theme = new_dark
            self._sync_theme_controls()
            mode_str = "GTA VI Dark (sifr_dark)" if new_dark else "Paper Light (sifr)"
            self._status_lbl.setText(f"Updated LibreOffice UI theme to {mode_str} (reopen LibreOffice to apply).")
            log_info(f"Vice Office Studio set LibreOffice theme dark={new_dark}")
        except Exception as exc:
            log_error(f"Failed updating LibreOffice XCU: {exc}")
            QMessageBox.warning(self, "Theme Update Failed", str(exc))

    def _start_detached_office(self, prog: str, args: list) -> bool:
        docs = os.path.expanduser("~/Documents")
        workdir = docs if os.path.isdir(docs) else os.path.expanduser("~")
        env_bin = shutil.which("env")
        if env_bin:
            return bool(QProcess.startDetached(env_bin, ["SAL_USE_VCLPLUGIN=gtk3", prog] + args, workdir))
        return bool(QProcess.startDetached(prog, args, workdir))

    def _launch_suite_app(self, spec: dict, target_file: str = "") -> None:
        cmd = list(spec["cmd"])
        prog = shutil.which(cmd[0])
        args = cmd[1:]
        if not prog:
            for alt in spec.get("alt_bins", []):
                found = shutil.which(alt)
                if found:
                    prog = found
                    args = []
                    break
        if not prog and spec["id"] == "qpdfview":
            local_pdf = os.path.join(_HERE, "vice_pdf_viewer.py")
            opt_pdf = "/opt/vice-os/vice_pdf_viewer.py"
            pdf_script = opt_pdf if os.path.isfile(opt_pdf) else local_pdf
            if os.path.isfile(pdf_script):
                prog = shutil.which("python3") or sys.executable
                args = [pdf_script]

        if not prog:
            QMessageBox.warning(
                self, "Application Not Installed",
                f"Could not find '{cmd[0]}'. Install the corresponding Debian package."
            )
            return

        if target_file:
            args.append(target_file)

        if self._start_detached_office(prog, args):
            self._status_lbl.setText(f"Launched {spec['title']}.")
            log_info(f"Vice Office Studio launched {spec['title']}")
        else:
            QMessageBox.warning(self, "Launch Failed", f"Failed starting {prog}.")

    def _create_and_open_doc(self) -> None:
        docs_dir = os.path.expanduser("~/Documents")
        os.makedirs(docs_dir, exist_ok=True)
        label, ext, kind, mime = TEMPLATE_SPECS[self._tpl_combo.currentIndex()]
        raw_name = self._doc_name.text().strip()
        if not raw_name:
            raw_name = f"Leonida_Note_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        safe_name = "".join(c if c.isalnum() or c in "-_ ." else "_" for c in raw_name).strip()
        if not safe_name:
            safe_name = "Untitled"
        if not safe_name.lower().endswith(ext):
            safe_name += ext
        dest = os.path.join(docs_dir, safe_name)

        try:
            if ext in (".odt", ".ods", ".odp"):
                _create_minimal_odf(dest, mime, kind, os.path.splitext(safe_name)[0])
            elif ext == ".csv":
                with open(dest, "w", encoding="utf-8", newline="\n") as fp:
                    fp.write("Item,Category,Amount,Notes\n")
            else:
                with open(dest, "w", encoding="utf-8", newline="\n") as fp:
                    fp.write(f"# {os.path.splitext(safe_name)[0]}\n\nCreated in Vice Office Studio.\n")
        except OSError as exc:
            QMessageBox.critical(self, "Create Failed", str(exc))
            return

        self._doc_name.clear()
        self._refresh_recent()
        self._open_path(dest)

    def _open_path(self, path: str) -> None:
        if not os.path.isfile(path):
            QMessageBox.warning(self, "Missing File", f"File does not exist:\n{path}")
            return
        ext = os.path.splitext(path)[1].lower()
        if ext == ".pdf":
            self._launch_suite_app(OFFICE_APPS[5], path)
            return
        if ext in (".odt", ".doc", ".docx", ".rtf"):
            self._launch_suite_app(OFFICE_APPS[0], path)
            return
        if ext in (".ods", ".xls", ".xlsx", ".csv"):
            self._launch_suite_app(OFFICE_APPS[1], path)
            return
        if ext in (".odp", ".ppt", ".pptx"):
            self._launch_suite_app(OFFICE_APPS[2], path)
            return
        if ext == ".odg":
            self._launch_suite_app(OFFICE_APPS[3], path)
            return

        opener = shutil.which("xdg-open") or shutil.which("geany") or shutil.which("mousepad")
        if opener:
            QProcess.startDetached(opener, [path], os.path.dirname(path))
            self._status_lbl.setText(f"Opened {os.path.basename(path)}")

    def _browse_open_doc(self) -> None:
        start_dir = os.path.expanduser("~/Documents")
        if not os.path.isdir(start_dir):
            start_dir = os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Document",
            start_dir,
            "Office & Docs (*.odt *.ods *.odp *.odg *.docx *.xlsx *.pptx *.pdf *.csv *.md *.txt);;All Files (*)",
        )
        if path:
            self._open_path(path)

    def _open_documents_dir(self) -> None:
        docs_dir = os.path.expanduser("~/Documents")
        os.makedirs(docs_dir, exist_ok=True)
        fm = shutil.which("thunar") or shutil.which("pcmanfm") or shutil.which("xdg-open")
        if fm:
            QProcess.startDetached(fm, [docs_dir], docs_dir)

    def _refresh_recent(self) -> None:
        self._recent_list.clear()
        seen = set()
        candidates = []

        for path in _parse_lo_history(LO_USER_XCU):
            if path not in seen:
                seen.add(path)
                candidates.append(path)

        docs_dir = os.path.expanduser("~/Documents")
        if os.path.isdir(docs_dir):
            for root_dir, dirs, files in os.walk(docs_dir):
                depth = root_dir[len(docs_dir):].count(os.sep)
                if depth >= 2:
                    dirs[:] = []
                for fname in files:
                    if os.path.splitext(fname)[1].lower() in DOC_EXTENSIONS:
                        full = os.path.join(root_dir, fname)
                        if full not in seen:
                            seen.add(full)
                            candidates.append(full)

        def _mtime(p: str) -> float:
            try:
                return os.path.getmtime(p)
            except OSError:
                return 0.0

        candidates.sort(key=_mtime, reverse=True)
        for path in candidates[:40]:
            try:
                ts = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M")
            except OSError:
                ts = ""
            item = QListWidgetItem(f"{os.path.basename(path)}   —   {path}  ({ts})")
            item.setData(Qt.UserRole, path)
            self._recent_list.addItem(item)

        if self._recent_list.count() == 0:
            empty = QListWidgetItem("No recent documents found in ~/Documents yet — create one above.")
            empty.setFlags(Qt.NoItemFlags)
            self._recent_list.addItem(empty)
        self._status_lbl.setText(f"Indexed {len(candidates)} document(s).")

    def _open_recent_item(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.UserRole)
        if path:
            self._open_path(path)

    def _open_selected_recent(self) -> None:
        item = self._recent_list.currentItem()
        if item is not None:
            path = item.data(Qt.UserRole)
            if path:
                self._open_path(path)

    def closeEvent(self, event) -> None:
        event.accept()


def main() -> None:
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    apply_app_theme(app)
    win = ViceOfficeStudioApp()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
