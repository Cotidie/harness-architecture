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
- Never use em-dash in anything you write.

## Flags (partial entry)

- `--patch-only` : run step 0-1, then stop after presenting the patch (no resume expected).
- `--from-patch <file>` : skip steps 0-1, resume at step 3 (Builder) for an already-approved patch.
- `--inspect-only` : skip to step 4, run gate 1 + the Inspector on the current working diff.
- `--resurvey` : force step 0 to re-survey.
- `--no-survey` : force step 0 to skip.

## The loop

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

### Step 1: Architect -> patch

Dispatch the `architect` subagent with the feature request and the `.architecture/` docs. Before
dispatching, run `codegraph sync` (plain sync; rigorous freshness verification is deferred, see
below). Capture: the patch path, the reconciliation label, and the query count.

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
2. `python -m src.adapters.boundaries.cli src .architecture/boundaries.yaml` -> must exit 0.
3. Scope: `git diff --name-only` against the pre-Builder state is a subset of the patch's
   "Files allowed to edit".

If any fails, STOP. Emit the failing check as the verdict and do NOT dispatch the Inspector:

- tests fail -> `REJECT: TEST FAILURE`
- self-check exits non-zero -> `REJECT: ARCHITECTURE VIOLATION`
- a changed file outside the allowed list -> `REJECT: out-of-scope edit`

### Step 5: Inspector for judgment (gate 2 + verdict)

If gate 1 passed, dispatch the `inspector` subagent. Tell it gate 1 already passed (by you), so
it performs gate 2 (seam-signature conformance against the patch's grounded `proposed`
signatures) and the reconciliation check, and emits the final label + writes the report.

(Follow-up, out of scope here: trim the Inspector's now-redundant self-run of gate 1 now that the
orchestrator owns it.)

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

Note: the Inspector (iter-4 def) may also bump `state.yaml` on ACCEPT, to the pre-feature HEAD.
Under this orchestrator the orchestrator owns state, so overwrite the Inspector's bump with the
feature SHA in step 5. (Follow-up for iter 5b: stop the Inspector self-bumping under orchestration.)

On any non-ACCEPT verdict (`NEEDS PATCH REVISION` / any `REJECT`): STOP, surface the report, and
await the human. Do NOT auto-loop (the capped revise loop is deferred, see below).

## Deferred to iter 5b / 6 (this skill does NOT yet enforce)

- CodeGraph freshness *verification* gate: this slice runs plain `codegraph sync` only; verifying
  the index actually reflects HEAD before each query is deferred.
- Budget metering by actual tool calls (query counts are still self-reported by each agent).
- The `REJECT -> Architect re-scope -> re-approve -> Builder -> Inspector` auto-revise loop with a
  max-iteration cap. This slice stops and asks the human instead.

(Grounded Architect signatures are IN this slice, enforced by `architect.md`, not deferred.)
