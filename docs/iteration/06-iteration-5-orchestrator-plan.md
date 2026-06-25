# Iteration 5 (Orchestrator skill) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (or subagent-driven-development). Steps use checkbox (`- [ ]`) syntax.

**Goal:** Give the harness a single user-facing trigger, `/harness-feature "<request>"`, that drives the whole loop (conditional survey -> architect -> human approval -> builder -> validate -> commit) with the controls having teeth: the human approval is unforgeable, the orchestrator runs the deterministic gates itself, and the patch's declared seam signatures are grounded in CodeGraph (not invented), so gate 2 has a trustworthy baseline.

**Architecture:** The orchestrator is a Claude Code **skill** (`.claude/skills/harness-feature/SKILL.md`): instructions the main agent follows. It dispatches the existing `architect` / `builder` / `inspector` subagents by name, runs the mechanical checks and git itself via Bash, and pauses for the human at the approval gate by ending its turn. No new agent is added.

**Tech stack:** Markdown skill def; the existing Python linter + stdlib `unittest`; `codegraph` CLI; `git`; Claude Code subagents.

## Locked decisions (from planning forks, 2026-06-25)

- **Approval is unforgeable via skill-pause.** After the Architect writes the patch, the skill STOPS and yields control to the human; it cannot proceed without a real user turn. The model cannot fabricate a human message, so an agent can never self-approve. The skill must not tick the patch checkbox itself; the human's reply is the approval. (Closes iter-4 finding #1.)
- **MVP + grounded signatures scope.** Build: the loop, the unforgeable approval pause, the orchestrator executing the mechanical gate-1 itself (not trusting the Inspector's self-report, iter-4 finding #2), and **grounded Architect signatures** (the Architect derives each declared seam signature from its CodeGraph query and shows current -> proposed, so gate 2's baseline is real, not invented). Grounded signatures are pulled into this slice because an invented declared signature becomes a wrong gate-2 baseline and yields a false ACCEPT, which is a correctness hole, not polish. Explicitly **deferred to iter 5b / 6** (marked below, not built here): CodeGraph freshness *verification* gate (plain sync only this slice), budget metering, and the REJECT -> auto-revise loop with a max-iteration cap.
- **Auto-commit on ACCEPT.** The patch was already human-approved and the Inspector accepted, so the orchestrator commits code + artifacts together and reports the SHA. Non-ACCEPT verdicts STOP and surface the report (no auto-revise this slice).

## Global Constraints

- The orchestrator (main agent following the skill) NEVER approves a patch on the human's behalf and NEVER continues past the approval gate within the same turn that produced the patch.
- Gate 1 (tests + linter self-check + diff-in-allowed-files) is run by the orchestrator via Bash and is the gate of record. The Inspector is dispatched only for the judgment part (gate 2 + reconciliation + final label).
- One `codegraph_explore` query per agent (unchanged budget). The orchestrator runs `codegraph sync` before dispatching agents (plain sync; rigorous freshness verification is deferred).
- The Architect must ground every declared seam signature in its CodeGraph query: for an existing symbol, show the current signature from CodeGraph and the proposed one (current -> proposed); for a genuinely new symbol, mark it NEW. It must not declare a signature for an existing seam without reading the current one. This grounds gate 2's baseline.
- On non-ACCEPT, STOP and report; do not auto-loop (the capped revise loop is deferred).
- Never use em-dash in authored content.

## File structure

- Modify `.claude/agents/architect.md` : ground the seam-signature block in CodeGraph (Task 1).
- Create `.claude/skills/harness-feature/SKILL.md` : the orchestrator skill (the main deliverable).
- No change to `.claude/agents/*` this slice (Inspector keeps its own gate-1; the orchestrator's gate-1 is authoritative; trimming the Inspector's redundant gate-1 is a marked follow-up).
- Dogfood will touch `src/adapters/boundaries/{violation_reporter,cli}.py` + tests via the loop (Task 4), within whatever the Architect's patch allows.
- Save `docs/iteration/06-iteration-5-orchestrator-plan.md` (this file) and an iteration results note (Task 5).

---

### Task 1: Ground the Architect's seam signatures in CodeGraph

**Files:** Modify `.claude/agents/architect.md`

The Architect already emits a `## Seam signatures (Inspector gate 2)` block, but nothing forces those signatures to match the code that exists today, so a wrong declaration silently becomes a wrong gate-2 baseline (false ACCEPT). This task grounds them.

- [ ] **Step 1: Require grounding in the signature instructions.** In the sections-7/8 signature guidance and the `## Seam signatures` block instructions, add: every seam signature for an **existing** symbol must be derived from the one `codegraph_explore` query's verbatim source and written as `current -> proposed` (or `unchanged` when the feature does not change it). A symbol absent from the CodeGraph result is marked `NEW`. The Architect must not declare a signature for an existing seam it did not read.
- [ ] **Step 2: Forbid invented baselines explicitly.** Add a hard-rule line: "Do not invent or guess the current signature of an existing symbol; if the one query did not surface it, say so and mark the seam UNVERIFIED rather than fabricating it." This keeps the budget at one query while making a missing baseline visible instead of silently wrong.
- [ ] **Step 3: Verify the def reads correctly** (no em-dash, the `current -> proposed` / `NEW` / `UNVERIFIED` vocabulary is stated once and used consistently).
- [ ] **Step 4: Commit.** `git add .claude/agents/architect.md && git commit -m "feat: architect grounds declared seam signatures in codegraph (iter-5 gate-2 baseline)"`

