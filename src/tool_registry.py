# src/tool_registry.py

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

EffectModel = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class ToolDescriptor:
    name: str
    capability: str
    effect_model: EffectModel | None


def logging_effects(arguments: dict[str, Any]) -> dict[str, Any]:
    level = arguments.get("level")

    if not isinstance(level, str):
        return {}

    if level not in {"DEBUG", "INFO", "WARN", "ERROR", "NONE"}:
        return {}

    return {
        "audit_logging_enabled": level != "NONE",
    }


def disabled_audit_effects(
    arguments: dict[str, Any],
) -> dict[str, Any]:
    return {
        "audit_logging_enabled": False,
    }


TOOL_REGISTRY: dict[str, ToolDescriptor] = {
    "get_metrics": ToolDescriptor(
        name="get_metrics",
        capability="metrics.read",
        effect_model=None,
    ),
    "get_logs": ToolDescriptor(
        name="get_logs",
        capability="metrics.read",
        effect_model=None,
    ),
    "restart_service": ToolDescriptor(
        name="restart_service",
        capability="service.restart",
        effect_model=None,
    ),
    "disable_audit_logging": ToolDescriptor(
        name="disable_audit_logging",
        capability="logging.configure",
        effect_model=disabled_audit_effects,
    ),
    "set_log_verbosity_level": ToolDescriptor(
        name="set_log_verbosity_level",
        capability="logging.configure",
        effect_model=logging_effects,
    ),
}


def get_tool_descriptor(name: str) -> ToolDescriptor | None:
    return TOOL_REGISTRY.get(name)