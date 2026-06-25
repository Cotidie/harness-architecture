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

## Remaining issues (NOT yet fixed)

### #2 Budget hook never activated this session (HIGH, environmental) -- RE-TEST AFTER RESTART

After `/reload-plugins` the metered counter stayed 0 even for a MAIN-SESSION `codegraph_explore`,
so the project `.claude/settings.json` `PreToolUse` hook was not live (`/reload-plugins` reloads
plugin hooks, not a newly-added project settings hook; it appears to need a full session
restart and/or hook approval). Consequences:

- live hook enforcement is unproven;
- the **primary risk -- does a PreToolUse hook fire for a SUBAGENT's tool calls** -- stayed
  UNTESTED. Metering ran on the self-report fallback (now hardened by #3).

**Re-test procedure (run first thing after restart):**

1. Confirm the hook is loaded: trigger a MAIN-SESSION query and check the counter increments.

   ```sh
   cd <repo>
   rm -rf .architecture/.budget
   # then, from the agent, make ONE codegraph_explore call, then:
   cat .architecture/.budget/query-count   # expect 1 if the hook is now live
   ```

2. If main-session counts: dispatch ONE subagent that makes exactly one query (e.g. a trivial
   `architect` run), then check the counter delta.
   - delta == 1 -> hooks reach subagents; hook-based enforcement is viable. Wire the orchestrator
     to trust the metered count over self-report and mark budget metering fully done.
   - delta == 0 -> hooks do NOT reach subagents; hook-based per-agent enforcement is not viable.
     Keep the self-report+cross-check fallback (#3) as the metering of record, and record this as
     a hard constraint for packaging (iter 10): either accept the fallback or move metering into
     each agent's own wrapper.
3. Note: the hook is unit-tested standalone and now matches `tool_name` exactly (#1), so a 0 after
   restart means "does not reach this surface", not "script bug".

### #4 Drift-scan edge check unimplemented + no committed script (MED)

The skill prose promises flagging undeclared MODULES and cross-module EDGES, but the dogfood scan
only diffed modules, the edge check has no implementation, and the whole scan is re-improvised
(ad-hoc python) each run. Fix direction: commit a real `drift-scan` script that checks modules
AND edges (query CodeGraph's module-edge summary, diff against `boundaries.yaml` declared edges),
or downscope the skill prose to modules-only so it stops overpromising.

### #5 Capped-loop counter is ephemeral (LOW-MED)

"Track the count in the run" = orchestrator working memory. A mid-loop `/compact` or session drop
loses the cycle count, so the 2-cycle cap can be silently exceeded. Fix direction: persist the
count in a run artifact (e.g. `.architecture/.budget/revise-count`, or a line in the patch) so it
survives compaction.

### #7 Approval pause assumes a human exists (MED, design)

Fine interactively; an autonomous `/harness-feature` (loop/cron, packaging) has no human turn and
would deadlock at the approval pause. Fix direction: an explicit non-interactive contract
(`--auto-approve` with a recorded rationale, or documented human-required constraint), decided at
the packaging iteration (iter 10).

## Suggested sequencing

- #2 re-test: immediately after restart (procedure above). Decides whether hook metering is real
  or the fallback is permanent.
- #4, #5: fold into the iteration-6 follow-up / iteration-7 work, or fix opportunistically.
- #7: packaging iteration (iter 10), where autonomous install/run is in scope.

## Branch state at write time

`iter6-governance-budget`, 7 commits, 76 tests OK. Not yet merged. `main` also still has the
iter-6 plan commit unpushed. Finishing the branch (merge / push+PR / keep) is an open decision.
