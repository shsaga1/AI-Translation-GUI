from __future__ import annotations

import os
import re
import zipfile
from typing import Callable

from bs4 import BeautifulSoup

from app.core.quality.enhanced_pipeline import EnhancedTranslationPipeline
from app.services.chunk_service import ChunkService
from app.services.config_service import ConfigService
from app.services.quality_check_service import QualityCheckService


class TranslationCore:
    TRANSLATABLE_TAGS = {
        "p", "li", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6",
        "figcaption", "td", "th", "dd", "dt", "caption"
    }

    SKIP_CLASS_KEYWORDS = {
        "toc", "nav", "copyright", "cover", "index", "contents"
    }

    def __init__(
    self,
    base_translate_func: Callable[[str], str],
    source_language: str | None = None,
    target_language: str | None = None,
    ):
        self.base_translate_func = base_translate_func
        self.config_service = ConfigService()
        self.source_language = source_language or self.config_service.get("translation.source_lang", "auto")
        self.target_language = target_language or self.config_service.get("translation.target_lang", "zh")

        self.chunk_service = ChunkService(
            min_chunk_length=self.config_service.get("translation.min_chunk_length", 80),
            max_chunk_length=self.config_service.get("translation.max_chunk_length", 600),
        )

        self.quality_check_service = QualityCheckService()
        self.pipeline = self._build_pipeline()

    def _build_pipeline(self) -> EnhancedTranslationPipeline:
        glossary_path = self._get_active_glossary_path()

        return EnhancedTranslationPipeline(
            glossary_path=glossary_path,
            preserve_config_path=self.config_service.get_preserve_patterns_path(),
            consistency_memory_path=self.config_service.get_consistency_memory_path(),
            enable_consistency=self.config_service.get("quality.enable_consistency", True),
            enable_glossary=self.config_service.get("quality.enable_glossary", True),
            enable_preserve=self.config_service.get("quality.enable_preserve_rules", True),
        )

    def _get_active_glossary_path(self) -> str:
        user_path = self.config_service.get_user_glossary_path()
        default_path = self.config_service.get_default_glossary_path()

        if os.path.exists(user_path):
            return user_path
        return default_path

    def reload_glossary(self) -> None:
        self.pipeline.flush_memory()
        self.pipeline = self._build_pipeline()

    def translate_text(self, text: str) -> str:
        text = (text or "").strip()
        if not text:
            return text

        return self.pipeline.translate_text(
            text=text,
            base_translate_func=self.base_translate_func,
            source_language=self.source_language,
            target_language=self.target_language,
        )

    def translate_long_text(self, text: str) -> str:
        chunks = self.chunk_service.split_long_text(text)
        chunks = self.chunk_service.merge_short_segments(chunks)

        results: list[str] = []
        for chunk in chunks:
            if not chunk.strip():
                continue

            translated = self.translate_text(chunk)
            results.append(translated)

        self.pipeline.flush_memory()
        return "\n\n".join(results)

    def translate_epub(self, input_path: str, output_path: str) -> str:
        with zipfile.ZipFile(input_path, "r") as zin:
            with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    raw = zin.read(item.filename)

                    if self._is_html_file(item.filename):
                        try:
                            html = raw.decode("utf-8")
                        except UnicodeDecodeError:
                            try:
                                html = raw.decode("utf-8-sig")
                            except UnicodeDecodeError:
                                zout.writestr(item, raw)
                                continue

                        translated_html = self._translate_html_document(html)
                        zout.writestr(item, translated_html.encode("utf-8"))
                    else:
                        zout.writestr(item, raw)

        self.pipeline.flush_memory()
        return output_path

    def _translate_html_document(self, html: str) -> str:
        soup = BeautifulSoup(html, "lxml")
        body = soup.body
        if body is None:
            return str(soup)

        candidate_tags = body.find_all(self._is_translatable_tag)

        for tag in candidate_tags:
            if self._should_skip_tag(tag):
                continue

            source_text = self._extract_clean_text(tag)
            if not source_text or self._should_skip_text(source_text):
                continue

            translated = self.translate_text(source_text)
            issues = self.quality_check_service.check_translation(source_text, translated)

            if self.quality_check_service.has_serious_issue(issues):
                continue

            if self._looks_bad_translation(source_text, translated, issues):
                continue

            tag.clear()
            tag.append(translated)

        return str(soup)

    def _is_html_file(self, file_name: str) -> bool:
        lower = file_name.lower()
        return lower.endswith(".xhtml") or lower.endswith(".html") or lower.endswith(".htm")

    def _is_translatable_tag(self, tag) -> bool:
        return tag.name in self.TRANSLATABLE_TAGS

    def _should_skip_tag(self, tag) -> bool:
        if tag.find_parent(["script", "style", "pre", "code", "nav"]):
            return True

        classes = " ".join(tag.get("class", [])).lower()
        tag_id = (tag.get("id") or "").lower()

        for kw in self.SKIP_CLASS_KEYWORDS:
            if kw in classes or kw in tag_id:
                return True

        return False

    def _extract_clean_text(self, tag) -> str:
        text = tag.get_text(" ", strip=True)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _should_skip_text(self, text: str) -> bool:
        if len(text) <= 1:
            return True
        if re.fullmatch(r"[\W_]+", text):
            return True
        if re.fullmatch(r"\d+", text):
            return True
        return False

    def _looks_bad_translation(self, source_text: str, translated_text: str, issues) -> bool:
        has_warning = any(x.level == "warning" for x in issues)
        chinese_count = len(re.findall(r"[\u4e00-\u9fff]", translated_text))
        if has_warning and chinese_count < 3:
            return True
        return False

    def close(self) -> None:
        self.pipeline.flush_memory()


