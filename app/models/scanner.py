from pathlib import Path


def scan_models(model_root: str) -> list[dict]:
    root = Path(model_root)
    results = []

    if not root.exists() or not root.is_dir():
        return results

    for item in root.iterdir():
        if not item.is_dir():
            continue

        name_lower = item.name.lower()

        model_type = None
        capabilities = []
        description = ""

        if "faster-whisper" in name_lower or "whisper" in name_lower:
            model_type = "ASR"
            capabilities = ["asr"]
            description = "本地语音识别模型"

        elif "nllb" in name_lower:
            model_type = "MT"
            capabilities = ["mt"]
            description = "本地文本翻译模型"

        elif "seamless" in name_lower or "m4t" in name_lower:
            model_type = "MULTIMODAL"
            capabilities = ["asr", "mt"]
            description = "本地多模态翻译模型（可用于识别/翻译）"

        if model_type is None:
            continue

        results.append(
            {
                "name": item.name,
                "path": str(item.resolve()),
                "type": model_type,
                "capabilities": capabilities,
                "description": description,
                "available": True,
            }
        )

    results.sort(key=lambda x: (x["type"], x["name"].lower()))
    return results