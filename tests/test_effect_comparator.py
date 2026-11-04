
from src.effect_comparator import compare_effects


def make_state(audit_enabled=True):
    return {
        "payments-api": {
            "healthy": False,
            "restarts": 0,
            "audit_logging_enabled": audit_enabled,
        }
    }


def test_matching_predicted_effect():
    result = compare_effects(
        predicted_effects={
            "payments-api.audit_logging_enabled": True,
        },
        before_state=make_state(True),
        after_state=make_state(True),
    )

    assert result["status"] == "match"
    assert result["matched"] == [
        "payments-api.audit_logging_enabled"
    ]
    assert result["mismatched"] == []
    assert result["unknown"] == []


def test_predicted_safe_effect_contradicted_by_observation():
    result = compare_effects(
        predicted_effects={
            "payments-api.audit_logging_enabled": True,
        },
        before_state=make_state(True),
        after_state=make_state(False),
    )

    assert result["status"] == "mismatch"
    assert result["matched"] == []
    assert result["mismatched"] == [
        {
            "path": "payments-api.audit_logging_enabled",
            "predicted": True,
            "observed": False,
        }
    ]


def test_missing_observed_property_is_unknown():
    result = compare_effects(
        predicted_effects={
            "payments-api.audit_logging_enabled": True,
        },
        before_state=make_state(True),
        after_state={
            "payments-api": {
                "healthy": True,
            }
        },
    )

    assert result["status"] == "unknown"
    assert result["matched"] == []
    assert result["mismatched"] == []
    assert result["unknown"] == [
        "payments-api.audit_logging_enabled"
    ]


def test_empty_prediction_is_unknown():
    result = compare_effects(
        predicted_effects={},
        before_state=make_state(True),
        after_state=make_state(True),
    )

    assert result["status"] == "unknown"
    assert result["matched"] == []
    assert result["mismatched"] == []
    assert result["unknown"] == []


def test_partial_match_with_missing_property_is_unknown():
    result = compare_effects(
        predicted_effects={
            "payments-api.audit_logging_enabled": True,
            "payments-api.healthy": True,
        },
        before_state=make_state(True),
        after_state={
            "payments-api": {
                "audit_logging_enabled": True,
            }
        },
    )

    assert result["status"] == "unknown"
    assert result["matched"] == [
        "payments-api.audit_logging_enabled"
    ]
    assert result["unknown"] == [
        "payments-api.healthy"
    ]


def test_mismatch_takes_precedence_over_unknown():
    result = compare_effects(
        predicted_effects={
            "payments-api.audit_logging_enabled": True,
            "payments-api.missing_property": "expected",
        },
        before_state=make_state(True),
        after_state=make_state(False),
    )

    assert result["status"] == "mismatch"
    assert len(result["mismatched"]) == 1
    assert result["unknown"] == [
        "payments-api.missing_property"
    ]


def test_boolean_and_integer_are_not_equivalent():
    result = compare_effects(
        predicted_effects={
            "payments-api.audit_logging_enabled": True,
        },
        before_state=make_state(True),
        after_state={
            "payments-api": {
                "audit_logging_enabled": 1,
            }
        },
    )

    assert result["status"] == "mismatch"
