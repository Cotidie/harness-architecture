# Iteration 6 system test results (agentic harness, not the sample linter)

Date: 2026-06-25
Branch: `iter6-governance-budget` (HEAD `712050b` at time of writing)
Method: adversarial probes against the iter-6 governance + budget controls (cli-user-test style),
driving the harness controls, not the boundaries linter.

## What works well (verified)

- **Freshness verification.** Edited a file without `codegraph sync`; `status --json` reported
  `pendingChanges.modified: 1` -> gate verdict STALE -> orchestrator would STOP. Genuinely
  catches staleness, not always-green. Cheap.
- **Inspector cleanup (iter-6 core).** Inspector made 1 query, emitted `Next action: none`, and
  left `state.yaml` untouched (empty git diff after its run). No gate-1 re-run. The orchestrator
  owned gate 1 (76 tests, self-check exit 0, scope) and the state bump. Separation achieved.
- **Capped-loop routing.** Forced scratch forbidden edge -> orchestrator gate 1 exit 1 ->
  `REJECT: ARCHITECTURE VIOLATION` -> routed to builder (code-level), no Inspector dispatch,
  no commit (HEAD unchanged), scratch reverted.
- **Drift scan.** Repo-wide self-check clean (exit 0); undeclared-module diff = none (`shared`
  declared-but-not-materialized = intended-ahead-of-observed, not drift); wrote `drift-scan.md`.
- **Feature shipped.** `--quiet` clean ACCEPT path through the hardened loop (`7e65907`, state
  `4e033a8`), 76 tests OK.

## Fixed already (commit `712050b`)

- **#1 Hook over-count (was MED-HIGH).** The hook substring-matched the whole event JSON, so a
  `Read`/`Grep` of any file merely mentioning `mcp__codegraph__codegraph_explore` incremented the
  meter. Fixed: the hook now parses the `tool_name` field with python3 and matches it exactly.
  Verified: mention/malformed text no longer counts; real explore + spaced-JSON variant do.
- **#3 Self-report format not mandated (was MED).** The fallback meter expects a final
  `QUERIES_USED=<n>` line, but no agent def required it (only the Builder emitted it, prompted).
  Fixed: all four agent defs (architect, builder, surveyor, inspector) now mandate the line.
- **#6 Inspector retained Bash (was LOW).** Dropped `Bash` from the Inspector `tools:` and removed
  its `git diff` fallback (orchestrator supplies the changed-files list). It can no longer
  self-run gate 1 mechanically, not just by prose.

## Fixed in iteration-6 follow-up

### #2 Budget hook -- RESOLVED (hook live + reaches subagents)

Re-tested after restart with the hook live. Both checks passed:

1. **Main session:** reset counter to 0, made ONE `codegraph_explore` call -> `query-count` = 1.
   The `PreToolUse` project-settings hook is live and counts real explore calls (not mentions).
2. **Subagent (the primary unknown):** reset to 0, dispatched ONE subagent that made exactly one
   `codegraph_explore` -> `query-count` = 1. **The hook fires for a SUBAGENT's tool calls, and
   exactly once** (the subagent reported 2 tool_uses but only the real explore incremented).

Conclusion: hook-based per-agent metering is viable across subagents. The metered delta is the
metering of record (SKILL.md already says "report the metered counts, not the self-reported
ones"); the `QUERIES_USED=` self-report (#3) stays as a secondary cross-check, not the authority.

### #4 Drift-scan edge check -- FIXED (committed script, modules AND edges)

Was: edge check unimplemented, scan re-improvised (ad-hoc python) each run. Now: committed
`scripts/drift_scan.py` (+ `tests/test_drift_scan.py`, 5 tests) reuses the linter's scanner to
compute the observed module-edge graph and diffs it against `boundaries.yaml` -- flags undeclared
MODULES and undeclared EDGES, reports forbidden edges (linter's job) and unmaterialized modules as
info, exits 1 on drift / 0 clean. Deterministic from source, no CodeGraph query, so unmetered.
SKILL.md step 0b now calls it instead of ad-hoc python; the dogfood run reproduces the prior
manual result (5 declared / 4 observed, `shared` unmaterialized, no drift).

### #5 Capped-loop counter -- FIXED (persisted, survives /compact)

Was: cycle count lived in orchestrator working memory, so a mid-loop `/compact` could silently
exceed the 2-cycle cap. Now: the count is reset to 0 at loop start and incremented in
`.architecture/.budget/revise-count` at the START of each cycle, read back from the artifact. The
cap check reads the file, not memory, so a compaction between cycles cannot reset it.

## Remaining issues (NOT yet fixed)

### #7 Approval pause assumes a human exists (MED, design)

Fine interactively; an autonomous `/harness-feature` (loop/cron, packaging) has no human turn and
would deadlock at the approval pause. Fix direction: an explicit non-interactive contract
(`--auto-approve` with a recorded rationale, or documented human-required constraint), decided at
the packaging iteration (iter 10).

## Suggested sequencing

- #2, #4, #5: DONE in the iteration-6 follow-up (see above).
- #7: packaging iteration (iter 10), where autonomous install/run is in scope.

## Branch state at write time

`iter6-governance-budget`, 7 commits, 76 tests OK. Not yet merged. `main` also still has the
iter-6 plan commit unpushed. Finishing the branch (merge / push+PR / keep) is an open decision.
