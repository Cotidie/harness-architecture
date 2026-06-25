# Iteration 7 (Structured intended-architecture layer) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (or subagent-driven-development). Steps use checkbox (`- [ ]`) syntax.

**Goal:** Move the intended layer from prose to structured data, so reconciliation and the signature gate can become a mechanical diff (intended-as-data vs observed) instead of prose judgment. This iteration ships the structured layer plus a committed, deterministic diff engine; the full mechanical gate-2 wiring stays iteration 9.

**Architecture:** Two new curated YAML artifacts under `.architecture/` (`contracts.yaml`, `domain-model.yaml`), one new committed Python tool (`scripts/intended_diff.py`) that extracts observed signatures via `ast` and diffs them against the YAML, its unit tests, a Surveyor-def change to emit the YAMLs, and an orchestrator step-0b wiring change. No change to the linter's domain/contracts/application/adapters behavior.

**Tech stack:** YAML artifacts; Python `ast` + stdlib `unittest` (mirrors `scripts/drift_scan.py` from iter 6); Markdown agent def + skill; `git`.

## Locked decisions (from planning forks, 2026-06-25)

- **Observed source = AST-based committed script.** A committed, unit-tested Python script extracts observed contract fields and domain method signatures with `ast` and diffs them against the YAML. Deterministic, no MCP dependency, runnable in a gate. This is iteration 6's explicit lesson (commit the scan, do not re-improvise it). CodeGraph-fed observed for polyglot is deferred to iter 9; this slice is Python-only, which is fine (polyglot enforcement is iter 9 anyway).
- **Both schemas now; `contracts.yaml` real, `domain-model.yaml` near-empty.** Self-host has zero domain classes (the linter is adapters/application/contracts only), so `domain-model.yaml` is defined and valid but holds no entries. `contracts.yaml` is seeded from the three real contracts and is the genuine dogfood target.
- **YAML + diff script + Surveyor this iteration; Architect rewiring deferred.** Author the schemas/files, the diff script, and update the Surveyor to emit structured. The Architect's patch sections 7-8 becoming structured diffs is a follow-up, not in this slice.
- **Prose keeps rules, drops definitions.** `data-contracts.md` and `domain-model.md` shrink to their intended-rules narrative; the per-class definitions move to the YAML. No prose/data duplication; the rules stay human-readable.

## Global Constraints

- Do not change the linter's behavior or its domain/contracts/application/adapters code. This is intended-layer + tooling work, not a feature.
- `architecture.md` and `boundaries.yaml` are unchanged. Narrative stays prose; only contract/domain definitions go structured. `boundaries.yaml` was already structured data.
- The intended YAML is a **curated seam**, not a 1:1 dump of code. Do NOT auto-generate it from every class (that recreates the forbidden full index and couples intended to observed). Contracts are the boundary-crossing seam, so `contracts.yaml` covers all contract classes; `domain-model.yaml` covers only key domain classes.
- The diff is **surfaced, never an auto-block**, this iteration (same posture as the iter-6 drift scan). Mechanical gate-2 integration is iter 9.
- Never use em-dash in authored content.

## File structure

- Create `.architecture/contracts.yaml` : intended contracts as data (Task 1).
- Create `.architecture/domain-model.yaml` : intended domain classes as data, empty for self-host (Task 1).
- Modify `.architecture/data-contracts.md`, `.architecture/domain-model.md` : shrink to rules-only narrative (Task 1).
- Create `scripts/intended_diff.py` : the ast-based intended-vs-observed diff (Task 2).
- Create `tests/test_intended_diff.py` : its unit tests (Task 2).
- Modify `.claude/skills/harness-feature/SKILL.md` : add the intended-diff check to step 0b; reconciliation reads the YAML as data (Task 3).
- Modify `.claude/agents/surveyor.md` : emit the two YAMLs; write the prose files rules-only (Task 4).
- Save `docs/iteration/08-iteration-7-structured-intended-plan.md` (this file) + a results note (Task 5).

---

### Task 1: Author the structured intended layer

**Files:** Create `.architecture/contracts.yaml`, `.architecture/domain-model.yaml`; modify `.architecture/data-contracts.md`, `.architecture/domain-model.md`

