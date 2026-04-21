from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QFileDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QTextEdit,
    QMessageBox,
    QCheckBox,
    QProgressBar,
)

from app.models.scanner import scan_models
from app.tasks.file_translation_task import FileTranslationWorker


class FileTranslatePage(QWidget):
    CONTEXT_OPTIONS = [
        ("关闭上下文（最快）", 0),
        ("弱上下文（快）", 1),
        ("标准上下文（中等）", 2),
        ("强上下文（慢）", 4),
        ("超强上下文（极慢）", 8),
    ]

    def __init__(self):
        super().__init__()
        self.model_root_default = Path(r"D:\AI\Translation\Model")
        self.output_root = Path(__file__).resolve().parents[3] / "output"
        self.output_root.mkdir(parents=True, exist_ok=True)

        self.available_models = []
        self.worker = None

        self._build_ui()
        self.refresh_models()

    def _build_ui(self):
        root = QVBoxLayout(self)

        top_layout = QHBoxLayout()
        root.addLayout(top_layout, stretch=1)

        left_panel = QVBoxLayout()
        right_panel = QVBoxLayout()
        top_layout.addLayout(left_panel, stretch=3)
        top_layout.addLayout(right_panel, stretch=2)

        input_box = QGroupBox("文件输入")
        input_layout = QGridLayout(input_box)

        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText("请选择要翻译的文件")

        self.browse_btn = QPushButton("浏览")
        self.browse_btn.clicked.connect(self.choose_file)

        self.file_type_edit = QLineEdit()
        self.file_type_edit.setReadOnly(True)

        self.output_edit = QLineEdit()
        self.output_edit.setReadOnly(True)

        input_layout.addWidget(QLabel("输入文件"), 0, 0)
        input_layout.addWidget(self.file_edit, 0, 1)
        input_layout.addWidget(self.browse_btn, 0, 2)

        input_layout.addWidget(QLabel("文件类型"), 1, 0)
        input_layout.addWidget(self.file_type_edit, 1, 1, 1, 2)

        input_layout.addWidget(QLabel("输出目录"), 2, 0)
        input_layout.addWidget(self.output_edit, 2, 1, 1, 2)

        left_panel.addWidget(input_box)

        model_box = QGroupBox("模型设置")
        model_layout = QGridLayout(model_box)

        self.model_root_edit = QLineEdit(str(self.model_root_default))
        self.scan_btn = QPushButton("扫描模型")
        self.scan_btn.clicked.connect(self.refresh_models)

        self.mt_combo = QComboBox()

        self.source_lang_combo = QComboBox()
        self.source_lang_combo.addItems(["auto", "en", "ja", "zh"])

        self.target_lang_combo = QComboBox()
        self.target_lang_combo.addItems(["zh", "en", "ja"])

        self.context_combo = QComboBox()
        for label, value in self.CONTEXT_OPTIONS:
            self.context_combo.addItem(label, value)

        self.compute_precision_combo = QComboBox()
        self.compute_precision_combo.addItems(["auto", "fp16", "bf16", "int8", "float32"])

        self.keep_original_check = QCheckBox("保留原文（双语输出）")
        self.keep_original_check.setChecked(True)

        self.auto_review_check = QCheckBox("启用自动复查")
        self.auto_review_check.setChecked(True)

        model_layout.addWidget(QLabel("模型仓库"), 0, 0)
        model_layout.addWidget(self.model_root_edit, 0, 1)
        model_layout.addWidget(self.scan_btn, 0, 2)

        model_layout.addWidget(QLabel("翻译模型"), 1, 0)
        model_layout.addWidget(self.mt_combo, 1, 1, 1, 2)

        model_layout.addWidget(QLabel("源语言"), 2, 0)
        model_layout.addWidget(self.source_lang_combo, 2, 1, 1, 2)

        model_layout.addWidget(QLabel("目标语言"), 3, 0)
        model_layout.addWidget(self.target_lang_combo, 3, 1, 1, 2)

        model_layout.addWidget(QLabel("上下文联系"), 4, 0)
        model_layout.addWidget(self.context_combo, 4, 1, 1, 2)

        model_layout.addWidget(QLabel("推理精度"), 5, 0)
        model_layout.addWidget(self.compute_precision_combo, 5, 1, 1, 2)

        model_layout.addWidget(self.keep_original_check, 6, 0, 1, 3)
        model_layout.addWidget(self.auto_review_check, 7, 0, 1, 3)

        left_panel.addWidget(model_box)

        summary_box = QGroupBox("任务摘要")
        summary_layout = QVBoxLayout(summary_box)
        self.summary_label = QLabel("尚未配置任务")
        self.summary_label.setWordWrap(True)
        summary_layout.addWidget(self.summary_label)
        left_panel.addWidget(summary_box)
        left_panel.addStretch()

        status_box = QGroupBox("任务状态")
        status_layout = QVBoxLayout(status_box)

        self.status_label = QLabel("待机")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.progress_bar)
        right_panel.addWidget(status_box)

        log_box = QGroupBox("日志")
        log_layout = QVBoxLayout(log_box)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        right_panel.addWidget(log_box, stretch=1)

        button_layout = QHBoxLayout()
        root.addLayout(button_layout)

        self.start_btn = QPushButton("开始翻译")
        self.stop_btn = QPushButton("停止任务")
        self.clear_btn = QPushButton("清空日志")
        self.open_output_btn = QPushButton("打开输出目录")

        self.start_btn.clicked.connect(self.start_file_translation)
        self.stop_btn.clicked.connect(self.stop_task)
        self.clear_btn.clicked.connect(self.log_text.clear)
        self.open_output_btn.clicked.connect(self.open_output_dir)

        self.stop_btn.setEnabled(False)

        button_layout.addStretch()
        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.stop_btn)
        button_layout.addWidget(self.clear_btn)
        button_layout.addWidget(self.open_output_btn)

        self.file_edit.textChanged.connect(self.update_summary)
        self.mt_combo.currentIndexChanged.connect(self.update_summary)
        self.source_lang_combo.currentIndexChanged.connect(self.update_summary)
        self.target_lang_combo.currentIndexChanged.connect(self.update_summary)
        self.context_combo.currentIndexChanged.connect(self.update_summary)
        self.compute_precision_combo.currentIndexChanged.connect(self.update_summary)
        self.keep_original_check.stateChanged.connect(self.update_summary)
        self.auto_review_check.stateChanged.connect(self.update_summary)

    def choose_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择文件",
            "",
            "支持文件 (*.md *.markdown *.docx *.pdf *.epub);;所有文件 (*.*)"
        )
        if not file_path:
            return

        self.file_edit.setText(file_path)
        file_type = self.detect_file_type(file_path)
        self.file_type_edit.setText(file_type)

        input_path = Path(file_path)
        output_dir = self.output_root / input_path.stem
        output_dir.mkdir(parents=True, exist_ok=True)
        self.output_edit.setText(str(output_dir))

        self.log_text.append(f"[INFO] 已选择文件: {file_path}")
        self.log_text.append(f"[INFO] 文件类型识别为: {file_type}")
        self.update_summary()

    def detect_file_type(self, file_path: str) -> str:
        ext = Path(file_path).suffix.lower()
        mapping = {
            ".md": "Markdown",
            ".markdown": "Markdown",
            ".docx": "Word",
            ".pdf": "PDF",
            ".epub": "EPUB",
        }
        return mapping.get(ext, "未知类型")

    def refresh_models(self):
        model_root = self.model_root_edit.text().strip()
        self.available_models = scan_models(model_root)

        self.mt_combo.clear()
        mt_models = [m for m in self.available_models if "mt" in m.get("capabilities", [])]
        for model in mt_models:
            self.mt_combo.addItem(model["name"], model)

        self.log_text.append(f"[INFO] 扫描模型完成，共发现 {len(self.available_models)} 个模型。")
        self.log_text.append(f"[INFO] 文件翻译可用模型数量：{len(mt_models)}")
        self.update_summary()

    def update_summary(self):
        self.summary_label.setText(
            f"输入文件：{self.file_edit.text().strip() or '未选择'}\n"
            f"文件类型：{self.file_type_edit.text().strip() or '未知'}\n"
            f"输出目录：{self.output_edit.text().strip() or '未设置'}\n"
            f"翻译模型：{self.mt_combo.currentText().strip() or '未选择'}\n"
            f"源语言：{self.source_lang_combo.currentText()}\n"
            f"目标语言：{self.target_lang_combo.currentText()}\n"
            f"上下文联系：{self.context_combo.currentText()}（窗口={self.context_combo.currentData()}）\n"
            f"推理精度：{self.compute_precision_combo.currentText()}\n"
            f"保留原文：{'是' if self.keep_original_check.isChecked() else '否'}\n"
            f"自动复查：{self.auto_review_check.isChecked()}"
        )

    def start_file_translation(self):
        file_path = self.file_edit.text().strip()
        output_dir = self.output_edit.text().strip()
        model = self.mt_combo.currentData()

        if not file_path:
            QMessageBox.warning(self, "提示", "请先选择文件。")
            return
        if not Path(file_path).exists():
            QMessageBox.warning(self, "提示", "文件不存在。")
            return
        if not model:
            QMessageBox.warning(self, "提示", "请先选择翻译模型。")
            return

        payload = {
            "input_file": file_path,
            "output_dir": output_dir,
            "mt_model": model,
            "source_language": self.source_lang_combo.currentText(),
            "target_language": self.target_lang_combo.currentText(),
            "context_level_name": self.context_combo.currentText(),
            "context_window": self.context_combo.currentData(),
            "compute_precision": self.compute_precision_combo.currentText(),
            "keep_original": self.keep_original_check.isChecked(),
            "auto_review": self.auto_review_check.isChecked(),
        }

        self.worker = FileTranslationWorker(payload)
        self.worker.log_signal.connect(self.append_log)
        self.worker.progress_signal.connect(self.on_progress_changed)
        self.worker.status_signal.connect(self.on_status_changed)
        self.worker.finished_signal.connect(self.on_task_finished)
        self.worker.error_signal.connect(self.on_task_error)

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("任务启动中...")

        self.append_log("[INFO] 文件翻译任务开始。")
        self.worker.start()

    def stop_task(self):
        if self.worker is not None:
            self.worker.request_stop()
            self.append_log("[WARNING] 已请求停止任务。")

    def on_progress_changed(self, value: int):
        self.progress_bar.setValue(value)

    def on_status_changed(self, text: str):
        self.status_label.setText(text)

    def on_task_finished(self, message: str):
        self.append_log(f"[INFO] {message}")
        self.status_label.setText("已完成")
        self.progress_bar.setValue(100)
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def on_task_error(self, message: str):
        self.append_log(f"[ERROR] {message}")
        self.status_label.setText("失败")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        QMessageBox.critical(self, "任务失败", message)

    def append_log(self, text: str):
        self.log_text.append(text)

    def open_output_dir(self):
        path = Path(self.output_edit.text().strip())
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
        import os
        os.startfile(str(path))