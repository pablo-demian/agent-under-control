# Research Hypotheses

## H-001 — Architecture and Reliability

Agent reliability depends on harness architecture,
not solely on the underlying language model.

Status: Preliminary supporting evidence.

Relevant experiments:
ADV-001, ADV-002, ADV-003.

## H-002 — Risk-Adaptive Controls

Risk-adaptive enforcement may offer a better balance
between security, task utility, latency and cost than
uniformly strict controls.

Status: Not yet tested.

## H-003 — Trust Boundaries

Enforceable trust boundaries can preserve selected
security properties even when agent behavior or
effect predictions are incorrect.

Status: Preliminary supporting evidence.

Relevant experiments:
MODEL-001, BOUNDARY-001.

Limitations:
The execution boundary is currently an in-process
simulator abstraction, not an isolation mechanism
against arbitrary malicious code.