"""Contract: the shape of one reported boundary violation.

A frozen data shape that crosses back out to the reporter. Holds no behavior.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BoundaryViolation:
    source_module: str
    target_module: str
    rule_kind: str
    file_path: str
    line: int
