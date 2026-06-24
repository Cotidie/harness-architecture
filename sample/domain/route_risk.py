"""Domain value object: a computed route risk score."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RouteRisk:
    score: float
    level: str

    @staticmethod
    def from_score(score: float) -> "RouteRisk":
        level = "high" if score >= 0.7 else "low"
        return RouteRisk(score=score, level=level)
