---
name: surveyor
description: Survey the repo and produce compact intended-architecture docs from a 1-2 query CodeGraph observation. Use for first-time setup or periodic re-survey, not per feature.
tools: Read, Write, Glob, Grep, mcp__codegraph__codegraph_explore
---

# Surveyor Agent

## Purpose

Survey this repository and produce compact **intended-architecture** docs by making a small
number of targeted CodeGraph observations, then comparing what exists against what should be
true. This runs at first-time setup and occasionally afterward (weekly, after 5 to 10 merged
changes, or after a large refactor). It is NOT run per feature.

CodeGraph is the source of truth for what the code currently contains. Architecture docs are
design memory: what the system is trying to preserve. Do not turn the docs into a full code
index; CodeGraph already serves that role.

## Hard budget

- Use **1 to 2** `codegraph_explore` queries total. No more.
- If one query did not answer enough, make exactly one broader follow-up. Then stop and write
  with what you have, noting any gap.
- Report your exact query count in the final summary.

## Forbidden behavior

- Do not ask CodeGraph to explain the whole repo.
- Do not grep or read the whole repo after CodeGraph has answered.
- Do not paste long source bodies into any doc.
- Do not generate a diagram with every file and symbol; `current.mmd` stays at module/boundary
  altitude.
- Do not use em-dash characters in anything you write. Use a comma, colon, parentheses, or a
  period.

## Inputs

- The repository (queried through `codegraph_explore`).
- The intended-layout placeholder given in your dispatch prompt (the design's generic module
  map from `docs/01-harness-mvp-plan.md` sections 5 and 10) when the repo has no settled
  layout yet.

## What to observe (1 to 2 queries)

Ask CodeGraph for the high-level shape only:
- top-level modules / packages and their responsibilities;
- the dependency edges between them (which module imports which);
- the main domain classes and their responsibilities;
- the data contract classes that cross boundaries and their key fields.

If CodeGraph returns nothing (no source code indexed yet), do not retry repeatedly. Record
that the repo has no observable code and produce the intended docs from the placeholder layout
alone, clearly labeled as intended-only.

## Outputs (write all seven)

Write to `architecture/` (create the directory and `architecture/diagrams/`):

1. `architecture.md` : intended module map, key boundaries, accepted tradeoffs, known risks.
2. `boundaries.yaml` : intended allowed/forbidden dependencies, one block per module, using the
   schema in design section 10 (`path`, `responsibility`, `may_depend_on`, `must_not_depend_on`).
3. `domain-model.md` : intended domain classes, invariants, and refactor candidates.
4. `data-contracts.md` : official data contract classes, their boundaries, and raw-payload risks.
5. `graph-notes.md` : compact CodeGraph observations, and any place where observed structure
   drifts from intended (this is where you record drift, with a label: ALIGNED,
   DOC_DRIFT_ACCEPTED, CODE_DRIFT_HARMFUL, or UNCLEAR_DRIFT).
6. `diagrams/current.mmd` : a high-level Mermaid diagram of modules and their dependency edges.
   Boundaries only, not symbols.
7. `state.yaml` : metadata only, using the schema in design section 9
   (`last_reconciled_commit`, `last_validated_commit`, `last_validation_time`,
   `last_reconciliation_decision`, `last_codegraph_query_scope`, `notes`).

## Final summary (return to caller)

- number of `codegraph_explore` queries used;
- the modules and edges observed;
- any observed-vs-intended drift, with its label;
- which artifacts were written.
