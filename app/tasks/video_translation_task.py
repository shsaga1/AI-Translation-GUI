import subprocess
import sys
import re
from pathlib import Path

from PySide6.QtCore import QThread, Signal


class TranslationWorker(QThread):
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
            input_file = self.payload["input_file"]
            output_dir = self.payload["output_dir"]
            asr_model = self.payload["asr_model"]
            mt_model = self.payload["mt_model"]
            source_language = self.payload["source_language"]
            target_language = self.payload["target_language"]
            context_level_name = self.payload["context_level_name"]
            context_window = self.payload["context_window"]
            compute_precision = self.payload["compute_precision"]
            device = self.payload["device"]
            beam_size = self.payload["beam_size"]
            temperature = self.payload["temperature"]
            keep_original = self.payload["keep_original"]
            auto_review = self.payload["auto_review"]

            root_dir = Path(__file__).resolve().parents[2]
            script_path = root_dir / "scripts" / "trans_video.py"

            if not script_path.exists():
                raise FileNotFoundError(f"未找到脚本: {script_path}")

            self.status_signal.emit("准备调用 trans_video.py")
            self.progress_signal.emit(5)

            cmd = [
                sys.executable,
                "-u",
                str(script_path),
                "--input_file", str(input_file),
                "--output_dir", str(output_dir),
                "--asr_model_path", str(asr_model["path"]),
                "--mt_model_path", str(mt_model["path"]),
                "--source_language", str(source_language),
                "--target_language", str(target_language),
                "--context_level_name", str(context_level_name),
                "--context_window", str(context_window),
                "--compute_precision", str(compute_precision),
                "--device", str(device),
                "--beam_size", str(beam_size),
                "--temperature", str(temperature),
                "--keep_original", "1" if keep_original else "0",
                "--auto_review", "1" if auto_review else "0",
            ]

            self.log_signal.emit("[INFO] 启动真实翻译脚本...")
            self.log_signal.emit("[INFO] 命令如下：")
            self.log_signal.emit(" ".join(cmd))

            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )

            self.status_signal.emit("翻译任务执行中")
            self.progress_signal.emit(10)

            progress_pattern = re.compile(r"\[PROGRESS\]\s*(\d+)")
            status_pattern = re.compile(r"\[STATUS\]\s*(.+)")
            output_pattern = re.compile(r"\[OUTPUT\]\s*primary_srt=(.+)")
            primary_output = None

            while True:
                if self._stop_requested:
                    self.request_stop()
                    raise RuntimeError("任务已被用户停止。")

                line = self._process.stdout.readline()
                if not line:
                    if self._process.poll() is not None:
                        break
                    continue

                line = line.rstrip("\n")
                if not line.strip():
                    continue

                self.log_signal.emit(line)

                progress_match = progress_pattern.search(line)
                if progress_match:
                    try:
                        value = int(progress_match.group(1))
                        value = max(0, min(100, value))
                        self.progress_signal.emit(value)
                    except Exception:
                        pass

                status_match = status_pattern.search(line)
                if status_match:
                    self.status_signal.emit(status_match.group(1).strip())

                output_match = output_pattern.search(line)
                if output_match:
                    primary_output = output_match.group(1).strip()

            return_code = self._process.wait()

            if return_code != 0:
                raise RuntimeError(f"trans_video.py 执行失败，退出码: {return_code}")

            self.progress_signal.emit(100)
            self.status_signal.emit("已完成")
            if primary_output:
                self.finished_signal.emit(f"视频翻译完成，主字幕文件：{primary_output}")
            else:
                self.finished_signal.emit("视频翻译完成。")

        except Exception as e:
            self.error_signal.emit(str(e))