import sys,collections,json,csv,os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QFileDialog, QPushButton,
                             QTextEdit, QLineEdit, QLabel, QTreeWidget, QTreeWidgetItem,
                             QVBoxLayout, QHBoxLayout, QSplitter, QMessageBox, QStatusBar,
                             QStyle, QComboBox, QPlainTextEdit, QTabWidget,QMenu, QCheckBox, QWidgetAction)
from PyQt5.QtWidgets import (QAction)
from PyQt5.QtGui import (QTextCursor, QTextCharFormat, QColor, QIcon, QPainter, QCursor, QFont)
from PyQt5.QtCore import QSettings, QRect, QSize, Qt
from datetime import datetime
from functools import partial


__author__      = "Verification Team Analog STI - E.braud , V.Regnauld"
__copyright__   = "Copyright 2025-2030, NXP"
__credits__     = ["NXP"]
__license__     = "GPL"
__version__     = "V1.01"
__part__        = "ihm"
__status__      = "Development"
__maintainer__  = "Emmanuel braud"
__email__       = "emmanuel.braud@nxp.com"

'***************************************************************************************************'
version_info = [
                'V1.01 : E.Braud - 18/12/2025 - first version of IHM to andalyse and repair Json dB\n'
                ]
'***************************************************************************************************'

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.line_number_area_paint_event(event)

class JsonEditor(QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self.lineNumberArea = LineNumberArea(self)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.update_line_number_area_width(0)
    def line_number_area_width(self):
        digits = len(str(max(1, self.blockCount())))
        return 10 + self.fontMetrics().horizontalAdvance('9') * digits
    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)
    def update_line_number_area(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def line_number_area_paint_event(self, event):

        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), QColor("#252526"))
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible():
                painter.setPen(QColor("#6A9955"))
                painter.drawText(0, top, self.lineNumberArea.width() - 5, self.fontMetrics().height(), Qt.AlignRight, str(block_number + 1))
            block = block.next()
            top = bottom
            if block.isValid():
                bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1


def move_key(data, key, new_position):
    """
    move key in dico
    data : dict d'origine
    key : clé à déplacer
    new_position : nouvelle position (0 = début)
    """
    if key not in data: return data  # nothing to do
    items = list(data.items())
    # elemnt remove
    for i, (k, v) in enumerate(items):
        if k == key:
            elem = items.pop(i)
            break
    # position to secure
    new_position = max(0, min(new_position, len(items)))
    # insert in new position
    items.insert(new_position, elem)
    return dict(items)


