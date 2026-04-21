from __future__ import annotations

import re
from typing import Callable

from app.core.quality.consistency import ConsistencyManager
from app.core.quality.glossary import GlossaryManager
from app.core.quality.protector import PreserveProtector


class EnhancedTranslationPipeline:
    """
    翻译增强流水线：
    1. 先查全文一致性缓存（现在按语言对区分）
    2. 再保护术语表
    3. 再保护保留词
    4. 调用底层翻译函数
    5. 恢复保留词
    6. 恢复术语表
    7. 记录一致性
    """

    def __init__(
        self,
        glossary_path: str | None = None,
        preserve_config_path: str | None = None,
        consistency_memory_path: str | None = None,
        enable_consistency: bool = True,
        enable_glossary: bool = True,
        enable_preserve: bool = True,
    ):
        self.enable_consistency = enable_consistency
        self.enable_glossary = enable_glossary
        self.enable_preserve = enable_preserve

        self.glossary = GlossaryManager(glossary_path) if enable_glossary else None
        self.protector = PreserveProtector(preserve_config_path) if enable_preserve else None
        self.consistency = ConsistencyManager(consistency_memory_path) if enable_consistency else None

    def translate_text(
        self,
        text: str,
        base_translate_func: Callable[[str], str],
        source_language: str = "auto",
        target_language: str = "zh",
    ) -> str:
        if not text or not text.strip():
            return text

        source_text = text

        # 1. 全文一致性缓存命中（现在按语言对查）
        if self.consistency:
            known = self.consistency.get_known_translation(
                source_text=source_text,
                source_language=source_language,
                target_language=target_language,
            )
            if known:
                return known

        working_text = text

        # 2. 术语保护
        term_map = {}
        if self.glossary:
            working_text, term_map = self.glossary.protect_terms(working_text)

        # 3. 保留词保护
        keep_map = {}
        if self.protector:
            working_text, keep_map = self.protector.protect(working_text)

        # 4. 底层翻译
        translated = base_translate_func(working_text)

        # 5. 恢复保留词
        if self.protector:
            translated = self.protector.restore(translated, keep_map)

        # 6. 恢复术语
        if self.glossary:
            translated = self.glossary.restore_terms(translated, term_map)

        translated = self._cleanup_placeholders(translated)

        # 7. 记忆一致性（现在按语言对存）
        if self.consistency:
            self.consistency.remember(
                source_text=source_text,
                translated_text=translated,
                source_language=source_language,
                target_language=target_language,
            )

        return translated

    def flush_memory(self) -> None:
        if self.consistency:
            self.consistency.save()

    @staticmethod
    def _cleanup_placeholders(text: str) -> str:
        text = re.sub(r"\s+(__KEEP_\d+__)", r"\1", text)
        text = re.sub(r"(__KEEP_\d+__)\s+", r"\1", text)
        text = re.sub(r"\s+(__TERM_\d+__)", r"\1", text)
        text = re.sub(r"(__TERM_\d+__)\s+", r"\1", text)
        return text