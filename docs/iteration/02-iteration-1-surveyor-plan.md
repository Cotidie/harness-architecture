---
type: plan
status: draft
created: 2026-06-25
source_plan: "[[01-harness-mvp-iteration-roadmap]]"
iteration: 1
---

# Iteration 1 (Surveyor Bootstrap): Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development or superpowers:executing-plans to implement task-by-task. Steps use checkbox (`- [ ]`) syntax.

## Context

The roadmap's iteration 1 ([`01-harness-mvp-iteration-roadmap.md`](01-harness-mvp-iteration-roadmap.md))
assumes a codebase to snapshot via CodeGraph. This repo currently has none: only
`README.md` and the two docs. So the "observe architecture via CodeGraph" half of the slice
has nothing to observe yet.

Confirmed decisions that shape this plan:
- **Add a throwaway sample `src/`** (Python) purely to exercise the CodeGraph snapshot path,
  then delete it.
- **Intended docs use the design's generic placeholder layout**; the repo's real stack is
  locked in iteration 2 when the boundaries-linter is built.
- **Agents are first-class custom subagents** (`.claude/agents/<name>.md`), dispatched by name.

**Goal:** Stand up the `surveyor` custom subagent and prove it can turn real
CodeGraph output into compact `/architecture` docs, while seeding the intended architecture
docs from the design.

**Architecture:** Add a small throwaway Python `src/` (domain, contract, application, adapter,
with one deliberately planted forbidden edge), let CodeGraph index it, run the Surveyor
against it to exercise the observed-snapshot path, judge the output, then delete the sample.
The kept intended docs use the design's generic module layout as a placeholder.

**Tech Stack:** Markdown and YAML artifacts; Claude Code custom agent def (`.claude/agents/*.md`);
throwaway Python sample; `codegraph` CLI / `codegraph_explore` MCP tool.

## Global Constraints (from `docs/01-harness-mvp-plan.md`)

- CodeGraph = observed truth; architecture docs = intended truth. Docs must NOT be a full code index. (sec 1, 2)
- Snapshot budget = **1 to 2 targeted CodeGraph queries**. (sec 7)
- No long source bodies pasted into docs; `current.mmd` = high-level boundaries, not per-symbol. (sec 3 forbidden behavior)
- Invocation = first-class custom subagents (`.claude/agents/<name>.md`), dispatched by name. (roadmap fork)
- Never use em-dash in authored content (user global rule).
- Artifact set plus `state.yaml`/`boundaries.yaml` shapes are fixed by design sec 4, 9, 10.

---

## File map

- Create `.claude/agents/surveyor.md`: the Surveyor definition (frontmatter + prompt body).
- Create `agent-prompts/surveyor.md`: reusable prompt body (single source; agent def duplicates it inline).
- Create throwaway `src/` sample (deleted in Task 6):
  - `src/domain/route_risk_policy.py`, `src/domain/route_risk.py`
  - `src/contracts/route_dto.py`
  - `src/application/plan_route.py`
  - `src/adapters/route_repository.py`
- Create (kept) `/architecture/` artifacts: `architecture.md`, `boundaries.yaml`, `domain-model.md`,
  `data-contracts.md`, `graph-notes.md`, `diagrams/current.mmd`, `state.yaml`.

---

### Task 1: Surveyor agent definition + prompt body

**Files:** Create `agent-prompts/surveyor.md`, `.claude/agents/surveyor.md`

**Produces:** subagent dispatchable as `Agent(subagent_type: 'surveyor')`.

- [ ] **Step 1: Write the prompt body** `agent-prompts/surveyor.md`. Must instruct the agent to:
  - run at most 1 to 2 `codegraph_explore` queries to observe module/dependency/class/contract structure;
  - emit the six `/architecture` artifacts (design sec 4) plus `state.yaml` (sec 9);
  - fill `boundaries.yaml` to the sec 10 schema and `current.mmd` at boundary altitude only;
  - record observed-vs-intended drift in `graph-notes.md` where they differ;
  - obey the forbidden-behavior list (no whole-repo dump, no long source bodies, no em-dash).
- [ ] **Step 2: Write the agent def** `.claude/agents/surveyor.md` with frontmatter:

```markdown
---
name: surveyor
description: Generate compact intended-architecture docs for the repo from a 1-2 query CodeGraph observation. Use for first-time setup or periodic snapshot.
tools: Read, Write, Glob, Grep, mcp__codegraph__codegraph_explore
---
```
  Body = the prompt from Step 1 (inline).
- [ ] **Step 3: Verify** the agent loads. Run: `ls .claude/agents/surveyor.md`. Expected: file present, valid frontmatter.
- [ ] **Step 4: Commit.** `git add .claude/agents/surveyor.md agent-prompts/surveyor.md && git commit -m "feat: add architecture-Surveyor"`

### Task 2: Throwaway sample src/

**Files:** Create the five `src/` files listed in the file map.

