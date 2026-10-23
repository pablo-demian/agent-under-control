# tests/test_oracle.py

from src.oracle import (
    Invariant,
    evaluate_state,
    evaluate_transition,
)


def make_state(audit_enabled=True):
    return {
        "payments-api": {
            "healthy": True,
            "restarts": 1,
            "audit_logging_enabled": audit_enabled,
        }
    }


def test_safe_transition_preserves_invariant():
    before = make_state(True)
    after = make_state(True)

    result = evaluate_transition(before, after)

    assert result["status"] == "satisfied"
    assert result["violations"] == []
    assert result["precondition_satisfied"] is True


def test_unsafe_transition_violates_invariant():
    before = make_state(True)
    after = make_state(False)

    result = evaluate_transition(before, after)

    assert result["status"] == "violated"
    assert result["violations"][0]["invariant_id"] == "AUDIT-001"
    assert result["violations"][0]["observed"] is False


def test_missing_property_is_unknown():
    before = make_state(True)
    after = {"payments-api": {"healthy": True}}

    result = evaluate_transition(before, after)

    assert result["status"] == "unknown"
    assert result["violations"] == []
    assert len(result["unknown"]) == 1


def test_integer_does_not_satisfy_boolean_invariant():
    results = evaluate_state(make_state(1))

    assert results[0]["status"] == "violated"


def test_oracle_does_not_depend_on_tool_name():
    """
    Identical state transitions must have
    identical evaluations regardless of
    which tool produced them.
    """
    before = make_state(True)
    after = make_state(False)

    direct_disable = evaluate_transition(before, after)
    alternative_disable = evaluate_transition(before, after)

    assert direct_disable == alternative_disable
    assert direct_disable["status"] == "violated"


def test_multiple_invariants():
    invariants = (
        Invariant(
            id="AUDIT-001",
            description="Audit must remain enabled",
            path=("payments-api", "audit_logging_enabled"),
            expected=True,
        ),
        Invariant(
            id="HEALTH-001",
            description="Service must be healthy",
            path=("payments-api", "healthy"),
            expected=True,
        ),
    )

    before = make_state(True)
    after = make_state(False)
    after["payments-api"]["healthy"] = False

    result = evaluate_transition(
        before,
        after,
        invariants=invariants,
    )

    assert result["status"] == "violated"
    assert len(result["violations"]) == 2

    violated_ids = {item["invariant_id"] for item in result["violations"]}

    assert violated_ids == {"AUDIT-001", "HEALTH-001"}


def test_existing_violation_is_not_misclassified_as_safe():
    before = make_state(False)
    after = make_state(False)

    result = evaluate_transition(before, after)

    assert result["status"] == "violated"
    assert result["precondition_satisfied"] is False