### Task 2: Scaffold the skill and its flow skeleton

**Files:** Create `.claude/skills/harness-feature/SKILL.md`

- [ ] **Step 1: Frontmatter.**

```markdown
---
name: harness-feature
description: Drive one feature through the Living Architecture loop - conditional survey, architect patch, human approval, builder, validation gates, commit. Pauses for unforgeable human approval; runs the mechanical gates itself.
---
```

- [ ] **Step 2: Write the high-level flow** (the orchestrator reads the request from the skill args), as an ordered list the agent follows:
  - step 0 (conditional): re-survey if stale, else skip;
  - step 1: dispatch `architect` -> patch;
  - step 2: APPROVAL PAUSE (stop, yield to human);
  - step 3 (resume on approval): dispatch `builder`;
  - step 4: orchestrator runs gate 1 (mechanical);
  - step 5: dispatch `inspector` for gate 2 + verdict;
  - step 6: on ACCEPT, update state/docs and auto-commit; else stop and report.
- [ ] **Step 3: Verify** `ls .claude/skills/harness-feature/SKILL.md`.

### Task 3: Detail each step in SKILL.md

**Files:** `.claude/skills/harness-feature/SKILL.md`

- [ ] **Step 1: Step 0, conditional Surveyor.** Instruct: read `state.yaml.last_reconciled_commit`; compute `git rev-list --count <sha>..HEAD`. Re-survey (dispatch `surveyor`) only if the count exceeds a threshold (8), or `--resurvey` is passed, or the Architect later signals broad UNCLEAR_DRIFT; `--no-survey` forces skip; default skip. When it runs, announce it and record the reason in `state.yaml`. A re-survey is a reviewable doc change, not silent.
- [ ] **Step 2: Step 1, Architect.** Dispatch `architect` with the feature request + the `.architecture/` docs. Capture the patch path, query count, reconciliation label.
- [ ] **Step 3: Step 2, the unforgeable approval pause.** Instruct the orchestrator to present the patch path + reconciliation label + files-allowed + seam signatures to the human, then STOP and end the turn with an explicit request to approve, edit, or reject. State the hard rule: the orchestrator must not tick `- [ ] Approved`, must not run the Builder, and must not continue in the same turn. Approval is the human's next message. (Resume entry point = step 3; `--from-patch <file>` jumps straight here for an already-approved patch.)
- [ ] **Step 4: Step 3, Builder.** On the human's approval, dispatch `builder` with the approved patch + run targets. Capture its summary.
- [ ] **Step 5: Step 4, orchestrator runs gate 1 (mechanical, the agent runs these itself, does not delegate):**
  - `python -m unittest discover -s tests` (must pass);
  - `python -m src.adapters.boundaries.cli src .architecture/boundaries.yaml` (must exit 0);
  - scope: `git diff --name-only` is a subset of the patch's "Files allowed to edit".
  If any fails, STOP with the failing check (REJECT: ARCHITECTURE VIOLATION / TEST FAILURE / out-of-scope) and do not dispatch the Inspector.
