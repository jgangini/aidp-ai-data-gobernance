"""Explicit graph composition and public node contracts."""
from __future__ import annotations
from dataclasses import asdict
import json
from typing import TypedDict
from .contracts import DocumentReviews, DocumentationResult
from .documentation import DocumentationAdmission, AdmittedDraft, admit_documentation_items
from .documentation import documentation_generation_key
from .documentation import admit_document_reviews
from .inventory import identity
from .model_output import model_json
from .documentary_state import DocumentaryState
from .documentary_nodes import (_admission, _batch_snapshot, _batch_admissions, _batch_contexts, _initial_outcome, DocumentaryNodes, _reviewed_outcomes)

def build_documentary_graph(*, load_batch, claim_generation, generate, review, save_outcomes,
                            check_active, checkpointer):
    """One pass, no automatic model retry, no publish/catalog/DDL tools.

    claim_generation(phase, admission, key, config) must durably exclude a second
    start for each document or review key, including checkpoint resumption.
    False means unresolved or previously claimed work: do not
    call the model again. save_outcomes must reconcile its own partial commits.
    """
    from langgraph.graph import END, START, StateGraph

    if checkpointer is None or not all(callable(hook) for hook in (
        load_batch, claim_generation, generate, review, save_outcomes, check_active)):
        raise ValueError("Persistent memory and all trusted documentary hooks are required")
    nodes = DocumentaryNodes(load_batch=load_batch, claim_generation=claim_generation, generate=generate,
        review=review, save_outcomes=save_outcomes, check_active=check_active)
    graph = StateGraph(DocumentaryState)
    for name, node in (("load_batch", nodes.load), ("select_work", nodes.select), ("document", nodes.document),
                       ("validate_documents", nodes.validate), ("persist_outcomes", nodes.persist)):
        graph.add_node(name, node)
    graph.add_edge(START, "load_batch")
    graph.add_edge("load_batch", "select_work")
    graph.add_conditional_edges("select_work", lambda state: "document" if state["selected"] else "persist_outcomes")
    graph.add_edge("document", "validate_documents")
    graph.add_edge("validate_documents", "persist_outcomes")
    graph.add_edge("persist_outcomes", END)
    return graph.compile(checkpointer=checkpointer)
