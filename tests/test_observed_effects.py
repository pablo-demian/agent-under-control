
import pytest

from src.observed_effects import evaluate_observed_effects
from src.resource_resolution import ResourceResolutionError

ALLOWED_RESOURCES = frozenset({"payments-api"})

def test_observed_effects_match():
    result = evaluate_observed_effects(
        service="payments-api",
        predicted_effects={"audit_logging_enabled": True},
        before_state={
            "payments-api": {"audit_logging_enabled": True}
        },
        after_state={
            "payments-api": {"audit_logging_enabled": True}
        },
        allowed_resources=ALLOWED_RESOURCES,
    )

    assert result["status"] == "match"
    assert result["matched"] == [
        "payments-api.audit_logging_enabled"
    ]

def test_observed_effects_detect_divergence():
    result = evaluate_observed_effects(
        service="payments-api",
        predicted_effects={"audit_logging_enabled": True},
        before_state={
            "payments-api": {"audit_logging_enabled": True}
        },
        after_state={
            "payments-api": {"audit_logging_enabled": False}
        },
        allowed_resources=ALLOWED_RESOURCES,
    )

    assert result["status"] == "mismatch"
    assert result["mismatched"] == [
        {
            "path": "payments-api.audit_logging_enabled",
            "predicted": True,
            "observed": False,
        }
    ]

def test_observed_effects_reject_untrusted_resource():
    with pytest.raises(ResourceResolutionError):
        evaluate_observed_effects(
            service="billing-api",
            predicted_effects={"audit_logging_enabled": True},
            before_state={},
            after_state={},
            allowed_resources=ALLOWED_RESOURCES,
        )