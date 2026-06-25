# Iteration 6 (Governance + budget hardening) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (or subagent-driven-development). Steps use checkbox (`- [ ]`) syntax.

**Goal:** Close the loop's remaining honor-system gaps and make it provably cheap. Iteration 5 shipped the loop with unforgeable approval, orchestrator-run gate 1, and grounded signatures; this iteration adds the controls 5 deferred (freshness verification, a capped REJECT -> revise loop, Inspector cleanup) plus cost enforcement (budget metering by actual tool calls, a periodic full-graph drift scan).

**Architecture:** Mostly orchestrator-skill and agent-def edits (`.claude/skills/harness-feature/SKILL.md`, `.claude/agents/inspector.md`), plus one new mechanical piece: a Claude Code `PreToolUse` hook that counts real `codegraph_explore` invocations into a per-run counter the orchestrator checks. No change to the linter's domain/contracts/application layers.

**Tech stack:** Markdown skill + agent defs; `.claude/settings.json` + a small POSIX `sh` hook script; `codegraph` CLI (`status --json`, `sync`); `git`; the existing Python linter + stdlib `unittest`.

## Locked decisions (from planning forks, 2026-06-25)

- **One slice (not split 6a/6b).** All five components ship in iteration 6; no renumbering of 7-10.
- **Freshness verification = `codegraph status --json`.** After `codegraph sync`, parse the JSON and require `pendingChanges.added/modified/removed == 0` AND `worktreeMismatch == null` before any agent query. This replaces iter-5's plain-sync-only step. (Mechanism confirmed: `status --json` already reports both fields.)
- **Budget metering = hook-based real enforcement.** A `PreToolUse` hook matching `mcp__codegraph__codegraph_explore` increments a per-run counter file. The orchestrator resets it at loop start and reads the delta around each agent dispatch, flagging/failing when an agent exceeds its 1-query budget. This is "actual tool calls, not self-report" per the roadmap.
- **Inspector cleanup is the clean fix for iter-5 finding 2.** Under the orchestrator, the Inspector does gate 2 + the design check list + verdict + report ONLY. It no longer runs gate 1 (mechanical) and no longer bumps `state.yaml`; the orchestrator owns both.

## Global Constraints

- Do not change the linter's behavior or its domain/contracts/application/adapters code in this iteration. This is loop-control + cost work, not a feature.
- The unforgeable-approval control from iter 5 is preserved: every re-approve in the capped revise loop is still a real human turn. The cap bounds the NUMBER of cycles, not the human's role.
- The orchestrator owns gate 1 (mechanical) and `state.yaml`. The Inspector owns gate 2 + judgment. No double-ownership.
- One `codegraph_explore` query per agent stays the budget; this iteration measures and enforces it rather than loosening it.
- Never use em-dash in authored content.

## File structure

- Create `.claude/hooks/count-codegraph-query.sh` : the PreToolUse counter hook (Task 4).
- Create `.claude/settings.json` : registers the PreToolUse hook (Task 4).
- Modify `.claude/agents/inspector.md` : drop gate 1 + state bump under orchestration (Task 1).
- Modify `.claude/skills/harness-feature/SKILL.md` : freshness verification (Task 2), capped revise loop (Task 3), budget-meter checks (Task 4), drift-scan step (Task 5).
- New `.architecture/.budget/` (runtime counter dir; gitignored) - created by the hook/orchestrator at run time, not committed.
- Save `docs/iteration/07-iteration-6-governance-budget-plan.md` (this file) + a results note (Task 7).

---

### Task 1: Trim the Inspector to gate 2 + judgment only

**Files:** Modify `.claude/agents/inspector.md`

The Inspector (iter-4 def) still runs gate 1 (tests/self-check/scope) and bumps `state.yaml`. Under the iter-5 orchestrator both are owned by the orchestrator, so the Inspector duplicates gate 1 and writes state to the wrong (pre-feature) commit. This task removes both from the Inspector.

