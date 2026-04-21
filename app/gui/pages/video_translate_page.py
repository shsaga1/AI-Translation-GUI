from pathlib import Path

from PySide6.QtCore import Qt
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
    QProgressBar,
    QMessageBox,
    QCheckBox,
)

from app.models.scanner import scan_models
from app.services.config_service import load_settings, save_settings
from app.tasks.video_translation_task import TranslationWorker


class VideoTranslatePage(QWidget):
    CONTEXT_OPTIONS = [
        ("关闭上下文（最快）", 0),
        ("弱上下文（快）", 1),
        ("标准上下文（中等）", 2),
        ("强上下文（慢）", 4),
        ("超强上下文（极慢）", 8),
    ]

    def __init__(self):
        super().__init__()

        self.base_dir = Path(__file__).resolve().parents[3]
        self.model_root_default = Path(r"D:\AI\Translation\Model")
        self.output_root = self.base_dir / "output"
        self.output_root.mkdir(parents=True, exist_ok=True)

        self.worker = None
        self.available_models = []

        self._build_ui()
        self._load_settings_to_ui()
        self.refresh_models()

    def _build_ui(self):
        root = QVBoxLayout(self)

        top_layout = QHBoxLayout()
        root.addLayout(top_layout, stretch=1)

        left_panel = QVBoxLayout()
        top_layout.addLayout(left_panel, stretch=3)

        right_panel = QVBoxLayout()
        top_layout.addLayout(right_panel, stretch=2)

        # 输入输出
        input_box = QGroupBox("输入与输出")
        input_layout = QGridLayout(input_box)

        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText("请选择本地视频或音频文件")

        self.browse_btn = QPushButton("浏览")
        self.browse_btn.clicked.connect(self.choose_file)

        self.output_edit = QLineEdit()
        self.output_edit.setReadOnly(True)

        input_layout.addWidget(QLabel("输入文件"), 0, 0)
        input_layout.addWidget(self.file_edit, 0, 1)
        input_layout.addWidget(self.browse_btn, 0, 2)

        input_layout.addWidget(QLabel("输出目录"), 1, 0)
        input_layout.addWidget(self.output_edit, 1, 1, 1, 2)

        left_panel.addWidget(input_box)

        # 模型设置
        model_box = QGroupBox("模型设置")
        model_layout = QGridLayout(model_box)

        self.model_root_edit = QLineEdit(str(self.model_root_default))

        self.scan_btn = QPushButton("扫描模型")
        self.scan_btn.clicked.connect(self.refresh_models)

        self.asr_combo = QComboBox()
        self.mt_combo = QComboBox()

        self.model_info_text = QTextEdit()
        self.model_info_text.setReadOnly(True)
        self.model_info_text.setFixedHeight(120)

        self.asr_combo.currentIndexChanged.connect(self.update_model_info)
        self.mt_combo.currentIndexChanged.connect(self.update_model_info)

        model_layout.addWidget(QLabel("模型仓库"), 0, 0)
        model_layout.addWidget(self.model_root_edit, 0, 1)
        model_layout.addWidget(self.scan_btn, 0, 2)

        model_layout.addWidget(QLabel("识别模型"), 1, 0)
        model_layout.addWidget(self.asr_combo, 1, 1, 1, 2)

        model_layout.addWidget(QLabel("翻译模型"), 2, 0)
        model_layout.addWidget(self.mt_combo, 2, 1, 1, 2)

        model_layout.addWidget(QLabel("模型信息"), 3, 0, Qt.AlignTop)
        model_layout.addWidget(self.model_info_text, 3, 1, 1, 2)

        left_panel.addWidget(model_box)

        # 参数设置
        param_box = QGroupBox("参数设置")
        param_layout = QGridLayout(param_box)

        self.src_lang_combo = QComboBox()
        self.src_lang_combo.addItems(["auto", "en", "ja", "zh"])

        self.tgt_lang_combo = QComboBox()
        self.tgt_lang_combo.addItems(["zh", "en", "ja"])

        self.context_combo = QComboBox()
        for label, value in self.CONTEXT_OPTIONS:
            self.context_combo.addItem(label, value)

        self.compute_precision_combo = QComboBox()
        self.compute_precision_combo.addItems(["auto", "fp16", "bf16", "int8", "float32"])

        self.device_combo = QComboBox()
        self.device_combo.addItems(["auto", "cuda", "cpu"])

        self.beam_size_combo = QComboBox()
        self.beam_size_combo.addItems(["1", "3", "5"])

        self.temperature_combo = QComboBox()
        self.temperature_combo.addItems(["0.0", "0.2", "0.5", "0.8"])

        self.keep_original_check = QCheckBox("保留原文（双语字幕）")
        self.keep_original_check.setChecked(True)

        self.auto_open_check = QCheckBox("任务完成后自动打开输出目录")
        self.auto_open_check.setChecked(False)

        self.auto_review_check = QCheckBox("启用自动复查")
        self.auto_review_check.setChecked(True)

        param_layout.addWidget(QLabel("源语言"), 0, 0)
        param_layout.addWidget(self.src_lang_combo, 0, 1)

        param_layout.addWidget(QLabel("目标语言"), 1, 0)
        param_layout.addWidget(self.tgt_lang_combo, 1, 1)

        param_layout.addWidget(QLabel("上下文联系"), 2, 0)
        param_layout.addWidget(self.context_combo, 2, 1)

        param_layout.addWidget(QLabel("推理精度"), 3, 0)
        param_layout.addWidget(self.compute_precision_combo, 3, 1)

        param_layout.addWidget(QLabel("运行设备"), 4, 0)
        param_layout.addWidget(self.device_combo, 4, 1)

        param_layout.addWidget(QLabel("Beam Size"), 5, 0)
        param_layout.addWidget(self.beam_size_combo, 5, 1)

        param_layout.addWidget(QLabel("Temperature"), 6, 0)
        param_layout.addWidget(self.temperature_combo, 6, 1)

        param_layout.addWidget(self.keep_original_check, 7, 0, 1, 2)
        param_layout.addWidget(self.auto_open_check, 8, 0, 1, 2)
        param_layout.addWidget(self.auto_review_check, 9, 0, 1, 2)

        left_panel.addWidget(param_box)

        # 摘要
        summary_box = QGroupBox("任务摘要")
        summary_layout = QVBoxLayout(summary_box)

        self.summary_label = QLabel("尚未配置任务")
        self.summary_label.setWordWrap(True)

        summary_layout.addWidget(self.summary_label)
        left_panel.addWidget(summary_box)
        left_panel.addStretch()

        # 状态
        status_box = QGroupBox("任务状态")
        status_layout = QVBoxLayout(status_box)

        self.status_label = QLabel("待机")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.progress_bar)

        right_panel.addWidget(status_box)

        # 日志
        log_box = QGroupBox("日志")
        log_layout = QVBoxLayout(log_box)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)

        log_layout.addWidget(self.log_text)
        right_panel.addWidget(log_box, stretch=1)

        # 按钮
        button_layout = QHBoxLayout()
        root.addLayout(button_layout)

        self.start_btn = QPushButton("开始任务")
        self.stop_btn = QPushButton("停止任务")
        self.clear_log_btn = QPushButton("清空日志")
        self.open_output_btn = QPushButton("打开输出目录")

        self.start_btn.clicked.connect(self.start_task)
        self.stop_btn.clicked.connect(self.stop_task)
        self.clear_log_btn.clicked.connect(self.log_text.clear)
        self.open_output_btn.clicked.connect(self.open_output_dir)

        self.stop_btn.setEnabled(False)

        button_layout.addStretch()
        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.stop_btn)
        button_layout.addWidget(self.clear_log_btn)
        button_layout.addWidget(self.open_output_btn)

        self.file_edit.textChanged.connect(self.on_inputs_changed)
        self.model_root_edit.textChanged.connect(self.on_inputs_changed)
        self.src_lang_combo.currentIndexChanged.connect(self.on_inputs_changed)
        self.tgt_lang_combo.currentIndexChanged.connect(self.on_inputs_changed)
        self.context_combo.currentIndexChanged.connect(self.on_inputs_changed)
        self.compute_precision_combo.currentIndexChanged.connect(self.on_inputs_changed)
        self.device_combo.currentIndexChanged.connect(self.on_inputs_changed)
        self.beam_size_combo.currentIndexChanged.connect(self.on_inputs_changed)
        self.temperature_combo.currentIndexChanged.connect(self.on_inputs_changed)
        self.keep_original_check.stateChanged.connect(self.on_inputs_changed)
        self.auto_open_check.stateChanged.connect(self.on_inputs_changed)
        self.auto_review_check.stateChanged.connect(self.on_inputs_changed)
        self.asr_combo.currentIndexChanged.connect(self.on_inputs_changed)
        self.mt_combo.currentIndexChanged.connect(self.on_inputs_changed)

    def _load_settings_to_ui(self):
        settings = load_settings()

        self.model_root_edit.setText(settings.get("model_root", str(self.model_root_default)))
        self.file_edit.setText(settings.get("last_input_file", ""))
        self.output_edit.setText(settings.get("last_output_dir", ""))

        self.src_lang_combo.setCurrentText(settings.get("source_language", "auto"))
        self.tgt_lang_combo.setCurrentText(settings.get("target_language", "zh"))
        self.compute_precision_combo.setCurrentText(settings.get("compute_precision", "auto"))
        self.device_combo.setCurrentText(settings.get("device", "auto"))
        self.beam_size_combo.setCurrentText(settings.get("beam_size", "1"))
        self.temperature_combo.setCurrentText(settings.get("temperature", "0.0"))
        self.keep_original_check.setChecked(settings.get("keep_original", True))
        self.auto_open_check.setChecked(settings.get("auto_open_output", False))
        self.auto_review_check.setChecked(settings.get("auto_review", True))

        saved_context_window = settings.get("context_window", 2)
        for i in range(self.context_combo.count()):
            if self.context_combo.itemData(i) == saved_context_window:
                self.context_combo.setCurrentIndex(i)
                break

    def _save_settings_from_ui(self):
        settings = {
            "model_root": self.model_root_edit.text().strip(),
            "last_input_file": self.file_edit.text().strip(),
            "last_output_dir": self.output_edit.text().strip(),
            "source_language": self.src_lang_combo.currentText(),
            "target_language": self.tgt_lang_combo.currentText(),
            "context_level_name": self.context_combo.currentText(),
            "context_window": self.context_combo.currentData(),
            "compute_precision": self.compute_precision_combo.currentText(),
            "device": self.device_combo.currentText(),
            "beam_size": self.beam_size_combo.currentText(),
            "temperature": self.temperature_combo.currentText(),
            "keep_original": self.keep_original_check.isChecked(),
            "auto_open_output": self.auto_open_check.isChecked(),
            "auto_review": self.auto_review_check.isChecked(),
            "last_asr_model": self.current_asr_model_name(),
            "last_mt_model": self.current_mt_model_name(),
        }
        save_settings(settings)

    def choose_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择视频或音频文件",
            "",
            "媒体文件 (*.mp4 *.mkv *.avi *.mov *.mp3 *.wav *.flac *.m4a);;所有文件 (*.*)"
        )
        if not file_path:
            return

        self.file_edit.setText(file_path)
        input_path = Path(file_path)
        output_dir = self.output_root / input_path.stem
        output_dir.mkdir(parents=True, exist_ok=True)
        self.output_edit.setText(str(output_dir))
        self.append_log(f"[INFO] 已选择输入文件: {file_path}")

    def refresh_models(self):
        model_root = self.model_root_edit.text().strip()
        if not model_root:
            QMessageBox.warning(self, "提示", "请先填写模型仓库路径。")
            return

        self.append_log(f"[INFO] 开始扫描模型目录: {model_root}")
        result = scan_models(model_root)
        self.available_models = result

        self.asr_combo.blockSignals(True)
        self.mt_combo.blockSignals(True)
        self.asr_combo.clear()
        self.mt_combo.clear()

        asr_models = [m for m in result if "asr" in m.get("capabilities", [])]
        mt_models = [m for m in result if "mt" in m.get("capabilities", [])]

        for model in asr_models:
            self.asr_combo.addItem(model["name"], model)
        for model in mt_models:
            self.mt_combo.addItem(model["name"], model)

        self.asr_combo.blockSignals(False)
        self.mt_combo.blockSignals(False)

        self.append_log(f"[INFO] 扫描完成，共发现 {len(result)} 个模型。")
        self.append_log(f"[INFO] ASR 可用模型: {len(asr_models)} 个，翻译可用模型: {len(mt_models)} 个。")

        settings = load_settings()
        self._restore_combo_selection(self.asr_combo, settings.get("last_asr_model", ""))
        self._restore_combo_selection(self.mt_combo, settings.get("last_mt_model", ""))

        self.update_model_info()
        self.on_inputs_changed()

    def _restore_combo_selection(self, combo: QComboBox, target_name: str):
        if not target_name:
            return
        for i in range(combo.count()):
            if combo.itemText(i) == target_name:
                combo.setCurrentIndex(i)
                return

    def update_model_info(self):
        texts = []

        asr_model = self.current_asr_model()
        mt_model = self.current_mt_model()

        if asr_model:
            texts.append(
                f"【识别模型】\n"
                f"名称: {asr_model['name']}\n"
                f"类型: {asr_model['type']}\n"
                f"能力: {', '.join(asr_model.get('capabilities', []))}\n"
                f"路径: {asr_model['path']}\n"
                f"说明: {asr_model['description']}\n"
            )

        if mt_model:
            texts.append(
                f"【翻译模型】\n"
                f"名称: {mt_model['name']}\n"
                f"类型: {mt_model['type']}\n"
                f"能力: {', '.join(mt_model.get('capabilities', []))}\n"
                f"路径: {mt_model['path']}\n"
                f"说明: {mt_model['description']}\n"
            )

        self.model_info_text.setPlainText("\n".join(texts))

    def on_inputs_changed(self):
        input_file = self.file_edit.text().strip() or "未选择"
        output_dir = self.output_edit.text().strip() or "未设置"
        asr_name = self.current_asr_model_name() or "未选择"
        mt_name = self.current_mt_model_name() or "未选择"

        self.summary_label.setText(
            f"输入文件：{input_file}\n"
            f"输出目录：{output_dir}\n"
            f"识别模型：{asr_name}\n"
            f"翻译模型：{mt_name}\n"
            f"源语言：{self.src_lang_combo.currentText()}\n"
            f"目标语言：{self.tgt_lang_combo.currentText()}\n"
            f"上下文联系：{self.context_combo.currentText()}（窗口={self.context_combo.currentData()}）\n"
            f"推理精度：{self.compute_precision_combo.currentText()}\n"
            f"运行设备：{self.device_combo.currentText()}\n"
            f"Beam Size：{self.beam_size_combo.currentText()}\n"
            f"Temperature：{self.temperature_combo.currentText()}\n"
            f"双语字幕：{'是' if self.keep_original_check.isChecked() else '否'}\n"
            f"自动复查：{self.auto_review_check.isChecked()}"
        )
        self._save_settings_from_ui()

    def current_asr_model(self):
        return self.asr_combo.currentData()

    def current_mt_model(self):
        return self.mt_combo.currentData()

    def current_asr_model_name(self):
        return self.asr_combo.currentText().strip()

    def current_mt_model_name(self):
        return self.mt_combo.currentText().strip()

    def validate_inputs(self):
        input_file = self.file_edit.text().strip()
        output_dir = self.output_edit.text().strip()

        if not input_file:
            QMessageBox.warning(self, "提示", "请先选择输入文件。")
            return False
        if not Path(input_file).exists():
            QMessageBox.warning(self, "提示", "输入文件不存在。")
            return False
        if not output_dir:
            QMessageBox.warning(self, "提示", "输出目录为空。")
            return False
        if not self.current_asr_model():
            QMessageBox.warning(self, "提示", "未选择识别模型。")
            return False
        if not self.current_mt_model():
            QMessageBox.warning(self, "提示", "未选择翻译模型。")
            return False
        return True

    def start_task(self):
        if not self.validate_inputs():
            return

        self._save_settings_from_ui()

        payload = {
            "input_file": self.file_edit.text().strip(),
            "output_dir": self.output_edit.text().strip(),
            "asr_model": self.current_asr_model(),
            "mt_model": self.current_mt_model(),
            "source_language": self.src_lang_combo.currentText(),
            "target_language": self.tgt_lang_combo.currentText(),
            "context_level_name": self.context_combo.currentText(),
            "context_window": self.context_combo.currentData(),
            "compute_precision": self.compute_precision_combo.currentText(),
            "device": self.device_combo.currentText(),
            "beam_size": int(self.beam_size_combo.currentText()),
            "temperature": float(self.temperature_combo.currentText()),
            "keep_original": self.keep_original_check.isChecked(),
            "auto_review": self.auto_review_check.isChecked(),
        }

        self.worker = TranslationWorker(payload)
        self.worker.log_signal.connect(self.append_log)
        self.worker.progress_signal.connect(self.on_progress_changed)
        self.worker.status_signal.connect(self.on_status_changed)
        self.worker.finished_signal.connect(self.on_task_finished)
        self.worker.error_signal.connect(self.on_task_error)

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("任务启动中...")
        self.append_log("[INFO] 任务开始。")
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
        if self.auto_open_check.isChecked():
            self.open_output_dir()

    def on_task_error(self, message: str):
        self.append_log(f"[ERROR] {message}")
        self.status_label.setText("失败")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        QMessageBox.critical(self, "任务失败", message)

    def append_log(self, text: str):
        self.log_text.append(text)

    def open_output_dir(self):
        output_dir = self.output_edit.text().strip()
        if not output_dir:
            return
        path = Path(output_dir)
        if not path.exists():
            QMessageBox.warning(self, "提示", "输出目录不存在。")
            return
        import os
        os.startfile(str(path))