- [ ] **Step 1: Define and write `contracts.yaml`.** One entry per boundary-crossing contract under `src/contracts/`. Schema per entry: `name` (class), `layer` (e.g. contracts), `module` (file path under `src/contracts/`), `crosses` (the boundary it crosses, prose), `fields` (mapping of field name to its type annotation **exactly as the code writes it**, e.g. `Tuple[str, ...]`). Seed from the three real contracts: `ModuleRule`, `ImportEdge`, `BoundaryViolation`. For `BoundaryViolation`, record the `rule_kind` value set in a `notes` line (it is an accepted-value expansion, not a field).
- [ ] **Step 2: Define and write `domain-model.yaml`.** Schema per entry: `name`, `layer`, `module`, `responsibility`, `invariants` (list), `methods` (mapping of public method name to its signature string). Self-host has no domain classes, so write `domain_classes: []` with a header comment documenting the schema so the format is provable and the diff is exercisable once a domain class lands.
- [ ] **Step 3: Shrink `data-contracts.md` to rules-only.** Remove the "Official data contracts" definitions block (now in `contracts.yaml`). Keep the "Intended rules" and "Raw-payload risks" narrative. Add a one-line pointer: "Per-contract definitions live in `contracts.yaml`; this file states the intended rules."
- [ ] **Step 4: Shrink `domain-model.md` to rules-only.** Remove the "Intended domain classes" placeholder list (now `domain-model.yaml`). Keep "Invariants to preserve", "Rules", "Refactor candidates" narrative. Add the same pointer line to `domain-model.yaml`.
- [ ] **Step 5: Verify** both YAML files parse (`python -c "import yaml; yaml.safe_load(open('.architecture/contracts.yaml')); yaml.safe_load(open('.architecture/domain-model.yaml'))"`); the contract entries match the field names/types in `src/contracts/boundaries/*.py`; no em-dash anywhere.
- [ ] **Step 6: Commit.** `git add .architecture/contracts.yaml .architecture/domain-model.yaml .architecture/data-contracts.md .architecture/domain-model.md && git commit -m "feat(iter-7): structured intended layer (contracts.yaml + domain-model.yaml); prose keeps rules only"`

### Task 2: Build the committed ast-based intended-vs-observed diff

**Files:** Create `scripts/intended_diff.py`, `tests/test_intended_diff.py`

Mirror `scripts/drift_scan.py`: a `compute_*` function returning a frozen report dataclass, a `format_report`, and a `main(argv)` that exits 1 on drift / 0 ALIGNED. No MCP, no network; pure `ast` over the source tree.

- [ ] **Step 1: Observed-contract extractor.** Walk `src/contracts/**/*.py` with `ast`. For each `ClassDef` decorated with `dataclass` (handle both `@dataclass` and `@dataclass(frozen=True)`: a decorator that is a `Name` or a `Call` whose func is a `Name`/`Attribute` named `dataclass`), collect `{field_name: annotation_string}` from its `AnnAssign` statements (`ast.unparse` the annotation, whitespace-normalized). Key the result by class name.
- [ ] **Step 2: Observed-domain extractor.** Walk `src/domain/**/*.py`. For each `ClassDef`, collect public methods (name not starting with `_`) and their signature string (`ast.unparse` of the `arguments` plus the return annotation). Empty tree yields an empty map.
- [ ] **Step 3: Contract diff (strict, both directions).** For each `contracts.yaml` entry: class must exist in the observed map; declared `fields` must match observed exactly (missing field, extra observed field, or type-string mismatch = drift). A contract class observed under `src/contracts/` but absent from `contracts.yaml` = drift (the contract seam must be complete). Collect into the report.
- [ ] **Step 4: Domain diff (one-directional, lenient).** For each `domain-model.yaml` entry: class must exist; each declared method signature must match the observed signature (mismatch or missing = drift). A domain class observed but not in the YAML is **info, not drift** (the domain YAML curates key classes only). Empty `domain_classes` is trivially ALIGNED.
- [ ] **Step 5: Report + exit contract.** `DriftReport`-style frozen dataclass with `missing_classes`, `field_mismatches`, `undeclared_contracts`, `signature_mismatches`, `info_only` lists and a `has_drift` property (true if any strict-drift list is non-empty). `format_report` prints a markdown section per category and a verdict. `main(argv)`: usage `python -m scripts.intended_diff <src_dir> <contracts.yaml> <domain-model.yaml>`; print the report; return 1 if `has_drift` else 0.
- [ ] **Step 6: Tests** (`tests/test_intended_diff.py`, follow `tests/test_drift_scan.py` temp-tree style): (a) the real repo (`src`, the two committed YAMLs) reports ALIGNED, exit 0; (b) a planted field rename on a contract YAML entry -> field_mismatch drift; (c) a planted type change -> field_mismatch drift; (d) a contract class in code absent from YAML -> undeclared_contracts drift; (e) empty `domain_classes` -> ALIGNED; (f) a planted domain entry with a wrong method signature -> signature_mismatch drift.
- [ ] **Step 7: Verify** `python -m unittest tests.test_intended_diff` passes; `python -m scripts.intended_diff src .architecture/contracts.yaml .architecture/domain-model.yaml` exits 0 on the current repo; full suite `python -m unittest discover -s tests` still green; no em-dash.
- [ ] **Step 8: Commit.** `git add scripts/intended_diff.py tests/test_intended_diff.py && git commit -m "feat(iter-7): committed ast-based intended-vs-observed diff (contracts + domain), unit-tested"`