- [ ] **Step 1: Remove the gate-1 section.** Delete the `## Gate 1 - boundary edges + tests (mechanical, via Bash)` section. Replace its role with a one-line input note: "Gate 1 (tests, linter self-check, scope) has already been run by the orchestrator and passed; you are dispatched only when it did. Do not re-run it."
- [ ] **Step 2: Remove the state-update section.** Delete `## State update (ACCEPT or ACCEPT WITH DOC UPDATE only)`. Replace with: "Do NOT touch `state.yaml`. The orchestrator owns state and bumps it on ACCEPT."
- [ ] **Step 3: Keep gate 2, the full check list, the decision labels, the report.** The Inspector still makes exactly 1 CodeGraph query (gate 2), applies the design check list (the non-mechanical, judgment parts), emits one label, and writes `.architecture/validation/latest-report.md`. The `Bash` tool stays (it may still read git state) but the report must note gate 1 as "run upstream by orchestrator: PASS" rather than claiming to have run it.
- [ ] **Step 4: Add the machine-actionable next-action field** (shared with Task 3). In the report spec, require a final `## Next action` block: for `NEEDS PATCH REVISION` -> `re-invoke: architect` with what to change; for any `REJECT` -> `re-invoke: builder` (code fix) or `re-invoke: architect` (scope/contract fix) with the reason; for `ACCEPT*` -> `none`. This is what the orchestrator's capped loop reads.
- [ ] **Step 5: Verify** no em-dash; the def no longer mentions running tests/self-check or bumping state. `grep -n "state.yaml\|unittest\|self-check" .claude/agents/inspector.md` shows only the "owned by orchestrator / run upstream" notes.
- [ ] **Step 6: Commit.** `git add .claude/agents/inspector.md && git commit -m "refactor: inspector does gate 2 + verdict only; orchestrator owns gate 1 and state (iter-6)"`

### Task 2: Freshness verification before every agent query

**Files:** Modify `.claude/skills/harness-feature/SKILL.md`

- [ ] **Step 1: Add a freshness helper rule** near the top of the skill, referenced by every dispatch: "Before dispatching any agent that will query CodeGraph (Surveyor, Architect, Inspector), run `codegraph sync`, then `codegraph status --json` and confirm `pendingChanges.added`, `.modified`, `.removed` are all 0 and `worktreeMismatch` is null. If not, re-run `sync` once; if still stale, STOP and report a freshness failure (do not dispatch against a stale index)."
- [ ] **Step 2: Replace the plain-sync lines.** In step 1 (Architect) and step 5 (Inspector), replace "run `codegraph sync`" with "run the freshness check (see above)". Update the deferred-features note: remove "freshness verification" from the deferred list (it is now built); keep budget metering removed too once Task 4 lands.
- [ ] **Step 3: Verify** the skill no longer calls freshness "deferred" and the check is stated once and referenced, not duplicated.
- [ ] **Step 4: Commit.** `git add .claude/skills/harness-feature/SKILL.md && git commit -m "feat: orchestrator verifies codegraph freshness (status --json) before each query (iter-6)"`

### Task 3: Capped REJECT -> revise loop

**Files:** Modify `.claude/skills/harness-feature/SKILL.md`

Iter 5 stops and asks the human on any non-ACCEPT. This task adds a bounded automatic revise cycle that still pauses for human re-approval each round.

- [ ] **Step 1: Define the cycle** in step 6 of the skill. On a non-ACCEPT verdict, read the Inspector report's `## Next action` block and route:
  - `NEEDS PATCH REVISION` -> dispatch `architect` to revise the patch (re-scope / fix the declared seam) -> APPROVAL PAUSE (human re-approves) -> `builder` -> orchestrator gate 1 -> `inspector`.
  - `REJECT: TEST FAILURE` / `REJECT: ARCHITECTURE VIOLATION` (code-level) -> dispatch `builder` to fix within the SAME approved patch -> orchestrator gate 1 -> `inspector` (no re-approval needed; patch unchanged).
  - `REJECT: CONTRACT/DOMAIN VIOLATION` (design-level) -> treat like NEEDS PATCH REVISION (back to `architect` + re-approval).
- [ ] **Step 2: Add the max-iteration cap.** A run may execute at most **2** revise cycles. Track the count in the run. On exceeding it, STOP and surface the latest report with "revise cap reached, human intervention required". This prevents ping-pong and dead-ends.
- [ ] **Step 3: Preserve unforgeable approval.** State explicitly: any cycle that revises the PATCH re-enters the approval pause (a real human turn); only same-patch code fixes skip re-approval. The orchestrator never self-approves a revised patch.
- [ ] **Step 4: Update the deferred-features note** to remove "capped REJECT -> revise loop" (now built).
- [ ] **Step 5: Verify** the routing table covers all non-ACCEPT labels and the cap is stated once with a concrete number.
- [ ] **Step 6: Commit.** `git add .claude/skills/harness-feature/SKILL.md && git commit -m "feat: capped REJECT->revise loop in orchestrator (max 2 cycles, re-approval preserved) (iter-6)"`

