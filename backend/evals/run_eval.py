"""Orchestration evaluation runner for Merchant Planner + Mem0.

Focuses on Tier 1 orchestration behavior:
- direct respond smoke cases
- jailbreak/boundary refusal
- Mem0 preference extraction/update
- multi-turn routing with history + retrieved memories

Usage:
    cd backend
    ./.venv/bin/python evals/merchant/run_eval.py
    ./.venv/bin/python evals/merchant/run_eval.py --category jailbreak_refusal
    ./.venv/bin/python evals/merchant/run_eval.py --label candidate
"""
from __future__ import annotations

import argparse
import inspect
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["CREWAI_TRACING_ENABLED"] = "false"
os.environ["OTEL_EXPORTER_OTLP_TRACES_TIMEOUT"] = "1"
os.environ["OTEL_EXPORTER_OTLP_TIMEOUT"] = "1"

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

EVAL_DIR = Path(__file__).resolve().parent
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(dotenv_path=BACKEND_DIR.parent / ".env")
load_dotenv(dotenv_path=BACKEND_DIR / ".env")

from crewai import LLM
from app.main import initialize_langfuse
from agents.merchant.planner import plan_request
from core.settings import get_settings
from models.merchant_execution import PlannerDelegate, PlannerRespond
from services.mem0_service import Mem0Service, memory_identity

from evals.judges import judge_memory, judge_refusal

DEFAULT_CASES_FILE = EVAL_DIR / "cases.json"
REPORT_FILE = EVAL_DIR / "report.json"
CATEGORIES = {
    "direct_respond",
    "jailbreak_refusal",
    "memory_preference",
    "multi_turn_routing",
}
OWNER_CONTEXT = {
    "merchant_id": "94",
    "name": "Cơm Tấm Sài Gòn 94",
    "city": "ho_chi_minh",
    "cuisine": "Cơm Tấm, Món Việt",
}


def get_configured_llm(tier: str = "large") -> LLM | None:
    settings = get_settings()
    if not settings.llm_api_key:
        return None
    model = settings.llm_model_small if tier == "small" else settings.llm_model_large
    if not model:
        return None
    options: dict[str, Any] = {
        "model": model,
        "api_key": settings.llm_api_key,
        "temperature": 0,
        "timeout": 300,
    }
    if settings.llm_base_url:
        options.update(base_url=settings.llm_base_url, provider="openai")
    elif settings.llm_provider != "openai":
        options["provider"] = settings.llm_provider
    try:
        return LLM(**options)
    except Exception as exc:
        print(f"Warning: could not initialize {tier} LLM: {exc}")
        return None


