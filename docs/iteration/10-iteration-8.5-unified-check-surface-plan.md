# Iteration 8.5 (Unified, profile-driven check surface) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (or subagent-driven-development). Steps use checkbox (`- [ ]`) syntax.

**Goal:** Consolidate the harness's accreting deterministic checks behind ONE entrypoint that reads paths from the iteration-8 profile instead of hardcoding `src/`. One command, one combined report, one exit code, any repo layout.

**Architecture:** Add a `source_root` field to `profile.yaml`; a tiny committed path resolver (`scripts/harness_paths.py`) that turns the profile into concrete check paths; a thin aggregator (`scripts/harness_check.py`) that runs the three existing checks (boundaries linter, `drift_scan`, `intended_diff`) against the resolved paths and combines their results; and a one-line `harness-feature` step-0b change to call it. The three sub-checks are unchanged and stay independently runnable. No change to the linter's domain/contracts/application layers.

**Tech stack:** YAML; Python stdlib + `unittest` (mirrors the existing committed checks); Markdown skill edit.

## Locked decisions (from planning forks, 2026-06-25)

- **Source root is an explicit `source_root` field in `profile.yaml`.** The resolver reads it; the `.architecture/*.yaml` names stay fixed. Explicit and reviewable, not derived from glob prefixes.
- **Thin aggregator; sub-checks stay independent.** `harness_check` imports and calls `compute_drift` / `compute_diff` / a thin linter wrapper with resolved paths and aggregates the results. The three checks keep their own functions/CLIs and tests. The shared layer is only path resolution + aggregation (the roadmap's "keep it thin" warning).
- **`detect_profile` is excluded** from the check surface. It is a survey-time seed, not a per-run drift check.

## Global Constraints

- Do not change the linter's behavior or the `drift_scan` / `intended_diff` semantics. This is consolidation + path-resolution only.
- The aggregate exit code is: `2` if any check could-not-run, else `1` if any check found drift, else `0`.
- The unified surface is deterministic (no CodeGraph query), so it stays unmetered, like the checks it wraps.
- Never use em-dash in authored content.

## File structure

- Modify `.architecture/profile.yaml` : add `source_root: src` + schema doc (Task 1).
- Create `scripts/harness_paths.py` : the path resolver (Task 2).
- Create `tests/test_harness_paths.py` : resolver tests (Task 2).
- Create `scripts/harness_check.py` : the aggregating entrypoint (Task 3).
- Create `tests/test_harness_check.py` : aggregator tests (Task 3).
- Modify `.claude/skills/harness-feature/SKILL.md` : step 0b calls the one entrypoint (Task 4).
- Save `docs/iteration/10-iteration-8.5-unified-check-surface-plan.md` (this file) + a results note (Task 5).

---

### Task 1: Add `source_root` to the profile

**Files:** Modify `.architecture/profile.yaml`

- [ ] **Step 1: Add the field.** Add `source_root: src` and document it in the header comment ("the code root the deterministic checks target; relative to the repo root"). Keep it a single relative path.
- [ ] **Step 2: Verify** it parses and `source_root == "src"`; no em-dash.
- [ ] **Step 3: Commit.** `git add .architecture/profile.yaml && git commit -m "feat(iter-8.5): add source_root to profile.yaml (the checks' code root)"`

### Task 2: Path resolver (TDD)

**Files:** Create `scripts/harness_paths.py`, `tests/test_harness_paths.py`

- [ ] **Step 1 (test first, RED):** `tests/test_harness_paths.py` with temp-tree cases: (a) a tree with `.architecture/profile.yaml` (`source_root: app`) resolves `source_dir` to `<root>/app` and the three YAML paths under `<root>/.architecture/`; (b) missing `profile.yaml` raises a clear error; (c) `profile.yaml` without `source_root` raises a clear error.
- [ ] **Step 2: Implement `resolve_paths(repo_root=".", arch_dir=".architecture")`.** Return a frozen `Paths(source_dir, boundaries, contracts, domain_model)`. Read `profile.yaml.source_root`; build `source_dir = os.path.join(repo_root, source_root)`; the YAML paths are `arch_dir/boundaries.yaml`, `arch_dir/contracts.yaml`, `arch_dir/domain-model.yaml` (where `arch_dir` is resolved under `repo_root`). Raise a `HarnessPathsError` (could-not-run) with a clear message when `profile.yaml` is missing or has no `source_root`.
- [ ] **Step 3: GREEN.** `python -m unittest tests.test_harness_paths` passes; no em-dash.
- [ ] **Step 4: Commit.** `git add scripts/harness_paths.py tests/test_harness_paths.py && git commit -m "feat(iter-8.5): profile-driven path resolver (source_root + .architecture yaml paths)"`

### Task 3: Aggregating entrypoint (TDD)

**Files:** Create `scripts/harness_check.py`, `tests/test_harness_check.py`

- [ ] **Step 1 (test first, RED):** `tests/test_harness_check.py`: (a) the real self-host repo (`compute_results(repo_root=REPO_ROOT)`) is all-clean, aggregate exit 0; (b) a temp tree with a planted forbidden edge -> the linter sub-check reports drift, aggregate exit 1; (c) a temp tree with a contract-field mismatch -> the `intended_diff` sub-check reports drift, aggregate exit 1; (d) a temp tree with no `profile.yaml` -> could-not-run, exit 2; (e) **profile-driven proof:** a temp tree with `source_root: app` and an `app/` layout (not `src/`) runs the checks against `app/` and is all-clean, exit 0.
- [ ] **Step 2: Implement the linter wrapper.** A small internal `_run_linter(source_dir, boundaries)` that reuses `load_module_rules` + `LintBoundaries().build_rule_set` + `scan_imports` + `use_case.run` to return `(ok: bool, report_text: str)` WITHOUT the CLI's print/exit. A `BoundariesConfigError` (e.g. zero-match tree) maps to a could-not-run result, not a crash.
- [ ] **Step 3: Implement `compute_results(repo_root=".")`.** Resolve paths (Task 2); run the three checks: linter wrapper, `compute_drift`, `compute_diff`. Collect a list of `CheckResult(name, status, report_text)` where status is `clean` / `drift` / `error`. Catch could-not-run (`HarnessPathsError`, `BoundariesConfigError`, `FileNotFoundError`, `OSError`, `ValueError`, `yaml.YAMLError`) per check and mark it `error`.
- [ ] **Step 4: Aggregate + exit.** `format_report(results)` prints a section per check plus a summary line. `main(argv)`: usage `python -m scripts.harness_check [repo_root]` (default `.`); print the combined report; return `2` if any `error`, else `1` if any `drift`, else `0`.
- [ ] **Step 5: GREEN.** `python -m unittest tests.test_harness_check` passes; `python -m scripts.harness_check` on the real repo is all-clean exit 0; full suite green; no em-dash.
- [ ] **Step 6: Commit.** `git add scripts/harness_check.py tests/test_harness_check.py && git commit -m "feat(iter-8.5): one harness_check entrypoint aggregating linter + drift_scan + intended_diff, profile-driven"`

### Task 4: Wire the orchestrator to the one entrypoint

**Files:** Modify `.claude/skills/harness-feature/SKILL.md`

- [ ] **Step 1: Replace the three step-0b commands** with a single `python -m scripts.harness_check`, describing the combined report + exit code (`0` clean / `1` drift / `2` could-not-run) and that it is deterministic, profile-driven (reads `source_root`), and unmetered. Keep the "surfaced, never auto-block" posture.
- [ ] **Step 2: Verify** step 0b names one command, not three; no em-dash.
- [ ] **Step 3: Commit.** `git add .claude/skills/harness-feature/SKILL.md && git commit -m "feat(iter-8.5): orchestrator step 0b calls the one harness_check entrypoint"`

### Task 5: Dogfood and record results

- [ ] **Step 1: Real-repo run.** `python -m scripts.harness_check`; confirm all-clean exit 0 and the combined report shows the three checks.
- [ ] **Step 2: Planted-drift proof.** Plant a forbidden edge (scratch) and a contract mismatch (temporarily), confirm the aggregate reports the right sub-check and exits 1, then revert.
- [ ] **Step 3: Profile-driven proof.** Confirm (via the Task-3 test or a manual temp tree) that a `source_root` other than `src` retargets the checks, proving the `src/` hardcoding is gone.
- [ ] **Step 4: Adversarial / cli-user-test pass** (`cotidie:cli-user-test`): no profile, profile without `source_root`, a `source_root` pointing at a missing dir, a malformed YAML. Confirm clean could-not-run (exit 2), no traceback.
- [ ] **Step 5: Write the results note** and commit.

## Testable conditions (iteration acceptance)

- `profile.yaml` has `source_root`; the resolver builds the source dir + YAML paths from it.
- `python -m scripts.harness_check` on the self-host is all-clean, exit 0, one combined report covering all three checks.
- A planted forbidden edge or contract mismatch makes the right sub-check report drift with aggregate exit 1; a missing/!source_root profile is a clean could-not-run, exit 2.
- The checks retarget to a non-`src` `source_root` (proven on a temp layout), so `src/` is no longer hardcoded.
- Full suite passes; the three sub-checks remain independently runnable and tested.

## Deferred (explicitly NOT in iteration 8.5)

- **CodeGraph-index observed adapter:** iteration 9 (it slots behind this surface; the public contract here does not change).
- **A dedicated `harness-check` skill (vs the script):** packaging-time UX, iteration 10.
- **Folding `detect_profile` into the check surface:** out by design (it is a survey-time seed).

## Risks / open decisions

- **Do not over-abstract.** The three checks share a shape but take different intended inputs; the shared layer must stay path resolution + aggregation only, not a premature common-report framework. If the linter wrapper grows, that is a signal it should become a real `compute_*` in the linter adapter, not bloat in `harness_check`.
- **`source_root` is a single path.** Repos with multiple source roots (e.g. a monorepo) are out of scope here; revisit at packaging if a real case appears.

---

## Results (executed 2026-06-25)

Built Tasks 1-5: `source_root` in `profile.yaml`, the committed `scripts/harness_paths.py` resolver (+ 3 tests), the `scripts/harness_check.py` aggregator (+ 6 tests), and the one-line step-0b change. 107 tests OK (was 98, +9).

**Outcome: iteration shipped.**

- **One command, one report.** `python -m scripts.harness_check` on the self-host prints a single combined report (boundaries + drift_scan + intended_diff) and exits 0. `harness-feature` step 0b now calls just this, not three commands.
- **Profile-driven, not `src/`-bound.** The resolver reads `source_root` from `profile.yaml`; a test with `source_root: app` and an `app/` layout runs the checks against `app/` and is clean. The `src/` hardcoding is gone.
- **Aggregate exit contract holds.** Planted forbidden edge (scratch in `src/domain/`) -> `boundaries=drift`, aggregate exit 1, with file:line; reverted -> exit 0. A contract field mismatch -> `intended_diff=drift`, exit 1 (unit test).
- **Thin aggregator.** The three sub-checks are unchanged and still independently runnable/tested; `harness_check` only resolves paths, invokes, and combines, plus a small linter wrapper that adapts the CLI to a `(clean, report)` result.

### Adversarial pass (cli-user-test style)

- no profile -> `profile: ERROR`, exit 2;
- profile without `source_root` -> exit 2;
- `source_root` pointing at a missing dir -> `boundaries: ERROR` (scanner cannot run), exit 2;
- malformed profile YAML -> exit 2.

All clean could-not-run, no traceback.

### Findings

1. **The checks match `boundaries.yaml` globs against RELATIVE paths.** The linter/`drift_scan` resolve a file's module by longest glob-prefix (`src/domain/**`), which only matches when paths are repo-root-relative. So `harness_check` chdir's to the repo root and resolves paths relative to it (resolver joins are `normpath`-ed to strip `./`). This path-matching convention is a coupling to remember when iter 9 swaps the observed source to the CodeGraph index: the index will report its own path form, so the glob-matching layer may need to normalize against it.
2. **`source_root` is single-valued.** Fine for self-host and most repos; a monorepo with multiple roots is deferred to packaging.
