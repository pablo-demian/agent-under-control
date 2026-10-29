# src/opa_adapter.py

import json
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any

from src.effects import resolve_effects
from src.tool_registry import get_tool_descriptor

BASE_DIR = Path(__file__).resolve().parent.parent
POLICY_FILE = BASE_DIR / "policies" / "agent.rego"

def authorize_with_opa(
    name: str,
    arguments: dict[str, Any],
    *,
    opa_binary: str = "opa",
    policy_file: Path = POLICY_FILE,
) -> dict[str, Any]:
    """
    Authorize a simulated tool call using OPA.

    Fail closed on unknown tools, invalid input,
    missing OPA, timeouts or malformed decisions.
    """

    if get_tool_descriptor(name) is None:
        return {
            "allowed": False,
            "reason": "unknown_tool",
            "policy_id": "OPA-AUTHZ-001",
        }

    if not isinstance(arguments, dict):
        return {
            "allowed": False,
            "reason": "invalid_arguments",
            "policy_id": "OPA-AUTHZ-001",
        }

    if arguments.get("service") != "payments-api":
        return {
            "allowed": False,
            "reason": "invalid_resource",
            "policy_id": "OPA-AUTHZ-001",
        }

    if arguments.get("environment", "staging") != "staging":
        return {
            "allowed": False,
            "reason": "invalid_environment",
            "policy_id": "OPA-AUTHZ-001",
        }

    effects = resolve_effects(name, arguments)

    context = {
        "principal": "sre-agent",
        "resource": arguments["service"],
        "environment": "staging",
        "capability": effects["capability"],
        "arguments": arguments,
        "predicted_effects": effects["predicted_effects"],
    }

    command = [
        opa_binary,
        "eval",
        "--data",
        str(policy_file),
        "--stdin-input",
        "--format",
        "raw",
        "data.agent.authz.allow",
    ]

    try:
        completed = subprocess.run(
            command,
            input=json.dumps(context),
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )

    except (OSError, subprocess.TimeoutExpired):
        return {
            "allowed": False,
            "reason": "policy_engine_unavailable",
            "policy_id": "OPA-AUTHZ-001",
        }

    if completed.returncode != 0:
        return {
            "allowed": False,
            "reason": "policy_engine_error",
            "policy_id": "OPA-AUTHZ-001",
        }

    decision = completed.stdout.strip()

    if decision not in ("true", "false"):
        return {
            "allowed": False,
            "reason": "invalid_policy_response",
            "policy_id": "OPA-AUTHZ-001",
        }

    allowed = decision == "true"

    result = {
        "allowed": allowed,
        "reason": "opa_allow" if allowed else "opa_deny",
        "policy_id": "OPA-AUTHZ-001",
    }

    if allowed:
        result["evaluated_context"] = deepcopy(context)

    return result