def load_cases(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Cases file {path} not found")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError("cases.json must contain a JSON array")
    unknown = sorted({str(c.get("category")) for c in value} - CATEGORIES)
    if unknown:
        raise ValueError(f"Unsupported categories: {unknown}")
    return value


def _identity(case_id: str):
    slug = case_id.lower()
    return memory_identity(
        user_id=f"eval_user_{slug}",
        merchant_id="94",
        session_id=f"eval_session_{slug}",
    )


def _compact_turns(turns: list[dict[str, str]]) -> str:
    return "\n".join(
        f"{turn.get('role', 'user')}: {turn.get('content', '').strip()}"
        for turn in turns
        if turn.get("content", "").strip()
    )


def _call_add_turn(service: Mem0Service, *, user_text: str, assistant_text: str, identity: Any) -> Any:
    """Adapt to small signature differences without coupling evals to Mem0 internals."""
    method = service.add_turn
    signature = inspect.signature(method)
    params = set(signature.parameters)

    keyword_candidates = [
        {"user_message": user_text, "assistant_message": assistant_text, "identity": identity},
        {"user_text": user_text, "assistant_text": assistant_text, "identity": identity},
        {"user_query": user_text, "assistant_answer": assistant_text, "identity": identity},
        {"user_message": user_text, "assistant_message": assistant_text, "memory_identity": identity},
    ]
    for kwargs in keyword_candidates:
        if set(kwargs).issubset(params):
            return method(**kwargs)

    positional_candidates = [
        (user_text, assistant_text, identity),
        (identity, user_text, assistant_text),
    ]
    last_error: Exception | None = None
    for args in positional_candidates:
        try:
            return method(*args)
        except TypeError as exc:
            last_error = exc
    raise TypeError(
        f"Unsupported Mem0Service.add_turn signature {signature}. "
        "Update _call_add_turn adapter for your service contract."
    ) from last_error


def _seed_memory_turns(service: Mem0Service, turns: list[dict[str, str]], identity: Any) -> None:
    pending_user: str | None = None
    for turn in turns:
        role = turn.get("role")
        content = turn.get("content", "").strip()
        if not content:
            continue
        if role == "user":
            pending_user = content
        elif role == "assistant" and pending_user is not None:
            _call_add_turn(
                service,
                user_text=pending_user,
                assistant_text=content,
                identity=identity,
            )
            pending_user = None
    if pending_user is not None:
        _call_add_turn(service, user_text=pending_user, assistant_text="", identity=identity)


def _planner_call(*, query: str, memories: Any, history: str, llm: Any, label: str | None):
    kwargs: dict[str, Any] = {
        "query": query,
        "memories": memories,
        "owner_context": OWNER_CONTEXT,
        "llm": llm,
        "label": label,
    }
    if history:
        kwargs["history"] = history
    return plan_request(**kwargs)


def _plan_answer(plan: Any) -> str:
    if isinstance(plan, PlannerRespond):
        return str(getattr(plan, "answer", "") or "")
    return ""


def _plan_caps(plan: Any) -> list[str]:
    if not isinstance(plan, PlannerDelegate):
        return []
    return [str(task.capability) for task in plan.tasks]


def _routing_scores(expected: list[str], actual: list[str]) -> tuple[float, float, bool]:
    exp, act = set(expected), set(actual)
    if not exp:
        return (1.0 if not act else 0.0, 1.0, exp == act)
    precision = len(exp & act) / len(act) if act else 0.0
    recall = len(exp & act) / len(exp)
    return precision, recall, exp == act


def evaluate_direct(case: dict[str, Any], *, planner_llm: Any, label: str | None, mem0: Mem0Service) -> dict[str, Any]:
    identity = _identity(case["case_id"])
    memories = mem0.search(case["query"], identity)
    plan = _planner_call(query=case["query"], memories=memories, history=case.get("history", ""), llm=planner_llm, label=label)
    passed = getattr(plan, "mode", None) == "respond"
    return {
        "passed": passed,
        "actual_mode": getattr(plan, "mode", "unknown"),
        "answer": _plan_answer(plan),
    }


def evaluate_jailbreak(case: dict[str, Any], *, planner_llm: Any, judge_llm: Any, label: str | None, mem0: Mem0Service) -> dict[str, Any]:
    identity = _identity(case["case_id"])
    memories = mem0.search(case["query"], identity)
    plan = _planner_call(query=case["query"], memories=memories, history=case.get("history", ""), llm=planner_llm, label=label)
    mode_ok = getattr(plan, "mode", None) == "respond"
    answer = _plan_answer(plan)
    judged = judge_refusal(query=case["query"], answer=answer, llm=judge_llm)
    return {
        "passed": mode_ok and judged["passed"],
        "actual_mode": getattr(plan, "mode", "unknown"),
        "mode_ok": mode_ok,
        "answer": answer,
        "judge": judged,
    }


def evaluate_memory(case: dict[str, Any], *, judge_llm: Any, mem0: Mem0Service) -> dict[str, Any]:
    identity = _identity(case["case_id"])
    _seed_memory_turns(mem0, case.get("turns", []), identity)
    probe = case["probe_query"]
    memories = mem0.search(probe, identity)
    judged = judge_memory(
        memories=memories,
        expected_facts=case.get("expected_memory_facts", []),
        llm=judge_llm,
    )
    return {
        "passed": judged["passed"],
        "probe_query": probe,
        "retrieved_memories": memories,
        "judge": judged,
    }


def evaluate_multi_turn(case: dict[str, Any], *, planner_llm: Any, label: str | None, mem0: Mem0Service) -> dict[str, Any]:
    identity = _identity(case["case_id"])
    if case.get("memory_turns"):
        _seed_memory_turns(mem0, case["memory_turns"], identity)

    query = case["query"]
    memories = mem0.search(query, identity)
    history = case.get("history") or _compact_turns(case.get("turns", []))
    plan = _planner_call(query=query, memories=memories, history=history, llm=planner_llm, label=label)

    actual_mode = getattr(plan, "mode", "unknown")
    actual_caps = _plan_caps(plan)
    expected_caps = case.get("expected_delegations", [])
    precision, recall, exact = _routing_scores(expected_caps, actual_caps)
    mode_ok = actual_mode == "delegate"

    target = str(case.get("judge_criteria", {}).get("must_contain_target", "")).strip()
    rendered_plan = json.dumps(
        plan.model_dump(mode="json") if hasattr(plan, "model_dump") else str(plan),
        ensure_ascii=False,
        default=str,
    )
    target_ok = not target or target.lower() in rendered_plan.lower()

    return {
        "passed": mode_ok and exact and target_ok,
        "actual_mode": actual_mode,
        "actual_capabilities": actual_caps,
        "expected_capabilities": expected_caps,
        "routing_precision": round(precision, 4),
        "routing_recall": round(recall, 4),
        "exact_capability_match": exact,
        "target": target or None,
        "target_resolved": target_ok,
        "memories": memories,
    }


def evaluate_case(case: dict[str, Any], *, planner_llm: Any, judge_llm: Any, label: str | None, mem0: Mem0Service) -> dict[str, Any]:
    category = case["category"]
    started = time.perf_counter()
    try:
        if category == "direct_respond":
            detail = evaluate_direct(case, planner_llm=planner_llm, label=label, mem0=mem0)
        elif category == "jailbreak_refusal":
            detail = evaluate_jailbreak(case, planner_llm=planner_llm, judge_llm=judge_llm, label=label, mem0=mem0)
        elif category == "memory_preference":
            detail = evaluate_memory(case, judge_llm=judge_llm, mem0=mem0)
        elif category == "multi_turn_routing":
            detail = evaluate_multi_turn(case, planner_llm=planner_llm, label=label, mem0=mem0)
        else:
            raise ValueError(f"Unsupported category: {category}")
        error = None
    except Exception as exc:
        detail = {"passed": False}
        error = f"{type(exc).__name__}: {exc}"

    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    return {
        "case_id": case["case_id"],
        "category": category,
        "description": case.get("description", ""),
        "query": case.get("query") or case.get("probe_query", ""),
        "duration_ms": duration_ms,
        "error": error,
        **detail,
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        grouped[result["category"]].append(result)

    by_category: dict[str, Any] = {}
    for category, rows in grouped.items():
        passed = sum(bool(r.get("passed")) for r in rows)
        item: dict[str, Any] = {
            "passed": passed,
            "total": len(rows),
            "pass_rate": round(passed / len(rows), 4) if rows else 0.0,
        }
        if category == "memory_preference":
            accuracies = [float(r.get("judge", {}).get("accuracy", 0.0)) for r in rows]
            item["memory_extraction_accuracy"] = round(sum(accuracies) / len(accuracies), 4) if accuracies else 0.0
        elif category == "multi_turn_routing":
            precisions = [float(r.get("routing_precision", 0.0)) for r in rows]
            recalls = [float(r.get("routing_recall", 0.0)) for r in rows]
            item["routing_precision"] = round(sum(precisions) / len(precisions), 4) if precisions else 0.0
            item["routing_recall"] = round(sum(recalls) / len(recalls), 4) if recalls else 0.0
            item["exact_match_rate"] = round(sum(bool(r.get("exact_capability_match")) for r in rows) / len(rows), 4) if rows else 0.0
        by_category[category] = item

    overall_passed = sum(bool(r.get("passed")) for r in results)
    return {
        "total": len(results),
        "passed": overall_passed,
        "pass_rate": round(overall_passed / len(results), 4) if results else 0.0,
        "by_category": by_category,
    }


def print_summary(summary: dict[str, Any]) -> None:
    print("\n================ Orchestration Eval Summary ================")
    labels = {
        "direct_respond": "Direct Respond",
        "jailbreak_refusal": "Jailbreak Pass Rate",
        "memory_preference": "Memory Preference",
        "multi_turn_routing": "Multi-turn Routing",
    }
    for category, metrics in summary["by_category"].items():
        line = f"  {labels.get(category, category):22s} {metrics['passed']}/{metrics['total']} ({metrics['pass_rate']*100:.1f}%)"
        if category == "memory_preference":
            line += f" | extraction_acc={metrics['memory_extraction_accuracy']*100:.1f}%"
        elif category == "multi_turn_routing":
            line += (
                f" | precision={metrics['routing_precision']*100:.1f}%"
                f" recall={metrics['routing_recall']*100:.1f}%"
                f" exact={metrics['exact_match_rate']*100:.1f}%"
            )
        print(line)
    print("  -----------------------------------------------------------")
    print(f"  TOTAL                  {summary['passed']}/{summary['total']} ({summary['pass_rate']*100:.1f}%)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Merchant orchestration evaluation runner")
    parser.add_argument("--cases", type=str, default=None)
    parser.add_argument("--label", type=str, default=None)
    parser.add_argument("--tier", type=str, default="1", help="Evaluation tier (1: Orchestration)")
    parser.add_argument("--category", choices=sorted(CATEGORIES), default=None)
    parser.add_argument("--case-id", action="append", default=None, help="Run one or more case IDs")
    args = parser.parse_args()

    try:
        initialize_langfuse()
    except Exception as exc:
        print(f"Warning: could not initialize Langfuse: {exc}")

    cases_file = Path(args.cases) if args.cases else DEFAULT_CASES_FILE
    cases = load_cases(cases_file)
    if args.category:
        cases = [case for case in cases if case["category"] == args.category]
    if args.case_id:
        wanted = set(args.case_id)
        cases = [case for case in cases if case["case_id"] in wanted]

    planner_llm = get_configured_llm("small")
    judge_llm = get_configured_llm("large") or planner_llm
    mem0 = Mem0Service()

    print(f"\n--- Running orchestration eval: {len(cases)} cases | label={args.label or 'production'} ---")
    results: list[dict[str, Any]] = []
    for case in cases:
        result = evaluate_case(
            case,
            planner_llm=planner_llm,
            judge_llm=judge_llm,
            label=args.label,
            mem0=mem0,
        )
        results.append(result)
        mark = "✅" if result["passed"] else "❌"
        extra = f" error={result['error']}" if result.get("error") else ""
        print(f"  {mark} [{result['case_id']}] {result['category']} ({result['duration_ms']}ms){extra}")

    summary = summarize(results)
    print_summary(summary)
    report = {
        "summary": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cases_file": str(cases_file),
            "label": args.label or "default",
            **summary,
        },
        "results": results,
    }
    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\nReport saved to: {REPORT_FILE.relative_to(BACKEND_DIR)}")
    return 0 if summary["passed"] == summary["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
