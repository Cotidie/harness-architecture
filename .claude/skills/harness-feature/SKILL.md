---
name: harness-feature
description: Drive one feature through the Living Architecture loop - conditional survey, architect patch, human approval, builder, validation gates, commit. Pauses for unforgeable human approval; runs the mechanical gates itself.
---

# harness-feature

Drive a single feature request through the Living Architecture loop. The request is the skill
argument: `/harness-feature "<request>"` (plus optional flags below).

You (the main agent) are the **orchestrator**. You dispatch the existing `architect`, `builder`,
and `inspector` subagents by name, run the deterministic checks and git yourself via Bash, and
**pause for the human** at the approval gate. You do not write feature code; the Builder does.

## Non-negotiable controls

- **Approval is the human's, never yours.** You MUST stop and yield the turn after the Architect
  writes the patch. You must NOT tick `- [ ] Approved`, must NOT dispatch the Builder, and must
  NOT continue in the same turn that produced the patch. Approval is the human's next message.
- **You own gate 1.** Run the tests, the linter self-check, and the scope diff yourself via Bash.
  Do not accept the Inspector's word that they passed. The Inspector is dispatched only for the
  judgment part (gate 2 + reconciliation + final label).
- **Grounded baseline.** The Architect grounds its declared seam signatures in CodeGraph
  (`current -> proposed` / `NEW` / `UNVERIFIED`). Gate 2 checks the implementation against those.
  If the patch's seam block contains an `UNVERIFIED` seam, surface it at the approval pause.
- **Fresh index before every query.** Before dispatching any agent that queries CodeGraph
  (Surveyor, Architect, Inspector), run the **freshness check**: `codegraph sync`, then
  `codegraph status --json` and require `pendingChanges.added`, `.modified`, `.removed` all 0 and
  `worktreeMismatch` null. If still stale after one re-sync, STOP with a freshness failure; never
  dispatch an agent against a stale index (the watcher lags writes ~1s).
- **Metered budget, not self-report.** A `PreToolUse` hook counts real `codegraph_explore` calls
  into `.architecture/.budget/query-count`. Reset it to 0 at loop start; read it before and after
  each agent dispatch; the delta is that agent's actual query count. Require delta <= 1 (the
  per-agent budget). Flag any overage in the summary; a gross breach (delta >= 3) is a hard STOP.
  Report the metered counts, not the agents' self-reported ones.
- Never use em-dash in anything you write.

## Flags (partial entry)

- `--patch-only` : run step 0-1, then stop after presenting the patch (no resume expected).
- `--from-patch <file>` : skip steps 0-1, resume at step 3 (Builder) for an already-approved patch.
- `--inspect-only` : skip to step 4, run gate 1 + the Inspector on the current working diff.
- `--resurvey` : force step 0 to re-survey.
- `--no-survey` : force step 0 to skip.
- `--drift-scan` : force step 0b (full-graph drift scan) to run.

## The loop

**At loop start (before step 0):** reset both run counters:
`mkdir -p .architecture/.budget && echo 0 > .architecture/.budget/query-count && echo 0 >
.architecture/.budget/revise-count`. Every agent dispatch below is metered against the first (see
controls); the second is the persisted revise-cycle count (step 7).

### Step 0 (conditional): re-survey

Decide by a logged rule, not intuition:

1. Read `state.yaml.last_reconciled_commit`.
2. `git rev-list --count <sha>..HEAD -- src/` = commits since last reconcile **that touched code**.
   Count code commits only: doc, agent-def, and skill commits do not change observed
   architecture, so counting all commits over-triggers a re-survey in a doc-heavy interim.
3. Re-survey (dispatch `surveyor`) only if: the code-commit count exceeds **8**, OR `--resurvey`
   was passed, OR the Architect (step 1) reports broad `UNCLEAR_DRIFT` beyond the feature's area.
4. `--no-survey` forces skip. Default is **skip** (re-surveying every feature blows the budget).
5. If it runs: announce it, record the reason in `state.yaml` (e.g. `re-surveyed: 12 commits
   since last`). A re-survey rewrites the intended docs, so treat it as a reviewable doc change,
   not a silent refresh.

### Step 0b (conditional): full-graph drift scan

Run this whenever step 0's cadence fires (code-commit count over threshold, `--resurvey`, or
`--drift-scan`). It is **feature-independent**: it checks the WHOLE repo, not the feature's area,
to surface drift that accumulates outside any single feature. ONE committed entrypoint, no ad-hoc
python:

```
python -m scripts.harness_check
```

