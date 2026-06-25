# Iteration 9b: CodeGraph-backed signatures + mechanical gate 2

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Read domain method/function signatures from the CodeGraph index (not Python `ast`), make the intended-vs-observed signature diff polyglot and deterministic, and retire the Inspector's LLM-judged gate 2 in favor of that deterministic check.

**Architecture:** Iteration 9a moved the *dependency* observation to a schema-guarded CodeGraph adapter. 9b does the same for *signatures*: a new `observed_signature_nodes` read in `codegraph_index.py` feeds a `observed_domain_from_index` mapper in `codegraph_scanner.py`, which `intended_diff.compute_diff` consumes through an injectable seam (default CodeGraph, ast injected for un-indexed temp-tree tests, exactly like 9a's `scan_imports_fn`). Contract *field* diffing stays `ast` (the index has no reliable field nodes). With the signature diff now deterministic and language-agnostic, the Inspector's gate 2 stops being an LLM judgment over a `codegraph_explore` query and instead reads the committed check's verdict.

**Tech Stack:** Python stdlib (`sqlite3`, `re`, `ast`, `dataclasses`), `pyyaml`. Tests via `python -m unittest`.

## Global Constraints

- No em-dash (`—`) anywhere. Use a comma, colon, parentheses, or period.
- No `Co-Authored-By` trailer in commit messages. Branch is `iter9b-codegraph-signatures` (cut from `iter9a-codegraph-edges` if not merged, else from `main`).
- The CodeGraph DB is read **read-only** (`file:<path>?mode=ro`) and **schema-guarded**: reuse `codegraph_index.EXPECTED_SCHEMA` (currently `5`) and `_check_schema`; a mismatch raises `CodegraphIndexError`.
- The index has **no reliable field nodes**: contract field diffing stays `ast`. Only the *domain method signature* half moves to CodeGraph.
- A missing or stale index is a could-not-run condition (`CodegraphIndexError`), already mapped to exit 2 by `harness_check`. Do not add a silent ast fallback.
- Tests run on un-indexed temp trees, so every CodeGraph-default seam takes an injectable observer; temp-tree tests inject the `ast` observer.
- Test command throughout: `python -m unittest discover -s tests -q` (full suite) or `python -m unittest tests.<module> -v` (one module). `pytest` is NOT installed.
- Run `python -m unittest discover -s tests -q` green before every commit.

---

### Task 1: CodeGraph signature-node read

**Files:**
- Modify: `scripts/codegraph_index.py`
- Test: `tests/test_codegraph_index.py`

**Interfaces:**
- Consumes: existing `_connect_ro`, `_check_schema`, `EXPECTED_SCHEMA`, `CodegraphIndexError` in `scripts/codegraph_index.py`.
- Produces:
  ```python
  @dataclass(frozen=True)
  class SignatureNode:
      qualified_name: str  # "BoundaryRuleSet::module_for_path" for a method; bare "scan_imports" for a free function
      name: str            # "module_for_path"
      kind: str            # "method" | "function"
      signature: str       # raw, e.g. "(self, path: str) -> Optional[str]"
      file_path: str       # repo-relative, e.g. "src/domain/boundaries/boundary_rule_set.py"
      language: str        # e.g. "python", "typescript"

  def observed_signature_nodes(db_path: str = ".codegraph/codegraph.db") -> Tuple[SignatureNode, ...]: ...
  ```

- [ ] **Step 1: Write the failing test**

Add to `tests/test_codegraph_index.py` (it already imports from `scripts.codegraph_index` and points `REAL_DB` at the repo index; mirror that style):

```python
def test_observed_signature_nodes_reads_methods_with_signatures(self):
    from scripts.codegraph_index import observed_signature_nodes, SignatureNode
    nodes = observed_signature_nodes(REAL_DB)
    self.assertTrue(all(isinstance(n, SignatureNode) for n in nodes))
    # the known domain method is present, with its class via qualified_name and a real signature
    match = [
        n for n in nodes
        if n.qualified_name == "BoundaryRuleSet::module_for_path"
    ]
    self.assertEqual(len(match), 1, match)
    n = match[0]
    self.assertEqual(n.kind, "method")
    self.assertIn("path: str", n.signature)
    self.assertTrue(n.file_path.endswith("boundary_rule_set.py"))
    self.assertEqual(n.language, "python")

def test_observed_signature_nodes_schema_guard(self):
    import scripts.codegraph_index as ci
    saved = ci.EXPECTED_SCHEMA
    ci.EXPECTED_SCHEMA = 999
    try:
        with self.assertRaises(ci.CodegraphIndexError):
            ci.observed_signature_nodes(REAL_DB)
    finally:
        ci.EXPECTED_SCHEMA = saved
```

(If `REAL_DB` existence is guarded by a `skipUnless` in this file, reuse the same guard decorator on `test_observed_signature_nodes_reads_methods_with_signatures`; the schema-guard test needs the DB too, so guard it the same way.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_codegraph_index -v`
Expected: FAIL with `ImportError: cannot import name 'observed_signature_nodes'`.

- [ ] **Step 3: Write minimal implementation**

In `scripts/codegraph_index.py`, add `Tuple` to the typing import, then add:

```python
@dataclass(frozen=True)
class SignatureNode:
    qualified_name: str
    name: str
    kind: str
    signature: str
    file_path: str
    language: str


_SIGNATURE_SQL = """
SELECT qualified_name, name, kind, signature, file_path, language
FROM nodes
WHERE kind IN ('method', 'function')
  AND signature IS NOT NULL
  AND file_path IS NOT NULL
"""


def observed_signature_nodes(db_path: str = ".codegraph/codegraph.db") -> Tuple[SignatureNode, ...]:
    """Read method/function signatures from the CodeGraph index, schema-guarded
    and read-only. `qualified_name` carries `Class::method` (the language-neutral
    separator CodeGraph uses); a free function has a bare qualified name. The
    caller groups by class and maps `file_path` to a layer."""
    conn = _connect_ro(db_path)
    try:
        _check_schema(conn)
        rows = conn.execute(_SIGNATURE_SQL).fetchall()
    finally:
        conn.close()
    return tuple(
        SignatureNode(
            qualified_name=qn,
            name=name,
            kind=kind,
            signature=sig,
            file_path=fp,
            language=lang or "",
        )
        for qn, name, kind, sig, fp, lang in rows
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_codegraph_index -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/codegraph_index.py tests/test_codegraph_index.py
git commit -m "feat(iter-9b): schema-guarded CodeGraph read of method/function signatures"
```

---

### Task 2: Domain-signature mapper + signature normalizer

**Files:**
- Modify: `scripts/codegraph_scanner.py`
- Test: `tests/test_codegraph_scanner.py`

**Interfaces:**
- Consumes: `observed_signature_nodes`, `SignatureNode` from Task 1.
- Produces:
  ```python
  def normalize_signature(sig: str) -> str: ...
  # collapses whitespace and strips a leading self/cls receiver so the
  # comparison is language-neutral and method/free-function symmetric.

  def observed_domain_from_index(
      domain_dir: str,
      nodes: Optional[Tuple[SignatureNode, ...]] = None,
      db_path: str = ".codegraph/codegraph.db",
  ) -> Dict[str, Dict[str, str]]: ...
  # {ClassName: {method_name: normalized_signature}} for methods whose file is
  # under domain_dir. Free functions (no "::" in qualified_name) are skipped:
  # the domain seam is class methods. `nodes` overridable for tests.
  ```

- [ ] **Step 1: Write the failing test**

Add to `tests/test_codegraph_scanner.py`:

```python
def test_normalize_signature_strips_self_and_collapses_space(self):
    from scripts.codegraph_scanner import normalize_signature
    self.assertEqual(
        normalize_signature("(self,  path: str)  -> Optional[str]"),
        "(path: str) -> Optional[str]",
    )
    self.assertEqual(normalize_signature("(self)"), "()")
    self.assertEqual(normalize_signature("(cls, x: int)"), "(x: int)")
    # a free function with a leading non-receiver arg is untouched (besides spacing)
    self.assertEqual(normalize_signature("(rules:  Iterable)"), "(rules: Iterable)")

def test_observed_domain_from_index_groups_methods_by_class(self):
    from scripts.codegraph_index import SignatureNode
    from scripts.codegraph_scanner import observed_domain_from_index
    nodes = (
        SignatureNode("Foo::bar", "bar", "method", "(self, x: int) -> int",
                      "src/domain/foo.py", "python"),
        SignatureNode("Foo::_hidden", "_hidden", "method", "(self)",
                      "src/domain/foo.py", "python"),
        SignatureNode("free_fn", "free_fn", "function", "(a: int)",
                      "src/domain/foo.py", "python"),
        SignatureNode("Other::baz", "baz", "method", "(self)",
                      "src/adapters/other.py", "python"),
    )
    result = observed_domain_from_index("src/domain", nodes=nodes)
    self.assertEqual(result, {"Foo": {"bar": "(x: int) -> int", "_hidden": "()"}})
    # adapters file excluded by domain_dir; free function excluded (no "::")
    self.assertNotIn("Other", result)
    self.assertNotIn("free_fn", result.get("Foo", {}))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_codegraph_scanner -v`
Expected: FAIL with `ImportError: cannot import name 'normalize_signature'`.

- [ ] **Step 3: Write minimal implementation**

In `scripts/codegraph_scanner.py` add `import re`, `import os`, the typing imports (`Dict`, `Optional`, `Tuple`), and import `SignatureNode`, `observed_signature_nodes` from `scripts.codegraph_index`. Then:

```python
_RECEIVER_WITH_ARGS = re.compile(r"^\(\s*(?:self|cls)\s*,\s*")
_RECEIVER_ONLY = re.compile(r"^\(\s*(?:self|cls)\s*\)")


def normalize_signature(sig: str) -> str:
    """Whitespace-collapse and drop a leading self/cls receiver so a method and
    a same-shape free function compare equal, and so the declared YAML need not
    spell the receiver. Type strings are otherwise compared literally."""
    s = " ".join(sig.split())
    s = _RECEIVER_WITH_ARGS.sub("(", s)
    s = _RECEIVER_ONLY.sub("()", s)
    return s


def observed_domain_from_index(domain_dir, nodes=None, db_path=".codegraph/codegraph.db"):
    """Map CodeGraph signature nodes under `domain_dir` to {class: {method: sig}}.
    Methods only (qualified_name contains '::'); free functions are not seam."""
    if nodes is None:
        nodes = observed_signature_nodes(db_path)
    prefix = os.path.normpath(domain_dir)
    out = {}
    for node in nodes:
        if "::" not in node.qualified_name:
            continue
        if os.path.normpath(node.file_path).startswith(prefix + os.sep) or \
                os.path.normpath(node.file_path) == prefix:
            class_name, _, method = node.qualified_name.partition("::")
            out.setdefault(class_name, {})[method] = normalize_signature(node.signature)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_codegraph_scanner -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/codegraph_scanner.py tests/test_codegraph_scanner.py
git commit -m "feat(iter-9b): CodeGraph-backed domain signature map + receiver-stripping normalizer"
```

---

### Task 3: intended_diff reads signatures through an injectable seam

**Files:**
- Modify: `scripts/intended_diff.py`
- Test: `tests/test_intended_diff.py`

**Interfaces:**
- Consumes: `observed_domain_from_index`, `normalize_signature` from Task 2.
- Produces: `compute_diff(target_dir, contracts_file, domain_file, observe_domain_fn=_default_domain_observer)` where `observe_domain_fn(domain_dir) -> Dict[str, Dict[str, str]]`. Default reads CodeGraph; the `ast` observer `_observed_domain` is retained for injection. Both observers and the declared side are normalized through `normalize_signature`, so signatures are compared post-normalization on every path.

- [ ] **Step 1: Write the failing test**

The existing `tests/test_intended_diff.py` builds temp trees and calls `compute_diff`. Those calls now hit the CodeGraph default (no index in a temp tree). Update them to inject the ast observer, and add a test that the seam is honored. At the top of the test module import the ast observer:

```python
from scripts.intended_diff import compute_diff, _observed_domain
```

Add this test (and, in Step 3's wiring, update every existing `compute_diff(...)` call in this file to pass `observe_domain_fn=_observed_domain`):

```python
def test_domain_observer_seam_flags_signature_drift(self):
    # declared says module_for_path takes (path: str); code says (path: int) -> drift
    with _tree(self._files(domain_method_sig="(self, path: int) -> Optional[str]")) as root:
        report = compute_diff(
            os.path.join(root, "src"),
            os.path.join(root, ".architecture", "contracts.yaml"),
            os.path.join(root, ".architecture", "domain-model.yaml"),
            observe_domain_fn=_observed_domain,
        )
    self.assertTrue(report.has_drift)
    self.assertTrue(
        any("module_for_path" in m for m in report.signature_mismatches),
        report.signature_mismatches,
    )
```

(Use this file's existing temp-tree helper; if its helper does not already parametrize the domain method body, write the domain source inline so the observed signature is `(self, path: int) -> Optional[str]` while `domain-model.yaml` declares `(path: str) -> Optional[str]`. The point is: same method name, different type, observed via the injected ast observer.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_intended_diff -v`
Expected: FAIL (`compute_diff()` has no `observe_domain_fn` argument).

- [ ] **Step 3: Write minimal implementation**

In `scripts/intended_diff.py`:

1. Import the seam: `from scripts.codegraph_scanner import normalize_signature, observed_domain_from_index`.
2. Make the ast observer normalize, so the injected path matches the CodeGraph path. In `_observed_domain`, change the stored value to normalized:
   ```python
   methods[stmt.name] = normalize_signature(_format_signature(stmt))
   ```
3. Add the default observer and the new parameter:
   ```python
   def _default_domain_observer(domain_dir):
       return observed_domain_from_index(domain_dir)


   def compute_diff(target_dir, contracts_file, domain_file,
                    observe_domain_fn=_default_domain_observer):
       ...
       observed_domain = observe_domain_fn(domain_dir)
       ...
   ```
4. Normalize the declared method signatures before comparison:
   ```python
   declared_methods = {
       method: normalize_signature(str(sig))
       for method, sig in (entry.get("methods") or {}).items()
   }
   ```
   Leave contract field handling (`_observed_contracts`, declared `fields`) on `ast` and `_norm` exactly as is.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_intended_diff -v`
Expected: PASS (all tests in the module, including the updated injected-observer calls).

- [ ] **Step 5: Commit**

```bash
git add scripts/intended_diff.py tests/test_intended_diff.py
git commit -m "feat(iter-9b): intended_diff domain signatures via injectable observer (CodeGraph default, ast for tests)"
```

---

### Task 4: Re-curate domain-model.yaml to the normalized rendering

**Files:**
- Modify: `.architecture/domain-model.yaml`
- Modify: `tests/test_intended_diff.py` if it asserts on the old self-bearing strings (only if needed).

**Interfaces:** none new. This task makes the real-repo CodeGraph default report ALIGNED.

- [ ] **Step 1: See the current mismatch**

Run: `python -m scripts.intended_diff src .architecture/contracts.yaml .architecture/domain-model.yaml`
Expected: exit 1 if any declared signature differs from the normalized CodeGraph rendering (e.g. a `self` that survives, a quoted `'BoundaryRuleSet'` return vs the index rendering). Read the `## Domain signature mismatches` block.

- [ ] **Step 2: Update the declared signatures**

Edit `.architecture/domain-model.yaml` so each `methods:` value equals the normalized CodeGraph rendering reported in Step 1 (receiver stripped, whitespace collapsed). Update the header comment line that says signatures are written "EXACTLY as the code spells it (ast-unparsed)" to: "written as the normalized CodeGraph rendering (receiver stripped, whitespace collapsed); see scripts/codegraph_scanner.normalize_signature."

- [ ] **Step 3: Verify ALIGNED**

Run: `python -m scripts.intended_diff src .architecture/contracts.yaml .architecture/domain-model.yaml`
Expected: exit 0, `ALIGNED`.

- [ ] **Step 4: Full suite**

Run: `python -m unittest discover -s tests -q`
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add .architecture/domain-model.yaml tests/test_intended_diff.py
git commit -m "chore(iter-9b): re-curate domain-model.yaml to normalized CodeGraph signature rendering"
```

---

### Task 5: harness_check plumbs the domain observer; temp-tree tests inject ast

**Files:**
- Modify: `scripts/harness_check.py`
- Test: `tests/test_harness_check.py`

**Interfaces:**
- Consumes: `compute_diff(..., observe_domain_fn=...)` from Task 3.
- Produces: `compute_results(repo_root=".", only=None, scan_fn=_codegraph_scan, observe_domain_fn=None)`. When `observe_domain_fn` is `None`, `_intended()` calls `compute_diff` with its CodeGraph default; tests pass the ast observer. Mirrors the `scan_fn` plumbing added in 9a.

- [ ] **Step 1: Write the failing test**

The temp-tree tests in `tests/test_harness_check.py` already pass `scan_fn=scan_imports`. They will now break because `_intended` hits the CodeGraph default on an un-indexed temp tree. At the top of the test module import the ast domain observer:

```python
from scripts.intended_diff import _observed_domain
```

Update the helper or each temp-tree `compute_results(...)` call to also pass `observe_domain_fn=_observed_domain`, and add:

```python
def test_temp_tree_intended_diff_uses_injected_domain_observer(self):
    with _tree(_harness_files()) as root:
        results = compute_results(
            root, scan_fn=scan_imports, observe_domain_fn=_observed_domain
        )
    diff = _by_name(results, "intended_diff")
    self.assertIn(diff.status, ("clean", "drift"))
    self.assertNotEqual(diff.status, "error", diff)
```

(The real-repo test `test_real_repo_all_clean` keeps the CodeGraph default for both `scan_fn` and `observe_domain_fn`, proving the production path.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_harness_check -v`
Expected: FAIL (`compute_results()` has no `observe_domain_fn` argument), and/or the existing temp-tree tests error with `CodegraphIndexError` in `intended_diff`.

- [ ] **Step 3: Write minimal implementation**

In `scripts/harness_check.py`, add the parameter and thread it into `_intended`:

```python
def compute_results(repo_root=".", only=None, scan_fn=_codegraph_scan,
                    observe_domain_fn=None):
    ...
    def _intended():
        kwargs = {}
        if observe_domain_fn is not None:
            kwargs["observe_domain_fn"] = observe_domain_fn
        report = compute_diff(
            paths.source_dir, paths.contracts, paths.domain_model, **kwargs
        )
        return ("drift" if report.has_drift else "clean"), format_diff(report)
```

Leave `main()` calling `compute_results(args.repo_root, only=only)` so the CLI uses the CodeGraph default.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_harness_check -v` then `python -m unittest discover -s tests -q`
Expected: PASS / `OK`.

- [ ] **Step 5: Sanity-run the real entrypoint**

Run: `python -m scripts.harness_check`
Expected: `intended_diff: CLEAN` (domain signatures now read from CodeGraph), `ALL CLEAN`, exit 0.

- [ ] **Step 6: Commit**

```bash
git add scripts/harness_check.py tests/test_harness_check.py
git commit -m "feat(iter-9b): harness_check plumbs domain observer (CodeGraph default, ast injected in temp-tree tests)"
```

---

### Task 6: Retire the LLM-judged gate 2

**Files:**
- Modify: `.claude/agents/inspector.md`
- Modify: `.claude/skills/harness-feature/SKILL.md`

**Interfaces:** none in code. The Inspector's gate 2 stops being a `codegraph_explore` query judged by the LLM and becomes a read of the deterministic signature diff that the orchestrator already runs.

- [ ] **Step 1: Rewrite the Inspector gate-2 section**

In `.claude/agents/inspector.md`, replace the `## Gate 2 - seam-signature conformance (1 CodeGraph query)` block (the current 3 numbered steps) with:

```markdown
## Gate 2 - seam-signature conformance (deterministic, run by the orchestrator)

Gate 2 is now a committed deterministic check, not an LLM judgment. The
orchestrator runs `python -m scripts.harness_check --only intended_diff`, which
reads domain method signatures from the CodeGraph index and diffs them against
`.architecture/domain-model.yaml` (contract fields are diffed from `ast`). You
do NOT re-derive signatures with a `codegraph_explore` query.

1. Read the patch's `## Seam signatures (Inspector gate 2)` block. (A lite patch
   with no signature block: gate 2 is vacuously satisfied; say so.)
2. Read the orchestrator-provided `intended_diff` result (its `## Domain
   signature mismatches` section). Any mismatch on a symbol inside the patch's
   declared seam is gate-2 interface drift.
3. Use your one `codegraph_explore` query (optional, see budget) only for the
   design check list below, not to re-judge signatures.
```

Update the frontmatter `description:` on line 3: change "via gate 2 (seam-signature conformance, 1 CodeGraph query)" to "via gate 2 (deterministic seam-signature conformance, read from the committed intended_diff)".

Update the budget lines (around lines 31, 110, 118, 120): the `codegraph_explore` query is now **optional** and at most 1, used for the design check list (forbidden/unapproved edge, cycle), not gate 2. Change "Make **exactly 1**" to "Make **at most 1**", keep "Report your query count" and the `QUERIES_USED=<n>` final line (n may now be 0).

In the `## Decision` block, leave `NEEDS PATCH REVISION : seam-signature drift inside the patch's declared scope (gate 2)` as the label, but the input is now the deterministic diff.

- [ ] **Step 2: Rewrite the orchestrator gate-2 handoff**

In `.claude/skills/harness-feature/SKILL.md`:

- In Step 4 (gate 1, mechanical), add a line after the `--only boundaries` run: `python -m scripts.harness_check --only intended_diff` is also run here to produce the deterministic gate-2 input; a mismatch on a symbol the patch did not touch is reconciliation (Inspector step 5), not a gate-1 stop. Boundaries remains the only hard gate-1 stop.
- In Step 5 (Inspector for judgment), change "The Inspector ... does gate 2 + the design check list + verdict" to "The Inspector reads the orchestrator's deterministic `intended_diff` result for gate 2, then does the design check list + verdict." Pass the `intended_diff` report text to the Inspector along with the gate-1 PASS note.
- Update the line "Make one `codegraph_explore` query (gate 2)" expectations: the metered-query delta requirement becomes "at most 1" (the design check list may need 0 or 1), not "require 1".
- Update the iter-history note near the bottom ("Inspector (iter-6 def) does gate 2 + verdict ...") to note that as of iter-9b gate 2 is the deterministic `intended_diff` check, read (not re-derived) by the Inspector.

- [ ] **Step 3: Consistency scan**

Run: `grep -rn "exactly 1\|gate 2\|1 CodeGraph query" .claude/agents/inspector.md .claude/skills/harness-feature/SKILL.md`
Expected: no remaining claim that gate 2 *requires* a `codegraph_explore` query or that the Inspector derives signatures. Fix any stragglers.

- [ ] **Step 4: Full suite (no code changed, but confirm nothing references removed text)**

Run: `python -m unittest discover -s tests -q`
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add .claude/agents/inspector.md .claude/skills/harness-feature/SKILL.md
git commit -m "refactor(iter-9b): retire LLM-judged gate 2; Inspector reads the deterministic intended_diff signature check"
```

---

## After all tasks

- Append an iteration-9b results note to this file (what shipped, the polyglot signature proof if `ts-mini` gains a curated domain class, residual gaps: contract fields still ast).
- Update `docs/iteration/01-harness-mvp-iteration-roadmap.md`: mark 9b done; note the single-observed-source goal is now met for edges (9a) and signatures (9b), with contract fields the one remaining ast holdout.
- Then run superpowers:finishing-a-development-branch.

## Self-Review

- **Spec coverage:** signatures from CodeGraph (Tasks 1-2), deterministic polyglot signature diff via injectable seam (Task 3), contract fields stay ast (Task 3 leaves `_observed_contracts` untouched), re-curate (Task 4), unified surface wiring (Task 5), retire LLM gate 2 (Task 6). All roadmap 9b clauses covered.
- **Placeholder scan:** every code step shows real code; Task 4 values are repo-derived at run time by design (re-curation is "make declared equal observed"), with exact verify commands and expected exit codes.
- **Type consistency:** `SignatureNode` fields used identically in Tasks 1-2; `observe_domain_fn(domain_dir) -> Dict[str, Dict[str, str]]` consistent across Tasks 3 and 5; `normalize_signature` applied to declared, ast-observed, and CodeGraph-observed signatures so all three compare in the same space.
