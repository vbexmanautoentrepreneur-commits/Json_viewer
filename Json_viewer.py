import sys,collections,json
from PyQt5.QtWidgets import ( QApplication, QMainWindow,QWidget, QFileDialog, QPushButton,
                            QTextEdit, QLineEdit, QLabel, QTreeWidget, QTreeWidgetItem,
                            QVBoxLayout, QHBoxLayout, QSplitter, QMessageBox, QStatusBar,
                            QStyle,QComboBox,QPlainTextEdit)
from PyQt5.QtWidgets import (QAction)
from PyQt5.QtGui import (QTextCursor, QTextCharFormat, QColor,QIcon,QPainter,QCursor)
from PyQt5.QtCore import QSettings, QRect, QSize, Qt

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


class JsonExplorer(QMainWindow):

    def __init__(self):
        super().__init__()

        self.current_file = ""
        self.setWindowTitle("JSON Explorer Pro")
        self.setWindowIcon(QIcon("icons/json.ico"))
        self.resize_and_center()
        self.resize(1400, 900)
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
        toolbar = QHBoxLayout()
        self.settings = QSettings("JsonExplorer", "JsonExplorerPro")
        self.recent_files = self.settings.value("recent_files", [], type=list)

        self.btn_open = QPushButton("📂 Open")
        self.btn_save = QPushButton("💾 Save")
        self.btn_save_as = QPushButton("💾 Save As")
        self.btn_refresh = QPushButton("🔄 Refresh")
        self.btn_validate = QPushButton("✅ Validate")
        self.btn_expand = QPushButton("➕ Expand")
        self.btn_collapse = QPushButton("➖ Collapse")
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
                                    QPlainTextEdit{ background:#1E1E1E; color:#DCDCDC; 
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
        main_layout.addWidget(QLabel("Logs"))
        self.logs = QTextEdit()
        self.logs.setMaximumHeight(200)
        self.logs.setReadOnly(True)
        main_layout.addWidget(self.logs)
        self.status = QStatusBar()
        main_layout.addWidget(self.status)
        self.setLayout(main_layout)
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
        self.btn_quit.clicked.connect(self.close)
        self.combo_root.setStyleSheet(""" QComboBox{ background:#2D2D2D; color:white; border:1px solid #555; 
                                        border-radius:4px; padding:4px; }
                                        QComboBox::drop-down{ width:25px; }
                                        QComboBox QAbstractItemView{ background:#2D2D2D; color:white;
                                         selection-background-color:#1976D2; }""")

    def resize_and_center(self, margin=50):
        screen = QApplication.screenAt(QCursor.pos())
        if screen is None:
            screen = QApplication.primaryScreen()
        geo = screen.availableGeometry()
        width = int(geo.width()/2) - 2 * margin
        height = int(geo.height()/2) - 2 * margin
        self.setGeometry( geo.x() + margin,  geo.y() + margin,  width, height  )
        screen_geometry = screen.availableGeometry()
        window_geometry = self.frameGeometry()
        x = screen_geometry.x() + (screen_geometry.width() - window_geometry.width()) // 2
        y = screen_geometry.y() + (screen_geometry.height() - window_geometry.height()) // 2
        self.setMinimumHeight(height)
        self.setMinimumWidth(width-2*margin)
        self.move(x, y)
    def create_menu(self):

        menubar = self.menuBar()
        file_menu = menubar.addMenu("📂 File")
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
        fmt.setBackground(QColor("#2d2d2d"))
        cursor.mergeCharFormat(fmt)
        # recherche de la clé
        cursor = editor.document().find(f'"{key}"')
        if cursor.isNull(): return

        # sélection trouvée
        editor.setTextCursor(cursor)
        highlight = QTextCharFormat()
        highlight.setBackground(QColor("#FFD54F"))
        highlight.setForeground(QColor("black"))
        cursor.mergeCharFormat(highlight)
        editor.setTextCursor(cursor)
        # centrer la vue sur la clé
        editor.ensureCursorVisible()



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

    def load_json_file(self, file_name):

        try:
            with open(file_name, "r", encoding="utf-8") as file:
                data = json.load(file)
            self.current_file = file_name
            txt = json.dumps(data, indent=4, ensure_ascii=False)
            print("Longueur =", len(txt))
            self.editor.setPlainText(txt)
            # self.editor.setPlainText(json.dumps(data, indent=4, ensure_ascii=False))
            # print("3")
            self.populate_tree(data)
            self.update_stats(data)
            self.add_recent_file(file_name)
            self.fill_root_combo(data)
            self.log(f"Loaded : {file_name}")

        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    ####################################################
    # SAVE
    ####################################################

    def save_json(self):

        try:
            data = json.loads(self.editor.toPlainText())
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
            if not self.check_duplicate_keys(): return
            QMessageBox.information(self, "Validation", "JSON Valid\nNo duplicate keys found.")
            self.log("JSON Valid")

        except Exception as e:
            QMessageBox.critical(self, "Invalid JSON", str(e))

    def check_duplicate_keys(self):

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
