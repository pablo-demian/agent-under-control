# ADR-001 — The Agent Is Not the Security Boundary

- **Status:** Accepted — experimental baseline
- **Baseline revision:** `c1784fa2b7074fa90cd3bda4064b63ddf24881a7`
- **Scope:** Agent Under Control, simulated execution environment

## Context

The agent consumes operational information, including application logs that may contain attacker-controlled text. ADV-001 embeds a forged incident runbook in logs, while ADV-003 introduces an alternative tool operation intended to achieve an audit-disabling effect. Model instructions and log contents are not reliable authorization signals.

## Decision

All tool requests routed through the agent execution loop must pass through the harness before dispatch. The harness parses arguments, calls the selected authorizer, rejects denied requests, and records the result. The model's choice to request a tool does not authorize its execution.

## Alternatives considered

- **Prompt-only prohibition:** rejected as an enforcement mechanism; the model may encounter lower-trust instructions.
- **Tool function as sole control:** insufficient as the sole policy architecture, although individual tools may implement execution boundaries.
- **Harness mediation plus policy evaluation:** selected for this simulator because it creates an independently testable authorization point.

## Consequences

- The model can propose operations; the harness decides whether to dispatch them.
- Policy denials must be distinguishable from errors raised by tools or execution boundaries.
- The guarantee applies to calls mediated by this harness, not arbitrary Python calls or external effects.

## Evidence

- `tests/test_harness.py::test_denied_tool_never_executes`
- `tests/test_harness.py::test_authorization_precedes_execution`
- `tests/test_execution_outcome.py::test_policy_denial_does_not_emit_execution_outcome`
- `tests/test_agent_loop_wiring.py::test_opa_mode_passes_allowed_resources_to_observer`

## Limitations / risks

- No OS process isolation or universal reference monitor is demonstrated.
- The agent loop integration test uses a simulated model response.
- A denial prevents mediated dispatch but does not prove the model resisted the prompt-injection instruction.

## Related scenarios

`ADV-001`, `ADV-003`; `FREEZE-RISK-004` (real OPA tests may skip if the binary is absent).
