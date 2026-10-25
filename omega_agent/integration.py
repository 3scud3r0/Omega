"""Host assembly of existing Nextorch proposals and finite Boolean admission.

No model is trained, capability minted, tool invoked or database opened at
import time. The checker certifies a truth table, not general goal fulfillment,
minimal circuits, unrestricted mathematics or general intelligence.
"""
from .problem import Problem
from .runtime import CognitiveAgent, ToolRequest
from omega_security.encoding import decode, snapshot

BOOLEAN_DOMAIN = 'boolean.truth-table'
BOOLEAN_CONTRACT = 'omega-nextorch:exact-bounded-truth-table:1'


def boolean_problem(task):
    from omega_nextorch.gate import validate_domain
    copied = snapshot(task)
    validate_domain(copied)
    return Problem(copied['id'], BOOLEAN_DOMAIN, copied, (), BOOLEAN_CONTRACT)


def decode_proposal(raw):
    """Decode data envelopes without allowing models to supply authorization."""
    if type(raw) is str:
        if len(raw)>1024*1024:raise ValueError('Proposal text budget exceeded')
        value = decode(raw.encode('utf-8'))
    elif type(raw) is bytes:
        value = decode(raw)
    else:
        value = snapshot(raw)
    if type(value) is dict and value.get('kind') == 'tool_request':
        if set(value) != {'kind', 'name', 'arguments'}:
            raise ValueError('Tool proposals cannot contain authority fields')
        return ToolRequest(value['name'], value['arguments'])
    return value


def check_boolean(problem, candidate):
    from omega_nextorch.gate import certify, validate_domain
    if type(problem) is not Problem or problem.domain != BOOLEAN_DOMAIN or problem.success_contract != BOOLEAN_CONTRACT or problem.constraints:
        raise ValueError('Checker does not support this success contract')
    validate_domain(problem.inputs)
    if problem.id != problem.inputs['id']:
        raise ValueError('Problem/task binding mismatch')
    try:
        certificate = certify(problem.inputs, candidate, 'omega-agent:bounded-proposal')
    except (ValueError, TypeError, KeyError, IndexError, RecursionError, OverflowError) as exc:
        return {'valid': False, 'error_type': type(exc).__name__}
    return {'valid': True, 'certificate': certificate}


def boolean_agent(model, *, verifier, principal, audit, tools=None,
                  authorize_tool=None, observe_tool=None, episode_store=None):
    """Wire a host-selected ReasoningModel, tools and an optional metadata sink.

    NextorchBooleanAdapter implements the proposal side without granting neural
    scores any admission authority. Retention/reuse of episodes remains the
    responsibility of the private memory facade and its consent policy.
    """
    return CognitiveAgent(model, decode_proposal, check_boolean, verifier, principal, audit,
                          tools=tools, authorize_tool=authorize_tool, observe_tool=observe_tool,
                          record_episode=episode_store.append if episode_store is not None else None,
                          checker_id=BOOLEAN_CONTRACT)
