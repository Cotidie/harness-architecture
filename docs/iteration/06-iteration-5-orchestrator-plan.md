# Iteration 5 (Orchestrator skill) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (or subagent-driven-development). Steps use checkbox (`- [ ]`) syntax.

**Goal:** Give the harness a single user-facing trigger, `/harness-feature "<request>"`, that drives the whole loop (conditional survey -> architect -> human approval -> builder -> validate -> commit) with the controls having teeth: the human approval is unforgeable, and the orchestrator runs the deterministic gates itself.

**Architecture:** The orchestrator is a Claude Code **skill** (`.claude/skills/harness-feature/SKILL.md`): instructions the main agent follows. It dispatches the existing `architect` / `builder` / `inspector` subagents by name, runs the mechanical checks and git itself via Bash, and pauses for the human at the approval gate by ending its turn. No new agent is added.

**Tech stack:** Markdown skill def; the existing Python linter + stdlib `unittest`; `codegraph` CLI; `git`; Claude Code subagents.

## Locked decisions (from planning forks, 2026-06-25)

- **Approval is unforgeable via skill-pause.** After the Architect writes the patch, the skill STOPS and yields control to the human; it cannot proceed without a real user turn. The model cannot fabricate a human message, so an agent can never self-approve. The skill must not tick the patch checkbox itself; the human's reply is the approval. (Closes iter-4 finding #1.)
- **MVP scope: chain + approval + orchestrator-runs-the-gates.** Build the loop, the unforgeable approval pause, and the orchestrator executing the mechanical gate-1 itself (not trusting the Inspector's self-report, iter-4 finding #2). Explicitly **deferred to iter 5b / 6** (marked below, not built here): CodeGraph freshness-verification gate, grounded-Architect-signatures, budget metering, and the REJECT -> auto-revise loop with a max-iteration cap.
- **Auto-commit on ACCEPT.** The patch was already human-approved and the Inspector accepted, so the orchestrator commits code + artifacts together and reports the SHA. Non-ACCEPT verdicts STOP and surface the report (no auto-revise this slice).

## Global Constraints

- The orchestrator (main agent following the skill) NEVER approves a patch on the human's behalf and NEVER continues past the approval gate within the same turn that produced the patch.
- Gate 1 (tests + linter self-check + diff-in-allowed-files) is run by the orchestrator via Bash and is the gate of record. The Inspector is dispatched only for the judgment part (gate 2 + reconciliation + final label).
- One `codegraph_explore` query per agent (unchanged budget). The orchestrator runs `codegraph sync` before dispatching agents (plain sync; rigorous freshness verification is deferred).
- On non-ACCEPT, STOP and report; do not auto-loop (the capped revise loop is deferred).
- Never use em-dash in authored content.

## File structure

- Create `.claude/skills/harness-feature/SKILL.md` : the orchestrator skill (the whole deliverable).
- No change to `.claude/agents/*` this slice (Inspector keeps its own gate-1; the orchestrator's gate-1 is authoritative; trimming the Inspector's redundant gate-1 is a marked follow-up).
- Dogfood will touch `src/adapters/boundaries/{violation_reporter,cli}.py` + tests via the loop (Task 3), within whatever the Architect's patch allows.
- Save `docs/iteration/06-iteration-5-orchestrator-plan.md` (this file) and an iteration results note (Task 4).

---

### Task 1: Scaffold the skill and its flow skeleton

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

### Task 2: Detail each step in SKILL.md

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
- [ ] **Step 9: Deferred-features note.** Add a short "Deferred to iter 5b/6" list in the skill: freshness-verification gate, grounded Architect signatures, budget metering, capped auto-revise loop. So the skill is honest about what it does not yet enforce.
- [ ] **Step 10: Commit the skill.** `git add .claude/skills/harness-feature/SKILL.md && git commit -m "feat: add harness-feature orchestrator skill (iteration 5)"`

### Task 3: Dogfood the full loop on a tiny real feature

**Reload caveat:** a new skill is not invocable as `/harness-feature` until `/reload-plugins`. Until then, follow the SKILL.md steps inline. The `architect`/`builder`/`inspector` agents already register by name.

**Feature:** add a `--format json` option to the linter CLI that prints violations as a JSON array (seam: a new public `format_report_json(violations) -> str` in the reporter; a `--format {text,json}` flag in the CLI). Small, real, end-to-end testable, and it exercises gate 2 (a new declared seam signature).

- [ ] **Step 1: Run the loop** with the request "add a `--format json` output option to the boundaries linter CLI". Drive step 0 (expect SKIP, only ~1 commit since last reconcile) and step 1 (Architect patch).
- [ ] **Step 2: Verify the approval pause.** Confirm the orchestrator STOPPED after the patch and did NOT run the Builder or tick the checkbox. This is the core governance check: the loop cannot proceed without this human turn.
- [ ] **Step 3: Approve**, then resume: Builder implements; the orchestrator runs gate 1 itself (capture the actual test + self-check + scope output); Inspector returns gate-2 + verdict.
- [ ] **Step 4: Verify ACCEPT auto-commit.** Confirm a single commit landed with code + tests + patch + report + bumped `state.yaml`, and the reported SHA matches `git rev-parse HEAD`. Run `python -m unittest discover -s tests` (pass) and `python -m src.adapters.boundaries.cli sample sample/boundaries.yaml --format json` (valid JSON, exit 1 with the planted violation).
- [ ] **Step 5: Probe a non-ACCEPT path (scratch).** Introduce a scratch forbidden edge, run `--inspect-only`, confirm the orchestrator's own gate 1 STOPS the loop with a REJECT and does not commit; revert the scratch edit.

### Task 4: Record the iteration and finish the branch

- [ ] **Step 1: CodeGraph sync.** `codegraph sync`.
- [ ] **Step 2:** Append a short results section to this file (what the loop did, whether the pause held, gate-1-by-orchestrator behavior, the dogfood SHA).
- [ ] **Step 3: Commit** the doc: `git add docs/iteration && git commit -m "docs: iteration 5 orchestrator results"`.
- [ ] **Step 4:** Use superpowers:finishing-a-development-branch (verify tests, then merge / PR / keep per the user's choice).

---

## Verification (end-to-end)

1. `.claude/skills/harness-feature/SKILL.md` exists with all six steps, the partial-entry args, and the deferred-features note.
2. Running the loop pauses after the Architect's patch and provably does not proceed without a human turn (no Builder dispatch, no ticked checkbox in that turn).
3. After approval, the orchestrator runs gate 1 itself (its own test + self-check + scope output is shown), then the Inspector returns gate 2 + verdict.
4. On ACCEPT, one commit lands with code + artifacts + bumped `state.yaml`; the reported SHA matches HEAD; tests pass.
5. A forced gate-1 failure stops the loop with no commit.

## Feedback to collect (feeds iter 5b / 6 / 7)

- Did the approval pause feel unforgeable and natural, or clunky (too many turns)?
- Was orchestrator-run gate 1 clearly more trustworthy than the Inspector's self-report, and is the Inspector's duplicate gate-1 worth trimming now?
- How often did step-0 want to re-survey, and was the threshold (8) right?
- Did auto-commit-on-ACCEPT feel safe, or is a pre-commit human glance wanted after all?
- Which deferred control (freshness, grounded sigs, budget meter, capped revise) is most missed in practice? That orders iter 5b/6.

## Deferred to iter 5b / 6 (explicitly NOT built here)

- CodeGraph freshness-verification gate before each query (plain `codegraph sync` only, this slice).
- Grounded Architect signatures (Architect diffs declared seams against CodeGraph).
- Budget metering by actual tool calls (still self-reported this slice).
- REJECT -> auto-revise loop with a max-iteration cap (this slice stops and asks the human).
- Trimming the Inspector's redundant gate-1 now that the orchestrator owns it.
