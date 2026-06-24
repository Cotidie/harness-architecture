# CodeGraph Observations and Drift

> Historical record of the iteration 1 snapshot exercise. It was run against a
> throwaway sample `src/` (route risk planning) created only to prove the
> CodeGraph to docs path works. That sample has since been removed, so the
> symbols below no longer exist on disk. The key result: the Surveyor
> correctly detected the deliberately planted forbidden `domain -> contracts`
> edge in 1 query. Observed architecture is empty until iteration 2 adds real code.

CodeGraph queries used for this snapshot: 1.

Query scope: high-level shape of `route_risk_policy`, `route_risk`,
`plan_route`, `route_dto`, `route_repository` (domain classes, contract fields,
inter-module dependency edges).

## Observed modules and symbols
- `domain`: `RouteRisk` (value object, `from_score`), `RouteRiskPolicy`
  (`evaluate`).
- `contracts`: `RouteRequestDTO` (fields `waypoints: List[str]`,
  `robot_count: int`).
- `application`: `PlanRouteUseCase` (`__init__(policy)`, `run(dto)`).
- `adapters`: `route_repository` (caller of `PlanRouteUseCase` and `RouteRisk`).

## Observed dependency edges
- `application -> domain`: `PlanRouteUseCase` imports `RouteRisk`,
  `RouteRiskPolicy`. [allowed]
- `application -> contracts`: `PlanRouteUseCase` imports `RouteRequestDTO`.
  [allowed]
- `adapters -> application`: `route_repository` uses `PlanRouteUseCase`.
  [allowed]
- `adapters -> domain`: `route_repository` references `RouteRisk`. [allowed]
- `domain -> contracts`: `RouteRiskPolicy` imports `RouteRequestDTO`.
  [FORBIDDEN per boundaries.yaml]

## Observed-vs-intended drift

### domain -> contracts edge (RouteRiskPolicy imports RouteRequestDTO)
- Label: CODE_DRIFT_HARMFUL
- Intended: `domain` must_not_depend_on `contracts`.
- Observed: `src/domain/route_risk_policy.py:9` imports `RouteRequestDTO`.
  (The module docstring itself notes this is a planted boundary violation.)
- Action: refactor `RouteRiskPolicy.evaluate` to take domain inputs instead of
  the DTO; move DTO-to-domain mapping into the application layer. Refactor
  before further feature work that touches this policy.

### Missing test coverage on all core symbols
- Label: UNCLEAR_DRIFT
- Observed: CodeGraph reports no covering tests for `RouteRisk`,
  `RouteRiskPolicy`, `PlanRouteUseCase`, `RouteRequestDTO`.
- Action: design lists required tests (domain behavior, contract validation,
  boundary). Whether this is acceptable for a sample repo or a gap to fix is a
  human call.

### shared module not materialized
- Label: DOC_DRIFT_ACCEPTED
- Intended: `shared` exists in the layout.
- Observed: no `src/shared/` on disk.
- Action: none; no shared primitive is needed yet. Keep reserved.

## Layered direction (everything except the domain->contracts edge)
- Label: ALIGNED
- The application and adapter layers depend inward exactly as intended.
