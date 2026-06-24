"""Use case orchestrating route planning. Allowed edges: domain + contracts."""

from sample.contracts.route_dto import RouteRequestDTO
from sample.domain.route_risk import RouteRisk
from sample.domain.route_risk_policy import RouteRiskPolicy


class PlanRouteUseCase:
    def __init__(self, policy: RouteRiskPolicy) -> None:
        self._policy = policy

    def run(self, dto: RouteRequestDTO) -> RouteRisk:
        return self._policy.evaluate(dto)