### Task 3: Wire the diff into the orchestrator and reconciliation

**Files:** Modify `.claude/skills/harness-feature/SKILL.md`

- [ ] **Step 1: Add the intended-diff to step 0b.** Alongside the linter self-check and `drift_scan`, add a third check: `python -m scripts.intended_diff src .architecture/contracts.yaml .architecture/domain-model.yaml`, reporting any intended-vs-observed drift. It is deterministic from source (no CodeGraph query), so it is not metered. Surface its output; do not auto-block (same posture as `drift_scan`).
- [ ] **Step 2: Reconciliation reads the YAML as data.** In the step-1 (Architect) and step-5 (Inspector) descriptions, note that the intended contract/domain definitions now live in `contracts.yaml` / `domain-model.yaml` (data), and the prose `.md` files hold only the intended rules. The agents read the YAML for definitions and the prose for rules. (The Architect's patch sections 7-8 emitting structured diffs is a deferred follow-up, called out in the deferred list below.)
- [ ] **Step 3: Write the diff output to `.architecture/validation/`** when step 0b runs (e.g. append an `intended-diff` section to the drift-scan record, or a sibling file), so the structured-drift result is a reviewable artifact like the drift scan.
- [ ] **Step 4: Verify** the skill names all three step-0b checks and states the diff is unmetered/surfaced-only; no em-dash.
- [ ] **Step 5: Commit.** `git add .claude/skills/harness-feature/SKILL.md && git commit -m "feat(iter-7): orchestrator runs intended-vs-observed diff in step 0b; reconciliation reads structured intended layer"`

### Task 4: Surveyor emits the structured layer

**Files:** Modify `.claude/agents/surveyor.md`

- [ ] **Step 1: Update the outputs list.** Add `contracts.yaml` and `domain-model.yaml` to the Surveyor's written artifacts, with their schemas (from Task 1). The Surveyor seeds them from its CodeGraph observation (the curated seam: all boundary-crossing contracts, key domain classes), within the same 1-2 query budget; a human curates/trims afterward.
- [ ] **Step 2: Update the prose-file instructions.** `data-contracts.md` and `domain-model.md` are now written rules-only (intended rules + risks narrative), not per-class definitions. State the curated-seam guardrail explicitly: do NOT dump every class; emit the seam worth preserving, trimmed.
- [ ] **Step 3: Verify** the Surveyor def lists nine artifacts (the seven prior + the two YAML), states the seam guardrail, keeps the 1-2 query budget and `QUERIES_USED=` line; no em-dash.
- [ ] **Step 4: Commit.** `git add .claude/agents/surveyor.md && git commit -m "feat(iter-7): surveyor emits contracts.yaml + domain-model.yaml; prose files rules-only"`

### Task 5: Dogfood and record results

**Files:** Create a results note (e.g. append a `## Results` section to this file, matching the iter-6 plan doc)

- [ ] **Step 1: Run the diff on the clean repo.** Confirm ALIGNED, exit 0. Record the contract entries diffed.
- [ ] **Step 2: Plant a mismatch and confirm detection.** Temporarily rename a `ModuleRule` field in `contracts.yaml` (or change a type), run the diff, confirm it reports the drift deterministically (not by prose reading), then revert. This is the roadmap's headline testable condition.
- [ ] **Step 3: Adversarial / cli-user-test pass** on `intended_diff` (use the `cotidie:cli-user-test` skill): malformed YAML, missing file, a `src` with no contracts, an extra undeclared contract, a `dataclass(frozen=True)` vs bare `@dataclass`. Record what breaks or behaves unexpectedly.
- [ ] **Step 4: Write the results note** (what worked, findings, any remaining gaps) and fold lessons into the iteration-8 detailing when it comes. Note explicitly that domain remains unexercised on self-host (no domain classes) so domain-diff correctness is proven only by unit test, not dogfood.
- [ ] **Step 5: Commit** the results note.

## Testable conditions (iteration acceptance)

- `contracts.yaml` and `domain-model.yaml` exist, parse, and describe this repo's seam (contracts populated, domain empty-but-valid).
- `data-contracts.md` / `domain-model.md` hold rules only, no per-class definitions, with a pointer to the YAML.
- `python -m scripts.intended_diff src .architecture/contracts.yaml .architecture/domain-model.yaml` reports ALIGNED (exit 0) on current code.
- A planted intended-vs-code mismatch (renamed field, changed type, undeclared contract, wrong domain signature) is reported as drift by the script, deterministically, not by a model reading prose.
- The full test suite passes; the diff is wired into step 0b as a surfaced (non-blocking) check.

## Deferred (explicitly NOT in iteration 7)

- **Architect patch sections 7-8 as structured diffs** to the YAML (follow-up; this slice keeps the Architect emitting seam signatures as before, now informed by the YAML).
- **Mechanical gate-2 integration** (making gate 2 a deterministic diff instead of LLM judgment): iteration 9, reusing this iteration's extractor.
- **CodeGraph-fed observed extraction for polyglot** (TS/Java): iteration 9. This slice is Python-`ast` only.
- **Framework-aware schemas** (the convention profile shaping these YAML): iteration 8.

## Risks / open decisions

- **Type-string brittleness.** The contract diff compares annotation strings (`Tuple[str, ...]`), so a cosmetic re-spelling (`typing.Tuple` vs `Tuple`, `tuple` lowercase) reads as drift. Mitigation this iteration: author the YAML to match the code's exact idiom and whitespace-normalize only. A semantic type normalizer is out of scope (revisit if it proves noisy).
- **Domain unexercised on self-host.** With zero domain classes, the domain diff is proven only by unit test, never by dogfood, until a feature introduces a domain class. Accepted; called out in the results note.
- **Curated-seam discipline is a human judgment.** The guardrail against 1:1 generation lives in the Surveyor prose and human curation, not in a mechanical limit. If the YAML balloons, that is the signal to trim, not to add a cap.

---

## Results (executed 2026-06-25)

Built Tasks 1-5: structured intended layer (`contracts.yaml`, `domain-model.yaml`), the committed ast diff (`scripts/intended_diff.py` + 10 unit tests), orchestrator step-0b wiring, and the Surveyor-def change. 91 tests OK (was 81, +10).

**Outcome: iteration shipped.** `python -m scripts.intended_diff src .architecture/contracts.yaml .architecture/domain-model.yaml` reports ALIGNED (exit 0) on the current repo; both other step-0b checks (linter self-check, `drift_scan`) stay clean.

- **Contracts diffed for real:** the three contracts (`ModuleRule`, `ImportEdge`, `BoundaryViolation`) are declared in `contracts.yaml` and match the code's fields/types exactly. Strict both-directions: a renamed field, a changed type, an undeclared contract in code, and an extra observed field are all reported as drift (verified by planted mismatch + unit test).
- **Domain diff is genuinely dogfooded (plan premise corrected).** The plan assumed zero domain classes from the stale `domain-model.md`, but `src/domain/` has `BoundaryRuleSet` (the boundary-policy object). It is now curated in `domain-model.yaml` with its three public method signatures; the diff confirms they match the code, and a planted signature change is reported as drift. So the "domain unexercised on self-host" risk in the plan no longer holds. `BoundaryDecision` (a value object with no public methods) and private `_ModuleEntry` are correctly NOT drift (info-only / filtered).
- **Determinism:** the diff is `ast`-only, no CodeGraph, so it is committed, unit-tested, and unmetered, exactly the iteration-6 lesson applied. Detection is by the script, not by a model reading prose.

### Adversarial pass (cli-user-test style)

- planted field rename / type change / domain signature change -> each reported as the right drift category, exit 1;
- ALIGNED -> exit 0;
- malformed YAML, missing file -> clean `error:` on stderr, exit 2 (no traceback);
- too few args -> usage on stderr, exit 2;
- target dir with no `contracts/` subdir -> all declared contracts reported missing, exit 1;
- empty `contracts:` -> the three code contracts reported as undeclared, exit 1.

### Findings / remaining gaps

1. **Plan premise was wrong about domain emptiness** (corrected in commit `45e9f92`). Lesson: the prose `domain-model.md` had drifted ("no domain classes exist yet") from the actual code, which is exactly the prose-drift this iteration exists to kill. Structuring it surfaced the staleness immediately.
2. **Type-string brittleness is real but bounded.** Comparison is whitespace-normalized literal string match, so `Tuple` vs `tuple` vs `typing.Tuple` would read as drift. Acceptable this iteration; a semantic normalizer is out of scope and deferred.
3. **`BoundaryDecision` is a domain value object not yet curated** (info-only). If a future feature gives it behavior, curate it. The domain schema is method-centric, so a fields-only value object adds little to the diff today.
4. **Architect sections 7-8 still emit prose seam signatures**, now informed by the YAML but not yet structured diffs to it. Deferred follow-up, as planned.
