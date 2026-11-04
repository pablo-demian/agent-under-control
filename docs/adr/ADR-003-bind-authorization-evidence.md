# ADR-003 — Bind Authorization Evidence to the Evaluated Context

- **Status:** Accepted — experimental baseline
- **Baseline revision:** `c1784fa2b7074fa90cd3bda4064b63ddf24881a7`
- **Scope:** OPA adapter, harness, observed execution

## Context

Recomputing effect predictions after dispatch could produce a different answer from the prediction originally submitted to the policy. The authorized arguments and resource also must not drift between evaluation and dispatch.

## Decision

For successful OPA decisions, `src/opa_adapter.py` returns a deep-copied `evaluated_context` matching the logical context sent to OPA. The harness passes a copy of arguments to the authorizer and, when `evaluated_context` is present on an allow decision, checks that its arguments and resource match the dispatch request. The observer captures the authorized prediction and uses it for post-execution comparison.

## Alternatives considered

- **Recompute effects after tool execution:** rejected because mutable registry state can change the basis of comparison.
- **Trust the original decision object without copying:** rejected due to in-process mutation risk.
- **Retain evaluated context as evidence:** selected, with explicit limitations.

## Consequences

- Inconsistent supplied authorization context causes a pre-dispatch rejection.
- Effect comparison can use the prediction captured at authorization time, even when the Tool Registry changes later.
- Legacy baseline/strict authorizations can proceed without `evaluated_context`; this property is **conditional**, not universal.

## Evidence

- `tests/test_opa_adapter.py::test_opa_allow_returns_evaluated_context`
- `tests/test_harness.py::test_mismatched_authorized_arguments_never_dispatch`
- `tests/test_harness.py::test_mismatched_authorized_resource_never_dispatch`
- `tests/test_harness.py::test_authorizer_argument_mutation_cannot_change_dispatch`
- `tests/test_observed_effect_integration.py::test_observer_uses_authorized_effect_prediction`
- `tests/test_observed_effect_integration.py::test_observer_uses_prediction_captured_before_registry_change`

## Limitations / risks

- Presence of `evaluated_context` is not mandatory for all positive authorizations.
- The observer currently captures the decision context through both a callback and traced policy event; this duplication is a review item, not an independently verified integrity channel.
- The pre-dispatch context checks do not establish process isolation or protect against arbitrary trusted-code compromise.

## Related risks

`FREEZE-RISK-001` (optional context), `FREEZE-RISK-003` (dual capture path).
