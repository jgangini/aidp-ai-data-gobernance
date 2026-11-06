"""Portable factories use injected trusted hooks and never discover native services."""
from .governance_graph import build_governance_graph, READ_OPERATIONS
from .documentary_graph import build_documentary_graph


def _runtime(runtime, names):
    if runtime.get('external_effects_allowed') is not False:
        raise ValueError('Portable evaluation must disable external effects')
    services = runtime.get('services')
    if not isinstance(services, dict) or any(not callable(services.get(name)) for name in names):
        raise ValueError('All trusted graph hooks must be explicitly injected')
    if runtime.get('checkpointer') is None:
        raise ValueError('An explicit checkpointer is required')
    return {name: services[name] for name in names}


def governance(runtime):
    hooks = _runtime(runtime, ('authorize', 'resolve_assets', 'read', 'call_model'))
    return build_governance_graph(**hooks, capabilities=READ_OPERATIONS, checkpointer=runtime['checkpointer'])


def documentation(runtime):
    hooks = _runtime(runtime, ('load_batch', 'claim_generation', 'generate', 'review', 'save_outcomes', 'check_active'))
    return build_documentary_graph(**hooks, checkpointer=runtime['checkpointer'])
