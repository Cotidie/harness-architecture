"""Domain policy that evaluates route risk.

NOTE (planted drift): this module imports a data contract from sample.contracts,
which the intended boundaries forbid (domain must_not_depend_on contracts).
This forbidden domain -> contracts edge exists so the harness agents have a real
observed-vs-intended drift to detect across iterations.
"""

from sample.contracts.route_dto import RouteRequestDTO
from sample.domain.route_risk import RouteRisk


class RouteRiskPolicy:
    def evaluate(self, dto: RouteRequestDTO) -> RouteRisk:
        score = min(1.0, 0.1 * len(dto.waypoints) + 0.2 * dto.robot_count)
        return RouteRisk.from_score(score)
