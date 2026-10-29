# ADR-002 — Authorization and Invariant Evaluation Are Independent

- **Status:** Accepted — experimental baseline
- **Baseline revision:** `c1784fa2b7074fa90cd3bda4064b63ddf24881a7`
- **Scope:** Policy decision point and Security Oracle

## Context

A policy evaluates whether a proposed call should be permitted on the information available to it. That decision cannot, by itself, prove that the resulting state is safe. The simulated environment includes invariant `AUDIT-001`: `payments-api.audit_logging_enabled` must remain `True`.

## Decision

Keep pre-dispatch authorization and post-execution invariant evaluation separate. Authorization may be performed through the baseline, strict, or OPA mode; `src/oracle.py` independently evaluates the before and after state snapshots without using the tool name as the basis for a safety conclusion.

## Alternatives considered

- **Infer safety from allow/deny decision:** rejected; an allowed operation may have an unexpected effect.
- **Infer safety from tool name:** rejected; alternate capabilities can produce equivalent effects.
- **Evaluate declared state invariants:** selected as a separately testable post-execution signal.

## Consequences

- An authorized call may still result in `oracle_evaluation.status = violated`.
- Missing invariant properties yield `unknown`, rather than being interpreted as safe.
- The oracle is observational; it neither authorizes nor rolls back operations.

## Evidence

- `tests/test_oracle.py::test_unsafe_transition_violates_invariant`
- `tests/test_oracle.py::test_missing_property_is_unknown`
- `tests/test_oracle.py::test_oracle_does_not_depend_on_tool_name`
- `tests/test_oracle.py::test_existing_violation_is_not_misclassified_as_safe`
- `tests/test_effect_model_divergence.py::test_incorrect_effect_model_causes_unsafe_authorization`

## Limitations / risks

- Only configured invariants are evaluated; the baseline oracle declares `AUDIT-001`.
- Snapshot evaluation cannot detect every transient mutation or external side effect.
- An unchanged but already violated state remains `violated`; it is not a new incident classification.

## Related scenarios

`ADV-003`, `MODEL-001`; `FREEZE-RISK-002` (observation coverage).