def _simple_detect_lang(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return "en"

    if re.search(r"[\u3040-\u30ff]", text):
        return "ja"

    if re.search(r"[\uac00-\ud7af]", text):
        return "ko"

    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh"

    if re.search(r"[\u0400-\u04FF]", text):
        return "ru"

    return "en"


def _map_nllb_lang(lang: str) -> str | None:
    if not lang:
        return None

    lang = str(lang).strip().lower()

    mapping = {
        "en": "eng_Latn",
        "eng": "eng_Latn",

        "zh": "zho_Hans",
        "zh-cn": "zho_Hans",
        "zh-hans": "zho_Hans",
        "cn": "zho_Hans",

        "zh-tw": "zho_Hant",
        "zh-hant": "zho_Hant",

        "ja": "jpn_Jpan",
        "jp": "jpn_Jpan",
        "jpn": "jpn_Jpan",

        "ko": "kor_Hang",
        "kr": "kor_Hang",

        "fr": "fra_Latn",
        "fra": "fra_Latn",

        "de": "deu_Latn",
        "deu": "deu_Latn",

        "es": "spa_Latn",
        "spa": "spa_Latn",

        "ru": "rus_Cyrl",
        "rus": "rus_Cyrl",

        "it": "ita_Latn",
        "ita": "ita_Latn",

        "pt": "por_Latn",
        "por": "por_Latn",

        "ar": "arb_Arab",
        "ara": "arb_Arab",
    }

    if lang == "auto":
        return None

    return mapping.get(lang)


def _normalize_space(text: str) -> str:
    text = str(text or "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _get_lang_token_id(tokenizer, lang_code: str) -> int | None:
    if not lang_code:
        return None

    if hasattr(tokenizer, "lang_code_to_id"):
        token_id = tokenizer.lang_code_to_id.get(lang_code)
        if token_id is not None:
            return token_id

    try:
        token_id = tokenizer.convert_tokens_to_ids(lang_code)
        if isinstance(token_id, int) and token_id >= 0:
            return token_id
    except Exception:
        pass

    return None


def _decode_first_text(tokenizer, outputs) -> str:
    decoded = tokenizer.batch_decode(
        outputs,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=True,
    )
    if not decoded:
        return ""
    return _normalize_space(decoded[0])


def _has_excessive_ngram_repetition(text: str, n: int = 3, threshold: int = 4) -> bool:
    text = _normalize_space(text)
    if not text:
        return False

    words = re.findall(r"\S+", text.lower())
    if len(words) >= n * threshold:
        counts: dict[tuple[str, ...], int] = {}
        for i in range(len(words) - n + 1):
            key = tuple(words[i:i + n])
            counts[key] = counts.get(key, 0) + 1
            if counts[key] >= threshold:
                return True

    chars = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    if chars:
        merged = "".join(chars)
        for size in range(2, 8):
            seen: dict[str, int] = {}
            for i in range(len(merged) - size + 1):
                piece = merged[i:i + size]
                seen[piece] = seen.get(piece, 0) + 1
                if seen[piece] >= threshold:
                    return True

    return False


def _looks_like_wrong_target_language(text: str, target_language: str) -> bool:
    text = _normalize_space(text)
    if not text:
        return False

    tgt = str(target_language or "").strip().lower()

    if tgt == "en":
        has_english = bool(re.search(r"[A-Za-z]", text))
        suspicious_french = len(re.findall(r"\b(de la|c'est|une|des|le|la)\b", text.lower())) >= 6
        suspicious_spanish = len(re.findall(r"\b(el|la|los|las|muy|es|una|de)\b", text.lower())) >= 6
        if suspicious_french or suspicious_spanish:
            return True

    if tgt == "zh":
        chinese_count = len(re.findall(r"[\u4e00-\u9fff]", text))
        latin_words = len(re.findall(r"\b[A-Za-z]{2,}\b", text))
        if chinese_count < 3 and latin_words >= 8:
            return True

    if tgt == "ja":
        kana_count = len(re.findall(r"[\u3040-\u30ff]", text))
        latin_words = len(re.findall(r"\b[A-Za-z]{2,}\b", text))
        if kana_count < 2 and latin_words >= 8:
            return True

    return False


def _build_generate_kwargs(input_token_len: int, strict: bool = False) -> dict:
    if strict:
        max_new_tokens = min(192, max(48, int(input_token_len * 1.20)))
        return {
            "max_new_tokens": max_new_tokens,
            "num_beams": 5,
            "no_repeat_ngram_size": 4,
            "repetition_penalty": 1.22,
            "length_penalty": 1.0,
            "early_stopping": True,
        }

    max_new_tokens = min(256, max(64, int(input_token_len * 1.35)))
    return {
        "max_new_tokens": max_new_tokens,
        "num_beams": 4,
        "no_repeat_ngram_size": 3,
        "repetition_penalty": 1.12,
        "length_penalty": 1.0,
        "early_stopping": True,
    }


def _build_hf_translate_func(
    tokenizer,
    model,
    source_language: str = "auto",
    target_language: str = "zh",
    logger: Callable[[str], None] | None = None,
):
    import torch

    def _log(msg: str):
        if logger is not None:
            try:
                logger(msg)
            except Exception:
                pass

    device = "cuda" if torch.cuda.is_available() else "cpu"

    try:
        model.to(device)
    except Exception:
        pass

    model.eval()

    model_name = ""
    try:
        model_name = str(getattr(model.config, "_name_or_path", "")).lower()
    except Exception:
        model_name = ""

    has_lang_code_to_id = hasattr(tokenizer, "lang_code_to_id")
    is_nllb = ("nllb" in model_name) or ("nllb" in type(tokenizer).__name__.lower())

    _log(f"[DEBUG] model_name={model_name}")
    _log(f"[DEBUG] tokenizer_class={type(tokenizer).__name__}")
    _log(f"[DEBUG] has_lang_code_to_id={has_lang_code_to_id}")
    _log(f"[DEBUG] is_nllb={is_nllb}")

    def _build_inputs_for_nllb(text: str, src_lang_code: str, tgt_lang_code: str):
        # 先尝试显式设置 tokenizer 语言
        try:
            tokenizer.src_lang = src_lang_code
        except Exception:
            pass

        try:
            tokenizer.tgt_lang = tgt_lang_code
        except Exception:
            pass

        # 优先使用 tokenizer 官方翻译输入接口（更稳）
        if hasattr(tokenizer, "_build_translation_inputs"):
            try:
                trans_inputs = tokenizer._build_translation_inputs(
                    text,
                    return_tensors="pt",
                    src_lang=src_lang_code,
                    tgt_lang=tgt_lang_code,
                    max_length=1024,
                    truncation=True,
                )
                return {k: v.to(device) for k, v in trans_inputs.items() if hasattr(v, "to")}
            except Exception as e:
                _log(f"[WARN] _build_translation_inputs 失败，回退普通 tokenizer：{e}")

        # 回退普通 tokenizer
        normal_inputs = tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=1024,
        )
        return {k: v.to(device) for k, v in normal_inputs.items()}

    def _run_generate(text: str, strict: bool = False) -> str:
        text = _normalize_space(text)

        # ====== NLLB 专用翻译路径 ======
        if is_nllb:
            detected_source = source_language
            if str(source_language).strip().lower() == "auto":
                detected_source = _simple_detect_lang(text)

            src_lang_code = _map_nllb_lang(detected_source) or "zho_Hans"
            tgt_lang_code = _map_nllb_lang(target_language)
            if tgt_lang_code is None:
                raise ValueError(f"未识别的目标语言: {target_language}")

            inputs = _build_inputs_for_nllb(text, src_lang_code, tgt_lang_code)

            input_ids = inputs.get("input_ids")
            input_token_len = int(input_ids.shape[-1]) if input_ids is not None else 64
            gen_kwargs = _build_generate_kwargs(input_token_len=input_token_len, strict=strict)

            forced_bos_token_id = _get_lang_token_id(tokenizer, tgt_lang_code)

            _log(f"[DEBUG] src_lang_code={src_lang_code}")
            _log(f"[DEBUG] tgt_lang_code={tgt_lang_code}")
            _log(f"[DEBUG] forced_bos_token_id={forced_bos_token_id}")
            _log(f"[INFO] NLLB 源语言解析: {detected_source} -> {src_lang_code}")
            _log(f"[INFO] NLLB 目标语言解析: {target_language} -> {tgt_lang_code}")
            _log(f"[INFO] 生成参数: {gen_kwargs}")

            if forced_bos_token_id is None:
                raise ValueError(
                    f"NLLB tokenizer 无法解析目标语言 token: {tgt_lang_code}。"
                    f" 当前 tokenizer 类型: {type(tokenizer).__name__}"
                )

            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    forced_bos_token_id=forced_bos_token_id,
                    **gen_kwargs,
                )

            return _decode_first_text(tokenizer, outputs)

        # ====== 通用 seq2seq 回退路径 ======
        inputs = tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=1024,
        )
        inputs = {k: v.to(device) for k, v in inputs.items()}

        input_ids = inputs.get("input_ids")
        input_token_len = int(input_ids.shape[-1]) if input_ids is not None else 64
        gen_kwargs = _build_generate_kwargs(input_token_len=input_token_len, strict=strict)

        _log(f"[INFO] 通用生成参数: {gen_kwargs}")

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                **gen_kwargs,
            )

        return _decode_first_text(tokenizer, outputs)

    def _translate(text: str) -> str:
        text = _normalize_space(text)
        if not text:
            return text

        translated = _run_generate(text, strict=False)

        if _has_excessive_ngram_repetition(translated) or _looks_like_wrong_target_language(
            translated, target_language
        ):
            _log("[WARN] 检测到可疑重复/目标语言异常，启用严格解码重试。")
            retry_translated = _run_generate(text, strict=True)

            retry_bad = _has_excessive_ngram_repetition(retry_translated) or _looks_like_wrong_target_language(
                retry_translated, target_language
            )
            if not retry_bad and retry_translated.strip():
                translated = retry_translated

        return _normalize_space(translated)

    return _translate



    def _log(msg: str):
        if logger is not None:
            try:
                logger(msg)
            except Exception:
                pass

    device = "cuda" if torch.cuda.is_available() else "cpu"

    try:
        model.to(device)
    except Exception:
        pass

    model.eval()

    model_name = ""
    try:
        model_name = str(getattr(model.config, "_name_or_path", "")).lower()
    except Exception:
        model_name = ""

    has_lang_code_to_id = hasattr(tokenizer, "lang_code_to_id")
    is_nllb = ("nllb" in model_name) or has_lang_code_to_id

    _log(f"[DEBUG] model_name={model_name}")
    _log(f"[DEBUG] tokenizer_class={type(tokenizer).__name__}")
    _log(f"[DEBUG] has_lang_code_to_id={has_lang_code_to_id}")
    _log(f"[DEBUG] is_nllb={is_nllb}")

    def _run_generate(text: str, strict: bool = False) -> str:
        inputs = tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=1024,
        )
        inputs = {k: v.to(device) for k, v in inputs.items()}

        input_ids = inputs.get("input_ids")
        input_token_len = int(input_ids.shape[-1]) if input_ids is not None else 128
        gen_kwargs = _build_generate_kwargs(input_token_len=input_token_len, strict=strict)

        # 关键修正：只要识别成 NLLB，就直接走 NLLB 逻辑
        if is_nllb:
            detected_source = source_language
            if str(source_language).strip().lower() == "auto":
                detected_source = _simple_detect_lang(text)

            src_lang_code = _map_nllb_lang(detected_source) or "eng_Latn"
            tgt_lang_code = _map_nllb_lang(target_language)
            if tgt_lang_code is None:
                raise ValueError(f"未识别的目标语言: {target_language}")

            try:
                tokenizer.src_lang = src_lang_code
            except Exception:
                pass

            forced_bos_token_id = _get_lang_token_id(tokenizer, tgt_lang_code)

            _log(f"[DEBUG] src_lang_code={src_lang_code}")
            _log(f"[DEBUG] tgt_lang_code={tgt_lang_code}")
            _log(f"[DEBUG] forced_bos_token_id={forced_bos_token_id}")

            if forced_bos_token_id is None:
                raise ValueError(
                    f"NLLB tokenizer 无法解析目标语言 token: {tgt_lang_code}。"
                    f" 当前 tokenizer 类型: {type(tokenizer).__name__}"
                )

            _log(f"[INFO] NLLB 源语言解析: {detected_source} -> {src_lang_code}")
            _log(f"[INFO] NLLB 目标语言解析: {target_language} -> {tgt_lang_code}")
            _log(f"[INFO] 生成参数: {gen_kwargs}")

            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    forced_bos_token_id=forced_bos_token_id,
                    **gen_kwargs,
                )
            return _decode_first_text(tokenizer, outputs)

        _log(f"[INFO] 通用生成参数: {gen_kwargs}")
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                **gen_kwargs,
            )
        return _decode_first_text(tokenizer, outputs)

    def _translate(text: str) -> str:
        text = _normalize_space(text)
        if not text:
            return text

        translated = _run_generate(text, strict=False)

        if _has_excessive_ngram_repetition(translated) or _looks_like_wrong_target_language(
            translated, target_language
        ):
            _log("[WARN] 检测到可疑重复/目标语言异常，启用严格解码重试。")
            retry_translated = _run_generate(text, strict=True)

            retry_bad = _has_excessive_ngram_repetition(retry_translated) or _looks_like_wrong_target_language(
                retry_translated, target_language
            )
            if not retry_bad and retry_translated.strip():
                translated = retry_translated

        return _normalize_space(translated)

    return _translate