### Task 4: Budget metering via a PreToolUse hook

**Files:** Create `.claude/hooks/count-codegraph-query.sh`, `.claude/settings.json`; modify `.claude/skills/harness-feature/SKILL.md`, `.gitignore`

**CRITICAL PREREQUISITE - validate the mechanism first (Step 1). The whole approach assumes a PreToolUse hook fires for a SUBAGENT's tool calls, not just the main session's. If it does not, switch to the fallback in Step 7 before building the rest.**

- [ ] **Step 1: Prove the hook fires for a subagent.** Write a throwaway hook that appends a line to `/tmp/cg-hook-probe.log` on `mcp__codegraph__codegraph_explore`, register it in `.claude/settings.json`, reload, then dispatch ANY agent that makes one CodeGraph query (e.g. a trivial `architect` run). Confirm the probe log gained a line. If yes -> proceed. If no (hooks fire only for the main session) -> go to Step 7 fallback and record the finding.
- [ ] **Step 2: Write the counter hook** `.claude/hooks/count-codegraph-query.sh`:

```sh
#!/bin/sh
# PreToolUse hook: count codegraph_explore invocations into a per-run counter.
# Reads the tool event JSON on stdin; increments the counter only for the explore tool.
COUNTER_DIR="${CLAUDE_PROJECT_DIR:-.}/.architecture/.budget"
COUNTER="$COUNTER_DIR/query-count"
# tool_name arrives in the stdin JSON; match the codegraph explore tool only.
event="$(cat)"
case "$event" in
  *mcp__codegraph__codegraph_explore*)
    mkdir -p "$COUNTER_DIR"
    n=$(cat "$COUNTER" 2>/dev/null || echo 0)
    echo $((n + 1)) > "$COUNTER"
    ;;
esac
exit 0   # never block; metering only
```