class JsonExplorer(QMainWindow):

    def __init__(self):
        super().__init__()
        self.boo_cell_empty = None
        self.csv_file_list_iso_signal_enum = None
        self.updating_tree = False
        self.boo_highlight_key=False
        self.current_file = ""
        self.setWindowTitle("JSON Explorer Pro")
        self.setWindowIcon(QIcon("icons/json.ico"))
        self.resize_and_center(100)
        # self.resize(1000, 800)
        self.setAcceptDrops(True)
        self.init_ui()
        self.create_menu()
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        copyright_label = QLabel("© 2026 Verification AMS | JSON Explorer Pro v1.0")
        copyright_label.setStyleSheet(""" color: lightgray; font-size: 9pt; padding-right: 10px; """)
        self.statusbar.addPermanentWidget(copyright_label)
        self.apply_style()
    ####################################################
    # UI
    ####################################################
    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        self.tabs = QTabWidget()
        toolbar = QHBoxLayout()
        self.settings = QSettings("JsonExplorer", "JsonExplorerPro")
        self.recent_files = self.settings.value("recent_files", [], type=list)
        self.btn_open = QPushButton("Open")
        self.btn_open.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.btn_save = QPushButton("Save")
        self.btn_save.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.btn_save_as = QPushButton("Save As")
        self.btn_save_as.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        self.btn_validate = QPushButton("Validate")
        self.btn_validate.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self.btn_expand = QPushButton("Expand")
        self.btn_expand.setIcon(self.style().standardIcon(QStyle.SP_ArrowDown))
        self.btn_collapse = QPushButton("Collapse")
        self.btn_collapse.setIcon(self.style().standardIcon(QStyle.SP_ArrowUp))

        self.btn_quit = QPushButton("Quit")
        self.btn_quit.setIcon(self.style().standardIcon(QStyle.SP_DialogCloseButton))
        self.btn_quit.setStyleSheet("""
                                    QPushButton{ background:#C62828; color:white; border:none; border-radius:6px;
                                    padding:8px 15px; min-width:120px; min-height:35px; }
                                    QPushButton:hover{ background:#E53935; }
                                """)
        # toolbar.addWidget(self.btn_open)
        # toolbar.addWidget(self.btn_save)
        # toolbar.addWidget(self.btn_save_as)
        toolbar.addWidget(self.btn_refresh)
        toolbar.addWidget(self.btn_validate)
        toolbar.addWidget(self.btn_expand)
        toolbar.addWidget(self.btn_collapse)
        toolbar.addWidget(QLabel("Root Keys"))

        self.combo_root = QComboBox()
        self.combo_root.setMinimumWidth(250)

        toolbar.addWidget(self.combo_root)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Search"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("search key or value...")
        self.search_edit.setFixedWidth(400)
        toolbar.addWidget(self.search_edit)
        main_layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Horizontal)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Key", "Value"])
        self.tree.setStyleSheet("""
                        QTreeWidget { background:#2D2D2D; color:white; border:1px solid #555; }
                        QHeaderView::section { background:#404040; color:#6A9955; font-weight:bold; padding:5px; border:none; }
                        """)
        self.tree.itemClicked.connect(self.highlight_key)
        self.tree.setFixedHeight(500)
        self.tree.setColumnWidth(0, 300)  # Key
        self.tree.setColumnWidth(1, 300)  # Value
        self.tree.expandToDepth(0)
        self.editor = JsonEditor() #QTextEdit()
        self.editor.setStyleSheet("""
                                    QPlainTextEdit{ background:#FFFFFF; color:#000000; 
                                    border:1px solid #555; font-family:Consolas; font-size:11pt; }
                                    """)
        splitter.addWidget(self.tree)
        splitter.addWidget(self.editor)
        splitter.setSizes([500, 900])
        main_layout.addWidget(splitter)
        stats_layout = QHBoxLayout()
        self.lbl_stats = QLabel("Objects : 0")
        stats_layout.addWidget(self.lbl_stats)
        stats_layout.addStretch()
        main_layout.addLayout(stats_layout)
        self.status = QStatusBar()
        main_layout.addWidget(self.status)
        self.setLayout(main_layout)

        # --------------------------------------------------------------------------
        self.explorer_tab = QWidget()
        explorer_layout = QVBoxLayout(self.explorer_tab)
        explorer_layout.addWidget(splitter)
        explorer_layout.addWidget(self.lbl_stats)
        self.tabs.addTab(self.explorer_tab, QIcon("icons/open.png"),"Explorer")
        main_layout.addWidget(self.tabs)
        #--------------------------------------------------------------------------
        self.correction_tab = QWidget()
        correction_layout = QVBoxLayout(self.correction_tab)
        correction_tab_layout= QHBoxLayout()
        self.btn_validate_keys = QPushButton("Check Duplicate Keys")
        icon = QIcon.fromTheme("view-refresh")
        if icon.isNull(): icon = self.style().standardIcon(QStyle.SP_BrowserReload)
        self.btn_validate_keys.setIcon(icon)

        self.btn_general_repair = QPushButton("General Repair")
        icon = QIcon.fromTheme("tools-check-spelling")
        if icon.isNull(): icon = self.style().standardIcon(QStyle.SP_DialogApplyButton)
        self.btn_general_repair.setIcon(icon)

        self.btn_load_csv = QPushButton("📄 Load CSV LS and ISO")

        self.repair_actions = {}
        repairs = ["Load CSV described Level Shifter list  and ISO Signal",
                   "[General][field_options] enum and none iso na repaired",
                   "[General][field_options] [Dual Mode Lsh] added or repaired",
                   "[Fields][field_options] format [Dual Mode Lsh] key and choose right LS with rw key",
                   "[Fields] cell ,Iso Signal , Dual Mode Lsh and group repaired",
                   "[Fields]  ISO signal corresponding to Level shifter described in cell key repaired",
                   '[General][field_options][RW Mode] repaired ["True", "enum", ["r-", "rw", "-w"], "True"]',
                   "[General][ie_options][Cell][2] = list Level shifter from CSV repaired",
                   "[General][ie_options][Cell] = ['True', 'enum', list ISO name from CSV, 'True', 'none']  repaired",
                   "[General][ie_options] enum and none iso na repaired",
                   "[Interface_elements][field_options] format [Dual Mode Lsh] key and choose right LS with direction key",
                   "[Interface_elements] cell ,Iso Signal , Dual Mode Lsh and group repaired",
                   "[Interface_elements] attached ISO signal vs level shifter indicated in cell repaired",
                   "[General] [ie_options] added ['Input', 'Output'] repaired",
                   "[General] [date] now and [Version] +1 updated",
                   "Sort some keys Cell Iso Signal Dual Mode Lsh and group in [Fields]",
                   "Sort some keys Cell Iso Signal Dual Mode Lsh  in [Interface_elements]",
                   "Sort some keys  Iso Signal Dual Mode Lsh  in [General][field_options]",
                   "Update [General][Date] and [General][version]+1",
                   "Update [General][_comment_repairs_XXXXXXXX] some information to indicate which script corrects Json"
                   ]
        menu = QMenu(self)
        for name in repairs:
            cb = QCheckBox(name)
            cb.setChecked(True)
            action = QWidgetAction(menu)
            action.setDefaultWidget(cb)
            menu.addAction(action)
            self.repair_actions[name] = cb
        menu.addSeparator()
        select_all_cb = QCheckBox("Select All")
        select_all_cb.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
        def select_all(state):
            checked = state != 0
            for cb in self.repair_actions.values():
                cb.setChecked(checked)
        select_all_cb.stateChanged.connect(select_all)
        action = QWidgetAction(menu)
        action.setDefaultWidget(select_all_cb)
        menu.addAction(action)
        menu.addSeparator()
        validate_btn = QPushButton("Valider")
        validate_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
        action = QWidgetAction(menu)
        action.setDefaultWidget(validate_btn)
        menu.addAction(action)
        validate_btn.clicked.connect(self.repair_keys_in_general_part)
        self.btn_general_repair.setMenu(menu)

        self.btn_format = QPushButton("✨ Format JSON")
        self.btn_sort = QPushButton("📑 Sort Keys")
        correction_tab_layout.addWidget(self.btn_validate_keys)
        correction_tab_layout.addWidget(self.btn_general_repair)
        # correction_tab_layout.addWidget(self.btn_load_csv)
        # correction_tab_layout.addWidget(menu)
        # correction_tab_layout.addWidget(self.btn_format)
        # correction_tab_layout.addWidget(self.btn_sort)
        correction_layout.addLayout(correction_tab_layout)
        self.correction_log = QTextEdit()
        self.correction_log.setReadOnly(True)
        correction_layout.addWidget(self.correction_log)
        self.tabs.addTab(self.correction_tab,QIcon("icons/json_repair.png"), "Correction Json RMI")
        # --------------------------------------------------------------------------
        self.report_tab = QWidget()

        report_layout = QVBoxLayout(self.report_tab)
        self.btn_health = QPushButton("🩺 Health Check")
        self.health_report = QTextEdit()
        self.health_report.setReadOnly(True)
        report_layout.addWidget(self.btn_health)
        report_layout.addWidget(self.health_report)
        self.tabs.addTab(self.report_tab, QIcon("icons/reporting.png"),"Reporting")
        self.btn_health.clicked.connect(self.json_health_check)
        # --------------------------------------------------------------------------
        # explorer_layout.addWidget(self.logs)
        main_layout.addWidget(QLabel("Logs"))
        self.logs = QTextEdit()
        self.logs.setMaximumHeight(200)
        self.logs.setReadOnly(True)
        main_layout.addWidget(self.logs)

        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.btn_quit)
        main_layout.addLayout(bottom_layout)

        # self.btn_open.clicked.connect(self.load_json)
        # self.btn_save.clicked.connect(self.save_json)
        # self.btn_save_as.clicked.connect(self.save_as_json)
        self.btn_refresh.clicked.connect(self.refresh_tree)
        self.btn_validate.clicked.connect(self.validate_json)
        self.btn_expand.clicked.connect(self.tree.expandAll)
        self.btn_collapse.clicked.connect(self.tree.collapseAll)

        self.search_edit.textChanged.connect(self.filter_tree)
        self.combo_root.currentTextChanged.connect(self.select_root_key)
        self.btn_validate_keys.clicked.connect(self.check_duplicate_keys)
        # self.btn_general_repair.clicked.connect(self.repair_keys_in_general_part)
        self.btn_load_csv.clicked.connect(self.load_csv_file)
        self.btn_quit.clicked.connect(self.close)
        self.tree.itemChanged.connect(self.on_tree_changed)
        self.tree.currentItemChanged.connect(self.on_current_changed)
        self.tree.itemSelectionChanged.connect(self.on_selection_changed)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_tree_menu)
        self.combo_root.setStyleSheet(""" QComboBox{ background:#2D2D2D; color:white; border:1px solid #555; 
                                        border-radius:4px; padding:4px; }
                                        QComboBox::drop-down{ width:25px; }
                                        QComboBox QAbstractItemView{ background:#2D2D2D; color:white;
                                         selection-background-color:#1976D2; }""")

        self.tabs.setTabEnabled(1, False)  # Désactive l'onglet n°1
        self.tabs.setTabEnabled(2, False)  # Désactive l'onglet n°2

    def resize_and_center(self, margin=50):
        screen = QApplication.screenAt(QCursor.pos())
        if screen is None:
            screen = QApplication.primaryScreen()
        geo = screen.availableGeometry()
        width = int(geo.width()/2) - 3 * margin
        height = int(geo.height()/2) - 1 * margin
        self.setGeometry( geo.x() + margin,  geo.y() + margin,  width, height  )
        screen_geometry = screen.availableGeometry()
        window_geometry = self.frameGeometry()
        x = screen_geometry.x() + (screen_geometry.width() - window_geometry.width()) // 2
        y = screen_geometry.y() + (screen_geometry.height() - window_geometry.height()) // 2
        self.setMinimumHeight(height-margin)
        self.setMinimumWidth(width-4*margin)
        self.move(x, y)

    def create_menu(self):

        menubar = self.menuBar()
        file_menu = menubar.addMenu(self.style().standardIcon(QStyle.SP_DirIcon), "File")
        open_action = QAction(self.style().standardIcon(QStyle.SP_DialogOpenButton),"Open", self)
        open_action.triggered.connect(self.load_json)
        open_action.setShortcut("Ctrl+L")
        save_action = QAction(self.style().standardIcon(QStyle.SP_DialogSaveButton),"Save", self)
        save_action.triggered.connect(self.save_json)
        save_action.setShortcut("Ctrl+S")
        save_as_action = QAction(self.style().standardIcon(QStyle.SP_DialogSaveButton),"SaveAs", self)
        save_as_action.triggered.connect(self.save_as_json)
        exit_action = QAction(self.style().standardIcon(QStyle.SP_DialogCloseButton), "Quit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(open_action)
        file_menu.addAction(save_action)
        file_menu.addAction(save_as_action)
        file_menu.addAction(exit_action)
        file_menu.addSeparator()
        self.recent_menu = file_menu.addMenu("Recent Files")
        self.update_recent_menu()

    def validate_repairs(self):
        selected_repairs = [name for name, cb in self.repair_actions.items() if cb.isChecked()]

        print("Réparations sélectionnées :", selected_repairs)

        # Fermer le menu
        # self.btn_repair.menu().hide()

        # # Lancer la réparation
        # self.repair_json(selected_repairs)

    def add_recent_file(self, filepath):

        if filepath in self.recent_files:
            self.recent_files.remove(filepath)
        self.recent_files.insert(0, filepath)
        self.recent_files = self.recent_files[:10]
        self.settings.setValue("recent_files", self.recent_files)
        self.update_recent_menu()

    def update_recent_menu(self):

        self.recent_menu.clear()
        for file_path in self.recent_files:
            action = QAction(file_path, self)
            action.triggered.connect(lambda checked, p=file_path: self.load_json_file(p))
            self.recent_menu.addAction(action)

        if len(self.recent_files) > 0:
            self.recent_menu.addSeparator()
            clear_action = QAction("Clear History", self)
            clear_action.triggered.connect(self.clear_history)
            self.recent_menu.addAction(clear_action)

    def clear_history(self):

        self.recent_files = []
        self.settings.setValue("recent_files", [])
        self.update_recent_menu()
        self.log("History cleared")

    def highlight_key(self, item, column):
        key = item.text(0)
        if key == "root": return
        editor = self.editor
        # remise à zéro des couleurs
        cursor = editor.textCursor()
        cursor.select(QTextCursor.Document)
        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#FFFFFF"))
        cursor.mergeCharFormat(fmt)
        # recherche de la clé
        cursor = editor.document().find(f'"{key}"')
        if cursor.isNull(): return
        # sélection trouvée
        editor.setTextCursor(cursor)
        highlight = QTextCharFormat()
        # highlight.setBackground(QColor("#000000"))
        highlight.setForeground(QColor("Red"))
        cursor.mergeCharFormat(highlight)
        editor.setTextCursor(cursor)
        # centrer la vue sur la clé
        editor.ensureCursorVisible()

    def show_tree_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item: return
        menu = QMenu(self)
        delete_action = menu.addAction("🗑 Delete Node")
        expand_action = menu.addAction("➕ Expand")
        collapse_action = menu.addAction("➖ Collapse")
        action = menu.exec_(self.tree.viewport().mapToGlobal(pos))
        if action == delete_action:self.delete_node(item)
        elif action == expand_action:item.setExpanded(True)
        elif action == collapse_action:item.setExpanded(False)

    def delete_node(self, item):
        if item is None: return
        self.updating_tree = True
        self.tree.blockSignals(True)
        try:
            parent = item.parent()
            if parent:
                parent.removeChild(item)
            else:
                idx = self.tree.indexOfTopLevelItem(item)
                if idx >= 0: self.tree.takeTopLevelItem(idx)
        finally:
            self.tree.blockSignals(False)
            self.updating_tree = False
        self.update_json_from_tree()


    def on_tree_changed(self, item, column):
        if self.updating_tree: return
        if item is None: return
        if self.tree.topLevelItemCount() == 0: return
        self.update_json_from_tree()

    def on_current_changed(self, current, previous):
        if self.updating_tree: return
        if current is None: return

    def on_selection_changed(self):
        if self.updating_tree: return
        item = self.tree.currentItem()
        if item is None: return

    def update_json_from_tree(self):
        if self.updating_tree: return
        try:
            self.updating_tree = True
            data = self.tree_to_json()
            self.editor.blockSignals(True)
            self.editor.setPlainText(json.dumps(data, indent=4, ensure_ascii=False))
            self.editor.blockSignals(False)
        except Exception as e:
            print("JSON update error:", e)
        finally:
            self.updating_tree = False
            self.boo_highlight_key = False

    def tree_to_json(self):
        result = {}
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item is None:
                continue
            key = item.text(0)
            result[key] = self.item_to_dict(item)
        return result

    def item_to_dict(self, item):
        if item is None: return None
        if item.childCount() == 0: return item.text(1)
        data = {}
        for i in range(item.childCount()):
            child = item.child(i)
            if child is None: continue
            data[child.text(0)] = self.item_to_dict(child)
        return data

    def check_duplicate_keys(self):
        text = self.editor.toPlainText()
        duplicates = []
        def detect_duplicates(pairs):
            counter = collections.Counter(key for key, value in pairs)
            for key, count in counter.items():
                if count > 1:
                    duplicates.append(key)
            return dict(pairs)
        try:
            json.loads(text, object_pairs_hook=detect_duplicates)
            if duplicates:
                self.correction_log.append("❌ Duplicate keys found:")
                for key in sorted(set(duplicates)):
                    self.correction_log.append(f"   • {key}")
            else:
                self.correction_log.append("✅ No duplicate keys found")
        except Exception as e:
            self.correction_log.append(f"❌ JSON Error : {e}")

    def repair_keys_in_general_part(self):
        try:
            data = json.loads(self.editor.toPlainText())
            self.editor.blockSignals(True)
            repaired = self.normalize_general(data)
            txt = json.dumps(repaired, indent=4, ensure_ascii=False)
            self.editor.setPlainText(txt)
            self.editor.blockSignals(False)
        except Exception as e:
            self.correction_log.append(f"❌ {e}")

    def normalize_general(self,obj):
        self.boo_cell_empty=True

        selected_repairs = [name for name, cb in self.repair_actions.items() if cb.isChecked()]
        if "Load CSV described Level Shifter list  and ISO Signal" in selected_repairs:
            self.load_csv_file()

        if isinstance(obj, dict):
            if "[General][field_options] enum and none iso na repaired" in selected_repairs:
                if obj.get('General', None).get('field_options', None) is not None:
                    obj.get('General', None).get('field_options', None)["RW Mode"] = ["True", "enum", ["r-", "rw", "-w"], "True"]
                    self.correction_log.append("✅ [General][field_options][RW Mode] =[True, enum, [r-, rw, -w], True] repaired")
                    obj.get('General', None).get('field_options', None)["Dual Mode Lsh"] = ["False", "enum", ["no", "yes"], "True", "no"]
                    self.correction_log.append("✅ [General][field_options][Dual Mode Lsh] =[False, enum, [no, yes], True, no] repaired")
                    obj.get('General', None).get('field_options', None).get("Cell", None)[1] = "enum"
                    self.correction_log.append("✅ [General][field_options][Cell] [1] = 'enum' repaired")
                    obj.get('General', None).get('field_options', None).get("Cell", None)[2] = self.csv_file_list_level_shifter[1:]
                    self.correction_log.append("✅ [General][field_options][Cell][2] = list Level shifter from CSV repaired")
                    obj.get('General', None).get('field_options', None)["Iso Signal"]= ["True", "enum", self.csv_file_list_iso_signal_enum[1:], "True", "none"]
                    self.correction_log.append("✅ [General][field_options][Cell] = ['True', 'enum', list ISO name from CSV, 'True', 'none']  repaired")

                ie_options = obj.get("General", {}).get("field_options", {})
                for key, value in ie_options.items():
                    if not isinstance(value, list) or len(value) < 3: continue
                    if value[1] != "enum":
                        if isinstance(value[2], list) and value[2]: value[1] = "enum"
                    if value[1] == "enum":
                        value[2] = [item for item in value[2] if str(item).lower() not in ("na", "none")]
                        value[2].insert(0, "none")
                self.correction_log.append("✅ [General][field_options] enum and none iso na repaired")
            # ---------------------------------------------------------------------------------------------
            # Added enum with Key Dual Mode Lsh if not exist
            # ---------------------------------------------------------------------------------------------
            if "[General][field_options] [Dual Mode Lsh] added or repaired" in selected_repairs:
                boo_dual_mode_field_found = False
                key_dual_mode_name = ""
                for element_gen_key in obj.get('General', None).get('field_options', None).keys():
                    if 'dual mode lsh' in str(element_gen_key).lower():
                        key_dual_mode_name = element_gen_key
                        boo_dual_mode_field_found = True
                if not boo_dual_mode_field_found:
                    obj.get('General', None).get('field_options', None)["Dual Mode Lsh"] = ["False", "enum", ["no", "yes"], "True", "no"]
                else:
                    obj.get('General', None).get('field_options', None)["Dual Mode Lsh"] = obj.get('General', None).get('field_options', None).pop(key_dual_mode_name)

                self.correction_log.append("✅ [General][field_options] [Dual Mode Lsh] added or repaired")
            # ---------------------------------------------------------------------------------------------
            # Add Key cell or Correct value for field corresponding to previous enum
            # ---------------------------------------------------------------------------------------------
            if obj.get('Fields', None) is not None:
                if "[Fields][field_options] format [Dual Mode Lsh] key and choose right LS with rw key" in selected_repairs:
            # ---------------------------------------------------------------------------------------------
            # Update Key dual Mode LSH in case not correct write with Capitalize first letter of each words
            # ---------------------------------------------------------------------------------------------
                    old = "Dual Mode LSH"
                    new = "Dual Mode Lsh"
                    for field_key, field in obj.get('Fields', None).items():
                        if field_key.startswith("f_"):
                            if old in field: field[new] = field.pop(old)
                            if obj.get('Fields', None)[field_key].get('cell', None) is None and \
                                    obj.get('Fields', None)[field_key].get('Iso Signal', None) is None and \
                                    (obj.get('Fields', None)[field_key].get('group', None) == "" or \
                                     obj.get('Fields', None)[field_key].get('group', None) is None) and \
                                    obj.get('Fields', None)[field_key].get('name', None) != "RESERVED":
                                if obj.get('Fields', None)[field_key].get('rw', None) == "rw":
                                    if len([x for x in self.csv_file_list_level_shifter if "d2a_ls" in x]) == 1:
                                        obj.get('Fields', None)[field_key]['cell'] = \
                                        [x for x in self.csv_file_list_level_shifter if "d2a_ls" in x][0]
                                elif obj.get('Fields', None)[field_key].get('rw', None) == "r-":
                                    if len([x for x in self.csv_file_list_level_shifter if "a2d_ls" in x]) == 1:
                                        obj.get('Fields', None)[field_key]['cell'] = \
                                        [x for x in self.csv_file_list_level_shifter if "a2d_ls" in x][0]
                    self.correction_log.append("✅ [Fields][field_options] format [Dual Mode Lsh] key and choose right LS with rw key")
            # ---------------------------------------------------------------------------------------------
            # Added in fields some keys if not exist
            # ---------------------------------------------------------------------------------------------
            if "[Fields] cell ,Iso Signal , Dual Mode Lsh and group repaired" in selected_repairs:
                for element_field_key, element_field_val in obj.get('Fields', None).items():
                    for data_keys in element_field_val.keys():
                        if str(element_field_val[data_keys]).lower() == 'na': element_field_val[data_keys] = 'none'
                    if element_field_val.get('cell', None) is None: element_field_val['cell'] = ''
                    if element_field_val.get('Iso Signal', None) is None: element_field_val['Iso Signal'] = 'none'
                    if element_field_val.get('Dual Mode Lsh', None) is None: element_field_val['Dual Mode Lsh'] = 'no'
                    if element_field_val.get('group', None) is None: element_field_val['group'] = ''
            # ---------------------------------------------------------------------------------------------
            # Kibo if cell="" used ls level shifter vs direction
            # ---------------------------------------------------------------------------------------------
                    if (obj.get('Fields', None)[element_field_key].get('cell', None) == "") and \
                            (obj.get('Fields', None)[element_field_key].get('group', None) == "") and \
                            obj.get('Fields', None)[element_field_key].get('name', None) != "RESERVED" and self.boo_cell_empty:
                        if obj.get('Fields', None)[element_field_key].get('rw', None) == "rw":
                            if len([x for x in self.csv_file_list_level_shifter if "d2a_ls" in x]) == 1:
                                obj.get('Fields', None)[element_field_key]['cell'] = [x for x in self.csv_file_list_level_shifter if "d2a_ls" in x][0]
                        elif obj.get('Fields', None)[element_field_key].get('rw', None) == "r-":
                            if len([x for x in self.csv_file_list_level_shifter if "a2d_ls" in x]) == 1:
                                obj.get('Fields', None)[element_field_key]['cell'] = [x for x in self.csv_file_list_level_shifter if "a2d_ls" in x][0]
                    elif obj.get('Fields', None)[element_field_key].get('group', None) != "" and \
                            len(obj.get('Fields', None)[element_field_key].get('cell', None)) < 6:
                        obj.get('Fields', None)[element_field_key]['cell'] = "none"
                self.correction_log.append("✅ [Fields] cell ,Iso Signal , Dual Mode Lsh and group repaired")
            # ---------------------------------------------------------------------------------------------
            # Attached ISO signal corresponding to Level shifter described in cell key
            # ---------------------------------------------------------------------------------------------
            if "[Fields]  ISO signal corresponding to Level shifter described in cell key repaired" in selected_repairs:
                for element_field_key, element_field_val in obj.get('Fields', None).items():
                    if obj.get('Fields', None)[element_field_key].get('cell', None) is not None:
                        if obj.get('Fields', None)[element_field_key].get('rw', None) == "rw":
                            if len([x for x in self.csv_file_list_level_shifter if
                                    obj.get('Fields', None)[element_field_key].get('cell', None) in x]) == 1:
                                obj.get('Fields', None)[element_field_key]['Iso Signal'] = \
                                    self.csv_file_list_iso_signal[self.csv_file_list_level_shifter.index(
                                        obj.get('Fields', None)[element_field_key].get('cell', None))]
                        elif obj.get('Fields', None)[element_field_key].get('rw', None) == "r-":
                            if len([x for x in self.csv_file_list_level_shifter if
                                    obj.get('Fields', None)[element_field_key].get('cell', None) in x]) == 1:
                                obj.get('Fields', None)[element_field_key]['Iso Signal'] = \
                                    self.csv_file_list_iso_signal[self.csv_file_list_level_shifter.index(
                                        obj.get('Fields', None)[element_field_key].get('cell', None))]
                self.correction_log.append("✅ [Fields]  ISO signal corresponding to Level shifter described in cell key repaired")

            # ---------------------------------------------------------------------------------------------
            # Correct enum in general part - RW mode
            # ---------------------------------------------------------------------------------------------
            if '[General][field_options][RW Mode] repaired ["True", "enum", ["r-", "rw", "-w"], "True"]' in selected_repairs:
                if obj.get('General', None).get('field_options', None).get("RW Mode", None) is not None:
                    obj.get('General', None).get('field_options', None)["RW Mode"] = ["True", "enum", ["r-", "rw", "-w"], "True"]
                    self.correction_log.append('✅ [General][field_options] ["RW Mode"] ["True", "enum", ["r-", "rw", "-w"], "True"] repaired')
            # ---------------------------------------------------------------------------------------------
            # Correct enum in general part - Interface
            # ---------------------------------------------------------------------------------------------
            if "[General][ie_options][Cell][2] = list Level shifter from CSV repaired" in selected_repairs:
                if obj.get('General', None).get('ie_options', None).get("Cell", None)[1] != "enum" and self.csv_file_list_level_shifter is not None:
                    obj.get('General', None).get('ie_options', None).get("Cell", None)[1] = "enum"
                    obj.get('General', None).get('ie_options', None).get("Cell", None)[2] = self.csv_file_list_level_shifter[1:]
                    self.correction_log.append("✅ [General][ie_options][Cell][2] = list Level shifter from CSV repaired")
            if "[General][ie_options][Cell] = ['True', 'enum', list ISO name from CSV, 'True', 'none']  repaired" in selected_repairs:
                if obj.get('General', None).get('ie_options', None).get("Iso Signal", None) is None and self.csv_file_list_iso_signal_enum is not None:
                    obj.get('General', None).get('ie_options', None)["Iso Signal"] = ["True", "any", self.csv_file_list_iso_signal_enum[1:], "True", "na"]
                    self.correction_log.append("✅ [General][ie_options][Cell] = ['True', 'enum', list ISO name from CSV, 'True', 'none']  repaired")
            # ---------------------------------------------------------------------------------------------
            if "[General][ie_options] enum and none iso na repaired" in selected_repairs:
                ie_options = obj.get("General", {}).get("ie_options", {})
                for key, value in ie_options.items():
                    if not isinstance(value, list) or len(value) < 3: continue
                    if value[1] != "enum":
                        if isinstance(value[2], list) and value[2]: value[1] = "enum"
                    if value[1] == "enum":
                        value[2] = [item for item in value[2] if str(item).lower() not in ("na", "none")]
                        value[2].insert(0, "none")
                self.correction_log.append("✅ [General][ie_options] enum and none iso na repaired")
            # ---------------------------------------------------------------------------------------------
            # Added enum with Key Dual Mode Lsh if not exist
            # ---------------------------------------------------------------------------------------------
            if "[General][ie_options] Dual Mode Lsh  repaired" in selected_repairs:
                boo_dual_mode_ie_found = False
                key_dual_mode_ie_name = ""
                for element_gen_key in obj.get('General', None).get('ie_options', None).keys():
                    if 'dual mode lsh' in str(element_gen_key).lower():
                        key_dual_mode_ie_name = element_gen_key
                        boo_dual_mode_ie_found = True
                if not boo_dual_mode_ie_found:
                    obj.get('General', None).get('ie_options', None)["Dual Mode Lsh"] = ["False", "enum", ["no", "yes"], "True", "no"]
                else:
                    obj.get('General', None).get('ie_options', None)["Dual Mode Lsh"] = obj.get('General', None).get('ie_options', None).pop(key_dual_mode_ie_name)
                self.correction_log.append("✅ [General][ie_options] Dual Mode Lsh  repaired")
            # ---------------------------------------------------------------------------------------------
            # Add Key cell or Correct value for field corresponding to previous enum
            # ---------------------------------------------------------------------------------------------
            if obj.get('Interface_elements', None) is not None:
                if "[Interface_elements][field_options] format [Dual Mode Lsh] key and choose right LS with direction key" in selected_repairs:
            # ---------------------------------------------------------------------------------------------
            # Update Key dual Mode LSH in case not correct write with Capitalize first letter of each words
            # ---------------------------------------------------------------------------------------------
                    old = "Dual Mode LSH"
                    new = "Dual Mode Lsh"
                    for interface_key, field in obj.get('Interface_elements', None).items():
                        if interface_key.startswith("ie_"):
                            if old in field: field[new] = field.pop(old)
                            if obj.get('Interface_elements', None)[interface_key].get('cell', None) is None and \
                                    obj.get('Interface_elements', None)[interface_key].get('Iso Signal', None) is None and \
                                    (obj.get('Interface_elements', None)[interface_key].get('group', None) == "" or \
                                     obj.get('Interface_elements', None)[interface_key].get('group', None) is None) and \
                                    obj.get('Interface_elements', None)[interface_key].get('name', None) != "RESERVED":
                                if obj.get('Interface_elements', None)[interface_key].get('direction', None) == "Input":
                                    if len([x for x in self.csv_file_list_level_shifter if "d2a_ls" in x]) == 1: obj.get('Interface_elements', None)[interface_key]['cell'] =\
                                        [x for x in self.csv_file_list_level_shifter if "d2a_ls" in x][0]
                                elif obj.get('Interface_elements', None)[interface_key].get('direction', None) == "Output":
                                    if len([x for x in self.csv_file_list_level_shifter if "a2d_ls" in x]) == 1: obj.get('Interface_elements', None)[interface_key]['cell'] = \
                                        [x for x in self.csv_file_list_level_shifter if "a2d_ls" in x][0]
                    self.correction_log.append("✅ [Interface_elements][field_options] format [Dual Mode Lsh] key and choose right LS with direction key")
            # ---------------------------------------------------------------------------------------------
            # Added in Interface_elements some keys if not exist
            # ---------------------------------------------------------------------------------------------
                if "[Interface_elements] cell ,Iso Signal , Dual Mode Lsh and group repaired" in selected_repairs:
                    for element_interface_key, element_field_val in obj.get('Interface_elements', None).items():
                        for data_keys in element_field_val.keys():
                            if str(element_field_val[data_keys]).lower() == 'na': element_field_val[data_keys] = 'none'
                        if element_field_val.get('cell', None) is None: element_field_val['cell'] = ''
                        if element_field_val.get('Iso Signal', None) is None: element_field_val['Iso Signal'] = 'none'
                        if element_field_val.get('Dual Mode Lsh', None) is None: element_field_val[
                            'Dual Mode Lsh'] = 'no'
                        if element_field_val.get('group', None) is None: element_field_val['group'] = ''
            # # ---------------------------------------------------------------------------------------------
            # # Kibo if cell="" used ls level shifter vs direction
            # # ---------------------------------------------------------------------------------------------
                    if (obj.get('Interface_elements', None)[element_interface_key].get('cell', None) == "") and (obj.get('Interface_elements', None)[element_interface_key].get('group', None) == "") and self.boo_cell_empty:
                        if obj.get('Interface_elements', None)[element_interface_key].get('direction', None) == "Input":
                            if len([x for x in self.csv_file_list_level_shifter if "d2a_ls" in x]) == 1: obj.get('Interface_elements', None)[element_interface_key]['cell'] = [x for x in self.csv_file_list_level_shifter if "d2a_ls" in x][0]
                        elif obj.get('Interface_elements', None)[element_interface_key].get('direction', None) == "Output":
                            if len([x for x in self.csv_file_list_level_shifter if "a2d_ls" in x]) == 1: obj.get('Interface_elements', None)[element_interface_key]['cell'] = [x for x in self.csv_file_list_level_shifter if "a2d_ls" in x][0]
                    elif obj.get('Interface_elements', None)[element_interface_key].get('group', None) != "" and len(obj.get('Interface_elements', None)[element_interface_key].get('cell', None)) < 6:
                        obj.get('Interface_elements', None)[element_interface_key]['cell'] = "none"
                    self.correction_log.append("✅ [Interface_elements] cell ,Iso Signal , Dual Mode Lsh and group repaired")
            # ---------------------------------------------------------------------------------------------
            # Attached ISO signal corresponding to Level shifter described in cell key
            # ---------------------------------------------------------------------------------------------
                if "[Interface_elements] attached ISO signal vs level shifter indicated in cell repaired" in selected_repairs:
                    for element_interface_key, element_field_val in obj.get('Interface_elements', None).items():
                        if obj.get('Interface_elements', None)[element_interface_key].get('cell', None) is not None:
                            if obj.get('Interface_elements', None)[element_interface_key].get(
                                    'direction', None) == "Input":
                                if len([x for x in self.csv_file_list_level_shifter if obj.get('Interface_elements', None)[element_interface_key].get('cell', None) in x]) == 1:
                                    obj.get('Interface_elements', None)[element_interface_key]['Iso Signal'] = \
                                        self.csv_file_list_iso_signal[self.csv_file_list_level_shifter.index(obj.get('Interface_elements', None)[element_interface_key].get('cell', None))]
                            elif obj.get('Interface_elements', None)[element_interface_key].get('direction', None) == "Output":
                                if len([x for x in self.csv_file_list_level_shifter if obj.get('Interface_elements', None)[element_interface_key].get('cell', None) in x]) == 1:
                                    obj.get('Interface_elements', None)[element_interface_key]['Iso Signal'] = \
                                        self.csv_file_list_iso_signal[self.csv_file_list_level_shifter.index(
                                            obj.get('Interface_elements', None)[element_interface_key].get('cell', None))]
                    self.correction_log.append("✅ [Interface_elements] attached ISO signal vs level shifter indicated in cell repaired")
            # ---------------------------------------------------------------------------------------------
            # Correct enum in general part - Interface
            # ---------------------------------------------------------------------------------------------
            if "[General] [ie_options] added ['Input', 'Output'] repaired" in selected_repairs:
                for element_in_general in obj.get('General', None).get('ie_options', None).keys():
                    if element_in_general == 'Direction':
                        if obj.get('General', None).get('ie_options', None).get(element_in_general, None)[1] == "any":
                            obj.get('General', None).get('ie_options', None).get(element_in_general, None)[2] = ['Input', 'Output']
                            obj.get('General', None).get('ie_options', None).get(element_in_general, None)[1] = 'enum'
                        elif obj.get('General', None).get('ie_options', None).get(element_in_general, None)[1] == "enum":
                            obj.get('General', None).get('ie_options', None).get(element_in_general, None)[2] = ['Input', 'Output']
                # ---------------------------------------------------------------------------------------------
                # Correct interface element value for field corresponding to previous enum
                # ---------------------------------------------------------------------------------------------
                    if obj.get('Interface_elements', None) is not None:
                        for element_field in obj.get('Interface_elements', None).values():
                            if element_field.get('direction', None) != "":
                                element_field['direction'] = str(element_field['direction']).capitalize()
                self.correction_log.append("✅ [General] [ie_options] added ['Input', 'Output'] repaired")
            # ---------------------------------------------------------------------------------------------
            # Update General date and version
            # ---------------------------------------------------------------------------------------------
            if "[General] [date] now and [Version] +1 updated" in selected_repairs:
                if obj.get('General', None).get('date', None) is not None:
                    obj['General']['date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if obj.get('General', None).get('version', None) is not None:
                    obj['General']['version'] += 1
                self.correction_log.append("✅ [General] [date] now and [Version] +1 updated")
            # ---------------------------------------------------------------------------------------------
            # Move Iso signal and Cell on top of each fields dico
            # ---------------------------------------------------------------------------------------------
            # list_key=['cell','Iso Signal','Dual Mode Lsh','group']
            if "Sort some keys Cell Iso Signal Dual Mode Lsh and group in [Fields]" in selected_repairs:
                if obj.get('Fields', None) is not None:
                    for element_field_key, element_field_val in obj.get('Fields', None).items():
                        obj.get('Fields', None)[element_field_key] = move_key(element_field_val, 'cell', 1)
                    for element_field_key, element_field_val in obj.get('Fields', None).items():
                        obj.get('Fields', None)[element_field_key] = move_key(element_field_val, "Iso Signal", 2)
                    for element_field_key, element_field_val in obj.get('Fields', None).items():
                        obj.get('Fields', None)[element_field_key] = move_key(element_field_val, "Dual Mode Lsh", 3)
                    for element_field_key, element_field_val in obj.get('Fields', None).items():
                        obj.get('Fields', None)[element_field_key] = move_key(element_field_val, "group", 3)
                    self.correction_log.append("✅ Sort some keys Cell Iso Signal Dual Mode Lsh and group in [Fields]")
            if "Sort some keys Cell Iso Signal Dual Mode Lsh  in [Interface_elements]" in selected_repairs:
                if obj.get('Interface_elements', None) is not None:
                    for element_interface_key, element_field_val in obj.get('Interface_elements', None).items():
                        obj.get('Interface_elements', None)[element_interface_key] = move_key(element_field_val, "cell", 1)
                    for element_interface_key, element_field_val in obj.get('Interface_elements', None).items():
                        obj.get('Interface_elements', None)[element_interface_key] = move_key(element_field_val, "Iso Signal", 2)
                    for element_interface_key, element_field_val in obj.get('Interface_elements', None).items():
                        obj.get('Interface_elements', None)[element_interface_key] = move_key(element_field_val, "Dual Mode Lsh", 3)
                    self.correction_log.append("✅ Sort some keys Cell Iso Signal Dual Mode Lsh  in [Interface_elements]")
            if "Sort some keys  Iso Signal Dual Mode Lsh  in [General][field_options]" in selected_repairs:
                if obj.get('General', None) is not None:
                    obj.get('General', None)['field_options'] = move_key(obj.get('General', None)['field_options'], "Iso Signal", 3)
                    obj.get('General', None)['field_options'] = move_key(obj.get('General', None)['field_options'], "Dual Mode Lsh", 4)
                    self.correction_log.append("✅ Sort some keys  Iso Signal Dual Mode Lsh  in [General][field_options]")
            if "Update [General][Date] and [General][version]+1" in selected_repairs:
                obj.get('General', None)['date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                obj.get('General', None)['version'] += 1
                self.correction_log.append("✅ Update [General][Date] and [General][version]+1")

        #---------------------------------------------------------------------------------------------
        # Added _comment in  General to indicate json db updated with ver_r_repair_json_database.py script
        # delivered by Verification team
        #---------------------------------------------------------------------------------------------
        if "Update [General][_comment_repairs_XXXXXXXX] some information to indicate which script corrects Json" in selected_repairs:
            obj['General']['_comment_repairs_'+datetime.now().strftime("%Y_%m_%d_%H_%M_%S")] ='Python script used: ' + str(os.path.basename(__file__)) +' , '+\
                                                                            'Python script Version: ' + str(__version__) +' , '+\
                                                                            'Pillar: ' + str(__part__)+' , '+\
                                                                            'Maintainer: ' + str(__maintainer__) + ' , '+\
                                                                            'Who: ' + os.getlogin()
            self.correction_log.append("✅ Update [General][_comment_repairs_XXXXXXXX] some information to indicate which script corrects Json")

        return obj

    def load_csv_file(self):
        if self.tree.topLevelItemCount() != 0:
            csv_file_list_level_shifter, _ = QFileDialog.getOpenFileName(self, "Select CSV File", "", "CSV Files (*.csv)")
            if not csv_file_list_level_shifter:
                return
            try:
                if csv_file_list_level_shifter is not None :
                    self.csv_file_list_level_shifter=[]
                    self.csv_file_list_iso_signal=[]
                    self.csv_file_list_iso_signal_enum=[]
                    with open(csv_file_list_level_shifter, newline="") as file_lvlsh:
                        csv_data = csv.reader(file_lvlsh, delimiter=',')
                        for ligne in csv_data:
                            self.csv_file_list_level_shifter.append(ligne[0])   # first column
                            self.csv_file_list_iso_signal.append(ligne[1])           # second column
                            if ligne[1] not in self.csv_file_list_iso_signal_enum :  self.csv_file_list_iso_signal_enum.append(ligne[1])
                else:
                    self.csv_file_list_level_shifter =None
                    self.csv_file_list_iso_signal =None
                self.correction_log.append("✅ Level Shifter Enum and ISO name loaded:")
                self.correction_log.append('['+ ' , '.join(self.csv_file_list_level_shifter) + ']')
                self.correction_log.append('['+ ' , '.join(self.csv_file_list_iso_signal)+ ']')
                self.log("Load csv Level shifter: "+csv_file_list_level_shifter)
            except FileNotFoundError:
                self.correction_log.append(f"❌ File not found")
            except Exception as e:
                 self.correction_log.append(f"❌ {e}")
        else:
            QMessageBox.warning(self, "Warning","Please load Json before")


    def json_health_check(self):

        self.health_report.clear()
        self.health_report.setFont(QFont("Consolas", 10))
        text = self.editor.toPlainText()
        self.health_report.append("=" * 60)
        self.health_report.append("JSON HEALTH CHECK")
        self.health_report.append("=" * 60)

        try:
            data = json.loads(text)
            self.health_report.append("✅ JSON syntax valid")
        except json.JSONDecodeError as e:
            self.health_report.append("")
            self.health_report.append("❌ JSON INVALID")
            self.health_report.append(f"Line    : {e.lineno}")
            self.health_report.append(f"Column  : {e.colno}")
            self.health_report.append(f"Message : {e.msg}")
            return

        stats = {"objects": 0, "lists": 0, "values": 0,"warning":0, "max_depth": 0}
        warnings,errors = [],[]
        def scan(obj, depth=0):
            stats["max_depth"] = max(stats["max_depth"], depth)
            if isinstance(obj, dict):
                stats["objects"] += 1
                for k, v in obj.items():
                    if not str(k).strip():
                        errors.append("Empty key detected")
                    scan(v, depth + 1)
            elif isinstance(obj, list):
                stats["lists"] += 1
                if len(obj) > 10000: warnings.append(f"Large array ({len(obj)} items)")
                for v in obj:
                    scan(v, depth + 1)
            else:
                stats["values"] += 1
                if obj in ("", None):
                    stats["warning"] += 1
                    if not any("Empty value detected"  in element for element in warnings): warnings.append("")
                    warnings[0]= str(stats["warning"])+ " Empty value detected"
        scan(data)

        self.health_report.append("")
        self.health_report.append("STATISTICS")
        self.health_report.append("-" * 60)
        self.health_report.append(f"Objects   : {stats['objects']}")
        self.health_report.append(f"Lists     : {stats['lists']}")
        self.health_report.append(f"Values    : {stats['values']}")
        self.health_report.append(f"Max Depth : {stats['max_depth']}")
        self.health_report.append("")
        self.health_report.append("ERRORS")
        self.health_report.append("-" * 60)

        if errors:
            for err in errors:
                self.health_report.append(f"❌ {err}")
        else:
            self.health_report.append("✅ No errors found")

        self.health_report.append("")
        self.health_report.append("WARNINGS")
        self.health_report.append("-" * 60)
        if warnings:
            for warn in warnings:
                self.health_report.append(f"⚠️ {warn}")
        else:
            self.health_report.append("✅ No warnings found")

        score = 100
        score -= len(errors) * 20
        score -= stats['warning'] * 5
        score = max(score, 0)
        self.health_report.append("")
        self.health_report.append("=" * 60)
        self.health_report.append(f"QUALITY SCORE : {score}%")

        if score >= 90:
            self.health_report.append("🟢 Excellent")
        elif score >= 70:
            self.health_report.append("🟠 Acceptable")
        else:
            self.health_report.append("🔴 Needs Attention")
        self.health_report.append("=" * 60)

    ####################################################
    # STYLE
    ####################################################

    def apply_style(self):
        self.setStyleSheet("""
            QWidget{ background:#202124; color:white; font-size:11pt; }
            QPushButton{ background:#0066cc; border:none; border-radius:8px; padding:8px; min-height:32px; }
            QPushButton:hover{ background:#0077ee; }
            QLineEdit,QTextEdit,QTreeWidget{ background:#2d2d2d; border:1px solid #444; border-radius:6px; padding:5px;}
            QHeaderView::section{ background:#404040; border:none; padding:5px; }
        """)

    def fill_root_combo(self, data):
        self.combo_root.clear()
        if isinstance(data, dict): self.combo_root.addItems(sorted(data.keys()))

    def select_root_key(self, key):
        if not key: return
        root = self.tree.invisibleRootItem()
        if root.childCount() == 0: return
        root_item = root.child(0)
        for i in range(root_item.childCount()):
            child = root_item.child(i)
            if child.text(0) == key:
                self.tree.setCurrentItem(child)
                child.setExpanded(True)
                self.tree.scrollToItem(child)
                self.highlight_key(child, 0)
                break

    ####################################################
    # LOGS
    ####################################################

    def log(self, message):
        self.logs.append(message)
        self.status.showMessage(message)

    ####################################################
    # OPEN
    ####################################################

    def load_json(self):

        file_name, _ = QFileDialog.getOpenFileName(self, "Open JSON", "", "JSON Files (*.json)")
        if not file_name: return
        self.load_json_file(file_name)
        self.tree.expandToDepth(0)
        self.tabs.setTabEnabled(1, True)  # Désactive l'onglet n°1
        self.tabs.setTabEnabled(2, True)  # Désactive l'onglet n°2

    def load_json_file(self, file_name):

        try:
            with open(file_name, "r", encoding="utf-8") as file:
                data = json.load(file)
            self.current_file = file_name
            txt = json.dumps(data, indent=4, ensure_ascii=False)
            self.editor.setPlainText(txt)
            # self.editor.setPlainText(json.dumps(data, indent=4, ensure_ascii=False))
            # print("3")
            self.populate_tree(data)
            self.update_stats(data)
            self.add_recent_file(file_name)
            self.fill_root_combo(data)
            self.log(f"Loaded : {file_name}")
            self.tabs.setTabEnabled(1, True)  # Désactive l'onglet n°1
            self.tabs.setTabEnabled(2, True)  # Désactive l'onglet n°2

        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    ####################################################
    # SAVE
    ####################################################

    def save_json(self):

        try:
            data = json.loads(self.editor.toPlainText())
            #Delete Root if only one in up level
            if isinstance(data, dict) and len(data) == 1:
                root_key = next(iter(data))
                data = data[root_key]
            if not self.current_file:
                self.current_file, _ = (QFileDialog.getSaveFileName(self, "Save JSON", "", "*.json"))

            if self.current_file:
                with open(self.current_file, "w", encoding="utf-8") as file:
                    json.dump(data, file, indent=4, ensure_ascii=False)
                self.log("File saved")

        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def save_as_json(self):

        try:
            data = json.loads(self.editor.toPlainText())
            #Delete Root if only one in up level
            if isinstance(data, dict) and len(data) == 1:
                root_key = next(iter(data))
                data = data[root_key]
            file_name, _ = QFileDialog.getSaveFileName(self, "Save As", "", "JSON Files (*.json)")
            if not file_name:
                return
            if not file_name.lower().endswith(".json"):
                file_name += ".json"
            with open(file_name, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=4, ensure_ascii=False)
            self.current_file = file_name
            self.log(f"File saved as : {file_name}")
            QMessageBox.information(self, "Save As", "File saved successfully")

        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
    ####################################################
    # VALIDATE
    ####################################################
    def validate_json(self):
        try:
            json.loads(self.editor.toPlainText())
            if not self.check_duplicate_first_tab_keys(): return
            QMessageBox.information(self, "Validation", "JSON Valid\nNo duplicate keys found.")
            self.log("JSON Valid")
        except Exception as e:
            QMessageBox.critical(self, "Invalid JSON", str(e))

    def check_duplicate_first_tab_keys(self):
        text = self.editor.toPlainText()
        duplicates = []
        def detect_duplicates(pairs):
            counter = collections.Counter(key for key, value in pairs)
            for key, count in counter.items():
                if count > 1: duplicates.append(key)
            return dict(pairs)
        try:
            json.loads(text, object_pairs_hook=detect_duplicates)
            if duplicates:
                QMessageBox.warning(self, "Duplicate Keys", "Duplicate keys found:\n\n" + "\n".join(sorted(set(duplicates))))
                self.log(f"Duplicate keys : {', '.join(sorted(set(duplicates)))}")
                return False
            return True

        except Exception as e:
            QMessageBox.critical(self, "JSON Error", str(e))
            return False

    ####################################################
    # TREE
    ####################################################

    def refresh_tree(self):

        try:
            data = json.loads(self.editor.toPlainText())
            self.populate_tree(data)
            self.update_stats(data)
            self.log("Tree refreshed")

        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def populate_tree(self, data):

        self.tree.clear()
        self.build_tree(self.tree.invisibleRootItem(), data)
        self.tree.expandToDepth(1)

    def build_tree(self, parent, data, name="root"):

        if isinstance(data, dict):
            item = QTreeWidgetItem([str(name), "{dict}"])
            parent.addChild(item)
            for key, value in data.items():
                self.build_tree(item, value, key)

        elif isinstance(data, list):
            item = QTreeWidgetItem([str(name), f"list[{len(data)}]"])
            parent.addChild(item)
            for index, value in enumerate(data):
                self.build_tree(item, value, f"[{index}]")
        else:
            item = QTreeWidgetItem([str(name), str(data)])
            parent.addChild(item)

    ####################################################
    # SEARCH
    ####################################################

    def filter_tree(self, text):

        text = text.lower()
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            self.filter_item(root.child(i), text)

    def filter_item(self, item, text):

        visible = False
        if text in item.text(0).lower(): visible = True
        if text in item.text(1).lower(): visible = True
        for i in range(item.childCount()):
            child = item.child(i)
            if self.filter_item(child, text): visible = True
        item.setHidden(not visible)
        return visible

    ####################################################
    # STATS
    ####################################################

    def update_stats(self, data):

        stats = {"objects": 0, "lists": 0, "values": 0}

        def explore(obj):
            if isinstance(obj, dict):
                stats["objects"] += 1
                for v in obj.values():
                    explore(v)
            elif isinstance(obj, list):
                stats["lists"] += 1
                for v in obj:
                    explore(v)
            else:
                stats["values"] += 1
        explore(data)
        self.lbl_stats.setText(f"Objects : {stats['objects']}    "
                               f"Lists : {stats['lists']}    "
                               f"Values : {stats['values']}")

    ####################################################
    # DRAG DROP
    ####################################################

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        file_path = (event.mimeData().urls()[0].toLocalFile())
        if file_path.lower().endswith(".json"):
            self.load_json_file(file_path)

    def closeEvent(self, event):
        reply = QMessageBox.question(self, "Quit", "Voulez-vous quitter l'application ?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        event.accept() if reply == QMessageBox.Yes else event.ignore()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = JsonExplorer()
    window.show()
    sys.exit(app.exec_())
