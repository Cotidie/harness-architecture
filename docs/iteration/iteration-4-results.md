# Iteration 4 Results: User-Test Report

Date: 2026-06-25. Tester drove the assembled artifacts as a user (adversarial inputs), not the
unit suite. Findings reported before any fix.

## What was tested

Iteration 4 shipped three things: the **Inspector** validation gate, the **Architect**
seam-signature emission, and the dogfood **`may_only_depend_on`** linter feature. Testing:

- **`may_only_depend_on` CLI feature** driven directly with a scratch fixture (`proj/a` imports
  `proj.b.thing`, `proj.c.thing`, and stdlib `os`) under ~12 adversarial `boundaries.yaml`
  variants: basic allowlist, empty/null allowlist, bogus + typo entries, overlap with
  `must_not_depend_on`, self-reference, duplicates, and wrong-typed values (string, mapping).
- **Inspector gate** assessed from its three build-time runs (ACCEPT / REJECT / NEEDS PATCH
  REVISION) plus its design.

Run shape: `python -m src.adapters.boundaries.cli <target_dir> <boundaries.yaml>`.

## Works well

- **Allowlist core is correct.** A present, non-empty `may_only_depend_on` flags a known target
  not on the list (`a -> c violates may_only_depend_on`, exit 1) and allows on-list targets;
  stdlib `os` is correctly ignored.
- **Strictly opt-in.** Empty list (`[]`) and `null` both leave behavior unchanged (exit 0). A
  module with no key is unaffected. Matches the patch's pinned semantics.
- **Overlap is honest.** A module with both `must_not_depend_on: [c]` and
  `may_only_depend_on: [b]` reports two distinct findings for `a -> c` (one per `rule_kind`).
- **Self-reference and duplicates** behave (self is ignored via the source==target skip;
  duplicate allowlist entries are harmless).
- **Inspector gate held on all three build cases:** ACCEPT on the clean build (report written,
  `state.yaml` validated fields bumped), REJECT: ARCHITECTURE VIOLATION on a forbidden
  `domain -> contracts` edge (no state bump, correctly named the edge as root cause over the
  downstream test failures), NEEDS PATCH REVISION on isolated seam drift. The 1-query budget
  held (gate-1 forbidden-edge run used 0 queries; gate-2 run used 1).

## Issues

### F1 (HIGH, pre-existing, surfaced now) - false PASS when globs match files but not imports

The scanner resolves an import by turning its dotted name into a path (`proj.b.thing` ->
`proj/b/thing`) and matching it against the **same** module globs used for files. If a
`boundaries.yaml` uses path globs that match the walked **file paths** but not the **dotted
import namespace** (for example absolute-path globs, or a target run from the "wrong" cwd), then
files match (so the zero-match loud-fail does NOT fire) but every import silently resolves to
"external" and is dropped. Result: `No boundary violations found.` exit 0 - a confident false
clean.

Repro: point globs at an absolute prefix (`path: "/abs/proj/a/**"`) with a target dir whose
walked files match that prefix; imports `proj.b.thing` never resolve; exit 0 despite a real
off-allowlist edge. The existing zero-match guard (exit 2) only catches when NO file matches,
not when files match but imports do not resolve.

