from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any


class ConfigService:
    def __init__(self, config_path: str = "app/config/settings.json"):
        self.config_path = config_path
        self.config = self._load_or_create_default()

    def _load_or_create_default(self) -> dict[str, Any]:
        default_config = {
            "translation": {
                "source_lang": "auto",
                "target_lang": "zh",
                "min_chunk_length": 80,
                "max_chunk_length": 600
            },
            "quality": {
                "enable_glossary": True,
                "enable_preserve_rules": True,
                "enable_consistency": True,
                "enable_auto_review": True
            },
            "paths": {
                "default_glossary_path": "data/glossary.csv",
                "user_glossary_path": "data/user_glossary.csv",
                "preserve_patterns_path": "data/preserve_patterns.json",
                "consistency_memory_path": "data/consistency_memory.json"
            }
        }

        if not os.path.exists(self.config_path):
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            self._save_config(default_config)
            return default_config

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            self._save_config(default_config)
            return default_config

        self._merge_missing_keys(data, default_config)
        self._save_config(data)
        return data

    def _merge_missing_keys(self, target: dict, default: dict) -> None:
        for key, value in default.items():
            if key not in target:
                target[key] = value
            elif isinstance(value, dict) and isinstance(target[key], dict):
                self._merge_missing_keys(target[key], value)

    def _save_config(self, config: dict[str, Any]) -> None:
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def save(self) -> None:
        self._save_config(self.config)

    def get(self, path: str, default: Any = None) -> Any:
        node = self.config
        for key in path.split("."):
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    def set(self, path: str, value: Any) -> None:
        keys = path.split(".")
        node = self.config
        for key in keys[:-1]:
            if key not in node or not isinstance(node[key], dict):
                node[key] = {}
            node = node[key]
        node[keys[-1]] = value
        self.save()

    def get_default_glossary_path(self) -> str:
        return self.get("paths.default_glossary_path", "data/glossary.csv")

    def get_user_glossary_path(self) -> str:
        return self.get("paths.user_glossary_path", "data/user_glossary.csv")

    def set_user_glossary_path(self, path: str) -> None:
        self.set("paths.user_glossary_path", path)

    def get_preserve_patterns_path(self) -> str:
        return self.get("paths.preserve_patterns_path", "data/preserve_patterns.json")

    def get_consistency_memory_path(self) -> str:
        return self.get("paths.consistency_memory_path", "data/consistency_memory.json")

    def is_glossary_enabled(self) -> bool:
        return bool(self.get("quality.enable_glossary", True))

    def set_glossary_enabled(self, enabled: bool) -> None:
        self.set("quality.enable_glossary", bool(enabled))


def _flatten_quality_config(cfg: dict[str, Any]) -> dict[str, Any]:
    return {
        "enable_glossary": cfg.get("quality", {}).get("enable_glossary", True),
        "enable_preserve_rules": cfg.get("quality", {}).get("enable_preserve_rules", True),
        "enable_consistency_memory": cfg.get("quality", {}).get("enable_consistency", True),
        "enable_auto_review": cfg.get("quality", {}).get("enable_auto_review", True),

        "glossary_path": cfg.get("paths", {}).get("user_glossary_path", "data/user_glossary.csv"),
        "preserve_rules_path": cfg.get("paths", {}).get("preserve_patterns_path", "data/preserve_patterns.json"),
        "consistency_memory_path": cfg.get("paths", {}).get("consistency_memory_path", "data/consistency_memory.json"),

        "min_block_merge_length": cfg.get("translation", {}).get("min_chunk_length", 80),
        "max_chars_per_chunk": cfg.get("translation", {}).get("max_chunk_length", 600),
    }


def load_quality_config(config_path: str = "app/config/settings.json") -> dict[str, Any]:
    service = ConfigService(config_path)
    return _flatten_quality_config(service.config)


