# Claims and Evidence Registry

## CLAIM-001

Claim:
Agent behavior and tool execution authorization
are separate security outcomes.

Evidence:
ADV-001, ADV-002.

Status:
Supported in the simulator.

## CLAIM-002

Claim:
Correct enforcement of a name-based policy does
not guarantee preservation of security invariants.

Evidence:
ADV-003.

Status:
Reproduced.

## CLAIM-003

Claim:
Incorrect effect predictions can lead to unsafe
authorization even when OPA evaluates its policy
correctly.

Evidence:
MODEL-001.

Status:
Reproduced.

## CLAIM-004

Claim:
An independently enforced write restriction can
preserve AUDIT-001 despite an incorrect effect model.

Evidence:
BOUNDARY-001.

Status:
Reproduced in the simulated protected-state interface.

Limitation:
Not demonstrated against arbitrary code executing
with unrestricted access to the same process.