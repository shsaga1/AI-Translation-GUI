from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QFileDialog,
    QMessageBox,
    QHBoxLayout,
    QComboBox,
    QSpinBox,
)

from app.services.config_service import (
    load_quality_config,
    save_quality_config,
    load_csv_headers,
    import_glossary_csv,
)


class SettingsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.resize(760, 620)

        self.quality_config = load_quality_config()

        self._build_ui()
        self._load_config_to_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)

        # 基础质量设置
        quality_box = QGroupBox("质量增强设置")
        quality_layout = QGridLayout(quality_box)

        self.enable_glossary_check = QCheckBox("启用术语表")
        self.enable_preserve_check = QCheckBox("启用保留词规则")
        self.enable_consistency_check = QCheckBox("启用全文一致性记忆")
        self.enable_auto_review_check = QCheckBox("默认启用自动复查")

        self.glossary_path_edit = QLineEdit()
        self.preserve_path_edit = QLineEdit()
        self.consistency_path_edit = QLineEdit()

        self.min_block_merge_spin = QSpinBox()
        self.min_block_merge_spin.setRange(10, 500)

        self.max_chars_spin = QSpinBox()
        self.max_chars_spin.setRange(200, 10000)

        quality_layout.addWidget(self.enable_glossary_check, 0, 0, 1, 2)
        quality_layout.addWidget(self.enable_preserve_check, 1, 0, 1, 2)
        quality_layout.addWidget(self.enable_consistency_check, 2, 0, 1, 2)
        quality_layout.addWidget(self.enable_auto_review_check, 3, 0, 1, 2)

        quality_layout.addWidget(QLabel("术语表路径"), 4, 0)
        quality_layout.addWidget(self.glossary_path_edit, 4, 1)

        quality_layout.addWidget(QLabel("保留规则路径"), 5, 0)
        quality_layout.addWidget(self.preserve_path_edit, 5, 1)

        quality_layout.addWidget(QLabel("一致性记忆路径"), 6, 0)
        quality_layout.addWidget(self.consistency_path_edit, 6, 1)

        quality_layout.addWidget(QLabel("短段合并阈值"), 7, 0)
        quality_layout.addWidget(self.min_block_merge_spin, 7, 1)

        quality_layout.addWidget(QLabel("单块最大字符数"), 8, 0)
        quality_layout.addWidget(self.max_chars_spin, 8, 1)

        root.addWidget(quality_box)

        # CSV 导入区
        csv_box = QGroupBox("导入术语表 CSV")
        csv_layout = QGridLayout(csv_box)

        self.csv_path_edit = QLineEdit()
        self.csv_browse_btn = QPushButton("选择 CSV")
        self.csv_browse_btn.clicked.connect(self.choose_csv)

        self.load_headers_btn = QPushButton("读取表头")
        self.load_headers_btn.clicked.connect(self.load_headers)

        self.source_col_combo = QComboBox()
        self.target_col_combo = QComboBox()

        self.import_btn = QPushButton("导入为术语表")
        self.import_btn.clicked.connect(self.import_csv_glossary)

        csv_layout.addWidget(QLabel("CSV 文件"), 0, 0)
        csv_layout.addWidget(self.csv_path_edit, 0, 1)
        csv_layout.addWidget(self.csv_browse_btn, 0, 2)

        csv_layout.addWidget(self.load_headers_btn, 1, 2)

        csv_layout.addWidget(QLabel("源语言列"), 2, 0)
        csv_layout.addWidget(self.source_col_combo, 2, 1, 1, 2)

        csv_layout.addWidget(QLabel("目标语言列"), 3, 0)
        csv_layout.addWidget(self.target_col_combo, 3, 1, 1, 2)

        csv_layout.addWidget(self.import_btn, 4, 0, 1, 3)

        root.addWidget(csv_box)

        # 底部按钮
        bottom_layout = QHBoxLayout()
        root.addLayout(bottom_layout)

        self.save_btn = QPushButton("保存设置")
        self.cancel_btn = QPushButton("关闭")

        self.save_btn.clicked.connect(self.save_config)
        self.cancel_btn.clicked.connect(self.close)

        bottom_layout.addStretch()
        bottom_layout.addWidget(self.save_btn)
        bottom_layout.addWidget(self.cancel_btn)

    def _load_config_to_ui(self):
        cfg = self.quality_config

        self.enable_glossary_check.setChecked(cfg.get("enable_glossary", True))
        self.enable_preserve_check.setChecked(cfg.get("enable_preserve_rules", True))
        self.enable_consistency_check.setChecked(cfg.get("enable_consistency_memory", True))
        self.enable_auto_review_check.setChecked(cfg.get("enable_auto_review", True))

        self.glossary_path_edit.setText(cfg.get("glossary_path", "data/user_glossary.csv"))
        self.preserve_path_edit.setText(cfg.get("preserve_rules_path", "data/preserve_patterns.json"))
        self.consistency_path_edit.setText(cfg.get("consistency_memory_path", "data/consistency_memory.json"))

        self.min_block_merge_spin.setValue(int(cfg.get("min_block_merge_length", 60)))
        self.max_chars_spin.setValue(int(cfg.get("max_chars_per_chunk", 1800)))

    def choose_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择术语表 CSV",
            "",
            "CSV 文件 (*.csv);;所有文件 (*.*)"
        )
        if not path:
            return
        self.csv_path_edit.setText(path)

    def load_headers(self):
        csv_path = self.csv_path_edit.text().strip()
        if not csv_path:
            QMessageBox.warning(self, "提示", "请先选择 CSV 文件。")
            return

        headers = load_csv_headers(csv_path)
        if not headers:
            QMessageBox.warning(self, "提示", "未读取到 CSV 表头。")
            return

        self.source_col_combo.clear()
        self.target_col_combo.clear()

        self.source_col_combo.addItems(headers)
        self.target_col_combo.addItems(headers)

        QMessageBox.information(self, "成功", f"已读取到 {len(headers)} 个表头。")

    def import_csv_glossary(self):
        csv_path = self.csv_path_edit.text().strip()
        source_col = self.source_col_combo.currentText().strip()
        target_col = self.target_col_combo.currentText().strip()

        if not csv_path:
            QMessageBox.warning(self, "提示", "请先选择 CSV 文件。")
            return

        if not source_col or not target_col:
            QMessageBox.warning(self, "提示", "请先读取表头并选择源语言列和目标语言列。")
            return

        output_csv_path = self.glossary_path_edit.text().strip()
        if not output_csv_path:
            output_csv_path = "data/user_glossary.csv"
            self.glossary_path_edit.setText(output_csv_path)

        if not output_csv_path.lower().endswith(".csv"):
            output_csv_path += ".csv"
            self.glossary_path_edit.setText(output_csv_path)

        try:
            Path(output_csv_path).parent.mkdir(parents=True, exist_ok=True)

            result = import_glossary_csv(
                csv_path=csv_path,
                source_column=source_col,
                target_column=target_col,
                output_csv_path=output_csv_path,
            )

            save_quality_config({
                "glossary_path": output_csv_path,
                "enable_glossary": True,
            })

            QMessageBox.information(
                self,
                "导入成功",
                f"总行数：{result['total_rows']}\n"
                f"成功导入：{result['imported_rows']}\n"
                f"跳过：{result['skipped_rows']}\n"
                f"输出文件：{result['output_path']}"
            )
        except Exception as e:
            QMessageBox.critical(self, "导入失败", str(e))

    def save_config(self):
        save_quality_config({
            "enable_glossary": self.enable_glossary_check.isChecked(),
            "enable_preserve_rules": self.enable_preserve_check.isChecked(),
            "enable_consistency_memory": self.enable_consistency_check.isChecked(),
            "enable_auto_review": self.enable_auto_review_check.isChecked(),
            "glossary_path": self.glossary_path_edit.text().strip(),
            "preserve_rules_path": self.preserve_path_edit.text().strip(),
            "consistency_memory_path": self.consistency_path_edit.text().strip(),
            "min_block_merge_length": self.min_block_merge_spin.value(),
            "max_chars_per_chunk": self.max_chars_spin.value(),
        })

        QMessageBox.information(self, "成功", "设置已保存。")