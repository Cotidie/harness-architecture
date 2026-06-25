"""Adapter: format BoundaryViolation contracts for output."""

import dataclasses
import json
from typing import Sequence

from src.contracts.boundaries.boundary_violation import BoundaryViolation


def format_violation(violation: BoundaryViolation) -> str:
    if violation.rule_kind == "parse_error":
        # A parse failure reuses the BoundaryViolation contract; render it as a
        # could-not-parse finding rather than a source -> target dependency.
        return (
            "%s:%d: parse_error: could not parse file (syntax error)"
            % (violation.file_path, violation.line)
        )
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


def format_report_json(violations: Sequence[BoundaryViolation]) -> str:
    # Serialize the existing contract one-to-one: each JSON array element
    # carries exactly the BoundaryViolation fields. This adds no behavior
    # beyond serialization; presentation stays in the adapters reporter.
    payload = [dataclasses.asdict(v) for v in violations]
    return json.dumps(payload)
