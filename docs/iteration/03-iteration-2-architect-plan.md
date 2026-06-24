---
type: plan
status: draft
created: 2026-06-25
source_plan: "[[01-harness-mvp-iteration-roadmap]]"
iteration: 2
---

# Iteration 2 (Reconcile + Patch): Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development or superpowers:executing-plans to implement task-by-task. Steps use checkbox (`- [ ]`) syntax.

## Context

Iteration 1 proved the Surveyor turns CodeGraph output into compact intended docs and flags
drift. Iteration 2 builds and exercises the **Architect**: given a feature request plus the
intended docs, it makes one targeted CodeGraph query, classifies observed-vs-intended drift,
and writes an approvable architecture patch, all **before** any implementation code.

This iteration produces a **patch, not code**. The code lands in iteration 3 (Builder). The
slice is done when there is a reviewable patch you would approve, edit, or reject.

**Dogfood feature (locked):** a `boundaries.yaml` linter. A tool that loads a `boundaries.yaml`
(module path globs + `may_depend_on` / `must_not_depend_on`), scans a target Python source
tree, resolves each module's imports, and reports every import that violates a
`must_not_depend_on` rule (non-zero exit when violations exist). Its first lint target is the
`sample/` fixture using `sample/boundaries.yaml`.

**Why this exercises the Architect well:** the linter is real harness tooling, so it is
greenfield in `src/` (the Architect must propose a clean layered design). The `sample/`
fixture carries a planted `domain -> contracts` violation, so the Architect's reconciliation
has real drift to classify and the linter has a known violation to be aimed at.

**Stack decision (locked here, was deferred from iteration 1): Python.** The lint target
(`sample/`) is Python and the linter must parse Python imports (stdlib `ast`), so a Python
linter is the coherent choice. This locks the real `src/` module map that
`.architecture/boundaries.yaml` described as placeholder.

## Global Constraints (from `docs/01-harness-mvp-plan.md`)

- CodeGraph = observed truth; intended docs = intended truth. (sec 1, 2)
- Architect budget = **1 targeted CodeGraph query** for reconciliation + patch planning. (sec 3)
- The Architect writes a patch only; it does **not** write implementation code. (sec 6 Agent 1 hard rules)
- New boundary data must propose a contract class; new business behavior must propose a domain
  class or method, never a module-level business function. (Rules 5, 6, 7)
- Patch must follow the design's 11-section template (sec 8) and live at
  `.architecture/patches/YYYY-MM-DD-<feature>.md` with an approval checkbox.
- Agents are self-contained custom subagents in `.claude/agents/<name>.md`. (roadmap)
- Never use em-dash in authored content (user global rule).

---

## File map

- Create `.claude/agents/architect.md`: the Architect custom subagent (frontmatter + full
  prompt body, self-contained).
- Create (by the Architect, at execution) `.architecture/patches/2026-06-25-boundaries-linter.md`:
  the reconciliation + patch artifact.
- No `src/` code is created this iteration (that is iteration 3).

---

### Task 1: Architect agent definition

**Files:** Create `.claude/agents/architect.md`

**Produces:** subagent dispatchable as `Agent(subagent_type: 'architect')`.

- [ ] **Step 1: Write the agent def** `.claude/agents/architect.md` with frontmatter:

```markdown
---
name: architect
description: Reconcile observed vs intended architecture for a feature request via one targeted CodeGraph query, then write an approvable architecture patch. Does not write implementation code.
tools: Read, Write, Glob, Grep, mcp__codegraph__codegraph_explore
---
```

- [ ] **Step 2: Write the prompt body** (inline, self-contained). It must instruct the Architect to:
  - read the intended docs first: `.architecture/.architecture.md`, `.architecture/boundaries.yaml`,
    `.architecture/domain-model.md`, `.architecture/data-contracts.md`, and (for the lint target)
    `sample/boundaries.yaml`;
  - make **exactly 1** `codegraph_explore` query about the affected area (here: the `sample/`
    structure and any place linter code would attach), then stop querying;
  - reconcile observed vs intended and pick one label: ALIGNED, DOC_DRIFT_ACCEPTED,
    CODE_DRIFT_HARMFUL, or UNCLEAR_DRIFT, with a justification tied to the comparison;
  - write the patch to `.architecture/patches/YYYY-MM-DD-<feature>.md` using the design's
    11-section template (sec 8): feature request, observed architecture, intended architecture,
    reconciliation decision, module changes, dependency changes (allowed + forbidden), domain
    model changes, data contract changes, files allowed to edit, tests required, risks, and an
    approval checkbox;
  - apply the hard rules: define/reuse a contract class for new boundary data; define/update a
    domain class for new business behavior; no module-level business functions; no broad repo
    exploration; **do not write implementation code**;
  - emit the compact "Relevant Architecture Context" summary (sec 3), not raw CodeGraph dumps;
  - report its query count and chosen drift label in the final summary.
