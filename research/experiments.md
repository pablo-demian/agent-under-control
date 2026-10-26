# Experiment Registry

| ID | Research question | Status |
|---|---|---|
| ADV-001 | Can untrusted logs redirect agent behavior? | Observed |
| ADV-002 | Can strict policy contain a sensitive request? | Observed |
| ADV-003 | Can equivalent tools bypass name-based policy? | Reproduced |
| PDP-001 | Does PDP failure prevent tool execution? | Tested |
| MODEL-001 | Can incorrect effects lead to unsafe authorization? | Reproduced |
| BOUNDARY-001 | Can an independent write restriction contain the effect? | Reproduced |

## Evidence requirements

Each experiment should record:

- Hypothesis
- Scenario and policy configuration
- Source commit
- Model version, when applicable
- Execution procedure
- Observed behavior
- Trace or test evidence
- Limitations

## Important

Passing tests establish behavior under the tested
conditions. They do not imply universal security.

## Historical trace compatibility

The initial evidence inventory contains 10 JSONL traces.

Not all traces share the same event schema:

- Some historical traces use `tool_execution`.
- Later traces distinguish requests, policy decisions,
  tool executions and tool rejections.
- Newer traces also include oracle evaluations.
- Two historical traces contain duplicate execution
  events associated with the same call IDs.

The evaluator currently uses tool-name-specific logic
and may not recognize equivalent effects or all
containment events.

Consequently, historical evaluator output must not
be interpreted as a uniform measurement dataset.

A normalized event contract will be developed in M4.1.