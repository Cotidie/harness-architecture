# Iteration 9a (CodeGraph-backed observed edges) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (or subagent-driven-development). Steps use checkbox (`- [ ]`) syntax.

**Goal:** Replace the Python-`ast` import extraction with a CodeGraph-index-backed observed-edge source, so the harness's boundary checking (the `harness_check` boundary check and `drift_scan`) reads import edges from CodeGraph: deterministic, committed, multi-language. This is the first half of the "one observed source" reframe (iter-9 split: 9a = edges, 9b = method-signature mechanical gate 2).

**Architecture:** A committed adapter (`scripts/codegraph_index.py`) reads `.codegraph/codegraph.db` (schema-version guarded) and yields observed import edges. A CodeGraph-backed scanner feeds those through the UNCHANGED domain `BoundaryRuleSet` to produce the existing `ScanResult` / `ImportEdge` contract. The harness checks (`harness_check` boundary check + `drift_scan`) switch to this source; the sample boundaries linter CLI keeps its `ast` scanner (it is the Python dogfood, not the harness). No change to the domain or to the `ImportEdge` contract.

**Tech stack:** Python stdlib `sqlite3` + `unittest`; the `codegraph` CLI (`sync`, `status --json`) for freshness; YAML for the profile.

## Spike result (gate, run 2026-06-25, recorded in the roadmap)

Confirmed BEFORE planning (the iteration-9 feasibility gate):

- CodeGraph stores, queryable deterministically: **import edges** (`import` nodes with filePath + imported name + line; `imports` edges) and **method/function signatures** (`signature` field, language-tagged). The signature string matches the iter-7 `ast` output.
- CodeGraph does NOT store **class field structure** (no field/property node kind; a class node carries only its line span; `contains` yields nothing for a dataclass). So contract field diffing stays `ast` (Python), out of scope here and in 9b.
- The CLI (`query`/`node`/`files --json`) is SEARCH-oriented, not a bulk exporter. Full-repo enumeration is clean against `codegraph.db` (`nodes` / `edges` tables), which also has a `schema_versions` table. **Decision: read the DB directly, guarded by the schema version**, so a CodeGraph upgrade fails loud rather than silently mis-reading.

## Locked decisions (from planning forks, 2026-06-25)

- **CodeGraph for edges (this slice) and method signatures (9b); contract fields stay `ast`.** Matches what the index actually holds.
- **Direct DB read, schema-version guarded.** Not the search-oriented CLI; not raw-and-unguarded. Read `codegraph.db`, assert `schema_versions` matches a pinned constant, fail loud otherwise.
- **The harness checks switch source; the sample linter CLI does not.** `harness_check`'s boundary check and `drift_scan` read CodeGraph edges (polyglot). `src/adapters/boundaries/cli.py` stays `ast` (it is the dogfood Python linter the harness built, not the harness).
- **Split:** 9a = edges (this plan); 9b = method-signature mechanical gate 2 + retire the LLM-judged gate 2.

## Global Constraints

- Do not change the domain `BoundaryRuleSet` or the `ImportEdge` / `ScanResult` contract. Only the OBSERVED source of edges changes; module mapping stays in the domain.
- The CodeGraph read is deterministic and local (no MCP, no LLM), so the harness check stays unmetered. Freshness is already gated by the orchestrator (`codegraph sync` + `status --json`) before any read.
- A missing or version-mismatched index is a could-not-run (exit 2 via the iter-8.5 aggregate), never a silent clean pass.
- Never use em-dash in authored content.

## File structure

- Create `scripts/codegraph_index.py` : the schema-guarded DB adapter (Task 2).
- Create `tests/test_codegraph_index.py` : adapter tests (Task 2).
- Create `scripts/codegraph_scanner.py` : the CodeGraph-backed `ScanResult` producer (Task 3).
- Create `tests/test_codegraph_scanner.py` : scanner tests (Task 3).
- Modify `scripts/drift_scan.py` and `scripts/harness_check.py` : use the CodeGraph scanner for the harness's observed edges (Task 4).
- Add a polyglot fixture under `examples/` + a test (Task 5).
- Save `docs/iteration/11-iteration-9a-codegraph-edges-plan.md` (this file) + a results note (Task 6).

