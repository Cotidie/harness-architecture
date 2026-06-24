"""Data contract crossing the request boundary."""

from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class RouteRequestDTO:
    waypoints: List[str] = field(default_factory=list)
    robot_count: int = 0
