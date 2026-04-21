from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMainWindow,
    QTabWidget,
)

from app.gui.pages.video_translate_page import VideoTranslatePage
from app.gui.pages.text_translate_page import TextTranslatePage
from app.gui.pages.web_translate_page import WebTranslatePage
from app.gui.pages.file_translate_page import FileTranslatePage
from app.gui.settings_window import SettingsWindow


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("本地翻译工具v1.1")
        self.resize(1360, 860)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.video_page = VideoTranslatePage()
        self.text_page = TextTranslatePage()
        self.web_page = WebTranslatePage()
        self.file_page = FileTranslatePage()

        self.tabs.addTab(self.video_page, "视频/音频翻译")
        self.tabs.addTab(self.text_page, "文字翻译")
        self.tabs.addTab(self.web_page, "网页翻译")
        self.tabs.addTab(self.file_page, "文件翻译")

        self._build_menu()

    def _build_menu(self):
        menu_bar = self.menuBar()
        settings_menu = menu_bar.addMenu("设置")

        open_settings_action = QAction("打开设置窗口", self)
        open_settings_action.triggered.connect(self.open_settings_window)

        settings_menu.addAction(open_settings_action)

    def open_settings_window(self):
        dialog = SettingsWindow(self)
        dialog.exec()