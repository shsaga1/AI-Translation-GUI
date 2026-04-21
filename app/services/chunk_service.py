from __future__ import annotations

import re
from typing import List


class ChunkService:
    def __init__(self, min_chunk_length: int = 80, max_chunk_length: int = 600):
        self.min_chunk_length = min_chunk_length
        self.max_chunk_length = max_chunk_length

    def merge_short_segments(self, segments: list[str]) -> list[str]:
        merged: List[str] = []
        buffer = ""

        for seg in segments:
            seg = seg.strip()
            if not seg:
                if buffer:
                    merged.append(buffer)
                    buffer = ""
                continue

            # 代码块 / 数学块不要和别的文本混合
            if self._is_protected_block(seg):
                if buffer:
                    merged.append(buffer)
                    buffer = ""
                merged.append(seg)
                continue

            if not buffer:
                buffer = seg
            elif len(buffer) < self.min_chunk_length:
                candidate = buffer + "\n\n" + seg
                if len(candidate) <= self.max_chunk_length:
                    buffer = candidate
                else:
                    merged.append(buffer)
                    buffer = seg
            else:
                merged.append(buffer)
                buffer = seg

        if buffer:
            merged.append(buffer)

        return merged

    def split_long_text(self, text: str) -> list[str]:
        text = text.strip()
        if not text:
            return []

        blocks = self._split_special_blocks(text)
        results: List[str] = []

        for block in blocks:
            block = block.strip()
            if not block:
                continue

            # 特殊块直接保留
            if self._is_protected_block(block):
                results.append(block)
                continue

            if len(block) <= self.max_chunk_length:
                results.append(block)
                continue

            results.extend(self._split_by_paragraph_and_sentence(block))

        return results

    def _split_special_blocks(self, text: str) -> list[str]:
        """
        先把代码块 / 数学块 / LaTeX 环境从正文中切出来，
        避免后面被句子分割逻辑破坏。
        """
        pattern = re.compile(
            r"(```[\s\S]*?```|\$\$[\s\S]*?\$\$|\\\[[\s\S]*?\\\]|\\begin\{[^{}]+\}[\s\S]*?\\end\{[^{}]+\})",
            flags=re.MULTILINE,
        )

        parts: List[str] = []
        last = 0

        for m in pattern.finditer(text):
            before = text[last:m.start()]
            if before.strip():
                parts.extend(self._split_plain_paragraphs(before))

            parts.append(m.group(0))
            last = m.end()

        tail = text[last:]
        if tail.strip():
            parts.extend(self._split_plain_paragraphs(tail))

        return parts

    def _split_plain_paragraphs(self, text: str) -> list[str]:
        paras = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
        return paras or ([text.strip()] if text.strip() else [])

    def _split_by_paragraph_and_sentence(self, text: str) -> list[str]:
        paragraphs = self._split_plain_paragraphs(text)
        chunks: List[str] = []
        current = ""

        for para in paragraphs:
            if len(para) > self.max_chunk_length:
                for sentence_chunk in self._split_by_sentence(para):
                    if not current:
                        current = sentence_chunk
                    elif len(current) + 2 + len(sentence_chunk) <= self.max_chunk_length:
                        current += "\n\n" + sentence_chunk
                    else:
                        chunks.append(current)
                        current = sentence_chunk
                continue

            if not current:
                current = para
            elif len(current) + 2 + len(para) <= self.max_chunk_length:
                current += "\n\n" + para
            else:
                chunks.append(current)
                current = para

        if current:
            chunks.append(current)

        return chunks

    def _split_by_sentence(self, text: str) -> list[str]:
        parts = re.split(r'(?<=[。！？!?\.])\s+|(?<=;|；)\s+', text)
        results: List[str] = []
        current = ""

        for part in parts:
            part = part.strip()
            if not part:
                continue

            if not current:
                current = part
            elif len(current) + 1 + len(part) <= self.max_chunk_length:
                current += " " + part
            else:
                results.append(current)
                current = part

        if current:
            results.append(current)

        return results

    def _is_protected_block(self, text: str) -> bool:
        stripped = text.strip()
        return (
            stripped.startswith("```") and stripped.endswith("```")
        ) or (
            stripped.startswith("$$") and stripped.endswith("$$")
        ) or (
            stripped.startswith(r"\[") and stripped.endswith(r"\]")
        ) or (
            stripped.startswith(r"\begin{") and r"\end{" in stripped
        )


def split_text_into_blocks(
    text: str,
    max_chars_per_chunk: int = 1800,
    min_block_merge_length: int = 60,
) -> list[str]:
    service = ChunkService(
        min_chunk_length=min_block_merge_length,
        max_chunk_length=max_chars_per_chunk,
    )
    chunks = service.split_long_text(text)
    chunks = service.merge_short_segments(chunks)
    return chunks


def build_context_chunks(
    blocks: list[str],
    context_window: int = 1,
) -> list[str]:
    return list(blocks)