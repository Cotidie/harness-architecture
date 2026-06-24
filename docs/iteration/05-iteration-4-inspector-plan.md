# Iteration 4 (Inspector + signature gate): plan + results

Status: complete (2026-06-25). Source roadmap: [`01-harness-mvp-iteration-roadmap.md`](01-harness-mvp-iteration-roadmap.md).

## Context

Iterations 1-3 proved Surveyor, Architect, Builder on this Python self-host. Iteration 4
closed the loop's back end: the **Inspector**, a validation gate run after coding that emits
ACCEPT / ACCEPT WITH DOC UPDATE / NEEDS PATCH REVISION / REJECT, per the locked design
(`docs/01-harness-mvp-plan.md:416-456`).

The gate has two mechanical checks:
- **Gate 1, boundary edges + tests:** reuse the Builder's self-check. Run the linter on `src/`
  against `.architecture/boundaries.yaml` (exit 0 required) and the unit tests (must pass), and
  confirm the diff stays inside the patch's allowed-files list.
- **Gate 2, seam signatures (new):** the implemented public signatures must match the patch's
  declared seam signatures. This required a prerequisite **Architect enhancement**: patch
  sections 7-8 now emit actual signatures (contract fields + types; public domain/application
  method signatures), collected into a `## Seam signatures (Inspector gate 2)` block. Seam only,
  no private helpers or bodies. The lite-patch path stays signature-free. Signatures are Python
  idiom for now; iteration 7 generalizes the idiom per framework profile.

## What was built

- `.claude/agents/architect.md`: seam-signature emission (commit `29e2c67`).
- `.claude/agents/inspector.md`: the validation + signature gate, the design's check list, the
  decision labels, the report, the 1-query budget, the `tests:`=callers caveat, the state bump
  rule (commit `f95192f`).
- `.architecture/validation/latest-report.md`: the validation report artifact (new).

## How it was tested: the full loop on one tiny feature

Per the user's decision, the iteration was validated by running the whole loop on a small real
feature: a `may_only_depend_on` allowlist rule for the linter (opt-in; a present, non-empty
allowlist flags any known target module not on it). The chain ran end to end:

1. **Architect** (1 CodeGraph query): label **ALIGNED**, patch
   `.architecture/patches/2026-06-25-may-only-depend-on.md` with a populated seam block
   (`ModuleRule(... may_only_depend_on: Tuple[str, ...])`, `from_rules`, `check`,
   `BoundaryDecision`). Approved.
2. **Builder**: implemented in scope (4 source files + `data-contracts.md` + 3 test files),
   52 tests OK, sample still exit 1, self-check exit 0. Notable judgment call: used
   `field(default_factory=tuple)` for the new contract field to keep the existing
   `test_no_business_methods` invariant green.
3. **Inspector**: validated the result across three cases (below).

## Inspector results

| Case | Setup | Expected | Got |
|------|-------|----------|-----|
| Clean build | the committed feature vs its approved patch | ACCEPT | **ACCEPT** (both gates pass; report written; `state.yaml` validated fields bumped) |
| Gate 1 | scratch forbidden `domain -> contracts` import | REJECT | **REJECT: ARCHITECTURE VIOLATION** (self-check exit 1; no state bump; correctly named the forbidden edge as root cause over the downstream test failures) |
| Gate 2 | scratch extra param `strict: bool = False` on `check`, gate 1 kept green | NEEDS PATCH REVISION | **NEEDS PATCH REVISION** (1 query; identified the exact drifted seam; mapped in-scope signature drift to revision, not reject) |

Both scratch edits were reverted; the committed state carries the genuine ACCEPT report and
state bump. Final tree: 52 tests OK, self-check exit 0.

## Feedback collected (feeds iteration 5, orchestrator)

- The enhanced Architect emitted accurate, useful seam signatures (verified against current
  code before approval); the signature block gives the Inspector a clean single anchor.
- Gate 2 caught the signature drift with one query and correctly distinguished in-scope drift
  (NEEDS PATCH REVISION) from a forbidden edge (REJECT) and from a public seam outside the patch.
- One query sufficed for the Inspector to verify signatures; the gate-1 forbidden-edge run used
  zero queries (mechanical), so the budget held comfortably.
- The report format (decision + per-check pass/fail + the query used + drift detail) is detailed
  enough to drive the iter-5 orchestrator's approve/commit step.
- Open question carried to iter 5: should the Inspector itself write doc updates on ACCEPT WITH
  DOC UPDATE, or is that firmly the orchestrator's job? This iteration deferred doc writing to
  the orchestrator.

## Notes / decisions

- The gate-2 forced case used an added optional parameter (signature change that keeps gate 1
  green) rather than the field rename the plan sketched, because a field rename would break
  callers and surface as a test failure, masking gate 2. The added-param variant isolates gate 2.
- Inspector is read-and-judge plus report: it does not edit `src/`, fix violations, or rewrite
  the patch.
- `inspector` is a new agent def, so it is dispatchable by name only after `/reload-plugins`;
  this iteration ran it via the inline general-purpose fallback.
