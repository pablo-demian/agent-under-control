# FREEZE-001.4 — Architecture Decision Records

**Baseline:** `c1784fa2b7074fa90cd3bda4064b63ddf24881a7`
**Status:** Accepted as documentation of the experimental baseline; not a certification of production security.

| ADR | Decision |
|---|---|
| [ADR-001](ADR-001-agent-is-not-security-boundary.md) | The Agent Is Not the Security Boundary |
| [ADR-002](ADR-002-authorization-is-not-invariant-evaluation.md) | Authorization and Invariant Evaluation Are Independent |
| [ADR-003](ADR-003-bind-authorization-evidence.md) | Bind Authorization Evidence to the Evaluated Context |
| [ADR-004](ADR-004-tool-return-is-not-effect-success.md) | Tool Return Is Not Evidence of Effect Success |

## Interpretation

Each decision has the following structure: context, decision, alternatives, consequences, evidence, and limitations. Test names are traceability references, **not** universal security proofs. Real OPA execution tests may skip in environments without the OPA binary.

## Related FREEZE risks

- **FREEZE-RISK-001:** `evaluated_context` optional for historical authorization modes.
- **FREEZE-RISK-002:** snapshots and explicitly modeled state cover only a subset of possible effects.
- **FREEZE-RISK-003:** observer captures authorization evidence through callback and trace event.
- **FREEZE-RISK-004:** OPA-dependent tests can be skipped without the OPA binary.

No executable source changes are introduced by these ADRs.
