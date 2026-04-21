import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.chunk_service import build_context_chunks, normalize_text
from app.services.translation_core import load_translation_model, translate_with_auto_review


def log(msg: str):
    print(msg, flush=True)


def status(msg: str):
    print(f"[STATUS] {msg}", flush=True)


def progress(val: int):
    print(f"[PROGRESS] {val}", flush=True)


def fetch_webpage(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or resp.encoding
    return resp.text


def extract_main_text(html: str) -> tuple[str, list[str]]:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript", "footer", "nav", "aside"]):
        tag.decompose()

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    candidates = []
    for selector in ["article", "main"]:
        found = soup.select(selector)
        for item in found:
            text = item.get_text("\n", strip=True)
            if len(text) > 300:
                candidates.append(item)

    if candidates:
        main_node = max(candidates, key=lambda x: len(x.get_text(" ", strip=True)))
    else:
        body = soup.body if soup.body else soup
        paragraphs = body.find_all(["p", "li", "h1", "h2", "h3", "blockquote"])
        texts = []
        for p in paragraphs:
            text = p.get_text(" ", strip=True)
            text = normalize_text(text)
            if len(text) >= 20:
                texts.append(text)
        return title, texts

    paragraphs = main_node.find_all(["p", "li", "h1", "h2", "h3", "blockquote"])
    texts = []
    for p in paragraphs:
        text = p.get_text(" ", strip=True)
        text = normalize_text(text)
        if len(text) >= 20:
            texts.append(text)

    return title, texts


def save_bilingual_html(
    output_dir: str,
    source_url: str,
    title: str,
    bilingual_blocks: list[tuple[str, str]],
):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    parsed = urlparse(source_url)
    safe_name = parsed.netloc.replace(":", "_") or "webpage"
    file_name = f"{safe_name}_bilingual.html"
    html_path = output_path / file_name

    html_parts = [
        "<!DOCTYPE html>",
        "<html lang='zh'>",
        "<head>",
        "<meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>",
        f"<title>{escape_html(title or '网页翻译结果')}</title>",
        "<style>",
        "body { font-family: Arial, sans-serif; max-width: 1100px; margin: 0 auto; padding: 24px; line-height: 1.7; }",
        ".meta { color: #666; margin-bottom: 24px; }",
        ".block { border: 1px solid #ddd; border-radius: 10px; padding: 16px; margin-bottom: 18px; }",
        ".src { margin-bottom: 10px; color: #222; white-space: pre-wrap; }",
        ".tgt { color: #0b5394; background: #f5fbff; padding: 12px; border-radius: 8px; white-space: pre-wrap; }",
        "h1 { margin-bottom: 8px; }",
        "</style>",
        "</head>",
        "<body>",
        f"<h1>{escape_html(title or '网页翻译结果')}</h1>",
        f"<div class='meta'>来源：{escape_html(source_url)}</div>",
    ]

    for src, tgt in bilingual_blocks:
        html_parts.extend([
            "<div class='block'>",
            f"<div class='src'>{escape_html(src)}</div>",
            f"<div class='tgt'>{escape_html(tgt)}</div>",
            "</div>",
        ])

    html_parts.extend(["</body>", "</html>"])
    html_path.write_text("\n".join(html_parts), encoding="utf-8")
    return html_path


def escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )


def translate_webpage(
    url: str,
    output_dir: str,
    mt_model_path: str,
    source_language: str,
    target_language: str,
    context_level_name: str,
    context_window: int,
    compute_precision: str,
    auto_review: bool,
):
    status("抓取网页中")
    progress(5)
    log(f"[INFO] URL: {url}")
    log(f"[INFO] 翻译模型路径: {mt_model_path}")
    log(f"[INFO] 源语言: {source_language}")
    log(f"[INFO] 目标语言: {target_language}")
    log(f"[INFO] 上下文联系: {context_level_name}（窗口={context_window}）")
    log(f"[INFO] 推理精度: {compute_precision}")
    log(f"[INFO] 自动复查: {auto_review}")

    html = fetch_webpage(url)

    status("提取正文中")
    progress(20)
    title, paragraphs = extract_main_text(html)

    if not paragraphs:
        raise RuntimeError("未提取到可翻译的正文内容。")

    log(f"[INFO] 提取到正文段落数: {len(paragraphs)}")
    chunks = build_context_chunks(paragraphs, context_window)
    log(f"[INFO] 分块后块数: {len(chunks)}")

    status("加载翻译模型")
    progress(35)
    tokenizer, model = load_translation_model(mt_model_path)

    bilingual_blocks = []
    total = len(chunks)

    for idx, chunk in enumerate(chunks, start=1):
        status(f"翻译中（{idx}/{total}）")
        current_progress = 35 + int((idx / max(total, 1)) * 55)
        progress(current_progress)

        src_text = "\n\n".join(chunk)
        log(f"[INFO] 正在翻译第 {idx}/{total} 块，字符数={len(src_text)}")

        translated = translate_with_auto_review(
            source_text=src_text,
            tokenizer=tokenizer,
            model=model,
            source_language=source_language,
            target_language=target_language,
            auto_review=auto_review,
            logger=log,
        )
        bilingual_blocks.append((src_text, translated))

    status("输出 HTML 中")
    progress(95)
    html_path = save_bilingual_html(
        output_dir=output_dir,
        source_url=url,
        title=title,
        bilingual_blocks=bilingual_blocks,
    )

    progress(100)
    status("完成")
    log(f"[INFO] 网页翻译完成，输出文件: {html_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--mt_model_path", required=True)
    parser.add_argument("--source_language", default="en")
    parser.add_argument("--target_language", default="zh")
    parser.add_argument("--context_level_name", default="标准上下文（中等）")
    parser.add_argument("--context_window", type=int, default=2)
    parser.add_argument("--compute_precision", default="auto")
    parser.add_argument("--auto_review", default="0")

    args = parser.parse_args()

    translate_webpage(
        url=args.url,
        output_dir=args.output_dir,
        mt_model_path=args.mt_model_path,
        source_language=args.source_language,
        target_language=args.target_language,
        context_level_name=args.context_level_name,
        context_window=args.context_window,
        compute_precision=args.compute_precision,
        auto_review=(str(args.auto_review) == "1"),
    )


if __name__ == "__main__":
    main()