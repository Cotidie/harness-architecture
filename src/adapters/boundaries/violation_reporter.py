"""Adapter: format BoundaryViolation contracts for output."""

from typing import Sequence

from src.contracts.boundaries.boundary_violation import BoundaryViolation


def format_violation(violation: BoundaryViolation) -> str:
    return (
        "%s:%d: %s -> %s violates %s"
        % (
            violation.file_path,
            violation.line,
            violation.source_module,
            violation.target_module,
            violation.rule_kind,
        )
    )


def format_report(violations: Sequence[BoundaryViolation]) -> str:
    if not violations:
        return "No boundary violations found."
    lines = [format_violation(v) for v in violations]
    lines.append(
        "%d boundary violation(s) found." % (len(violations),)
    )
    return "\n".join(lines)