def save_quality_config(updates: dict[str, Any], config_path: str = "app/config/settings.json") -> None:
    service = ConfigService(config_path)

    if "enable_glossary" in updates:
        service.set("quality.enable_glossary", bool(updates["enable_glossary"]))

    if "enable_preserve_rules" in updates:
        service.set("quality.enable_preserve_rules", bool(updates["enable_preserve_rules"]))

    if "enable_consistency_memory" in updates:
        service.set("quality.enable_consistency", bool(updates["enable_consistency_memory"]))

    if "enable_auto_review" in updates:
        service.set("quality.enable_auto_review", bool(updates["enable_auto_review"]))

    if "glossary_path" in updates and updates["glossary_path"]:
        service.set("paths.user_glossary_path", str(updates["glossary_path"]))

    if "preserve_rules_path" in updates and updates["preserve_rules_path"]:
        service.set("paths.preserve_patterns_path", str(updates["preserve_rules_path"]))

    if "consistency_memory_path" in updates and updates["consistency_memory_path"]:
        service.set("paths.consistency_memory_path", str(updates["consistency_memory_path"]))

    if "min_block_merge_length" in updates:
        service.set("translation.min_chunk_length", int(updates["min_block_merge_length"]))

    if "max_chars_per_chunk" in updates:
        service.set("translation.max_chunk_length", int(updates["max_chars_per_chunk"]))


def load_settings(config_path: str = "app/config/settings.json") -> dict[str, Any]:
    service = ConfigService(config_path)
    return service.config


def save_settings(updates: dict[str, Any], config_path: str = "app/config/settings.json") -> None:
    service = ConfigService(config_path)

    nested_sections = {"translation", "quality", "paths"}
    quality_alias_keys = {
        "enable_glossary",
        "enable_preserve_rules",
        "enable_consistency_memory",
        "enable_auto_review",
        "glossary_path",
        "preserve_rules_path",
        "consistency_memory_path",
        "min_block_merge_length",
        "max_chars_per_chunk",
    }

    direct_updates = {k: v for k, v in updates.items() if k not in nested_sections and k not in quality_alias_keys}
    if direct_updates:
        service.config.update(direct_updates)

    nested_updates = {k: v for k, v in updates.items() if k in nested_sections}
    if nested_updates:
        service.config.update(nested_updates)

    service.save()

    alias_updates = {k: v for k, v in updates.items() if k in quality_alias_keys}
    if alias_updates:
        save_quality_config(alias_updates, config_path)


def load_csv_headers(csv_path: str) -> list[str]:
    if not os.path.exists(csv_path):
        return []

    encodings = ["utf-8-sig", "utf-8", "gbk"]
    for encoding in encodings:
        try:
            with open(csv_path, "r", encoding=encoding, newline="") as f:
                reader = csv.reader(f)
                headers = next(reader, [])
                return [str(x).strip() for x in headers if str(x).strip()]
        except Exception:
            continue

    return []


def import_glossary_csv(
    csv_path: str,
    source_column: str,
    target_column: str,
    output_csv_path: str,
) -> dict[str, Any]:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV 文件不存在: {csv_path}")

    Path(output_csv_path).parent.mkdir(parents=True, exist_ok=True)

    total_rows = 0
    imported_rows = 0
    skipped_rows = 0

    rows_to_write: list[dict[str, str]] = []
    seen_pairs: set[tuple[str, str]] = set()

    encodings = ["utf-8-sig", "utf-8", "gbk"]
    last_error = None
    loaded = False

    for encoding in encodings:
        try:
            with open(csv_path, "r", encoding=encoding, newline="") as f:
                reader = csv.DictReader(f)

                if not reader.fieldnames:
                    raise ValueError("CSV 没有表头")

                if source_column not in reader.fieldnames:
                    raise ValueError(f"找不到源语言列: {source_column}")

                if target_column not in reader.fieldnames:
                    raise ValueError(f"找不到目标语言列: {target_column}")

                for row in reader:
                    total_rows += 1

                    source = str(row.get(source_column, "")).strip()
                    target = str(row.get(target_column, "")).strip()

                    if not source or not target:
                        skipped_rows += 1
                        continue

                    pair = (source, target)
                    if pair in seen_pairs:
                        skipped_rows += 1
                        continue

                    seen_pairs.add(pair)
                    rows_to_write.append({
                        "source": source,
                        "target": target,
                        "case_sensitive": "false",
                    })
                    imported_rows += 1

            loaded = True
            break
        except Exception as e:
            last_error = e

    if not loaded:
        raise RuntimeError(f"CSV 读取失败: {last_error}")

    with open(output_csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["source", "target", "case_sensitive"]
        )
        writer.writeheader()
        writer.writerows(rows_to_write)

    return {
        "total_rows": total_rows,
        "imported_rows": imported_rows,
        "skipped_rows": skipped_rows,
        "output_path": output_csv_path,
    }