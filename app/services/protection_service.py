from __future__ import annotations

import csv
import os
import shutil
from typing import List, Tuple


class ProtectionService:
    REQUIRED_COLUMNS = {"source", "target"}

    def validate_glossary_csv(self, csv_path: str) -> tuple[bool, str]:
        if not os.path.exists(csv_path):
            return False, "文件不存在"

        if not csv_path.lower().endswith(".csv"):
            return False, "只支持 CSV 文件"

        try:
            with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                headers = set(reader.fieldnames or [])

                if not self.REQUIRED_COLUMNS.issubset(headers):
                    return False, "CSV 必须至少包含 source,target 两列"

                row_count = 0
                for row in reader:
                    source = (row.get("source") or "").strip()
                    target = (row.get("target") or "").strip()
                    if source and target:
                        row_count += 1

                if row_count == 0:
                    return False, "CSV 中没有有效术语行"

        except Exception as e:
            return False, f"CSV 读取失败: {e}"

        return True, "术语表校验通过"

    def import_glossary_csv(self, src_csv_path: str, dst_csv_path: str) -> tuple[bool, str]:
        ok, msg = self.validate_glossary_csv(src_csv_path)
        if not ok:
            return False, msg

        try:
            os.makedirs(os.path.dirname(dst_csv_path), exist_ok=True)
            shutil.copyfile(src_csv_path, dst_csv_path)
        except Exception as e:
            return False, f"术语表复制失败: {e}"

        return True, "术语表导入成功"

    def preview_glossary(self, csv_path: str, limit: int = 10) -> List[Tuple[str, str]]:
        rows: List[Tuple[str, str]] = []

        if not os.path.exists(csv_path):
            return rows

        try:
            with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    source = (row.get("source") or "").strip()
                    target = (row.get("target") or "").strip()
                    if source and target:
                        rows.append((source, target))
                    if len(rows) >= limit:
                        break
        except Exception:
            return []

        return rows