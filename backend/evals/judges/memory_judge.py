from __future__ import annotations

import json
import re
from typing import Any

from .common import call_llm_json


def _memory_text(memories: Any) -> str:
    if isinstance(memories, str):
        return memories
    if isinstance(memories, (list, tuple)):
        items = []
        for m in memories:
            if hasattr(m, "memory"):
                items.append(str(m.memory))
            elif isinstance(m, dict) and "memory" in m:
                items.append(str(m["memory"]))
            else:
                items.append(str(m))
        return "\n".join(f"- {it}" for it in items)
    try:
        return json.dumps(memories, ensure_ascii=False, default=str)
    except Exception:
        return str(memories)


def _rule_judge(memories: Any, expected_facts: list[str]) -> dict[str, Any]:
    haystack = _memory_text(memories).lower()
    matched: list[str] = []
    missing: list[str] = []
    for fact in expected_facts:
        tokens = [t for t in re.findall(r"[\wÀ-ỹ]+", fact.lower()) if len(t) >= 4]
        overlap = sum(1 for token in tokens if token in haystack)
        if tokens and overlap / len(tokens) >= 0.45:
            matched.append(fact)
        else:
            missing.append(fact)
    accuracy = len(matched) / len(expected_facts) if expected_facts else 1.0
    return {
        "passed": not missing,
        "accuracy": round(accuracy, 4),
        "matched_facts": matched,
        "missing_facts": missing,
        "reason": "lexical_fallback",
        "judge": "rule",
    }


def judge_memory(*, memories: Any, expected_facts: list[str], llm: Any = None) -> dict[str, Any]:
    memory_text = _memory_text(memories)
    facts_text = "\n".join(f"- {fact}" for fact in expected_facts)
    prompt = f"""You evaluate whether a memory service preserved user preferences/facts.
Semantic equivalence is enough; wording and language may differ. Do not require exact string matching.
Return ONLY one JSON object:
{{"passed":true|false,"matched_facts":["..."],"missing_facts":["..."],"accuracy":0.0,"reason":"short reason"}}

Expected facts:
{facts_text}

Retrieved memories:
{memory_text}

Rules:
- A fact is matched only when the retrieved memory explicitly or clearly semantically entails it.
- Do not infer missing preferences from the probe query.
- accuracy = matched expected facts / total expected facts.
- passed=true only when every expected fact is matched.
"""
    judged = call_llm_json(llm, prompt)
    if judged is None:
        return _rule_judge(memories, expected_facts)
    matched = [str(x) for x in judged.get("matched_facts", [])]
    missing = [str(x) for x in judged.get("missing_facts", [])]
    try:
        accuracy = float(judged.get("accuracy", len(matched) / max(len(expected_facts), 1)))
    except (TypeError, ValueError):
        accuracy = len(matched) / max(len(expected_facts), 1)
    return {
        "passed": bool(judged.get("passed")) and not missing,
        "accuracy": round(max(0.0, min(1.0, accuracy)), 4),
        "matched_facts": matched,
        "missing_facts": missing,
        "reason": str(judged.get("reason", "")),
        "judge": "llm",
    }
