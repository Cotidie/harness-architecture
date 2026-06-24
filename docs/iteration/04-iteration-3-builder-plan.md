---
type: plan
status: draft
created: 2026-06-25
source_plan: "[[01-harness-mvp-iteration-roadmap]]"
patch: "[[2026-06-25-boundaries-linter]]"
iteration: 3
---

# Iteration 3 (Builder): Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (or subagent-driven-development). Steps use checkbox (`- [ ]`) syntax.

## Context

Iterations 1-2 proved the Surveyor and Architect. Iteration 3 builds and exercises the
**Builder**: it implements the approved architecture patch
(`.architecture/patches/2026-06-25-boundaries-linter.md`) into real code, editing ONLY the
files the patch allows, and proves the boundaries-linter works by catching the planted
`sample/` violation and passing its own self-check.

This is the first iteration that writes `src/` code. The patch is the spec; this plan does
not re-derive it.

**Locked decisions:**
- Stack: **Python**. Dependency posture: **PyYAML** (YAML load, adapters layer only) plus stdlib
  `unittest` for tests. No pytest.
- The linter is layered per the patch: contracts (data shapes), domain (`BoundaryRuleSet`, the
  check logic, plain inputs only), application (`LintBoundaries` maps contracts to domain),
  adapters (YAML loader, `ast` import scanner, reporter, CLI).

**Gap found in the approved patch:** section 9 (files allowed to edit) lists only `src/` and
`tests/`. It does not allow a dependency manifest, but PyYAML needs one. So Task 1 amends the
patch (adds `requirements.txt` plus a Dependency-changes note) before the Builder runs,
otherwise a disciplined Builder would correctly stop and request revision.

## Global Constraints

- Builder edits ONLY files in the patch's allowed list (as amended). No hidden changes. (design sec 6 Agent 2)
- No raw dict/list across a boundary: rules, edges, violations are contract classes.
- Boundary-check business logic lives in the `BoundaryRuleSet` domain class, not a module-level function.
- `domain` must NOT import `contracts`: the application layer maps contract data to plain domain inputs.
- PyYAML is imported only in `src/adapters/boundaries/boundaries_config_loader.py` (external dep, adapters layer).
- Tests use stdlib `unittest`, runnable via `python -m unittest`.
- `sample/` is out of scope to edit (the planted violation stays).
- Never use em-dash in authored content.

## File map (from patch section 9, plus the dep manifest)

- Create `requirements.txt` (PyYAML) [patch amendment].
- Contracts: `src/contracts/boundaries/{module_rule,import_edge,boundary_violation}.py`.
- Domain: `src/domain/boundaries/boundary_rule_set.py`.
- Application: `src/application/boundaries/lint_boundaries.py`.
- Adapters: `src/adapters/boundaries/{boundaries_config_loader,python_import_scanner,violation_reporter,cli}.py`.
- Package `__init__.py` at each level.
- Tests under `tests/` (stdlib unittest): domain behavior, contract validation, integration (sample), self-check (src).

---

### Task 1: Amend the approved patch for the dependency

**Files:** `.architecture/patches/2026-06-25-boundaries-linter.md`

- [ ] **Step 1:** In section 6 (Dependency changes), add a line: the linter takes one external
  dependency, PyYAML, used only in the adapters loader (allowed; external deps belong in adapters).
- [ ] **Step 2:** In section 9 (Files allowed to edit), add `requirements.txt` (create).
- [ ] **Step 3:** Add a short note that the amendment reflects the iteration-3 dependency
  decision (PyYAML plus stdlib unittest) and keep the approval checkbox checked.
- [ ] **Step 4: Commit.** `git add .architecture/patches && git commit -m "docs: amend linter patch for PyYAML dependency"`

### Task 2: Builder agent definition

**Files:** Create `.claude/agents/builder.md`

- [ ] **Step 1: Write the agent def** with frontmatter:

```markdown
---
name: builder
description: Implement only an approved architecture patch. Edit only the patch's allowed files, follow TDD, keep domain logic in domain classes, no raw dict/list across boundaries. Stop and request revision if the patch is insufficient.
tools: Read, Write, Edit, Glob, Grep, Bash, mcp__codegraph__codegraph_explore
---
```

