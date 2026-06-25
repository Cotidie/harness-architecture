# ts-mini (polyglot proof fixture)

A tiny TypeScript layout used to prove the harness's boundary checking works on
a non-Python language by reading import edges from the CodeGraph index. It is
**fixture only**, not a real app, and not part of the harness's own
architecture.

`domain/core.ts` deliberately imports `adapters/io.ts`, which
`boundaries.yaml` forbids (`domain.must_not_depend_on: [adapters]`). The
CodeGraph-backed scanner + the boundary use case should report that forbidden
edge with the correct file + line, same `ScanResult` contract as the Python
path. See `tests/test_polyglot_boundary.py`.