def load_translation_model(model_path_or_obj):
    if isinstance(model_path_or_obj, tuple) and len(model_path_or_obj) == 2:
        return model_path_or_obj

    if not isinstance(model_path_or_obj, str):
        return None, model_path_or_obj

    model_path = model_path_or_obj
    model_path_lower = model_path.lower()

    try:
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
    except Exception as e:
        raise ImportError(f"未安装 transformers，无法加载翻译模型: {e}")

    tokenizer = None
    last_tokenizer_error = None

    if "nllb" in model_path_lower:
        try:
            from transformers import NllbTokenizerFast
            tokenizer = NllbTokenizerFast.from_pretrained(
                model_path,
                src_lang="eng_Latn",
                trust_remote_code=True,
                local_files_only=True,
            )
        except Exception as e:
            last_tokenizer_error = e

        if tokenizer is None:
            try:
                from transformers import NllbTokenizer
                tokenizer = NllbTokenizer.from_pretrained(
                    model_path,
                    src_lang="eng_Latn",
                    trust_remote_code=True,
                    local_files_only=True,
                )
            except Exception as e:
                last_tokenizer_error = e

    if tokenizer is None:
        try:
            tokenizer = AutoTokenizer.from_pretrained(
                model_path,
                trust_remote_code=True,
                local_files_only=True,
                use_fast=False,
            )
        except Exception as e:
            if last_tokenizer_error is not None:
                raise RuntimeError(
                    f"加载 tokenizer 失败。\n"
                    f"NLLB 专用 tokenizer 错误: {last_tokenizer_error}\n"
                    f"AutoTokenizer 错误: {e}"
                )
            raise RuntimeError(f"加载 tokenizer 失败: {e}")

    try:
        model = AutoModelForSeq2SeqLM.from_pretrained(
            model_path,
            trust_remote_code=True,
            local_files_only=True,
        )
    except Exception as e:
        raise RuntimeError(f"加载翻译模型失败: {e}")

    return tokenizer, model