- [ ] **Step 2: Write the prompt body** (self-contained). It must instruct the Builder to:
  - read the approved patch and implement ONLY it; edit only the allowed-files list;
  - work test-first (write a failing `unittest`, then the minimal code to pass);
  - put boundary data in contract classes, never raw dict/list across a boundary;
  - keep boundary-check logic in the `BoundaryRuleSet` domain class, which takes plain inputs
    and does NOT import contracts (the application layer maps);
  - import PyYAML only in the adapters loader;
  - if the patch is ambiguous or insufficient, STOP and request a patch revision (do not improvise);
  - not call CodeGraph unless the patch is ambiguous;
  - emit a summary: files changed, domain/contract changes, deps, tests added, assumptions;
  - no em-dash.
- [ ] **Step 3: Verify** `ls .claude/agents/builder.md`. (Dispatch by name needs reload, see Task 3.)
- [ ] **Step 4: Commit.** `git add .claude/agents/builder.md && git commit -m "feat: add builder agent"`

### Task 3: Dispatch the Builder to implement the patch

**Reload caveat (from iters 1-2):** a fresh agent def is not dispatchable by name until reload.
If `subagent_type: 'builder'` is not found, dispatch a `general-purpose` subagent with the Task 2
prompt body inline.

- [ ] **Step 1: Dispatch** the Builder with: the approved and amended patch path, the locked deps
  (PyYAML plus stdlib unittest), the run targets (sample and src self-check), and the instruction
  to implement test-first and report its summary.
- [ ] **Step 2: Capture** the Builder's summary (files changed, tests added, assumptions).

### Task 4: Verify testable conditions

- [ ] **Step 1: Scope.** `git status --short` and `git diff --stat`: every changed/created path
  is in the patch's allowed list (plus `requirements.txt`, `tests/`). No `sample/` edits.
- [ ] **Step 2: Tests pass.** Run: `python -m unittest discover -s tests -v`. Expected: all pass.
  (Install dep first: `pip install -r requirements.txt`.)
- [ ] **Step 3: Catches the planted violation.** Run:
  `python -m src.adapters.boundaries.cli sample sample/boundaries.yaml; echo "exit=$?"`.
  Expected: reports the `sample.domain.route_risk_policy -> sample.contracts.route_dto` violation
  (correct file plus line) and `exit=1` (non-zero).
- [ ] **Step 4: Self-check passes.** Run:
  `python -m src.adapters.boundaries.cli src .architecture/boundaries.yaml; echo "exit=$?"`.
  Expected: zero violations, `exit=0` (the linter obeys its own intended boundaries; in
  particular no `domain -> contracts` edge in `src/domain/boundaries`).
- [ ] **Step 5: Architecture rules held.** Confirm `src/domain/boundaries/boundary_rule_set.py`
  does NOT import from `src/contracts`; boundary data is carried by the three contract classes;
  PyYAML appears only in the adapters loader.

### Task 5: Sync, refresh docs, commit

- [ ] **Step 1: CodeGraph sync.** Run: `codegraph sync`.
- [ ] **Step 2: Drop placeholder wording.** Update `.architecture/architecture.md` and
  `.architecture/state.yaml`: the `src/` layout is now real (Python), not a placeholder.
  `boundaries.yaml` already uses `src/**` paths, leave it.
- [ ] **Step 3: Commit.** `git add src tests requirements.txt .architecture && git commit -m "feat: boundaries linter (iteration 3 builder)"`

---

## Verification (end-to-end)

1. `python -m unittest discover -s tests` passes.
2. Linter on `sample/` reports exactly the planted violation and exits non-zero.
3. Linter self-check on `src/` reports zero violations and exits zero.
4. `git diff` touched only patch-allowed files plus `requirements.txt` and `tests/`; `sample/` untouched.

## Feedback to collect (feeds iteration 4 / Inspector)

- Did the Builder stay strictly in the allowed-files scope, or drift?
- Were the patch instructions enough to build from without re-querying or guessing?
- Did the self-check (linter on `src/`) pass first try, or did the Builder accidentally create a
  forbidden edge it then had to fix? (This is exactly the gate iteration 4 will automate.)
- Quality vs an un-harnessed implementation: worth the patch overhead?

## Open decisions

- Iteration 4 (Inspector) will reuse this self-check as its mechanical gate (already in the roadmap).
- `requirements.txt` vs `pyproject.toml`: MVP uses `requirements.txt` (simplest); revisit at iter7 packaging.
