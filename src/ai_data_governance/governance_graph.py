"""Explicit graph composition and public node contracts."""
from __future__ import annotations
import json
import asyncio
import re
from datetime import datetime, timezone
from typing import TypedDict
from .contracts import EvidenceReview, GovIntent, GovResponse, GovConsultationResponse, GovDiagnosis, TreatmentDraft
from .case_previews import validate_case_diagnosis, validate_case_treatment
from .model_output import model_json
from .consultation import SourceObservationExpired
from .governance_state import GovernanceState
from .governance_nodes import (consultation_operations, has_required_consultation_evidence, validate_quality_window, validate_quality_windows, measured_quality_evidence, validate_consultation_evidence, validate_source_reobservation, validate_review, validate_governance_response, governance_reference_cards, governance_response_input, consultation_limitations, explicit_case_reference_requested, admitted_case_intent, previous_completed_turn, GovernanceNodes, recoverable_source_node, observed_governance_node, READ_OPERATIONS)

def build_governance_graph(*, authorize, resolve_assets, read, call_model, capabilities, checkpointer, reauthorize_evidence=None,
                           observer=None, prepare_case=None, reobserve_evidence=None):
    from langgraph.graph import START, END, StateGraph

    if checkpointer is None or not all(callable(v) for v in (authorize, resolve_assets, read, call_model)):
        raise ValueError("Native authorization, tools and persistent memory are required")
    if not frozenset(capabilities).issubset(READ_OPERATIONS):
        raise ValueError("Unknown consultation capability")
    for callback,message in ((reauthorize_evidence,'Evidence admission must be callable'),
            (observer,'Activity observation must be callable'),
            (prepare_case,'Case preview requires an admitted callback'),
            (reobserve_evidence,'Source recovery requires an admitted callback')):
        if callback is not None and not callable(callback):
            raise ValueError(message)
    nodes = GovernanceNodes(authorize=authorize, resolve_assets=resolve_assets, read=read,
        call_model=call_model, capabilities=capabilities, reauthorize_evidence=reauthorize_evidence,
        prepare_case=prepare_case,reobserve_evidence=reobserve_evidence)
    graph = StateGraph(GovernanceState)
    order = ("admission", "understand", "retrieve", "assess", "respond")
    for name in order:
        function=getattr(nodes,name)
        if observer is not None:
            function=observed_governance_node(name,function,observer)
        if reobserve_evidence is not None and name in {'assess','respond'}:
            function=recoverable_source_node(function)
        graph.add_node(name,function)
    graph.add_edge(START, order[0])
    for before, after in zip(order[:3], order[1:4]):
        graph.add_edge(before, after)
    if reobserve_evidence is not None:
        function=nodes.reobserve
        if observer is not None:
            function=observed_governance_node('reobserve',function,observer)
        graph.add_node('reobserve',function)
        graph.add_conditional_edges('assess',lambda state: bool(state.get('source_recovery_pending')),
            {True:'reobserve',False:'respond'})
        graph.add_conditional_edges('respond',lambda state: bool(state.get('source_recovery_pending')),
            {True:'reobserve',False:END})
        graph.add_edge('reobserve','assess')
    else:
        graph.add_edge('assess','respond')
        graph.add_edge('respond', END)
    return graph.compile(checkpointer=checkpointer)
