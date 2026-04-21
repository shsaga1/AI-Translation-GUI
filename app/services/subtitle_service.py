from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class SubtitleSegment:
    start: float
    end: float
    source_text: str
    translated_text: str = ""

    @property
    def duration(self) -> float:
        return max(0.0, float(self.end) - float(self.start))


def normalize_subtitle_text(text: str) -> str:
    text = str(text or "")
    text = text.replace("\u3000", " ")
    text = text.replace("\r", "\n")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"\s+([，。；：！？、])", r"\1", text)
    return text.strip()


def format_srt_timestamp(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    total_ms = int(round(seconds * 1000))
    hours = total_ms // 3_600_000
    minutes = (total_ms % 3_600_000) // 60_000
    secs = (total_ms % 60_000) // 1000
    millis = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _text_display_width(text: str) -> float:
    width = 0.0
    for ch in str(text or ""):
        if re.match(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", ch):
            width += 1.0
        elif ch.isspace():
            width += 0.35
        else:
            width += 0.55
    return width


def _split_by_width(text: str, max_width: float) -> list[str]:
    text = normalize_subtitle_text(text)
    if not text:
        return []

    if _text_display_width(text) <= max_width:
        return [text]

    pieces: list[str] = []
    current = ""

    tokens = re.findall(r"\S+\s*", text)
    if not tokens:
        tokens = list(text)

    for token in tokens:
        candidate = (current + token).strip()
        if current and _text_display_width(candidate) > max_width:
            pieces.append(current.strip())
            current = token.strip()
            continue
        current = candidate

    if current.strip():
        pieces.append(current.strip())

    fixed: list[str] = []
    for piece in pieces:
        if _text_display_width(piece) <= max_width:
            fixed.append(piece)
            continue

        buffer = ""
        for ch in piece:
            candidate = buffer + ch
            if buffer and _text_display_width(candidate) > max_width:
                fixed.append(buffer)
                buffer = ch
            else:
                buffer = candidate
        if buffer:
            fixed.append(buffer)

    return [x.strip() for x in fixed if x.strip()]


def wrap_subtitle_text(text: str, max_lines: int = 2, max_width: float = 18.0) -> str:
    lines = _split_by_width(text, max_width=max_width)
    if not lines:
        return ""

    if len(lines) <= max_lines:
        return "\n".join(lines)

    merged = lines[: max_lines - 1]
    merged.append(" ".join(lines[max_lines - 1 :]))
    return "\n".join(merged)


def _ends_like_sentence(text: str) -> bool:
    text = normalize_subtitle_text(text)
    return bool(re.search(r"[。！？!?….,，;；:]$", text))


def merge_subtitle_segments(
    segments: list[SubtitleSegment],
    *,
    max_duration: float = 7.0,
    max_gap: float = 0.45,
    max_chars: int = 90,
) -> list[SubtitleSegment]:
    merged: list[SubtitleSegment] = []

    for raw_seg in segments:
        text = normalize_subtitle_text(raw_seg.source_text)
        if not text:
            continue

        seg = SubtitleSegment(
            start=float(raw_seg.start),
            end=max(float(raw_seg.end), float(raw_seg.start) + 0.05),
            source_text=text,
        )

        if not merged:
            merged.append(seg)
            continue

        prev = merged[-1]
        gap = seg.start - prev.end
        combined_text = f"{prev.source_text} {seg.source_text}".strip()
        combined_duration = max(prev.end, seg.end) - prev.start

        short_prev = len(prev.source_text) <= 16 or prev.duration <= 1.4
        short_next = len(seg.source_text) <= 16 or seg.duration <= 1.4
        continuation = not _ends_like_sentence(prev.source_text)

        should_merge = (
            gap <= max_gap
            and combined_duration <= max_duration
            and len(combined_text) <= max_chars
            and (short_prev or short_next or continuation)
        )

        if should_merge:
            prev.end = max(prev.end, seg.end)
            prev.source_text = combined_text
        else:
            merged.append(seg)

    return merged


def build_output_segments(
    raw_segments: list[dict],
    *,
    context_window: int = 2,
) -> list[SubtitleSegment]:
    normalized: list[SubtitleSegment] = []
    for item in raw_segments:
        try:
            start = float(item.get("start", 0.0))
            end = float(item.get("end", start))
        except Exception:
            continue

        text = normalize_subtitle_text(item.get("text", ""))
        if not text:
            continue

        normalized.append(SubtitleSegment(start=start, end=end, source_text=text))

    if not normalized:
        return []

    max_duration = 6.0 + min(max(context_window, 0), 8) * 0.45
    max_chars = 72 + min(max(context_window, 0), 8) * 8
    return merge_subtitle_segments(
        normalized,
        max_duration=max_duration,
        max_gap=0.55,
        max_chars=max_chars,
    )


def write_srt(path: str | Path, segments: list[SubtitleSegment], mode: str = "target") -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    blocks: list[str] = []
    for idx, seg in enumerate(segments, start=1):
        if mode == "source":
            content = wrap_subtitle_text(seg.source_text, max_lines=2, max_width=24.0)
        elif mode == "bilingual":
            src = wrap_subtitle_text(seg.source_text, max_lines=2, max_width=24.0)
            tgt = wrap_subtitle_text(seg.translated_text, max_lines=2, max_width=20.0)
            content = f"{src}\n{tgt}".strip()
        else:
            content = wrap_subtitle_text(seg.translated_text, max_lines=2, max_width=20.0)

        content = content.strip()
        if not content:
            continue

        blocks.append(
            f"{idx}\n"
            f"{format_srt_timestamp(seg.start)} --> {format_srt_timestamp(seg.end)}\n"
            f"{content}\n"
        )

    path.write_text("\n".join(blocks), encoding="utf-8")
    return str(path)


def write_plain_text(path: str | Path, segments: list[SubtitleSegment], mode: str = "target") -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    for seg in segments:
        if mode == "source":
            lines.append(seg.source_text)
        elif mode == "bilingual":
            lines.append(seg.source_text)
            lines.append(seg.translated_text)
            lines.append("")
        else:
            lines.append(seg.translated_text)

    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return str(path)


def write_segments_json(path: str | Path, segments: list[SubtitleSegment]) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = [asdict(seg) for seg in segments]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)