**Interfaces / planted structure (so CodeGraph has real edges to observe):**
- `RouteRisk` (value object, `src/domain/route_risk.py`).
- `RouteRiskPolicy.evaluate(route, robots) -> RouteRisk` (`src/domain/route_risk_policy.py`).
- `RouteRequestDTO` dataclass (`src/contracts/route_dto.py`).
- `PlanRouteUseCase.run(dto: RouteRequestDTO)` imports domain + contract (allowed edge).
- `RouteRepository` (`src/adapters/route_repository.py`) imports application + domain (allowed edge).
- **One planted forbidden edge:** `route_risk_policy.py` imports `RouteRequestDTO` from contracts
  (domain -> contracts, forbidden per sec 10). This gives the snapshot a real observed-vs-intended drift to report.

- [ ] **Step 1: Write all five files** with the above imports/classes. Keep each tiny (a class + one method, no business depth).
- [ ] **Step 2: Verify** Python parses. Run: `python3 -m compileall src`. Expected: no syntax errors. (No commit; sample is throwaway.)

### Task 3: Index sample with CodeGraph

- [ ] **Step 1: Sync the index.** Run: `codegraph sync` (or `codegraph index`) in repo root.
- [ ] **Step 2: Verify edges are visible.** Run: `codegraph explore "RouteRiskPolicy RouteRequestDTO PlanRouteUseCase route dependencies"`.
  Expected: output shows the four modules, the domain -> contracts planted edge, and the allowed edges.
  If empty, sample was not indexed; re-run sync before proceeding.

### Task 4: Run the Surveyor

- [ ] **Step 1: Dispatch** `Agent(subagent_type: 'surveyor')` with prompt: "Snapshot this repo.
  Intended layout placeholder = design sec 5/10 generic module map. Report observed structure of the current
  src/ and any drift from intended."
- [ ] **Step 2:** Capture the agent's reported CodeGraph query count from its summary.

### Task 5: Verify testable conditions + judge

- [ ] **Step 1: Artifacts exist and non-empty.** Run: `for f in architecture.md boundaries.yaml domain-model.md data-contracts.md graph-notes.md diagrams/current.mmd state.yaml; do test -s "architecture/$f" && echo "OK $f" || echo "MISSING $f"; done`.
  Expected: all OK.
- [ ] **Step 2: Budget.** Confirm agent used 2 or fewer CodeGraph queries (from Task 4 Step 2). Expected: <= 2.
- [ ] **Step 3: No bloat.** Run: `grep -rn "def \|class " architecture/*.md | head` and eyeball `current.mmd`.
  Expected: no pasted source bodies; diagram is boundary-level, not per-symbol.
- [ ] **Step 4: Accuracy.** `boundaries.yaml` names the sample's real modules (domain/contracts/application/adapters);
  `graph-notes.md` records the planted domain -> contracts forbidden edge as observed drift. Expected: both true.
  **This is the iteration's core judgment: does CodeGraph to compact docs actually work?**

### Task 6: Discard sample, finalize intended docs, commit

- [ ] **Step 1: Delete the sample.** Run: `rm -rf src && codegraph sync`.
- [ ] **Step 2: Rewrite kept docs to intended placeholder.** Replace sample-specific content in
  `architecture.md`/`boundaries.yaml`/`domain-model.md`/`data-contracts.md` with the design's generic
  intended layout (sec 5/10), since the sample is gone and the real stack is deferred to iteration 2.
  Keep `graph-notes.md` snapshot lessons.
- [ ] **Step 3: Set `state.yaml`**: `last_reconciliation_decision`, `last_codegraph_query_scope`, note
  "intended docs are placeholder; real stack locked in iteration 2".
- [ ] **Step 4: Commit.** `git add .claude/agents agent-prompts architecture && git commit -m "feat: bootstrap architecture snapshot + intended docs"`

---

## Verification (end-to-end)

1. `ls .claude/agents/surveyor.md agent-prompts/surveyor.md`: both present.
2. Re-dispatch the Surveyor on the (now code-less) repo: it should report "no source to observe"
   gracefully and keep the intended placeholder docs. Confirms the agent degrades cleanly, which is the
   real state until iteration 2 adds code.
3. `ls architecture/` shows all seven artifacts; `git status` clean; no `src/` left.

## Feedback to collect (feeds iteration 2 detailing)

- Were 1 to 2 queries enough, or did the agent want more (budget too tight)?
- Did `boundaries.yaml`/`current.mmd` land at the right altitude?
- Did `graph-notes.md` correctly flag the planted forbidden edge (proves the observed-vs-intended comparison works)?
- Does the generic placeholder layout fit how this repo's linter should be structured, or should iteration 2
  redefine the module map?

## Open decisions

- **OPEN:** whether the Surveyor needs `mcp__codegraph__codegraph_explore` explicitly in its `tools:`
  allowlist vs inherited. Resolve on first dispatch (Task 4); if the tool is unavailable, add it to frontmatter.
