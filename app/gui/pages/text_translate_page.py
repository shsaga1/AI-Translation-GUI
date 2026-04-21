from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QTextEdit,
    QPushButton,
    QComboBox,
    QMessageBox,
    QLineEdit,
    QCheckBox,
    QProgressBar,
)

from app.models.scanner import scan_models
from app.tasks.text_translation_task import TextTranslationWorker


class TextTranslatePage(QWidget):
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
        self.available_models = []
        self.worker = None
        self._build_ui()
        self.refresh_models()

    def _build_ui(self):
        root = QVBoxLayout(self)

        top_layout = QHBoxLayout()
        root.addLayout(top_layout, stretch=1)

        left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()
        top_layout.addLayout(left_layout, stretch=3)
        top_layout.addLayout(right_layout, stretch=2)

        input_box = QGroupBox("输入文本")
        input_layout = QVBoxLayout(input_box)

        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("请输入或粘贴要翻译的文本")
        input_layout.addWidget(self.input_text)
        left_layout.addWidget(input_box)

        model_box = QGroupBox("模型设置")
        model_layout = QGridLayout(model_box)

        self.model_root_edit = QLineEdit(str(self.model_root_default))
        self.scan_btn = QPushButton("扫描模型")
        self.scan_btn.clicked.connect(self.refresh_models)

        self.mt_combo = QComboBox()

        self.source_lang_combo = QComboBox()
        self.source_lang_combo.addItems(["auto", "en", "ja", "zh", "ko", "ru"])

        self.target_lang_combo = QComboBox()
        self.target_lang_combo.addItems(["zh", "en", "ja", "ko", "ru"])

        self.context_combo = QComboBox()
        for label, value in self.CONTEXT_OPTIONS:
            self.context_combo.addItem(label, value)

        self.compute_precision_combo = QComboBox()
        self.compute_precision_combo.addItems(["auto", "fp16", "bf16", "int8", "float32"])

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

        model_layout.addWidget(self.auto_review_check, 6, 0, 1, 3)

        left_layout.addWidget(model_box)

        summary_box = QGroupBox("任务摘要")
        summary_layout = QVBoxLayout(summary_box)
        self.summary_label = QLabel("尚未配置任务")
        self.summary_label.setWordWrap(True)
        summary_layout.addWidget(self.summary_label)
        left_layout.addWidget(summary_box)

        button_layout = QHBoxLayout()
        self.translate_btn = QPushButton("开始翻译")
        self.stop_btn = QPushButton("停止任务")
        self.clear_btn = QPushButton("清空")

        self.translate_btn.clicked.connect(self.start_translation)
        self.stop_btn.clicked.connect(self.stop_task)
        self.clear_btn.clicked.connect(self.clear_all)

        self.stop_btn.setEnabled(False)

        button_layout.addStretch()
        button_layout.addWidget(self.translate_btn)
        button_layout.addWidget(self.stop_btn)
        button_layout.addWidget(self.clear_btn)

        left_layout.addLayout(button_layout)

        status_box = QGroupBox("任务状态")
        status_layout = QVBoxLayout(status_box)

        self.status_label = QLabel("待机")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.progress_bar)
        right_layout.addWidget(status_box)

        output_box = QGroupBox("翻译结果")
        output_layout = QVBoxLayout(output_box)

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        output_layout.addWidget(self.output_text)
        right_layout.addWidget(output_box)

        log_box = QGroupBox("日志")
        log_layout = QVBoxLayout(log_box)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        right_layout.addWidget(log_box)

        self.model_root_edit.textChanged.connect(self.update_summary)
        self.source_lang_combo.currentIndexChanged.connect(self.update_summary)
        self.target_lang_combo.currentIndexChanged.connect(self.update_summary)
        self.context_combo.currentIndexChanged.connect(self.update_summary)
        self.compute_precision_combo.currentIndexChanged.connect(self.update_summary)
        self.auto_review_check.stateChanged.connect(self.update_summary)
        self.mt_combo.currentIndexChanged.connect(self.update_summary)

    def refresh_models(self):
        model_root = self.model_root_edit.text().strip()
        self.available_models = scan_models(model_root)

        self.mt_combo.clear()
        mt_models = [m for m in self.available_models if "mt" in m.get("capabilities", [])]

        for model in mt_models:
            self.mt_combo.addItem(model["name"], model)

        self.log_text.append(f"[INFO] 扫描模型完成，共发现 {len(self.available_models)} 个模型。")
        self.log_text.append(f"[INFO] 可用于文字翻译的模型数量：{len(mt_models)}")
        self.update_summary()

    def update_summary(self):
        model_name = self.mt_combo.currentText().strip() or "未选择"
        self.summary_label.setText(
            f"翻译模型：{model_name}\n"
            f"源语言：{self.source_lang_combo.currentText()}\n"
            f"目标语言：{self.target_lang_combo.currentText()}\n"
            f"上下文联系：{self.context_combo.currentText()}（窗口={self.context_combo.currentData()}）\n"
            f"推理精度：{self.compute_precision_combo.currentText()}\n"
            f"自动复查：{self.auto_review_check.isChecked()}"
        )

    def start_translation(self):
        text = self.input_text.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "提示", "请输入要翻译的文本。")
            return

        model = self.mt_combo.currentData()
        if not model:
            QMessageBox.warning(self, "提示", "请先选择翻译模型。")
            return

        payload = {
            "input_text": text,
            "mt_model": model,
            "source_language": self.source_lang_combo.currentText(),
            "target_language": self.target_lang_combo.currentText(),
            "context_level_name": self.context_combo.currentText(),
            "context_window": self.context_combo.currentData(),
            "compute_precision": self.compute_precision_combo.currentText(),
            "auto_review": self.auto_review_check.isChecked(),
        }

        self.worker = TextTranslationWorker(payload)
        self.worker.log_signal.connect(self.append_log)
        self.worker.progress_signal.connect(self.on_progress_changed)
        self.worker.status_signal.connect(self.on_status_changed)
        self.worker.finished_signal.connect(self.on_task_finished)
        self.worker.error_signal.connect(self.on_task_error)

        self.translate_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("任务启动中...")
        self.output_text.clear()

        self.append_log("[INFO] 文字翻译任务开始。")
        self.worker.start()

    def stop_task(self):
        if self.worker is not None:
            self.worker.request_stop()
            self.append_log("[WARNING] 已请求停止任务。")

    def on_progress_changed(self, value: int):
        self.progress_bar.setValue(value)

    def on_status_changed(self, text: str):
        self.status_label.setText(text)

    def on_task_finished(self, translated_text: str):
        self.output_text.setPlainText(translated_text)
        self.append_log("[INFO] 文字翻译任务执行完成。")
        self.status_label.setText("已完成")
        self.progress_bar.setValue(100)
        self.translate_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def on_task_error(self, message: str):
        self.append_log(f"[ERROR] {message}")
        self.status_label.setText("失败")
        self.translate_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        QMessageBox.critical(self, "任务失败", message)

    def append_log(self, text: str):
        self.log_text.append(text)

    def clear_all(self):
        self.input_text.clear()
        self.output_text.clear()
        self.log_text.clear()
        self.progress_bar.setValue(0)
        self.status_label.setText("待机")