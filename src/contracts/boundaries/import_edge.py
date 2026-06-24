"""Contract: the shape of one resolved import emitted by the scanner.

A frozen data shape that crosses the scanner boundary. Holds no behavior.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ImportEdge:
    source_module: str
    imported_module: str
    file_path: str
    line: int
