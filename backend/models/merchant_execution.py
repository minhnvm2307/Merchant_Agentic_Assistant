"""Planner execution contracts.

The planner is the sole entity that produces a PlannerDecision.
It outputs either a direct response (PlannerRespond) or a set of 1-4 distinct
delegated tasks (PlannerDelegate).
"""
from __future__ import annotations

from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

CapabilityName = Literal["owner", "market", "policy", "review", "cohort"]


class PlannedTask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capability: CapabilityName
    instruction: str = Field(min_length=1, max_length=600)


class PlannerRespond(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["respond"]
    answer: str = Field(min_length=1, max_length=4000)


class PlannerDelegate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["delegate"]
    tasks: list[PlannedTask] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def distinct_capabilities(self) -> "PlannerDelegate":
        capabilities = [task.capability for task in self.tasks]
        if len(capabilities) != len(set(capabilities)):
            raise ValueError("delegated capabilities must be distinct")
        return self


PlannerDecision = Annotated[PlannerRespond | PlannerDelegate, Field(discriminator="mode")]
_DECISION_ADAPTER = TypeAdapter(PlannerDecision)


def parse_planner_decision(raw: str) -> PlannerDecision:
    """Strictly validate and parse raw JSON string into PlannerDecision using Pydantic."""
    text = raw.strip()
    if not text:
        raise ValueError("Planner returned empty response")

    # Strip markdown code fence if present
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2:
            first_idx = 1
            last_idx = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
            text = "\n".join(lines[first_idx:last_idx]).strip()

    return _DECISION_ADAPTER.validate_json(text)
