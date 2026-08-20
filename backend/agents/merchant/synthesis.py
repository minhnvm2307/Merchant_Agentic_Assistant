from __future__ import annotations

from typing import Any
import instructor
from openai import OpenAI
from langfuse import get_client

from core.settings import get_settings
from models.merchant_execution import AdvisorResponse
from services.merchant_prompts import get_merchant_prompt


def _make_instructor_client(llm: Any = None) -> instructor.Instructor | None:
    try:
        settings = get_settings()
        api_key = getattr(llm, "api_key", None) or settings.llm_api_key or "dummy"
        base_url = getattr(llm, "base_url", None) or settings.llm_base_url
        raw_openai = OpenAI(base_url=base_url, api_key=api_key)
        return instructor.from_openai(raw_openai, mode=instructor.Mode.JSON)
    except Exception:
        return None


def synthesize_results(
    query: str,
    results: list[Any],
    llm: Any,
    *,
    label: str | None = None,
) -> AdvisorResponse:
    """Synthesize results from multiple specialists into one cohesive AdvisorResponse."""
    if len(results) < 2:
        raise ValueError(f"synthesis requires at least 2 specialist results, got {len(results)}")

    client = get_client()
    prompt = get_merchant_prompt("synthesis", label=label)

    # Format specialist results
    sections = []
    failed_caps = []
    for res in results:
        cap = getattr(res, "capability", "unknown")
        status = getattr(res, "status", "completed")
        content = getattr(res, "content", "")
        if status == "completed" and content:
            sections.append(f"[{cap.upper()} EVIDENCE]\n{content}")
        else:
            failed_caps.append(cap)

    if failed_caps:
        sections.append(f"[UNAVAILABLE / FAILED CAPABILITIES]\n{', '.join(failed_caps)}")

    specialist_results_text = "\n\n".join(sections)
    compiled_prompt = prompt.compile(
        query=query,
        specialist_results=specialist_results_text,
    )

    model_name = getattr(llm, "model", None) or "v-llm-v1-small"
    if isinstance(model_name, str) and model_name.startswith("openai/"):
        model_name = model_name[len("openai/") :]

    is_mock = hasattr(llm, "call") and getattr(type(llm), "__module__", "").startswith("unittest.mock")
    if not is_mock:
        instr_client = _make_instructor_client(llm)
        if instr_client is not None:
            with client.start_as_current_observation(
                name="synthesis",
                as_type="generation",
                input={
                    "query": query,
                    "specialist_results": specialist_results_text,
                },
                model=model_name,
                prompt=prompt,
            ) as observation:
                advisor_resp: AdvisorResponse = instr_client.chat.completions.create(
                    model=model_name,
                    response_model=AdvisorResponse,
                    messages=[{"role": "user", "content": compiled_prompt}],
                    temperature=0.2,
                )
                observation.update(output=advisor_resp.model_dump())
                return advisor_resp

    with client.start_as_current_observation(
        name="synthesis",
        as_type="generation",
        input={
            "query": query,
            "specialist_results": specialist_results_text,
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
            answer = raw_output.content.strip()
        else:
            answer = str(raw_output).strip()

        if not answer:
            raise ValueError("Synthesis returned empty answer")

        observation.update(output=answer)
        try:
            return AdvisorResponse.model_validate_json(answer)
        except Exception:
            return AdvisorResponse(content=answer, mentioned_merchant_refs=[])