---

### Task 1: Mini-spike: confirm CodeGraph indexes a non-Python file here

**Files:** none (investigation); record the outcome in the results note.

- [ ] **Step 1:** Add a throwaway non-Python file (e.g. `examples/_probe/a.ts` importing `./b`), run `codegraph sync`, and query it (`codegraph query --json` / inspect `nodes.language`).
- [ ] **Step 2: Decide the polyglot proof's language.** If CodeGraph indexes TS here, Task 5 uses a TS fixture. If it indexes only Python in this environment, 9a still ships the architecture proven on Python, and the polyglot fixture is recorded as documented-pending (the adapter is language-agnostic by construction; only the live proof waits on indexer support). Remove the probe file.
- [ ] **Step 3:** Record which languages CodeGraph actually indexes here, in the results note.

### Task 2: CodeGraph index adapter (TDD)

**Files:** Create `scripts/codegraph_index.py`, `tests/test_codegraph_index.py`

- [ ] **Step 1 (test first, RED):** with a hand-built tiny SQLite fixture matching the observed schema (`nodes`, `edges`, `schema_versions`): (a) `observed_import_edges` yields `(source_file, imported_name, line)` rows from the import data; (b) a missing DB file raises `CodegraphIndexError`; (c) an unrecognized `schema_versions` value raises `CodegraphIndexError`.
- [ ] **Step 2: Implement.** `CodegraphIndexError(Exception)`. `_check_schema(conn)` reads `schema_versions` (and/or `project_metadata`) and compares to a pinned `EXPECTED_SCHEMA` constant; mismatch or absence raises. `observed_import_edges(db_path=".codegraph/codegraph.db")` opens read-only, guards schema, and returns a list of `ImportObservation(source_file, imported_name, line)` (a small frozen dataclass) read from the `import` nodes (filePath, name, line) and/or `imports` edges. Open the DB read-only (`file:...?mode=ro` URI) so the check never mutates the index.
- [ ] **Step 3: GREEN** on the fixture; then a smoke assertion against the REAL `.codegraph/codegraph.db` (skip cleanly if absent) that it returns a non-empty edge list including a known self-host import. No em-dash.
- [ ] **Step 4: Commit.** `git add scripts/codegraph_index.py tests/test_codegraph_index.py && git commit -m "feat(iter-9a): schema-guarded CodeGraph index adapter (observed import edges)"`

### Task 3: CodeGraph-backed scanner producing ScanResult (TDD)

**Files:** Create `scripts/codegraph_scanner.py`, `tests/test_codegraph_scanner.py`

- [ ] **Step 1 (test first, RED):** given a fake edge source (inject a list of `ImportObservation`) and a `BoundaryRuleSet` built from a test `boundaries.yaml`, `scan_imports_from_index(...)` returns a `ScanResult` whose `edges` are `ImportEdge`s with the right `source_module` / `imported_module` (mapped by the domain rule set), and `matched_file_count` reflects the source files seen. Imports that map to no module are dropped, same as the ast scanner.
- [ ] **Step 2: Implement.** Reuse the domain `BoundaryRuleSet.module_for_path` for BOTH the source file and the imported dotted name (convert dotted name to a path the same way the ast scanner does), emitting `ImportEdge`. Keep the `ScanResult` contract identical (`edges`, `parse_failures`, `matched_file_count`). Parse failures are not applicable from the index (CodeGraph already parsed); return an empty list and note it.
- [ ] **Step 3: Dependency injection seam.** `scan_imports_from_index(rule_set, edges=None, db_path=...)`: if `edges` is None, read them via `codegraph_index.observed_import_edges(db_path)`; otherwise use the injected list. This is the seam the tests use and the harness wires.
- [ ] **Step 4: GREEN**; full suite green; no em-dash.
- [ ] **Step 5: Commit.** `git add scripts/codegraph_scanner.py tests/test_codegraph_scanner.py && git commit -m "feat(iter-9a): CodeGraph-backed scanner producing the ImportEdge/ScanResult contract"`