- [ ] **Step 3: Register the hook** in `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "mcp__codegraph__codegraph_explore",
        "hooks": [
          { "type": "command", "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/count-codegraph-query.sh" }
        ]
      }
    ]
  }
}
```

  `chmod +x .claude/hooks/count-codegraph-query.sh`. (If Step 1 showed the matcher field does not filter MCP tool names reliably, keep the matcher broad and rely on the script's `case` guard, which already filters.)
- [ ] **Step 4: Gitignore the runtime counter.** Add `.architecture/.budget/` to `.gitignore` (it is per-run state, not source).
- [ ] **Step 5: Wire the orchestrator to meter.** In the skill: at loop start, reset the counter (`mkdir -p .architecture/.budget && echo 0 > .architecture/.budget/query-count`). Before and after each agent dispatch, read the counter; the delta is that agent's actual query count. Require delta <= 1 (the per-agent budget). If an agent exceeded it, flag it in the run summary and treat a gross overage (delta >= 3) as a hard STOP ("budget breach"). Report the metered counts, not the agents' self-reported ones.
- [ ] **Step 6: Update the deferred-features note** to remove "budget metering" (now built); the only items left deferred there should be none from iter 6 (drift scan lands in Task 5).
- [ ] **Step 7: FALLBACK (only if Step 1 failed).** If PreToolUse hooks do not fire for subagent tool calls, meter at the orchestrator boundary instead: have each agent print a machine-readable `QUERIES_USED=<n>` line as the last line of its summary, and the orchestrator parses and records it, cross-checking against the report/patch (one declared query each). Document clearly in the skill that this is self-reported-plus-cross-check, weaker than hook enforcement, and file it as a finding for the packaging iteration.
- [ ] **Step 8: Commit.** `git add .claude/hooks .claude/settings.json .gitignore .claude/skills/harness-feature/SKILL.md && git commit -m "feat: meter codegraph queries via PreToolUse hook, orchestrator enforces per-agent budget (iter-6)"`

### Task 5: Periodic full-graph drift scan

**Files:** Modify `.claude/skills/harness-feature/SKILL.md`

The Architect classifies drift only for the feature's area, so harmful drift elsewhere accumulates invisibly. Add a cheap, feature-independent scan on the same cadence as step-0 re-survey.

- [ ] **Step 1: Define the scan** as a skill step that runs whenever step 0's re-survey condition fires (code-commit count over threshold, or `--resurvey`, or `--drift-scan`). It is feature-independent: it checks the WHOLE repo, not the feature's area.
- [ ] **Step 2: Two cheap checks, no new code:**
  - run the full linter self-check (`python -m src.adapters.boundaries.cli src .architecture/boundaries.yaml`) and report any forbidden edge anywhere in `src/` (this is the existing tool, repo-wide);
  - one `codegraph_explore` query for the module-level edge summary, and flag any observed module or cross-module edge that is NOT represented in `.architecture/boundaries.yaml` (a module/edge the intended map does not mention = undeclared structural drift).
- [ ] **Step 3: Report, do not auto-fix.** The scan writes a short `.architecture/validation/drift-scan.md` (date, forbidden edges found, undeclared modules/edges) and the orchestrator surfaces it. Resolving drift is a human/Architect decision, not automatic. The scan counts against the freshness + budget rules like any query.
- [ ] **Step 4: Verify** the scan is gated on the cadence trigger (not run every feature) and is clearly feature-independent.
- [ ] **Step 5: Commit.** `git add .claude/skills/harness-feature/SKILL.md && git commit -m "feat: periodic full-graph drift scan on the re-survey cadence (iter-6)"`

### Task 6: Dogfood the hardened loop

**Reload caveat:** the new hook + edited skill/agent need `/reload-plugins` (and a settings reload) to take effect. Until then, follow the skill steps inline; the hook only meters once registered, so Task 4 Step 1 must have reloaded already.

**Feature for the dogfood:** add a `--quiet` flag to the linter CLI (suppress the "No boundary violations found." line on a clean run; exit codes unchanged). Small, real, seam-touching (a new `--quiet` branch in `cli.main`, no new contract), end-to-end testable.

- [ ] **Step 1: Run the loop** on `--quiet`. Confirm the freshness check ran (sync + status clean) before the Architect query.
- [ ] **Step 2: Verify budget metering.** After each agent, the metered counter delta is 1 (or the fallback's parsed count). Confirm the orchestrator reports metered counts, and that a deliberately induced second query (scratch: tell a throwaway architect run to query twice) is flagged.
- [ ] **Step 3: Verify Inspector cleanup.** The Inspector run makes exactly 1 query, does NOT run tests/self-check, does NOT touch `state.yaml`; the orchestrator bumps state on ACCEPT.
- [ ] **Step 4: Verify the capped revise loop.** Force one `NEEDS PATCH REVISION` (scratch: have the Builder implement a seam that diverges from the patch's declared signature), confirm the orchestrator routes to the Architect, re-enters the approval pause, and that two forced failures hit the cap and STOP. Revert scratch.
- [ ] **Step 5: Verify the drift scan.** Run the loop with `--drift-scan` (or trip the cadence), confirm `.architecture/validation/drift-scan.md` is written and reports the clean `src/` (no forbidden edge, no undeclared module).
- [ ] **Step 6: Confirm the feature still shipped** on a clean ACCEPT path: 70+ tests pass, `--quiet` works, one feature commit + trailing state commit.

### Task 7: Record the iteration and finish the branch

- [ ] **Step 1: CodeGraph sync** + a final freshness check.
- [ ] **Step 2: Append a results section** to this file: which controls now have teeth, the hook-fires-for-subagent finding (Task 4 Step 1 outcome), metered vs self-reported counts observed, whether the capped loop behaved, and the dogfood SHA.
- [ ] **Step 3: Update `.architecture/state.yaml` notes:** Inspector is gate-2-only; orchestrator owns gate 1 + state; freshness + budget + drift-scan are enforced.
- [ ] **Step 4: Commit.** `git add docs/iteration .architecture/state.yaml && git commit -m "docs: iteration 6 governance + budget hardening results"`
- [ ] **Step 5:** Use superpowers:finishing-a-development-branch (verify tests, then merge / PR / keep per the user's choice). Branch first if starting from `main`.

---

## Verification (end-to-end)

1. `inspector.md` no longer runs gate 1 or bumps `state.yaml`; it emits gate 2 + verdict + a `## Next action` block.
2. The orchestrator runs `codegraph sync` + `status --json` and refuses to dispatch against a stale index (pendingChanges or worktreeMismatch non-clean -> STOP).
3. The PreToolUse hook increments `.architecture/.budget/query-count` on a real `codegraph_explore` call (proven for a subagent in Task 4 Step 1), and the orchestrator enforces the per-agent budget from the metered count, not the self-report. (Or the documented fallback if hooks do not reach subagents.)
4. A forced non-ACCEPT routes through the capped revise loop (max 2 cycles), every patch revision re-enters the human approval pause, and exceeding the cap STOPS.
5. The drift scan runs on the cadence trigger, writes `drift-scan.md`, and reports the repo-wide forbidden-edge + undeclared-module state.
6. The dogfood feature (`--quiet`) ships on a clean ACCEPT path; tests pass.

## Feedback to collect (feeds iter 7+)

- Did PreToolUse hooks reach subagent tool calls, or did metering fall back to self-report-plus-cross-check? (Decides whether hook-based enforcement is viable for packaging.)
- Was the freshness check ever actually stale after `sync` (does the ~1s watcher lag bite in practice), or is it always clean and the check is cheap insurance?
- Did the capped revise loop converge, or did real revisions usually need the human anyway (signal on whether automation past the first REJECT earns its complexity)?
- Is repo-wide drift-scan output actionable, or noisy (too many undeclared-module false positives on a healthy repo)?
- After this iteration, are any honor-system gaps left before the harness is worth packaging (iter 10)?

## Risks / open decisions

- **Hook reach into subagents (primary risk).** NOT validated this session: the settings hook never activated (see Results finding 1), so the fallback shipped the iteration. Re-test after a full session restart; this is a hard gate for packaging.
- **Drift-scan signal-to-noise.** The "undeclared module/edge" check may be noisy on a repo whose `boundaries.yaml` is intentionally coarse. Keep it a surfaced report, never an auto-block, this iteration.
- **Capped-loop value.** Two cycles is a guess; the dogfood + feedback decide whether to keep, raise, or drop automatic revision in favor of always-ask-human.

---

## Results (executed 2026-06-25)

Built Tasks 1-5 (Inspector trim, freshness verification, capped revise loop, budget-meter hook, drift scan), then dogfooded the hardened loop on `--quiet`.

**Loop outcome: ACCEPT.** Feature shipped at `7e65907`; harness state trails at `4e033a8`. 76 tests OK.

- **Freshness verification:** `codegraph sync` + `status --json` returned FRESH (pendingChanges all 0, worktreeMismatch null) before the Architect and before the Inspector. Cheap, ran clean both times.
- **Inspector cleanup (finding-2 fix):** the Inspector made 1 query, did gate 2 + verdict + `## Next action: none`, and did NOT run gate 1 or touch `state.yaml` (`git diff` on state was empty after its run). The orchestrator ran gate 1 itself (76 tests, self-check exit 0, scope = 2 allowed files) and owned the state bump.
- **Capped revise loop:** a forced scratch forbidden edge made the orchestrator's gate 1 exit 1 -> `REJECT: ARCHITECTURE VIOLATION` -> routed to builder (code-level, same patch), no Inspector dispatch, no commit (HEAD unchanged). The full 2-cycle cap is deterministic skill routing, verified by inspection rather than by burning multiple agent cycles.
- **Drift scan:** `--drift-scan` ran the repo-wide self-check (clean, exit 0) and the undeclared-module diff (none; `shared` is declared-but-not-materialized, intended-ahead-of-observed, not drift), wrote `.architecture/validation/drift-scan.md`.
- **Feature:** `--quiet` clean run prints nothing (exit 0); default + violations + could-not-run paths unchanged.

### Findings

1. **Budget hook did not activate this session (primary risk realized, fallback used).** After `/reload-plugins`, the metered counter stayed 0 even for a MAIN-SESSION `codegraph_explore`, so the project `.claude/settings.json` `PreToolUse` hook was not live (Claude Code appears to gate newly-added settings hooks behind a full session restart and/or explicit hook approval; `/reload-plugins` reloads plugin hooks, not this one). Consequence: the subagent-reach question (the actual primary risk) stayed UNTESTED, and metering ran on the documented Task-4 Step-7 fallback (each agent's self-reported `QUERIES_USED`, cross-checked against artifacts: architect=1, builder=0, inspector=1, all within budget). The hook files are committed and unit-tested standalone (counts explore, ignores Read); confirming live activation + subagent reach is the first thing to retry after a full restart, and is a hard gate for the packaging iteration.
2. **Builder needs no CodeGraph query for a lite patch.** `QUERIES_USED=0` for the Builder on `--quiet`; the per-agent budget is an upper bound (<= 1), not a floor. The meter should not flag 0 as anomalous.

The core hardening behaved correctly: freshness-gated, orchestrator-owned gate 1 + state, Inspector reduced to judgment, capped routing on REJECT, repo-wide drift surfaced. The one gap is live hook enforcement, which is environmental (session restart) rather than a design failure, and the fallback kept metering honest in the meantime.
