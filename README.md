# Agent Under Control

**Engineering Trust in Autonomous Agents** — an experimental lab exploring **Harness Engineering**, **Agent Reliability Engineering (ARE)**, tool authorization, security properties, and the limits of autonomous execution.

> **A tool request is not an authorization.**

This repository accompanies a public research series. It uses a **local Python simulator** of an incident-recovery agent to study the difference between what a model requests, what an execution harness authorizes, and what changes in system state.

**This is research code, not a production security boundary or hardened agent runtime.**

## Read the series

- **PUB-000 — [Engineering Trust in Autonomous Agents](https://medium.com/@rebolini.pablo/engineering-trust-in-autonomous-agents-d7e4d22376e4)** — introduction and publication roadmap.
- **PUB-001 — [The Agent Is Not the Security Boundary](https://medium.com/@rebolini.pablo/the-agent-is-not-the-security-boundary-5fd3fe038e2c)** — prompt injection through untrusted logs; baseline execution versus strict tool authorization.
- **PUB-002 onward** — planned; see [research/roadmap.md](research/roadmap.md).

## Research questions

- Can lower-trust operational content influence an agent's tool selection?
- Can an authorization check prevent a dangerous request from executing without preventing legitimate recovery?
- What happens when different tools produce the same prohibited effect?
- What if an effect model makes an incorrect prediction?
- Which properties can be enforced at the execution boundary, and which can only be observed?
- How should reliability, task utility, containment, latency, and cost be measured?

## Laboratory architecture

```text
Untrusted logs / observations
             |
             v
       Agent reasoning
             |
             v
         Tool request
             |
             v
    Harness authorization  <---- baseline / strict / OPA policy
          /      \
      denied    allowed
         |         |
   tool_rejected  dispatch
                   |
                   v
            Simulated state
                   |
                   v
            Security Oracle
                   |
                   v
              JSONL trace
```

Key components:

| Component | Purpose |
| --- | --- |
| `src/agent.py` | Simulated incident-recovery environment, agent loop, tool definitions, and policy selection. |
| `src/harness.py` | Parse, authorize, dispatch, and trace tool requests. |
| `src/observed_execution.py` | Observe state around tool execution and invoke the oracle. |
| `src/oracle.py` | Evaluate selected security properties against observed simulator state. |
| `src/opa_adapter.py` | Invoke OPA to evaluate authorization policies, with fail-closed behavior. |
| `src/tool_registry.py` and `src/effects.py` | Describe tool capabilities and predicted effects. |
| `src/execution_boundary.py` | In-process protected-state prototype used in boundary tests. |
| `policies/agent.rego` | Rego authorization rules. |
| `scenarios/` | Experimental inputs including adversarial log content. |
| `tests/` | Unit and integration tests for the simulator and enforcement mechanisms. |
| `research/` | Hypotheses, evidence registry, and research roadmap. |

The execution boundary prototype constrains writes through a Python mapping interface; **it does not isolate arbitrary untrusted Python code**. A correct OPA decision also depends on trustworthy input and actual enforcement of the decision.

## Running the lab

Use a Python virtual environment and install the dependencies declared by the repository. Running model-backed scenarios requires an OpenAI API key; **never commit your `.env` file or tokens**.

```bash
# From the repository root, with dependencies installed:
export OPENAI_API_KEY='your-key-here'  # Prefer a local secret manager or untracked .env

# Baseline or strict policy, using the adversarial scenario
AUC_SCENARIO=adv001 AUC_POLICY_MODE=baseline python -m src.agent
AUC_SCENARIO=adv001 AUC_POLICY_MODE=strict python -m src.agent

# Automated checks
python -m pytest tests/ -q
python -m ruff check src/ tests/

# Rego policy check, when OPA CLI is installed
opa check --strict policies/agent.rego

# Evaluate a single local trace
python -m src.evaluator results/<run-id>.jsonl
```

The simulator uses model-generated decisions, so individual runs may differ. Historical traces can use different event schemas; they should not be pooled into a statistical dataset without normalization. Inspect traces before sharing them because they may include prompts, tool arguments, and other operational context.

## Evidence and reproducibility

- [Research hypotheses](research/hypotheses.md)
- [Experiment registry](research/experiments.md)
- [Claims and evidence](research/claims.md)
- [ADV-001 record](research/experiments/ADV-001.md)
- [ADV-002 record](research/experiments/ADV-002.md)

ADV-001 and ADV-002 are **individual observed simulator runs**, not estimates of attack or defense success rates. The original source commits for those historical executions were not recorded. Later commits document the implementation and evidence files, but must not be mistaken for the original execution commits.

The lab's research trace inventory includes historical duplicate-call behavior, and the evaluator's semantics are evolving. These limitations are part of the research record, not silently corrected observations.

## Development status

The laboratory is **experimental and actively evolving**. Current work focuses on explicit execution outcomes, predicted-versus-observed effects, and then a frozen architecture for comparative measurements.

For a point-in-time view of the experiments, use Git commit links and release tags rather than assuming the default branch reproduces every historical run.

## Security and responsible use

All service changes in the published scenarios are simulated. Do not treat this code as an authorization gateway for real production systems. Do not publish raw traces without reviewing and sanitizing them. No security guarantee is implied beyond the tested conditions.