def _extract_text_value(args, kwargs) -> str | None:
    text_keys = [
        "text",
        "source_text",
        "input_text",
        "chunk",
        "chunk_text",
        "block",
        "block_text",
        "content",
        "src_text",
        "sentence",
        "paragraph",
    ]

    for key in text_keys:
        value = kwargs.get(key)
        if isinstance(value, str):
            return value

    for arg in args:
        if isinstance(arg, str):
            return arg

    return None


def _extract_tokenizer_model_value(args, kwargs):
    tokenizer = kwargs.get("tokenizer")
    model = kwargs.get("model")

    if tokenizer is not None or model is not None:
        return tokenizer, model

    tokenizer_aliases = ["mt_tokenizer", "hf_tokenizer"]
    model_aliases = ["mt_model", "hf_model", "translator", "translation_model"]

    for key in tokenizer_aliases:
        if kwargs.get(key) is not None:
            tokenizer = kwargs.get(key)
            break

    for key in model_aliases:
        if kwargs.get(key) is not None:
            model = kwargs.get(key)
            break

    if tokenizer is not None or model is not None:
        return tokenizer, model

    for arg in args:
        if isinstance(arg, tuple) and len(arg) == 2:
            return arg[0], arg[1]

    non_str_args = [x for x in args if not isinstance(x, str)]

    if len(non_str_args) >= 2:
        return non_str_args[0], non_str_args[1]

    if len(non_str_args) == 1:
        return None, non_str_args[0]

    return None, None


