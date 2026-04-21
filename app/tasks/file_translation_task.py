from __future__ import annotations

import os
import traceback

from PySide6.QtCore import QThread, Signal

from app.services.translation_core import TranslationCore


class FileTranslationTask:
    def __init__(self, model_instance):
        self.model_instance = model_instance

        self.translation_core = TranslationCore(
            base_translate_func=self._call_model_translate,
        )

    def _call_model_translate(self, text: str) -> str:
        if hasattr(self.model_instance, "translate"):
            return self.model_instance.translate(text)

        if hasattr(self.model_instance, "generate_translation"):
            return self.model_instance.generate_translation(text)

        raise AttributeError("模型实例缺少 translate()/generate_translation() 方法")

    def run(self, input_path: str, output_path: str) -> str:
        ext = os.path.splitext(input_path)[1].lower()

        if ext == ".txt":
            return self._translate_txt(input_path, output_path)

        if ext == ".epub":
            return self.translation_core.translate_epub(input_path, output_path)

        raise ValueError(f"暂不支持的文件类型: {ext}")

    def _translate_txt(self, input_path: str, output_path: str) -> str:
        with open(input_path, "r", encoding="utf-8") as f:
            text = f.read()

        translated = self.translation_core.translate_long_text(text)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(translated)

        self.translation_core.close()
        return output_path


class FileTranslationWorker(QThread):
    progress = Signal(str)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, model_instance, input_path: str, output_path: str, parent=None):
        super().__init__(parent)
        self.model_instance = model_instance
        self.input_path = input_path
        self.output_path = output_path

    def run(self):
        try:
            self.progress.emit("开始翻译文件...")

            task = FileTranslationTask(self.model_instance)
            result_path = task.run(self.input_path, self.output_path)

            self.progress.emit("翻译完成")
            self.finished.emit(result_path)

        except Exception as e:
            err = f"{e}\n\n{traceback.format_exc()}"
            self.error.emit(err)