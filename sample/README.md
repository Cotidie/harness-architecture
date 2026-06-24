# Sample fixture

A tiny self-contained mini-repo (route risk planning) used as the dogfood target
for the harness agents (Surveyor, Architect, Builder, Inspector) across iterations.
It is a test fixture, NOT real harness code; the real tooling lives in `src/`.

## Layout

```
sample/
  domain/       RouteRisk (value object), RouteRiskPolicy (policy)
  contracts/    RouteRequestDTO (data contract)
  application/  PlanRouteUseCase (orchestration)
  adapters/     RouteRepository (persistence)
  boundaries.yaml   intended dependency rules for this fixture
```

## Planted violation (intentional)

`sample/domain/route_risk_policy.py` imports `RouteRequestDTO` from
`sample.contracts`, creating a forbidden `domain -> contracts` edge
(domain `must_not_depend_on` contracts). This is deliberate: it gives the
agents a real observed-vs-intended drift to detect and, in later iterations, to
reconcile and fix.

Allowed edges present: `application -> domain`, `application -> contracts`,
`adapters -> application`, `adapters -> domain`.
