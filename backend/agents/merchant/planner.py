from __future__ import annotations

import json
from typing import Any
import instructor
from openai import OpenAI
from langfuse import get_client

from core.settings import get_settings
from models.merchant_execution import PlannerDecision, parse_planner_decision
from services.mem0_service import MemoryHit
from services.merchant_prompts import get_merchant_prompt


def _make_instructor_client(llm: Any = None) -> instructor.Instructor | None:
    try:
        settings = get_settings()
        api_key = getattr(llm, "api_key", None) or settings.llm_api_key or "dummy"
        base_url = getattr(llm, "base_url", None) or settings.llm_base_url
        raw_openai = OpenAI(base_url=base_url, api_key=api_key)
        # Use Mode.JSON to avoid 'Thinking mode does not support this tool_choice' on reasoning/thinking models
        return instructor.from_openai(raw_openai, mode=instructor.Mode.JSON)
    except Exception:
        return None


def plan_request(
    query: str,
    memories: list[MemoryHit],
    owner_context: dict[str, Any],
    llm: Any,
    *,
    history: list[dict[str, Any]] | None = None,
    label: str | None = None,
) -> PlannerDecision:
    client = get_client()
    prompt = get_merchant_prompt("planner", label=label)

    memory_list = [hit.memory for hit in memories if hit.memory]
    memory_context_str = json.dumps(memory_list, ensure_ascii=False)
    owner_context_str = json.dumps(owner_context, ensure_ascii=False, sort_keys=True)

    compile_kwargs = {
        "query": query,
        "memory_context": memory_context_str,
        "owner_context": owner_context_str,
        "history_context": (history if isinstance(history, str) else json.dumps(history, ensure_ascii=False)) if history else "",
    }

    compiled_prompt = prompt.compile(**compile_kwargs)
    model_name = getattr(llm, "model", None) or "v-llm-v1-small"
    if isinstance(model_name, str) and model_name.startswith("openai/"):
        model_name = model_name[len("openai/") :]

    # Primary enforcement: Use instructor for native Pydantic structured output
    is_mock = hasattr(llm, "call") and getattr(type(llm), "__module__", "").startswith("unittest.mock")
    if not is_mock:
        instr_client = _make_instructor_client(llm)
        if instr_client is not None:
            with client.start_as_current_observation(
                name="planner",
                as_type="generation",
                input={
                    "query": query,
                    "memory_context": memory_list,
                    "owner_context": owner_context,
                    "history_context": history or "",
                },
                model=model_name,
                prompt=prompt,
            ) as observation:
                decision: PlannerDecision = instr_client.chat.completions.create(
                    model=model_name,
                    response_model=PlannerDecision,
                    messages=[{"role": "user", "content": compiled_prompt}],
                    temperature=0.1,
                )
                observation.update(output=decision.model_dump())
                return decision

    with client.start_as_current_observation(
        name="planner",
        as_type="generation",
        input={
            "query": query,
            "memory_context": memory_list,
            "owner_context": owner_context,
            "history_context": history or "",
        },
        model=getattr(llm, "model", None),
        prompt=prompt,
    ) as observation:
        if hasattr(llm, "call"):
            raw_output = llm.call(compiled_prompt)
        elif callable(llm):
            raw_output = llm(compiled_prompt)
        else:
            raw_output = str(llm)

        if hasattr(raw_output, "content"):
            raw_text = raw_output.content
        else:
            raw_text = str(raw_output)

        decision = parse_planner_decision(raw_text)
        observation.update(output=decision.model_dump())
        return decision