### Task 4: Point the harness checks at the CodeGraph source

**Files:** Modify `scripts/drift_scan.py`, `scripts/harness_check.py`

- [ ] **Step 1: drift_scan.** Let `compute_drift` get its observed edges from the CodeGraph scanner instead of `scan_imports` (ast). Keep the module/edge diff logic unchanged; only the edge source swaps. Preserve the existing function signature where possible (add an optional injectable edge source for tests).
- [ ] **Step 2: harness_check boundary check.** Replace `_run_linter`'s `scan_imports` (ast) with the CodeGraph scanner for the harness's boundary check, so `harness_check --only boundaries` is polyglot. The use-case (`LintBoundaries`) and the violation formatting are unchanged.
- [ ] **Step 3: Could-not-run mapping.** A `CodegraphIndexError` (missing/stale index) maps to the existing could-not-run path (status `error`, aggregate exit 2), so a missing index never reads as clean.
- [ ] **Step 4: Verify** the self-host `harness_check` is all-clean exit 0 using CodeGraph edges (after a `codegraph sync`); the planted-forbidden-edge proof still reports with file + line; full suite green; no em-dash.
- [ ] **Step 5: Commit.** `git add scripts/drift_scan.py scripts/harness_check.py && git commit -m "feat(iter-9a): harness boundary check + drift_scan read edges from CodeGraph (polyglot), sample linter stays ast"`

### Task 5: Polyglot proof

**Files:** Create a non-Python fixture under `examples/` + a test (language per Task 1)

- [ ] **Step 1:** Add the fixture in the language Task 1 confirmed (a tiny tree with a forbidden cross-module import) and a `boundaries.yaml` for it.
- [ ] **Step 2:** Ensure it is indexed (`codegraph sync`), then assert the CodeGraph-backed scanner + linter use-case reports the planted forbidden edge with the correct file + line, exit non-zero, same `ScanResult` shape as the Python path.
- [ ] **Step 3:** If Task 1 found CodeGraph does not index a non-Python language here, skip the live test with a clear `skipUnless` and record polyglot as documented-pending (architecture is language-agnostic; only the live proof waits on the indexer). Do not fake it.
- [ ] **Step 4: Commit.**

### Task 6: Dogfood and record results

- [ ] **Step 1:** `codegraph sync`; run `python -m scripts.harness_check` (now CodeGraph-backed for edges); confirm all-clean exit 0 and that the boundary + drift sections match the prior ast-based output (no regression).
- [ ] **Step 2:** Planted-forbidden-edge proof through the CodeGraph path (scratch file, sync, confirm drift + file:line, revert).
- [ ] **Step 3: Could-not-run proof:** point the adapter at a missing/garbage DB, confirm could-not-run (exit 2), no traceback.
- [ ] **Step 4: Adversarial / cli-user-test pass** on the adapter + scanner: empty edge set, an import to an unmapped module, a stale schema version, a DB locked by the daemon (read-only open should still work).
- [ ] **Step 5:** Write the results note (what worked, the indexed-languages finding, any gaps), commit.

## Testable conditions (iteration acceptance)

- `harness_check` and `drift_scan` derive observed import edges from `.codegraph/codegraph.db`, not `ast`, with a schema-version guard.
- Self-host `harness_check` stays all-clean exit 0 and matches the prior ast output (no regression); a planted forbidden edge is reported with file + line through the CodeGraph path.
- A missing or version-mismatched index is a could-not-run (exit 2), never a silent clean pass.
- The polyglot proof passes on a non-Python fixture, OR is recorded as documented-pending with a clean `skipUnless` if CodeGraph does not index that language in this environment.
- The sample linter CLI is unchanged (still `ast`); the domain `BoundaryRuleSet` and `ImportEdge` contract are unchanged.

## Deferred

- **9b: method-signature mechanical gate 2.** Read method/function `signature` from CodeGraph, diff against the patch's declared seam signatures deterministically, and retire the LLM-judged gate 2. Same DB adapter, extended to signatures.
- **Contract field diffing stays `ast`** (Python). The index has no field nodes; revisit only if CodeGraph adds field indexing.
- **Packaging (iter 10):** the cross-repo launch form and the artifact-set dependency.

