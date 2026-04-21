import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
import wave
from pathlib import Path


# ========= 强制 UTF-8 输出，尽量避免 Windows 下日志乱码 =========
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.subtitle_service import (  # noqa: E402
    build_output_segments,
    write_plain_text,
    write_segments_json,
    write_srt,
)
from app.services.translation_core import load_translation_model, translate_with_auto_review  # noqa: E402


def log(msg: str):
    print(msg, flush=True)


def status(msg: str):
    print(f"[STATUS] {msg}", flush=True)


def progress(val: int):
    try:
        val = int(val)
    except Exception:
        val = 0
    val = max(0, min(100, val))
    print(f"[PROGRESS] {val}", flush=True)


def error(msg: str):
    print(f"[ERROR] {msg}", flush=True)


def parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def resolve_ffmpeg() -> str | None:
    candidates = [
        shutil.which("ffmpeg"),
        str(PROJECT_ROOT / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe"),
        str(PROJECT_ROOT / "ffmpeg" / "bin" / "ffmpeg.exe"),
        str(PROJECT_ROOT.parent / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe"),
        str(PROJECT_ROOT.parent / "ffmpeg" / "bin" / "ffmpeg.exe"),
    ]

    for item in candidates:
        if item and Path(item).exists():
            return str(item)

    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and Path(exe).exists():
            return str(exe)
    except Exception:
        pass

    return None


def extract_audio_to_wav(input_file: str, wav_path: str) -> str | None:
    ffmpeg = resolve_ffmpeg()
    if not ffmpeg:
        log("[WARN] 未找到 ffmpeg，跳过预提取音频，改为直接把原始媒体文件送入 ASR。")
        return None

    cmd = [
        ffmpeg,
        "-y",
        "-i", str(input_file),
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        "-c:a", "pcm_s16le",
        str(wav_path),
    ]

    log(f"[INFO] 调用 ffmpeg 提取音频: {' '.join(cmd[:6])} ...")
    completed = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        log("[WARN] ffmpeg 预提取失败，改为直接把原始媒体文件送入 ASR。")
        log(completed.stdout[-1200:])
        return None

    if not Path(wav_path).exists():
        log("[WARN] ffmpeg 未生成 wav 文件，改为直接把原始媒体文件送入 ASR。")
        return None

    return str(wav_path)


def get_wav_duration_seconds(wav_path: str) -> float:
    with wave.open(str(wav_path), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        if not rate:
            return 0.0
        return frames / float(rate)


def resolve_runtime_device(device: str) -> str:
    device = str(device or "auto").strip().lower()
    if device in {"cuda", "cpu"}:
        return device

    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def resolve_compute_type(compute_precision: str, runtime_device: str) -> str:
    precision = str(compute_precision or "auto").strip().lower()

    if runtime_device == "cuda":
        mapping = {
            "auto": "float16",
            "fp16": "float16",
            "bf16": "float16",
            "int8": "int8_float16",
            "float32": "float32",
        }
        return mapping.get(precision, "float16")

    mapping = {
        "auto": "int8",
        "fp16": "int8",
        "bf16": "int8",
        "int8": "int8",
        "float32": "float32",
    }
    return mapping.get(precision, "int8")


def load_asr_model(asr_model_path: str, runtime_device: str, compute_type: str):
    try:
        from faster_whisper import WhisperModel
    except Exception as e:
        raise ImportError(f"未安装 faster-whisper，无法进行视频识别: {e}")

    try:
        model = WhisperModel(
            asr_model_path,
            device=runtime_device,
            compute_type=compute_type,
            local_files_only=True,
        )
    except TypeError:
        model = WhisperModel(
            asr_model_path,
            device=runtime_device,
            compute_type=compute_type,
        )
    except Exception as e:
        raise RuntimeError(f"加载 ASR 模型失败: {e}")

    return model


def transcribe_audio(
    media_path: str,
    asr_model_path: str,
    source_language: str,
    runtime_device: str,
    compute_type: str,
    beam_size: int,
    temperature: float,
):
    status("加载识别模型")
    progress(20)
    log(f"[INFO] ASR 模型路径: {asr_model_path}")
    log(f"[INFO] ASR 运行设备: {runtime_device}")
    log(f"[INFO] ASR compute_type: {compute_type}")

    model = load_asr_model(asr_model_path, runtime_device=runtime_device, compute_type=compute_type)

    total_duration = 0.0
    language = None if str(source_language).strip().lower() == "auto" else str(source_language).strip().lower()

    status("语音识别中")
    progress(25)

    kwargs = {
        "beam_size": max(1, int(beam_size)),
        "vad_filter": True,
        "condition_on_previous_text": True,
    }

    if language:
        kwargs["language"] = language

    try:
        temp_val = float(temperature)
        kwargs["temperature"] = temp_val
    except Exception:
        pass

    try:
        segments_iter, info = model.transcribe(media_path, **kwargs)
    except TypeError:
        kwargs.pop("condition_on_previous_text", None)
        segments_iter, info = model.transcribe(media_path, **kwargs)
    except Exception as e:
        raise RuntimeError(f"语音识别失败: {e}")

    try:
        total_duration = float(getattr(info, "duration", 0.0) or 0.0)
    except Exception:
        total_duration = 0.0

    raw_segments: list[dict] = []
    last_progress = 25

    for idx, seg in enumerate(segments_iter, start=1):
        text = str(getattr(seg, "text", "") or "").strip()
        start = float(getattr(seg, "start", 0.0) or 0.0)
        end = float(getattr(seg, "end", start) or start)

        if text:
            raw_segments.append({
                "start": start,
                "end": end,
                "text": text,
            })

        if total_duration > 0:
            ratio = max(0.0, min(1.0, end / total_duration))
            current = 25 + int(ratio * 30)
            if current > last_progress:
                progress(current)
                last_progress = current

        if idx % 10 == 0:
            log(f"[INFO] ASR 已处理 {idx} 段，当前时间轴 {end:.2f}s")

    detected_lang = getattr(info, "language", None)
    if detected_lang:
        log(f"[INFO] ASR 检测语言: {detected_lang}")
    log(f"[INFO] ASR 原始分段数: {len(raw_segments)}")

    if not raw_segments:
        raise RuntimeError("语音识别完成，但未得到有效文本分段。")

    return raw_segments


def translate_segments(
    segments,
    mt_model_path: str,
    source_language: str,
    target_language: str,
    auto_review: bool,
):
    status("加载翻译模型")
    progress(58)
    log(f"[INFO] 翻译模型路径: {mt_model_path}")

    tokenizer, model = load_translation_model(mt_model_path)
    if tokenizer is None or model is None:
        raise RuntimeError("翻译模型加载失败：tokenizer 或 model 为空。")

    total = len(segments)
    status("文本翻译中")

    for idx, seg in enumerate(segments, start=1):
        current = 58 + int((idx / max(total, 1)) * 30)
        progress(current)
        status(f"文本翻译中（{idx}/{total}）")
        log(f"[INFO] 正在翻译第 {idx}/{total} 条字幕，字符数={len(seg.source_text)}")

        translated = translate_with_auto_review(
            source_text=seg.source_text,
            tokenizer=tokenizer,
            model=model,
            source_language=source_language,
            target_language=target_language,
            auto_review=auto_review,
            logger=log,
        )
        seg.translated_text = str(translated or "").strip()

    return segments


def save_outputs(output_dir: str, stem: str, segments, keep_original: bool) -> dict[str, str]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    source_srt = write_srt(output_path / f"{stem}_source.srt", segments, mode="source")
    target_srt = write_srt(output_path / f"{stem}_target.srt", segments, mode="target")
    bilingual_srt = write_srt(output_path / f"{stem}_bilingual.srt", segments, mode="bilingual")

    source_txt = write_plain_text(output_path / f"{stem}_source.txt", segments, mode="source")
    target_txt = write_plain_text(output_path / f"{stem}_target.txt", segments, mode="target")
    bilingual_txt = write_plain_text(output_path / f"{stem}_bilingual.txt", segments, mode="bilingual")
    segments_json = write_segments_json(output_path / f"{stem}_segments.json", segments)

    primary = bilingual_srt if keep_original else target_srt

    return {
        "primary_srt": primary,
        "source_srt": source_srt,
        "target_srt": target_srt,
        "bilingual_srt": bilingual_srt,
        "source_txt": source_txt,
        "target_txt": target_txt,
        "bilingual_txt": bilingual_txt,
        "segments_json": segments_json,
    }


def translate_video(
    input_file: str,
    output_dir: str,
    asr_model_path: str,
    mt_model_path: str,
    source_language: str,
    target_language: str,
    context_level_name: str,
    context_window: int,
    compute_precision: str,
    device: str,
    beam_size: int,
    temperature: float,
    keep_original: bool,
    auto_review: bool,
):
    status("校验输入")
    progress(5)

    input_path = Path(input_file)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        raise RuntimeError(f"输入文件不存在: {input_file}")
    if not Path(asr_model_path).exists():
        raise RuntimeError(f"识别模型路径不存在: {asr_model_path}")
    if not Path(mt_model_path).exists():
        raise RuntimeError(f"翻译模型路径不存在: {mt_model_path}")

    runtime_device = resolve_runtime_device(device)
    compute_type = resolve_compute_type(compute_precision, runtime_device)

    log(f"[INFO] 输入文件: {input_file}")
    log(f"[INFO] 输出目录: {output_dir}")
    log(f"[INFO] ASR 模型: {asr_model_path}")
    log(f"[INFO] 翻译模型: {mt_model_path}")
    log(f"[INFO] 源语言: {source_language}")
    log(f"[INFO] 目标语言: {target_language}")
    log(f"[INFO] 上下文联系: {context_level_name}（窗口={context_window}）")
    log(f"[INFO] 推理精度: {compute_precision}")
    log(f"[INFO] 运行设备: {device} -> {runtime_device}")
    log(f"[INFO] ASR compute_type: {compute_type}")
    log(f"[INFO] Beam Size: {beam_size}")
    log(f"[INFO] Temperature: {temperature}")
    log(f"[INFO] 保留原文: {keep_original}")
    log(f"[INFO] 自动复查: {auto_review}")

    status("提取音频中")
    progress(10)

    with tempfile.TemporaryDirectory(prefix="video_trans_", dir=str(output_path)) as tmpdir:
        wav_path = Path(tmpdir) / f"{input_path.stem}_audio.wav"
        asr_input_path = extract_audio_to_wav(str(input_path), str(wav_path))
        if asr_input_path:
            log(f"[INFO] 临时音频: {wav_path}")
            try:
                duration = get_wav_duration_seconds(str(wav_path))
                log(f"[INFO] 音频时长: {duration:.2f}s")
            except Exception:
                pass
        else:
            asr_input_path = str(input_path)
            log(f"[INFO] 直接使用原始媒体送入 ASR: {asr_input_path}")

        raw_segments = transcribe_audio(
            media_path=str(asr_input_path),
            asr_model_path=asr_model_path,
            source_language=source_language,
            runtime_device=runtime_device,
            compute_type=compute_type,
            beam_size=beam_size,
            temperature=temperature,
        )

        status("整理字幕分段")
        progress(56)
        segments = build_output_segments(raw_segments, context_window=context_window)
        log(f"[INFO] 整理后字幕分段数: {len(segments)}")

        if not segments:
            raise RuntimeError("字幕分段整理后为空。")

        segments = translate_segments(
            segments=segments,
            mt_model_path=mt_model_path,
            source_language=source_language,
            target_language=target_language,
            auto_review=auto_review,
        )

        status("生成字幕中")
        progress(92)
        outputs = save_outputs(
            output_dir=str(output_path),
            stem=input_path.stem,
            segments=segments,
            keep_original=keep_original,
        )

    progress(100)
    status("完成")
    log(f"[INFO] 主字幕输出: {outputs['primary_srt']}")
    for key, value in outputs.items():
        log(f"[OUTPUT] {key}={value}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_file", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--asr_model_path", required=True)
    parser.add_argument("--mt_model_path", required=True)
    parser.add_argument("--source_language", default="auto")
    parser.add_argument("--target_language", default="zh")
    parser.add_argument("--context_level_name", default="标准上下文（中等）")
    parser.add_argument("--context_window", type=int, default=2)
    parser.add_argument("--compute_precision", default="auto")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--beam_size", type=int, default=1)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--keep_original", default="1")
    parser.add_argument("--auto_review", default="0")

    args = parser.parse_args()

    try:
        translate_video(
            input_file=args.input_file,
            output_dir=args.output_dir,
            asr_model_path=args.asr_model_path,
            mt_model_path=args.mt_model_path,
            source_language=args.source_language,
            target_language=args.target_language,
            context_level_name=args.context_level_name,
            context_window=args.context_window,
            compute_precision=args.compute_precision,
            device=args.device,
            beam_size=args.beam_size,
            temperature=args.temperature,
            keep_original=parse_bool(args.keep_original),
            auto_review=parse_bool(args.auto_review),
        )
    except Exception as e:
        progress(100)
        status("失败")
        error(f"{type(e).__name__}: {e}")
        error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
