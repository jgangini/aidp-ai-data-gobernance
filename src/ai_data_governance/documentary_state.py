"""Typed state for the portable documentary graph."""
from typing import TypedDict

class DocumentaryState(TypedDict, total=False):
    batch_ref: str
    admissions: list[dict]
    contexts: dict[str, str]
    selected: list[dict]
    outcomes: list[dict]
    candidates: dict
    completed: bool
