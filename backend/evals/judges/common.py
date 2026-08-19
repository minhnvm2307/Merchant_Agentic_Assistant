from __future__ import annotations

import json
import re
from typing import Any


def call_llm_json(llm: Any, prompt: str) -> dict[str, Any] | None:
    if llm is None:
        return None
    try:
        raw = llm.call(prompt)
    except Exception:
        return None

    if not isinstance(raw, str):
        raw = str(raw)
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if not match:
            return None
        try:
            value = json.loads(match.group(0))
            return value if isinstance(value, dict) else None
        except json.JSONDecodeError:
            return None
