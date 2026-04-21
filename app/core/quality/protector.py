from __future__ import annotations

import json
import os
import re
from typing import List, Tuple


DEFAULT_PATTERNS = [
    # fenced code blocks
    r"```[\s\S]*?```",

    # inline code
    r"`[^`\n]+`",

    # LaTeX block math
    r"\$\$[\s\S]*?\$\$",
    r"\\\[[\s\S]*?\\\]",

    # LaTeX inline math
    r"\$(?:\\.|[^$\n])+\$",
    r"\\\((?:\\.|[^)\n])+\\\)",

    # LaTeX environments
    r"\\begin\{[^{}]+\}[\s\S]*?\\end\{[^{}]+\}",

    # common latex commands
    r"\\[A-Za-z]+(?:\[[^\]]*\])?(?:\{[^{}]*\})*",

    # placeholders / variables
    r"\{[A-Za-z_][A-Za-z0-9_]*\}",
    r"\$\{[A-Za-z_][A-Za-z0-9_]*\}",
    r"%[sdifg]",
    r"\b[A-Za-z_][A-Za-z0-9_]*\(\)",

    # HTML / XML tags
    r"</?[A-Za-z][^>]*?>",

    # URL / email
    r"https?://[^\s]+",
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",

    # Windows / Linux paths
    r"[A-Za-z]:\\(?:[^\\/:*?\"<>|\r\n]+\\)*[^\\/:*?\"<>|\r\n]*",
    r"(?:/[^/\s]+)+",

    # Markdown link / image
    r"!\[[^\]]+\]\([^)]+\)",
    r"\[[^\]]+\]\([^)]+\)",

    # namespace / object access / code identifiers
    r"\b[A-Za-z_][A-Za-z0-9_]*(?:::[A-Za-z_][A-Za-z0-9_]*)+\b",
    r"\b[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+\b",

    # equation-like lines
    r"\b[A-Za-z](?:_[A-Za-z0-9]+)?\s*=\s*[^\n]{1,120}",
]


class PreserveProtector:
    """
    把不该翻译的内容替换成占位符，翻译后再恢复。
    强化保护：
    - 代码
    - 公式
    - LaTeX
    - 链接/路径
    - 占位符/变量
    """

    def __init__(self, config_path: str | None = None):
        self.patterns = list(DEFAULT_PATTERNS)
        if config_path and os.path.exists(config_path):
            self.load_config(config_path)

    def load_config(self, path: str) -> None:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        extra_patterns = data.get("patterns", [])
        if isinstance(extra_patterns, list):
            self.patterns.extend(extra_patterns)

    def protect(self, text: str) -> Tuple[str, dict[str, str]]:
        matches: List[Tuple[int, int, str]] = []

        for pattern in self.patterns:
            for m in re.finditer(pattern, text, flags=re.MULTILINE):
                matches.append((m.start(), m.end(), m.group(0)))

        # 去重 + 去重叠
        matches.sort(key=lambda x: (x[0], -(x[1] - x[0])))

        filtered: List[Tuple[int, int, str]] = []
        last_end = -1
        for start, end, value in matches:
            if start >= last_end:
                filtered.append((start, end, value))
                last_end = end

        if not filtered:
            return text, {}

        parts = []
        placeholder_map: dict[str, str] = {}
        prev = 0

        for idx, (start, end, value) in enumerate(filtered):
            placeholder = f"__KEEP_{idx}__"
            parts.append(text[prev:start])
            parts.append(placeholder)
            placeholder_map[placeholder] = value
            prev = end

        parts.append(text[prev:])
        protected_text = "".join(parts)
        return protected_text, placeholder_map

    @staticmethod
    def restore(text: str, placeholder_map: dict[str, str]) -> str:
        restored = text
        for placeholder, original in placeholder_map.items():
            restored = restored.replace(placeholder, original)
        return restored