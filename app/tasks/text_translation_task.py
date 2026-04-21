import subprocess
import sys
import re
from pathlib import Path

from PySide6.QtCore import QThread, Signal


class TextTranslationWorker(QThread):
    log_signal = Signal(str)
    progress_signal = Signal(int)
    status_signal = Signal(str)
    finished_signal = Signal(str)
    error_signal = Signal(str)

    def __init__(self, payload: dict):
        super().__init__()
        self.payload = payload
        self._stop_requested = False
        self._process = None

    def request_stop(self):
        self._stop_requested = True
        if self._process is not None:
            try:
                self._process.terminate()
            except Exception:
                pass

    def run(self):
        try:
            input_text = self.payload["input_text"]
            mt_model = self.payload["mt_model"]
            source_language = self.payload["source_language"]
            target_language = self.payload["target_language"]
            context_level_name = self.payload["context_level_name"]
            context_window = self.payload["context_window"]
            compute_precision = self.payload["compute_precision"]
            auto_review = self.payload["auto_review"]

            root_dir = Path(__file__).resolve().parents[2]
            script_path = root_dir / "scripts" / "translate_text.py"

            if not script_path.exists():
                raise FileNotFoundError(f"未找到脚本: {script_path}")

            self.status_signal.emit("准备调用 translate_text.py")
            self.progress_signal.emit(5)

            cmd = [
                sys.executable,
                "-u",
                str(script_path),
                "--input_text", input_text,
                "--mt_model_path", str(mt_model["path"]),
                "--source_language", str(source_language),
                "--target_language", str(target_language),
                "--context_level_name", str(context_level_name),
                "--context_window", str(context_window),
                "--compute_precision", str(compute_precision),
                "--auto_review", "1" if auto_review else "0",
            ]

            self.log_signal.emit("[INFO] 启动真实文字翻译脚本...")
            self.log_signal.emit(f"[INFO] 命令: {' '.join(cmd[:6])} ...")

            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            status_pattern = re.compile(r"^\[STATUS\]\s*(.*)$")
            progress_pattern = re.compile(r"^\[PROGRESS\]\s*(\d+)$")

            collecting_result = False
            result_lines = []

            while True:
                if self._stop_requested:
                    try:
                        self._process.terminate()
                    except Exception:
                        pass
                    raise RuntimeError("任务已停止。")

                line = self._process.stdout.readline()
                if line == "" and self._process.poll() is not None:
                    break
                if not line:
                    continue

                line = line.rstrip("\n")

                if line.strip() == "[RESULT_BEGIN]":
                    collecting_result = True
                    continue

                if line.strip() == "[RESULT_END]":
                    collecting_result = False
                    continue

                if collecting_result:
                    result_lines.append(line)
                    continue

                self.log_signal.emit(line)

                progress_match = progress_pattern.search(line)
                if progress_match:
                    try:
                        val = int(progress_match.group(1))
                        self.progress_signal.emit(val)
                    except Exception:
                        pass

                status_match = status_pattern.search(line)
                if status_match:
                    self.status_signal.emit(status_match.group(1).strip())

            return_code = self._process.wait()

            if return_code != 0:
                raise RuntimeError(f"translate_text.py 执行失败，退出码: {return_code}")

            translated_text = "\n".join(result_lines).strip()

            self.progress_signal.emit(100)
            self.status_signal.emit("已完成")
            self.finished_signal.emit(translated_text)

        except Exception as e:
            self.error_signal.emit(str(e))