- [ ] **Step 3: Verify** the file exists with valid frontmatter. Run: `ls .claude/agents/architect.md`.
  Expected: present. (Dispatch by name needs a plugin reload, see Task 2 note.)
- [ ] **Step 4: Commit.** `git add .claude/agents/architect.md && git commit -m "feat: add architect agent"`

### Task 2: Dispatch the Architect on the linter feature

**Note (reload caveat, carried from iteration 1):** a freshly written agent def is not
dispatchable by name until a plugin reload. If `subagent_type: 'architect'` is not found,
dispatch a `general-purpose` subagent with the Task 1 prompt body inline. Same budget, same output.

- [ ] **Step 1: Dispatch** the Architect with this feature request and context:
  > "Feature: add a boundaries linter. It loads a `boundaries.yaml` (module path globs plus
  > `may_depend_on` / `must_not_depend_on`), scans a target Python source tree, resolves each
  > module's imports to modules, and reports every import that violates a `must_not_depend_on`
  > rule, exiting non-zero when any violation exists. First lint target is the `sample/` fixture
  > with `sample/boundaries.yaml`. Stack is Python (stdlib only where possible). Reconcile
  > against the intended docs and the sample, then write the patch. Do not write code."
- [ ] **Step 2: Capture** the Architect's reported CodeGraph query count and drift label from its summary.

### Task 3: Verify the patch and judge

- [ ] **Step 1: Patch exists.** Run: `ls .architecture/patches/`. Expected: one
  `2026-06-25-boundaries-linter.md` (or similar dated name), non-empty.
- [ ] **Step 2: All 11 sections present.** Run:
  `grep -ciE "feature request|observed|intended|reconciliation|module|dependency|domain|contract|files allowed|tests required|risk|approv" .architecture/patches/*.md`.
  Expected: every section heading from the sec 8 template is present.
- [ ] **Step 3: Budget.** Confirm the Architect used exactly 1 CodeGraph query (from Task 2 Step 2).
  Expected: 1.
- [ ] **Step 4: Drift call justified.** The reconciliation decision is one of the four labels and
  is argued from the observed-vs-intended comparison (the planted `domain -> contracts` edge in
  the sample should be acknowledged). Read and judge: not asserted, justified.
- [ ] **Step 5: Harness-shaped design.** The patch proposes the linter as layered Python under
  `src/` with: a domain class/method holding the boundary-check logic (not a module-level
  function), contract classes for boundary data (a rule and a violation shape), an application
  use case, and adapters for YAML load + import scanning. "Files allowed to edit" is a concrete
  bounded list. No implementation code was written.
- [ ] **Step 6: Judge.** Would you approve this patch as-is, edit it, or reject it? Record the call.

### Task 4: Commit the patch and record outcome

- [ ] **Step 1: Commit.** `git add .architecture/patches && git commit -m "docs: architect patch for boundaries-linter"`
- [ ] **Step 2:** If you approve the patch, tick its approval checkbox in a follow-up edit (this
  is the human gate that authorizes iteration 3 to build it).

---

## Verification (end-to-end)

1. `.claude/agents/architect.md` exists; dispatch (by name after reload, or inline fallback) succeeds.
2. `.architecture/patches/2026-06-25-boundaries-linter.md` exists with all 11 sections, 1 query, a
   justified drift label, and a bounded allowed-files list.
3. No `src/` implementation code was created this iteration; `git status` shows only the agent def
   and the patch.

## Feedback to collect (feeds iteration 3 detailing)

- Was 1 query enough to reconcile, or did the Architect want more?
- Is the patch specific enough for the Builder to implement from without guessing?
- Did the drift classification match your judgment on the planted sample violation?
- Which of the 11 sections are essential vs noise for a feature this size (may justify a "small
  change" lite patch later)?
- Did the proposed `src/` module map feel right, or should `.architecture/boundaries.yaml` be
  refined now that the real stack is Python?

## Open decisions

- **Stack locked: Python.** Records the real `src/` layout; update `.architecture/boundaries.yaml`
  from placeholder to the Python module map when iteration 3 lands the code.
- **OPEN (carried):** human approval is recorded by ticking the patch checkbox in-file for MVP.
  Revisit when iteration 5 wires the full loop.
