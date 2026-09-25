"""User-selected GUI routing preference, separate from task authorization."""
import json
from pathlib import Path

POLICY_PATH = Path(__file__).with_name("routing-policy.json")


def preference_only():
    try:
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        # An advisory route must not become an accidental task blocker.
        return True
    return policy.get("mode", "prefer_jev") != "executor_required"


def user_boundary(reason):
    reason = reason or ""
    return (reason in {"USER_TAKEOVER", "USER_CLIPBOARD_CHANGED", "CANCELLED",
                       "CHROME_SESSION_INTERRUPTED", "USER_RELEASE_REQUIRED"}
            or "EMERGENCY_STOP" in reason or "DENIED" in reason
            or "UAC" in reason or "SECURE_DESKTOP" in reason)


def describe():
    if preference_only():
        return {"mode": "prefer_jev", "gui_scope": "all_gui_tasks",
                "direct_astra_gui": "only_parts_executor_cannot_perform_after_supported_recovery",
                "dedicated_cua": "non_blocking",
                "fallback_grant_required": False, "fallback_time_limit_seconds": None,
                "authorization": "unchanged_user_and_tool_permissions",
                "zero_jev_requests": "deterministic_delegation_not_model_comparison"}
    return {"mode": "executor_required", "direct_astra_gui": "runtime_capability_gap_only",
            "dedicated_cua": "default_deny_except_gateway_discovery_bound_gap",
            "fallback_grant_required": True, "fallback_time_limit_seconds": 120,
            "zero_jev_requests": "deterministic_delegation_not_model_comparison"}
