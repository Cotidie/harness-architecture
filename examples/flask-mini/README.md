# flask-mini (layout-only detection fixture)

A deliberately non-DDD layout used to prove the harness's framework detection is
not hardcoded to `domain/contracts/application/adapters`. It is **layout only**:
stub packages plus a `requirements.txt`, not a runnable Flask app, and not part
of the harness's own architecture.

`scripts/detect_profile` run against this directory should report
`framework_guess == "python/flask"` and name the candidate layers
`blueprints / models / services`, never the self-host's DDD layers. See
`tests/test_profile_fixture.py`.

This directory is not scanned by the boundaries linter, `drift_scan`, or
`intended_diff` (they target `src/`), so it cannot create false drift.
