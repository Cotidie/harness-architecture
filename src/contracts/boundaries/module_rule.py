"""Contract: the shape of one module entry loaded from boundaries.yaml.

A frozen data shape that crosses the YAML-load boundary. Holds no behavior.
"""

from dataclasses import dataclass, field
from typing import Tuple


@dataclass(frozen=True)
class ModuleRule:
    name: str
    path_glob: str
    may_depend_on: Tuple[str, ...]
    must_not_depend_on: Tuple[str, ...]
    may_only_depend_on: Tuple[str, ...] = field(default_factory=tuple)
