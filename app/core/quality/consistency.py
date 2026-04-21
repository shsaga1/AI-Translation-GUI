from __future__ import annotations

import json
import os
import re
from typing import Dict


class ConsistencyManager:
    """
    记录“同一个原文片段 -> 固定译文”的映射。
    现在按：
        source_language + target_language + source_text
    共同做 key
    避免 zh->en 的缓存污染 zh->ja。
    """

    def __init__(self, memory_path: str | None = None):
        self.memory_path = memory_path
        self.memory: Dict[str, str] = {}
        if memory_path and os.path.exists(memory_path):
            self.load()

    def load(self) -> None:
        if not self.memory_path or not os.path.exists(self.memory_path):
            return
        with open(self.memory_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            self.memory = {str(k): str(v) for k, v in data.items()}

    def save(self) -> None:
        if not self.memory_path:
            return
        os.makedirs(os.path.dirname(self.memory_path), exist_ok=True)
        with open(self.memory_path, "w", encoding="utf-8") as f:
            json.dump(self.memory, f, ensure_ascii=False, indent=2)

    @staticmethod
    def normalize_text(text: str) -> str:
        text = text.strip()
        text = re.sub(r"\s+", " ", text)
        return text

    def _make_key(self, source_text: str, source_language: str, target_language: str) -> str:
        src_lang = (source_language or "auto").strip().lower()
        tgt_lang = (target_language or "unknown").strip().lower()
        src_text = self.normalize_text(source_text)
        return f"{src_lang}=>{tgt_lang}::{src_text}"

    def get_known_translation(
        self,
        source_text: str,
        source_language: str,
        target_language: str,
    ) -> str | None:
        key = self._make_key(source_text, source_language, target_language)
        return self.memory.get(key)

    def remember(
        self,
        source_text: str,
        translated_text: str,
        source_language: str,
        target_language: str,
    ) -> None:
        value = self.normalize_text(translated_text)
        if not source_text or not value:
            return

        if len(source_text.strip()) < 2 or len(value.strip()) < 2:
            return

        key = self._make_key(source_text, source_language, target_language)
        if key not in self.memory:
            self.memory[key] = value