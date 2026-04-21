import argparse
import os
import sys
import traceback
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

from app.services.chunk_service import split_text_into_blocks, build_context_chunks
from app.services.translation_core import load_translation_model, translate_with_auto_review


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
    s = str(value).strip().lower()
    return s in {"1", "true", "yes", "y", "on"}


def safe_join_chunk(chunk) -> str:
    if isinstance(chunk, str):
        return chunk
    if isinstance(chunk, (list, tuple)):
        return "\n\n".join("" if x is None else str(x) for x in chunk)
    return str(chunk)


def translate_text(
    input_text: str,
    mt_model_path: str,
    source_language: str,
    target_language: str,
    context_level_name: str,
    context_window: int,
    compute_precision: str,
    auto_review: bool,
):
    status("校验输入")
    progress(5)

    if input_text is None:
        raise RuntimeError("input_text 为空。")

    input_text = str(input_text)
    mt_model_path = str(mt_model_path).strip()
    source_language = str(source_language).strip()
    target_language = str(target_language).strip()
    context_level_name = str(context_level_name).strip()
    compute_precision = str(compute_precision).strip()

    log(f"[INFO] 输入文本长度: {len(input_text)}")
    log(f"[INFO] 翻译模型路径: {mt_model_path}")
    log(f"[INFO] 源语言: {source_language}")
    log(f"[INFO] 目标语言: {target_language}")
    log(f"[INFO] 上下文联系: {context_level_name}（窗口={context_window}）")
    log(f"[INFO] 推理精度: {compute_precision}")
    log(f"[INFO] 自动复查: {auto_review}")

    if not input_text.strip():
        raise RuntimeError("输入文本为空，无法翻译。")

    model_path = Path(mt_model_path)
    if not model_path.exists():
        raise RuntimeError(f"翻译模型路径不存在: {mt_model_path}")

    status("分块中")
    progress(15)
    blocks = split_text_into_blocks(input_text)

    if not blocks:
        raise RuntimeError("未提取到可翻译内容。")

    log(f"[INFO] 初始内容块数: {len(blocks)}")

    chunks = build_context_chunks(blocks, context_window)
    if not chunks:
        raise RuntimeError("上下文构建后没有可翻译块。")

    log(f"[INFO] 上下文处理后块数: {len(chunks)}")

    status("加载翻译模型")
    progress(30)
    tokenizer, model = load_translation_model(mt_model_path)

    if tokenizer is None or model is None:
        raise RuntimeError("翻译模型加载失败：tokenizer 或 model 为空。")

    translated_chunks = []
    total = len(chunks)

    for idx, chunk in enumerate(chunks, start=1):
        status(f"翻译中（{idx}/{total}）")
        current_progress = 30 + int((idx / max(total, 1)) * 60)
        progress(current_progress)

        src_text = safe_join_chunk(chunk)
        log(f"[INFO] 正在翻译第 {idx}/{total} 块，字符数={len(src_text)}")

        if not src_text.strip():
            log(f"[WARN] 第 {idx}/{total} 块为空，跳过。")
            translated_chunks.append("")
            continue

        try:
            translated = translate_with_auto_review(
                source_text=src_text,
                tokenizer=tokenizer,
                model=model,
                source_language=source_language,
                target_language=target_language,
                auto_review=auto_review,
                logger=log,
            )
        except Exception as e:
            error(f"第 {idx}/{total} 块翻译失败: {e}")
            error(traceback.format_exc())
            raise

        if translated is None:
            translated = ""

        translated_chunks.append(str(translated))

    final_text = "\n\n".join(translated_chunks).strip()

    progress(100)
    status("完成")

    print("[RESULT_BEGIN]", flush=True)
    print(final_text, flush=True)
    print("[RESULT_END]", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_text", required=True)
    parser.add_argument("--mt_model_path", required=True)
    parser.add_argument("--source_language", default="en")
    parser.add_argument("--target_language", default="zh")
    parser.add_argument("--context_level_name", default="标准上下文（中等）")
    parser.add_argument("--context_window", type=int, default=2)
    parser.add_argument("--compute_precision", default="auto")
    parser.add_argument("--auto_review", default="0")

    args = parser.parse_args()

    try:
        translate_text(
            input_text=args.input_text,
            mt_model_path=args.mt_model_path,
            source_language=args.source_language,
            target_language=args.target_language,
            context_level_name=args.context_level_name,
            context_window=args.context_window,
            compute_precision=args.compute_precision,
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