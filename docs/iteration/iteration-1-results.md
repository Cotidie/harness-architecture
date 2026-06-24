---
type: report
status: complete
created: 2026-06-25
iteration: 1
source_plan: "[[02-iteration-1-surveyor-plan]]"
roadmap: "[[01-harness-mvp-iteration-roadmap]]"
---

# Iteration 1 (Surveyor Bootstrap): Results

## What was tested

The Surveyor agent was dispatched against a throwaway sample `src/` (domain,
contracts, application, adapters) carrying one deliberately planted forbidden
edge (`domain -> contracts`). Core question: can a single targeted CodeGraph
query become compact intended-architecture docs, and does observed-vs-intended
drift detection actually fire?

(The sample has since been restored as a permanent fixture under `sample/` for
use across later iterations.)

## Results vs the plan's testable conditions

| Check | Expected | Actual | Verdict |
|-------|----------|--------|---------|
| Budget | 2 or fewer CodeGraph queries | 1 query | PASS |
| Artifacts | all 7 written, non-empty | all 7 OK | PASS |
| No bloat | no source bodies pasted | only a `from_score(...)` prose reference; diagram 14 lines, boundary level | PASS |
| Accuracy | `boundaries.yaml` names real modules | domain / contracts / application / adapters all named | PASS |
| Drift detection (core) | planted forbidden edge flagged | caught `domain -> contracts` at `route_risk_policy.py:9`, labeled CODE_DRIFT_HARMFUL, with refactor recommendation | PASS |

The agent also classified the other observations correctly: missing tests as
UNCLEAR_DRIFT, absent `shared/` as DOC_DRIFT_ACCEPTED, the rest as ALIGNED.

## Verdict

The riskiest assumption holds: a single narrow CodeGraph query produces useful
compact docs AND correctly catches a boundary violation, with no repo-wide read.
The harness premise (observed-vs-intended reconciliation) is validated at the
cheapest surface.

## What this did NOT prove

- Ran via inline-prompt fallback, not the named `surveyor` subagent (that needed
  a plugin reload, since done). The named-dispatch path is unexercised until the
  next run.
- The sample was a clean planted case. Messy real-world drift (ambiguous edges,
  dynamic dispatch) is untested.
- Graceful degradation on a code-less repo was skipped (a re-run would have
  clobbered the curated docs).
- n = 1: one feature, one repo, one drift type.

## Feedback captured for iteration 2 (Architect)

- 1 query was enough; the budget is not too tight.
- `boundaries.yaml` and `current.mmd` landed at the right altitude.
- Drift labels were reliable.
- The generic placeholder layout was acceptable; the real module map is locked
  when the linter lands.
- Iteration 2 (Architect: reconcile + patch) can trust the Surveyor's output as
  input, and should run against the `sample/` fixture + `sample/boundaries.yaml`.

## Naming note

After this iteration the four agents were renamed for clarity:
Surveyor (was Snapshot), Architect (was Patch), Builder (was Scoped Coding),
Inspector (was Validation).