Why it matters for the harness: gate 1 (the Inspector's self-check) trusts this exit code. A
misaligned `boundaries.yaml` makes the standing validation gate pass vacuously. This is the most
dangerous failure mode for a gate: a silent false negative.

### F2 (MEDIUM, inherited loader pattern, now applies to the new field) - no type validation on list fields

`may_only_depend_on` (and `may_depend_on` / `must_not_depend_on`, same loader pattern) accept any
iterable without a type check: the loader does `tuple(spec.get(key, []) or [])`.

- `may_only_depend_on: "b"` is silently char-split into `('b',)` (proved: `a -> c` flagged, so
  the string became the allowlist `['b']`).
- `may_only_depend_on: "bc"` becomes `('b', 'c')`.
- `may_only_depend_on: {b: true}` becomes `('b',)` (dict reduced to its keys).

No error, no warning. A typo'd scalar silently becomes a wrong rule.

### F3 (LOW-MEDIUM) - allowlist entries are not checked against known module names

`may_only_depend_on: ["bb"]` (no module `bb` exists) is accepted silently and makes every known
target off-list, so `a -> b` and `a -> c` are both flagged with no hint that `bb` is not a real
module. A typo in an allowlist entry produces confidently wrong output.

### F4 (MEDIUM, design) - gate 2 flags backward-compatible signature additions as drift

In the build-time gate-2 test, adding an optional parameter (`strict: bool = False`) to `check`
was flagged as drift -> NEEDS PATCH REVISION. That is a backward-compatible addition, yet it
forces a patch edit. Gate 2 currently treats any signature delta as drift. Defensible as strict
("the patch is the contract; re-approve any change"), but it will nag on benign additions.

### F5 (LOW, cosmetic) - reporter wording and pluralization

- `a -> c violates may_only_depend_on` reads like `c` is on a forbidden list; for an allowlist
  rule the meaning is "a may only depend on its allowlist, and c is not on it." Slightly
  ambiguous next to the `must_not_depend_on` message.
- `1 boundary violation(s) found.` still prints the `(s)` placeholder (known from iter 3).

### F6 (NOTE) - gate 2 is model-judged, not mechanical

Gate 1 is deterministic tooling (run the linter, run the tests). Gate 2 is the Inspector reading
CodeGraph source and comparing to the patch text by judgment. It worked across the three cases,
but its reliability is model-dependent and rests on the Architect having declared accurate seam
signatures and the human having approved them (garbage-in risk).

## Fix directions

- **F1 (do first):** decouple file-path matching from import-name matching, or detect the
  vacuous case. Cheapest guard: after scanning, if `matched_file_count > 0` but **zero** imports
  resolved to any module, loud-fail (exit 2) the same way the zero-file case does, with a message
  pointing at the glob/namespace misalignment. Better: document and validate that path globs are
  relative to the import root so file paths and dotted names share a prefix. This is partly a
  harness self-check trust issue, so it likely belongs near iteration 6 (budget/guards) or as a
  linter hardening pass; flagging now because it weakens gate 1.
- **F2:** in `load_module_rules`, reject a non-list value for `may_depend_on` /
  `must_not_depend_on` / `may_only_depend_on` with a `BoundariesConfigError` (exit 2), instead of
  coercing. One guard covers all three fields. This is the same class as the iter-3 config
  hardening and fits the existing `BoundariesConfigError` path.
- **F3:** optionally warn (not necessarily fail) when an allowlist / denylist entry names no
  declared module. Keep it a warning to avoid breaking forward-reference configs; or make it a
  strict-mode opt-in.
- **F4:** decide gate-2 policy explicitly. Either (a) keep strict and document that any signature
  change needs a patch revision, or (b) treat the declared signature as a minimum contract so
  backward-compatible additions pass. Recommend deciding this when iteration 5 wires the
  orchestrator, since it affects how often the loop pauses.
- **F5:** render the allowlist message as `a -> c not allowed by may_only_depend_on` (or list the
  allowlist), and fix the `(s)` pluralization. Trivial reporter-only change.
- **F6:** consider a mechanical AST-based signature extractor for gate 2 so it becomes
  deterministic like gate 1. Larger; sensible alongside iteration 8 (polyglot enforcement), where
  signature extraction per language is needed anyway.

## Scope / honesty notes

- F1, F2, F3, F5 are linter/loader behaviors (the dogfood feature and its inherited loader
  pattern), found by driving the CLI. F4 and F6 are Inspector-design observations from the
  build-time runs, not separately re-run here.
- No code was changed during this test. All scratch fixtures live under the session scratchpad,
  not the repo. The committed iteration-4 state (52 tests, self-check exit 0, ACCEPT report) is
  unchanged.