`harness_check` reads the code root from `.architecture/profile.yaml` (`source_root`, so it is
not tied to `src/`) and runs the three deterministic checks against it, then prints ONE combined
report with one exit code:

1. **boundaries linter** (forbidden-edge self-check repo-wide);
2. **drift_scan** (undeclared modules AND undeclared cross-module edges vs `boundaries.yaml`);
3. **intended_diff** (missing classes, field mismatches, undeclared contracts, domain signature
   mismatches vs `contracts.yaml` / `domain-model.yaml`).

Exit code: `0` all clean, `1` any drift, `2` could-not-run (e.g. no profile / no `source_root` /
missing intended-layer YAML). None of the three needs a CodeGraph query, so this surface is
deterministic and **unmetered**. The structured intended layer it reads (`contracts.yaml`,
`domain-model.yaml`) is the definition layer; the prose `data-contracts.md` / `domain-model.md`
hold the intended rules only.

**Branch on the exit code (do not treat all non-zero the same):**

- `0` (clean): note it, continue.
- `1` (drift): **surface, do not auto-block.** Write the report (below) and flag the drift for the
  human/Architect; resolving drift is their decision, not the loop's. The feature loop continues.
- `2` (could-not-run): **STOP and flag a check failure.** The scan could not verify anything (no
  profile yet, missing `boundaries.yaml`/`contracts.yaml`/`domain-model.yaml`, or a bad
  `source_root`). Do NOT proceed as if the repo were clean: a silently skipped governance check is
  worse than a failing one. If the cause is "not yet surveyed" (no `profile.yaml`), route to the
  Surveyor (step 0) first; otherwise surface the setup error for a human to fix.

Note the precedence inside the combined exit code: error > drift > clean, so a `2` can hide a drift
the report still lists. Read the report, not just the exit code.

Write `harness_check`'s combined report to `.architecture/validation/drift-scan.md` (date, trigger,
plus the output) and surface it. Report only; resolving drift is a human/Architect decision, never
automatic.

### Step 1: Architect -> patch

Before dispatching, run the **freshness check** (see controls) and read the metered query-count.
Dispatch the `architect` subagent with the feature request and the `.architecture/` docs. The
intended contract/domain **definitions** are structured data in `contracts.yaml` /
`domain-model.yaml` (reconciliation reads them as data, e.g. via `scripts/intended_diff`); the
prose `data-contracts.md` / `domain-model.md` hold the intended **rules**. (The Architect's patch
sections 7-8 emitting structured diffs to these files is a deferred follow-up.) After it returns,
read the counter again: the delta is the Architect's metered query count (require <= 1). Capture:
the patch path, the reconciliation label, and the metered query count.

### Step 2: APPROVAL PAUSE (unforgeable)

Present to the human, then STOP and end the turn:

- patch path;
- reconciliation label (ALIGNED / DOC_DRIFT_ACCEPTED / CODE_DRIFT_HARMFUL / UNCLEAR_DRIFT);
- files allowed to edit;
- the `## Seam signatures (Inspector gate 2)` block, flagging any `UNVERIFIED` seam;
- an explicit request: approve, edit, or reject.

Hard rule (restated): do not tick the checkbox, do not run the Builder, do not continue this
turn. The resume entry point is step 3. `--from-patch <file>` jumps straight here for an
already-approved patch.

### Step 3 (resume on approval): Builder

On the human's approval, dispatch the `builder` subagent with the approved patch and the run
targets (tests + the `src/` self-check). Capture its summary (files changed, contract/domain
changes, tests, assumptions).

### Step 4: gate 1 (you run this, mechanically)

Run all three yourself via Bash:

1. `python -m unittest discover -s tests` -> must pass.
2. `python -m scripts.harness_check --only boundaries` -> must exit 0. This runs the boundary
   linter through the unified, profile-driven surface (it resolves the code root from
   `profile.yaml.source_root`, so it is not tied to `src/`). Gate 1 uses `--only boundaries`
   deliberately: it checks forbidden edges only, NOT the full repo-wide drift scan, because a
   legitimate new contract or signature is expected to differ from the docs until the patch's doc
   update lands (that intended-vs-observed reconciliation is the Inspector's job in step 5, not a
   gate-1 blocker). Exit 0 = clean; exit 1 = a forbidden edge; exit 2 = could-not-run.
3. Scope: `git diff --name-only` against the pre-Builder state is a subset of the patch's
   "Files allowed to edit".

If any fails, STOP. Emit the failing check as the verdict and do NOT dispatch the Inspector:

