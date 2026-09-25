"""Recovery guidance for preferred routing and optional legacy strict grants."""
import time
from . import storage
from .security import digest
from . import routing_policy

VERSION = 1
CAPABILITY_GAPS = frozenset({
    'CHROME_JS_DIALOG_HOST_BLOCKED', 'CHROME_BACKEND_CAPABILITY_UNAVAILABLE',
    'CHROME_FRAME_COORDINATES_REQUIRE_ASTRA', 'CHROME_FRAME_UNSUPPORTED',
    'CHROME_READONLY_SCOPE_UNAVAILABLE', 'CHROME_STATE_TOO_LARGE',
    'CHROME_FRAME_DEPTH_LIMIT', 'CHROME_FRAME_IDENTITY_UNAVAILABLE',
    'CHROME_UPLOAD_MULTIPLE_NOT_SUPPORTED',
    'CHROME_LAST_TAB_CLOSE_REQUIRES_ASTRA',
    'NO_RELIABLE_STRUCTURED_ADAPTER', 'OBSERVATION_TOO_LARGE_USE_SCOPED_ADAPTER',
    'UIA_SCROLL_PATTERN_UNAVAILABLE', 'UIA_RANGE_PATTERN_UNAVAILABLE',
    'WINDOWS_PATTERN_UNSUPPORTED', 'OPERATION_UNSUPPORTED',
})

def valid_grant(grant,directory=None):
    valid = (grant.get('policy_version') == VERSION
            and grant.get('kind') == 'executor_capability_gap'
            and grant.get('reason') in CAPABILITY_GAPS)
    if valid and directory is not None:
        current=storage.read(directory/'result.dpapi')
        valid=current.get('status')=='escalated' and current.get('escalation_reason')==grant['reason']
        valid=valid and not (directory/'cancel').exists() and not (storage.DATA/'STOP').exists()
    return valid

def issue(directory, contract, reason, deadline):
    # Revoke a previous gap when this task now needs a different kind of repair.
    for name in ('fallback.dpapi', 'fallback-binding.dpapi'):
        (directory / name).unlink(missing_ok=True)
    if routing_policy.preference_only():
        storage.event(directory, 'preferred_route_recovery', reason=reason, grant_required=False)
        return False
    if reason not in CAPABILITY_GAPS:
        storage.event(directory, 'direct_takeover_not_granted', reason=reason)
        return False
    from .hook import DIRECT_TOOLS
    storage.save(directory / 'fallback.dpapi', {
        'policy_version': VERSION, 'kind': 'executor_capability_gap',
        'task_id': directory.name, 'reason': reason,
        'expires_at': min(deadline, time.time() + 120),
        'scope_hash': digest(contract.scope.model_dump()),
        'scope': contract.scope.model_dump(), 'contract_hash': digest(contract.model_dump()),
        'allowed_tools': sorted(DIRECT_TOOLS),
        'authority': 'Observed executor capability gap; original user authorization only',
    })
    storage.event(directory, 'direct_takeover_granted', reason=reason)
    return True

def routing(usage, reason=None):
    if routing_policy.preference_only():
        # Guidance only: keep recoverable work delegated. The legacy grant set
        # includes scoping limits, which are not automatically capability gaps.
        scope_repair = {'CHROME_STATE_TOO_LARGE', 'CHROME_FRAME_DEPTH_LIMIT',
                        'OBSERVATION_TOO_LARGE_USE_SCOPED_ADAPTER'}
        boundary = routing_policy.user_boundary(reason)
        gap = reason in CAPABILITY_GAPS and reason not in scope_repair and not boundary
        if boundary:
            recovery = 'respect_user_or_permission_boundary'
        elif gap:
            recovery = 'astra_only_for_unsupported_portion_then_jev'
        elif reason == 'CHROME_SEGMENT_COMPLETE':
            recovery = 'continue_same_executor_task'
        elif reason:
            recovery = 'repair_or_supply_minimal_input_then_resume_jev'
        else:
            recovery = None
        return {'executor': 'jev_gui_delegate', 'mode': 'prefer_jev',
                'model_participation': 'jev_called' if usage.get('jev_requests', 0) else 'no_jev_request',
                'direct_astra_gui_allowed': gap,
                'fallback_grant_required': False,
                'recovery': recovery}
    return {'executor': 'jev_gui_delegate',
            'model_participation': 'jev_called' if usage.get('jev_requests', 0) else 'no_jev_request',
            'direct_astra_gui_allowed': reason in CAPABILITY_GAPS,
            'recovery': 'scoped_capability_fallback' if reason in CAPABILITY_GAPS else
                        ('repair_then_resume_executor' if reason else None)}
