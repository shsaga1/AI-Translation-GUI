# app/core/quality/glossary.py
from __future__ import annotations

import csv
import os
import re
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class GlossaryItem:
    source: str
    target: str
    case_sensitive: bool = False


class GlossaryManager:
    """
    术语表管理：
    - 从 CSV 读取术语
    - 在翻译前把术语替换成占位符，避免被模型乱翻
    - 在翻译后恢复成指定译文
    """

    def __init__(self, glossary_path: str | None = None):
        self.glossary_path = glossary_path
        self.items: List[GlossaryItem] = []
        if glossary_path and os.path.exists(glossary_path):
            self.load_csv(glossary_path)

    def load_csv(self, path: str) -> None:
        self.items.clear()
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                source = (row.get("source") or "").strip()
                target = (row.get("target") or "").strip()
                case_sensitive = str(row.get("case_sensitive", "false")).strip().lower() == "true"
                if source and target:
                    self.items.append(
                        GlossaryItem(
                            source=source,
                            target=target,
                            case_sensitive=case_sensitive,
                        )
                    )

        # 长词优先，避免短词先匹配把长词拆坏
        self.items.sort(key=lambda x: len(x.source), reverse=True)

    def protect_terms(self, text: str) -> Tuple[str, dict[str, str]]:
        """
        把术语替换成占位符，例如：
        House of Suns -> __TERM_0__
        最后统一恢复成 target
        """
        placeholder_map: dict[str, str] = {}
        protected_text = text

        for idx, item in enumerate(self.items):
            placeholder = f"__TERM_{idx}__"

            flags = 0 if item.case_sensitive else re.IGNORECASE
            pattern = re.escape(item.source)

            def repl(_match):
                placeholder_map[placeholder] = item.target
                return placeholder

            protected_text = re.sub(pattern, repl, protected_text, flags=flags)

        return protected_text, placeholder_map

    @staticmethod
    def restore_terms(text: str, placeholder_map: dict[str, str]) -> str:
        restored = text
        for placeholder, target in placeholder_map.items():
            restored = restored.replace(placeholder, target)
        return restored