## Risks / open decisions

- **Schema coupling.** Reading `codegraph.db` couples to its schema. Mitigation: the pinned-version guard fails loud on drift; the read is small (two tables, a few columns). If CodeGraph ships a stable export/CLI bulk dump later, swap the adapter's internals behind the same `observed_import_edges` function.
- **Polyglot proof depends on the indexer.** If CodeGraph does not index a second language in this environment, the live polyglot claim is deferred (Task 1 decides). The architecture does not change either way.
- **Daemon / lock contention.** The index DB may be open by the CodeGraph daemon. Open read-only and tolerate concurrent reads; surface any lock error as could-not-run, not a crash.

---

## Results (executed 2026-06-25 / 2026-06-26)

Built Tasks 1-6. 116 tests OK (was 115 at iter-8.5 merge; +8 new across adapter/scanner/polyglot, net of the harness_check tests switching to injected ast). The harness's boundary checking now reads observed import edges from the CodeGraph index; the sample linter CLI is unchanged (`ast`).

**Outcome: iteration shipped, polyglot proven live.**

- **Mini-spike (Task 1):** CodeGraph indexes TypeScript and Go here, not only Python. `imports` edges resolve source-file -> target-file for 103/103 edges, so the observation is `(source_file, target_file, line)`: language-agnostic, no dotted-vs-relative import parsing. DB schema captured; pinned `schema_versions` max = 5.
- **Adapter (Task 2):** `scripts/codegraph_index.py` reads `codegraph.db` READ-ONLY, guards the schema version (loud `CodegraphIndexError` on mismatch/missing), and yields deduped cross-file import edges (self-edges dropped).
- **Scanner (Task 3):** `scripts/codegraph_scanner.py` maps both files of each edge to modules via the UNCHANGED domain `BoundaryRuleSet`, emitting the same `ImportEdge` / `ScanResult` contract. Dependency-injection seam (`edges=...`) for tests.
- **Wiring (Task 4):** `harness_check`'s boundary check and `drift_scan` take an injected `scan_fn`, defaulting to the CodeGraph scanner (production) and overridable to `ast` (the temp-tree aggregation tests). `CodegraphIndexError` joins the could-not-run set, so a missing/stale index is exit 2, never a silent clean pass. Self-host `harness_check` stays all-clean exit 0 and matches the prior ast output; a planted forbidden edge is flagged through the CodeGraph path (after `codegraph sync`) with correct file:line.
- **Polyglot proof (Task 5):** `examples/ts-mini/` (TypeScript) with a forbidden `domain -> adapters` import. `tests/test_polyglot_boundary.py` reads the real index and asserts the boundary use case flags it with the `.ts` file + line, same contract as Python. Passes here; `skipUnless` keeps it honest where the fixture is not yet indexed.

### Adversarial pass (cli-user-test style)

- missing index, non-sqlite garbage file, stale schema version (999) -> loud `CodegraphIndexError`, mapped to could-not-run (exit 2);
- empty edge set -> empty `ScanResult`, no crash;
- self-host no-regression: `harness_check` exit 0 with ts-mini also indexed (ts-mini edges map to no `src` module, so they are ignored).

### Findings / gaps

1. **Freshness is load-bearing now.** The CodeGraph path only sees edges after `codegraph sync` (the planted-edge proof needed a sync). The orchestrator already gates `sync` + `status --json` before checks, so this holds in the loop, but a manual `harness_check` against a stale index reports stale edges. Documented; the orchestrator's freshness gate is the control.
2. **`matched_file_count` comes from edges, not file nodes.** A mapped file with zero imports is not counted (it has no import edge). The loud-fail guard still catches a total glob/layout mismatch (zero mapped sources). A future refinement could count from `kind='file'` nodes; out of scope for 9a.
3. **Contract field diffing still `ast` (Python).** Unchanged: the index has no field nodes. Edges and (in 9b) method signatures are the CodeGraph wins.

### 9b (next)

Read method/function `signature` from the same adapter, make gate 2 a deterministic signature diff, and retire the LLM-judged gate 2.
