# ADR-004 — Tool Return Is Not Evidence of Effect Success

- **Status:** Accepted — experimental baseline
- **Baseline revision:** `c1784fa2b7074fa90cd3bda4064b63ddf24881a7`
- **Scope:** Harness outcome semantics and observed effect comparison

## Context

A tool may return normally with an error-shaped payload, raise an exception, be blocked by an execution boundary, or return successfully while producing a state contrary to its predicted effect. Collapsing these cases into a single “success” signal obscures policy and reliability failures.

## Decision

Record `tool_outcome` independently of tool result content, with distinct statuses `returned`, `raised`, and `effect_denied` for the handled cases. Preserve the historical `tool_executed` event for compatibility, but interpret it only as a normal function return. For normally returned calls with eligible comparison context, compare declared post-state values with observed state snapshots using `match`, `mismatch`, or `unknown`.

## Alternatives considered

- **Classify outcomes by the returned JSON payload:** rejected; payload contents do not establish control-flow outcome.
- **Treat authorized or normally returned calls as effective:** rejected; the requested postcondition may not hold.
- **Separate invocation outcome, Oracle result, and prediction comparison:** selected.

## Consequences

- A normal return does not establish a successful remediation.
- A returned `{"error": ...}` payload is still a normal return at the harness level.
- A discrepancy between predicted and observed post-state can be represented without changing authorization semantics.

## Evidence

- `tests/test_execution_outcome.py::test_returned_error_is_not_classified_as_effect_denied`
- `tests/test_execution_outcome.py::test_dispatch_exception_emits_raised_outcome`
- `tests/test_execution_outcome.py::test_boundary_violation_emits_effect_denied`
- `tests/test_effect_comparator.py::test_predicted_safe_effect_contradicted_by_observation`
- `tests/test_effect_comparator.py::test_empty_prediction_is_unknown`
- `tests/test_effect_comparator.py::test_boolean_and_integer_are_not_equivalent`
- `tests/test_observed_effect_integration.py::test_returned_tool_emits_effect_divergence`

## Limitations / risks

- The comparator checks values at selected post-state paths; it does not measure comprehensive state transitions.
- The comparison is conditional on available authorized or explicitly supplied context and resource allowlist.
- The harness currently catches selected exception classes, not all possible runtime failures.
- A `match` means declared observed properties matched; it is not proof of universal operational success.

## Related risks

`FREEZE-RISK-002` (observation coverage); future M5/M6 metrics must keep invocation, authorization, and effect rates separate.
