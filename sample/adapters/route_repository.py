"""Adapter persisting route results. Allowed edges: application + domain."""

from sample.application.plan_route import PlanRouteUseCase
from sample.domain.route_risk import RouteRisk


class RouteRepository:
    def __init__(self, use_case: PlanRouteUseCase) -> None:
        self._use_case = use_case
        self._store: dict[str, RouteRisk] = {}

    def save(self, key: str, risk: RouteRisk) -> None:
        self._store[key] = risk
