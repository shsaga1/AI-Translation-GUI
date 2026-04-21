from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class QualityIssue:
    level: str
    code: str
    message: str


class QualityCheckService:
    PLACEHOLDER_PATTERNS = [
        r"__KEEP_\d+__",
        r"__TERM_\d+__",
        r"<unk>",
    ]

    def check_translation(self, source_text: str, translated_text: str) -> list[QualityIssue]:
        issues: list[QualityIssue] = []

        src = (source_text or "").strip()
        tgt = (translated_text or "").strip()

        if not src:
            return issues

        if not tgt:
            issues.append(QualityIssue("error", "empty_translation", "译文为空"))
            return issues

        for pattern in self.PLACEHOLDER_PATTERNS:
            if re.search(pattern, tgt, flags=re.IGNORECASE):
                issues.append(
                    QualityIssue(
                        "error",
                        "placeholder_left",
                        f"译文中残留占位符或异常标记: {pattern}"
                    )
                )

        src_en_words = self._count_english_words(src)
        tgt_en_words = self._count_english_words(tgt)

        if src_en_words >= 8 and tgt_en_words >= max(6, int(src_en_words * 0.6)):
            issues.append(
                QualityIssue(
                    "warning",
                    "too_much_english_left",
                    "译文中残留较多英文，可能存在漏翻"
                )
            )

        if len(src) >= 80 and len(tgt) <= max(8, int(len(src) * 0.2)):
            issues.append(
                QualityIssue(
                    "warning",
                    "translation_too_short",
                    "译文长度明显偏短，可能有省略"
                )
            )

        if self._normalized_similarity(src, tgt) > 0.85 and self._count_chinese_chars(tgt) < 3:
            issues.append(
                QualityIssue(
                    "warning",
                    "almost_not_translated",
                    "译文与原文高度相似，疑似未翻译"
                )
            )

        return issues

    def has_serious_issue(self, issues: list[QualityIssue]) -> bool:
        return any(x.level == "error" for x in issues)

    def _count_english_words(self, text: str) -> int:
        return len(re.findall(r"\b[A-Za-z]{2,}\b", text))

    def _count_chinese_chars(self, text: str) -> int:
        return len(re.findall(r"[\u4e00-\u9fff]", text))

    def _normalized_similarity(self, a: str, b: str) -> float:
        import difflib

        a_norm = re.sub(r"\s+", " ", a.strip())
        b_norm = re.sub(r"\s+", " ", b.strip())
        return difflib.SequenceMatcher(None, a_norm, b_norm).ratio()