- tests fail -> `REJECT: TEST FAILURE`
- the boundary check exits 1 (forbidden edge) -> `REJECT: ARCHITECTURE VIOLATION`
- the boundary check exits 2 (could-not-run, e.g. no profile / missing boundaries.yaml) ->
  `STOP: CHECK COULD NOT RUN` (the gate could not verify; fix the harness setup, do not proceed)
- a changed file outside the allowed list -> `REJECT: out-of-scope edit`

### Step 5: Inspector for judgment (gate 2 + verdict)

If gate 1 passed, run the **freshness check** and read the metered query-count, then dispatch the
`inspector` subagent. The Inspector (iter-6 def) does gate 2 + the design check list + verdict
ONLY: it does not re-run gate 1 and does not bump state. Tell it gate 1 already passed (by you).
It emits the final label, writes the report, and a `## Next action` block the revise loop reads.
After it returns, read the counter: the delta is the Inspector's metered query count (require
<= 1).

### Step 6: on ACCEPT, auto-commit

If the verdict is `ACCEPT` or `ACCEPT WITH DOC UPDATE`:

1. Apply any approved doc update.
2. `git add` code + tests + `.architecture/` (patch, report, any docs) but NOT `state.yaml` yet.
3. Commit with a clear message. This is the **feature commit**.
4. `git rev-parse HEAD` -> the feature SHA.
5. Write that SHA into `state.yaml` (`last_validated_commit`, `last_reconciled_commit`,
   `last_validation_time`, the decision), then commit `state.yaml` as a **separate trailing
   commit** ("chore: sync harness state to <sha>"). Do NOT `--amend`: amending rewrites the
   commit SHA, so a commit can never contain its own final SHA. State trails by one commit and
   names the feature commit whose code it validated.
6. Report the feature SHA.

The Inspector (iter-6 def) does not touch `state.yaml`; the orchestrator owns the bump here.

### Step 7: on non-ACCEPT, the capped revise loop

On any non-ACCEPT verdict, read the Inspector report's `## Next action` block and route. A run
may execute **at most 2** revise cycles. Track the count in a run artifact, not working memory:
at the START of each cycle, increment `.architecture/.budget/revise-count`
(`n=$(cat .architecture/.budget/revise-count); echo $((n + 1)) > .architecture/.budget/revise-count`)
and read it back. This survives a mid-loop `/compact` or session drop, so the cap cannot be
silently exceeded after compaction. If the read value exceeds 2, the cap is reached (see below).

- `NEEDS PATCH REVISION`, or `REJECT: CONTRACT VIOLATION` / `REJECT: DOMAIN MODEL VIOLATION`
  (design-level): dispatch `architect` to revise the patch (re-scope / fix the declared seam),
  then RE-ENTER the approval pause (step 2: a real human turn; the orchestrator never re-approves
  a revised patch itself), then `builder` (step 3) -> orchestrator gate 1 (step 4) ->
  `inspector` (step 5).
- `REJECT: ARCHITECTURE VIOLATION` / `REJECT: TEST FAILURE` (code-level, patch unchanged):
  dispatch `builder` to fix within the SAME approved patch -> orchestrator gate 1 -> `inspector`.
  No re-approval (the approved patch did not change).

If a cycle reaches ACCEPT, go to step 6. If `.architecture/.budget/revise-count` exceeds 2, STOP
and surface the latest report with "revise cap reached, human intervention required". The cap
prevents ping-pong and dead-ends; the unforgeable-approval rule still holds on every patch
revision. Because the count is read from the artifact (not memory), a `/compact` between cycles
cannot reset it.

## Enforced as of iteration 6

All the iter-5 honor-system gaps now have teeth:

- **Unforgeable approval** (iter 5): every patch revision re-enters the human approval pause.
- **Orchestrator-run gate 1** (iter 5): the orchestrator runs tests + self-check + scope itself.
- **Grounded signatures** (iter 5): the Architect grounds seam signatures in CodeGraph.
- **Freshness verification** (iter 6): `codegraph status --json` must be clean before any query.
- **Metered budget** (iter 6): a PreToolUse hook counts real `codegraph_explore` calls; the
  orchestrator enforces the per-agent budget from the metered delta, not self-report.
- **Capped revise loop** (iter 6): non-ACCEPT routes back through Architect/Builder, max 2 cycles.
- **Full-graph drift scan** (iter 6): a feature-independent repo-wide drift check on the cadence.

Inspector (iter-6 def) does gate 2 + verdict + `## Next action` only; the orchestrator owns
gate 1 and `state.yaml`.
