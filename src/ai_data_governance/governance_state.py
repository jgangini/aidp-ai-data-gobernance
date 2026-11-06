"""Typed state for the portable governance graph."""
from typing import TypedDict

class GovernanceState(TypedDict, total=False):
    question: str
    question_history: list[str]
    previous_completed_turn: dict | None
    intent: dict
    assets: list[dict]
    evidence: list[dict]
    review: dict
    gaps: list[str]
    response: dict
    diagnosis: dict
    treatment: dict
    case_preview: dict
    source_recovery_count: int
    source_recovery_pending: bool
    source_recovery_history: list[dict]
