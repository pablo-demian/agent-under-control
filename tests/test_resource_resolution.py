
import pytest

from src.resource_resolution import (
    ResourceResolutionError,
    resolve_effect_paths,
)

TRUSTED_RESOURCES = frozenset({"payments-api"})

def test_resolves_relative_effects_for_trusted_resource():
    result = resolve_effect_paths(
        service="payments-api",
        predicted_effects={
            "audit_logging_enabled": True,
            "healthy": False,
        },
        allowed_resources=TRUSTED_RESOURCES,
    )

    assert result == {
        "payments-api.audit_logging_enabled": True,
        "payments-api.healthy": False,
    }

def test_rejects_unknown_resource():
    with pytest.raises(ResourceResolutionError):
        resolve_effect_paths(
            service="billing-api",
            predicted_effects={
                "audit_logging_enabled": True,
            },
            allowed_resources=TRUSTED_RESOURCES,
        )

def test_rejects_resource_path_injection():
    with pytest.raises(ResourceResolutionError):
        resolve_effect_paths(
            service="payments-api.audit_logging_enabled",
            predicted_effects={"healthy": True},
            allowed_resources=TRUSTED_RESOURCES,
        )

def test_rejects_absolute_effect_paths():
    with pytest.raises(ResourceResolutionError):
        resolve_effect_paths(
            service="payments-api",
            predicted_effects={
                "billing-api.audit_logging_enabled": True,
            },
            allowed_resources=TRUSTED_RESOURCES,
        )

def test_empty_prediction_remains_empty():
    result = resolve_effect_paths(
        service="payments-api",
        predicted_effects={},
        allowed_resources=TRUSTED_RESOURCES,
    )

    assert result == {}

def test_rejects_non_string_resource():
    with pytest.raises(ResourceResolutionError):
        resolve_effect_paths(
            service=None,
            predicted_effects={"healthy": True},
            allowed_resources=TRUSTED_RESOURCES,
        )