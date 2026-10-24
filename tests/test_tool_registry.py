# tests/test_tool_registry.py

from src.effects import resolve_effects
from src.tool_registry import (
    TOOL_REGISTRY,
    ToolDescriptor,
    get_tool_descriptor,
)


def test_registered_tool_has_descriptor():
    descriptor = get_tool_descriptor("set_log_verbosity_level")

    assert descriptor is not None
    assert descriptor.capability == "logging.configure"


def test_unknown_tool_is_not_registered():
    assert get_tool_descriptor("unknown_tool") is None


def test_direct_disable_effect_is_preserved():
    result = resolve_effects(
        "disable_audit_logging",
        {
            "service": "payments-api",
            "environment": "staging",
        },
    )

    assert result["capability"] == "logging.configure"
    assert result["predicted_effects"] == {
        "audit_logging_enabled": False,
    }


def test_semantic_bypass_effect_is_preserved():
    result = resolve_effects(
        "set_log_verbosity_level",
        {
            "service": "payments-api",
            "environment": "staging",
            "level": "NONE",
        },
    )

    assert result["predicted_effects"] == {
        "audit_logging_enabled": False,
    }


def test_safe_logging_effect_is_preserved():
    result = resolve_effects(
        "set_log_verbosity_level",
        {"level": "INFO"},
    )

    assert result["predicted_effects"] == {
        "audit_logging_enabled": True,
    }


def test_unknown_effects_remain_unknown():
    result = resolve_effects(
        "set_log_verbosity_level",
        {"level": "INVALID"},
    )

    assert result["predicted_effects"] == {}


def test_unknown_tool_has_no_assigned_capability():
    result = resolve_effects("unknown_tool", {})

    assert result == {
        "capability": "unknown",
        "predicted_effects": {},
    }


def test_registry_extensibility(monkeypatch):
    """
    A descriptor can introduce a new effect model
    without modifying the central resolver.
    """

    descriptor = ToolDescriptor(
        name="set_simulated_feature",
        capability="feature.configure",
        effect_model=lambda args: {
            "feature_enabled": args["enabled"],
        },
    )

    monkeypatch.setitem(
        TOOL_REGISTRY,
        descriptor.name,
        descriptor,
    )

    result = resolve_effects(
        "set_simulated_feature",
        {"enabled": True},
    )

    assert result == {
        "capability": "feature.configure",
        "predicted_effects": {
            "feature_enabled": True,
        },
    }