- [ ] **Step 6: Step 5, Inspector for judgment.** If gate 1 passed, dispatch `inspector` told that gate 1 already passed, to perform gate 2 (seam-signature conformance) + the reconciliation check and emit the final label + report. (Note for a follow-up: trim the Inspector's now-redundant self-run of gate 1; out of scope here.)
- [ ] **Step 7: Step 6, on ACCEPT auto-commit.** If the verdict is ACCEPT / ACCEPT WITH DOC UPDATE: apply any approved doc update, then `git add` code + tests + `.architecture/` (patch, report, docs), commit with a clear message, capture `git rev-parse HEAD`, write that SHA into `state.yaml` (`last_validated_commit`, `last_reconciled_commit`, time, decision), and `git commit --amend --no-edit` so state ships in the same commit. Report the SHA. On any non-ACCEPT verdict: STOP, surface the report, await the human (no auto-revise this slice).
- [ ] **Step 8: Partial-entry args.** Document `--patch-only` (stop after step 1), `--from-patch <file>` (resume at step 3), `--inspect-only` (run gate 1 + Inspector on the current diff), `--resurvey` / `--no-survey`.
- [ ] **Step 9: Deferred-features note.** Add a short "Deferred to iter 5b/6" list in the skill: freshness-*verification* gate (plain sync only), budget metering, capped auto-revise loop. So the skill is honest about what it does not yet enforce. (Grounded Architect signatures are IN this slice via Task 1; do not list them as deferred.)
- [ ] **Step 10: Commit the skill.** `git add .claude/skills/harness-feature/SKILL.md && git commit -m "feat: add harness-feature orchestrator skill (iteration 5)"`

### Task 4: Dogfood the full loop on a tiny real feature

**Reload caveat:** a new skill is not invocable as `/harness-feature` until `/reload-plugins`. Until then, follow the SKILL.md steps inline. The `architect`/`builder`/`inspector` agents already register by name.

**Feature:** add a `--format json` option to the linter CLI that prints violations as a JSON array (seam: a new public `format_report_json(violations) -> str` in the reporter; a `--format {text,json}` flag in the CLI). Small, real, end-to-end testable, and it exercises gate 2 (a new declared seam signature).

- [ ] **Step 1: Run the loop** with the request "add a `--format json` output option to the boundaries linter CLI". Drive step 0 (expect SKIP, only ~1 commit since last reconcile) and step 1 (Architect patch).
- [ ] **Step 2: Verify grounded signatures.** In the patch's `## Seam signatures` block, confirm the touched existing reporter/CLI seams are written as `current -> proposed` (or `unchanged`), the new `format_report_json` seam is marked `NEW`, and nothing is fabricated/UNVERIFIED. This proves Task 1 took effect and gate 2 has a real baseline.
- [ ] **Step 3: Verify the approval pause.** Confirm the orchestrator STOPPED after the patch and did NOT run the Builder or tick the checkbox. This is the core governance check: the loop cannot proceed without this human turn.
- [ ] **Step 4: Approve**, then resume: Builder implements; the orchestrator runs gate 1 itself (capture the actual test + self-check + scope output); Inspector returns gate-2 + verdict (gate 2 now checks the implementation against the grounded `proposed` signatures).
- [ ] **Step 5: Verify ACCEPT auto-commit.** Confirm a single commit landed with code + tests + patch + report + bumped `state.yaml`, and the reported SHA matches `git rev-parse HEAD`. Run `python -m unittest discover -s tests` (pass) and `python -m src.adapters.boundaries.cli sample sample/boundaries.yaml --format json` (valid JSON, exit 1 with the planted violation).
- [ ] **Step 6: Probe a non-ACCEPT path (scratch).** Introduce a scratch forbidden edge, run `--inspect-only`, confirm the orchestrator's own gate 1 STOPS the loop with a REJECT and does not commit; revert the scratch edit.

### Task 5: Record the iteration and finish the branch

- [ ] **Step 1: CodeGraph sync.** `codegraph sync`.
- [ ] **Step 2:** Append a short results section to this file (what the loop did, whether the pause held, gate-1-by-orchestrator behavior, the dogfood SHA).
- [ ] **Step 3: Commit** the doc: `git add docs/iteration && git commit -m "docs: iteration 5 orchestrator results"`.
- [ ] **Step 4:** Use superpowers:finishing-a-development-branch (verify tests, then merge / PR / keep per the user's choice).

---

## Verification (end-to-end)

1. `architect.md` requires grounded seam signatures; the dogfood patch shows touched existing seams as `current -> proposed` (or `unchanged`) and the new seam as `NEW`, none fabricated.
2. `.claude/skills/harness-feature/SKILL.md` exists with all six steps, the partial-entry args, and the deferred-features note (which does NOT list grounded signatures).
3. Running the loop pauses after the Architect's patch and provably does not proceed without a human turn (no Builder dispatch, no ticked checkbox in that turn).
4. After approval, the orchestrator runs gate 1 itself (its own test + self-check + scope output is shown), then the Inspector returns gate 2 + verdict against the grounded baseline.
5. On ACCEPT, one commit lands with code + artifacts + bumped `state.yaml`; the reported SHA matches HEAD; tests pass.
6. A forced gate-1 failure stops the loop with no commit.

## Feedback to collect (feeds iter 5b / 6 / 7)

- Did the approval pause feel unforgeable and natural, or clunky (too many turns)?
- Was orchestrator-run gate 1 clearly more trustworthy than the Inspector's self-report, and is the Inspector's duplicate gate-1 worth trimming now?
- How often did step-0 want to re-survey, and was the threshold (8) right?
- Did auto-commit-on-ACCEPT feel safe, or is a pre-commit human glance wanted after all?
- Did grounding the Architect's signatures actually prevent a bad gate-2 baseline, or was it never at risk on small features (signal on whether it earned its place this slice)?
- Which remaining deferred control (freshness verification, budget meter, capped revise) is most missed in practice? That orders iter 5b/6.

## Deferred to iter 5b / 6 (explicitly NOT built here)

- CodeGraph freshness-*verification* gate before each query (plain `codegraph sync` only, this slice; verifying the index actually reflects HEAD is deferred).
- Budget metering by actual tool calls (still self-reported this slice).
- REJECT -> auto-revise loop with a max-iteration cap (this slice stops and asks the human).
- Trimming the Inspector's redundant gate-1 now that the orchestrator owns it.
