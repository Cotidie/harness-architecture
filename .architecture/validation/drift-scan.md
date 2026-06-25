# Full-graph drift scan

Date: 2026-06-25
Trigger: iteration-6 follow-up (committed `scripts/drift_scan.py`, replacing the ad-hoc scan)
Command: `python -m scripts.drift_scan src .architecture/boundaries.yaml` (exit 0)

Declared modules: adapters, application, contracts, domain, shared
Observed modules: adapters, application, contracts, domain

## Undeclared modules (observed, not in boundaries.yaml)
- none

## Undeclared edges (observed, not in any allow-list)
- none

## Unmaterialized modules (declared, no source yet -- info only)
- shared

## Verdict
No accumulated off-path drift. Report only; no auto-fix.

The scan is now a committed, unit-tested script (`scripts/drift_scan.py`,
`tests/test_drift_scan.py`) that checks both modules AND cross-module edges, instead of
re-improvised python each run. It reuses the boundaries linter's scanner, so it is deterministic
from source and needs no CodeGraph query. `shared` is declared-but-not-materialized
(intended-ahead-of-observed), reported as info, not drift.