def translate_with_auto_review(*args, **kwargs):
    text = _extract_text_value(args, kwargs)
    tokenizer, model = _extract_tokenizer_model_value(args, kwargs)

    source_language = kwargs.get("source_language", "auto")
    target_language = kwargs.get("target_language", "zh")
    logger = kwargs.get("logger")

    if text is None:
        raise ValueError("translate_with_auto_review 缺少 text 参数")

    if model is None and isinstance(tokenizer, tuple) and len(tokenizer) == 2:
        tokenizer, model = tokenizer

    if tokenizer is not None and model is not None:
        translate_func = _build_hf_translate_func(
            tokenizer,
            model,
            source_language=source_language,
            target_language=target_language,
            logger=logger,
        )

    elif model is not None:
        if hasattr(model, "translate") and callable(model.translate):
            translate_func = model.translate
        elif hasattr(model, "generate_translation") and callable(model.generate_translation):
            translate_func = model.generate_translation
        elif hasattr(model, "generate") and callable(model.generate):
            def translate_func(x: str) -> str:
                result = model.generate(x)
                if isinstance(result, str):
                    return result
                return str(result)
        else:
            raise AttributeError("model 缺少可用翻译方法，且没有 tokenizer 配套")

    else:
        raise ValueError("translate_with_auto_review 缺少 tokenizer/model 参数")

    core = TranslationCore(
        base_translate_func=translate_func,
        source_language=source_language,
        target_language=target_language,
    )
    translated = core.translate_text(str(text))
    core.close()
    return translated