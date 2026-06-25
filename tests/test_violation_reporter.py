"""Unit tests for the violation reporter formatters (adapters layer)."""

import dataclasses
import json
import unittest

from src.contracts.boundaries.boundary_violation import BoundaryViolation
from src.adapters.boundaries.violation_reporter import (
    format_report,
    format_report_json,
    format_violation,
)


_CONTRACT_FIELDS = (
    "source_module",
    "target_module",
    "rule_kind",
    "file_path",
    "line",
)


def _violation(**overrides):
    base = {
        "source_module": "domain",
        "target_module": "contracts",
        "rule_kind": "must_not_depend_on",
        "file_path": "src/domain/thing.py",
        "line": 9,
    }
    base.update(overrides)
    return BoundaryViolation(**base)


class FormatReportTextTests(unittest.TestCase):
    def test_empty_reports_no_violations(self):
        self.assertEqual(
            format_report([]), "No boundary violations found."
        )

    def test_single_violation_text(self):
        report = format_report([_violation()])
        self.assertIn(
            "src/domain/thing.py:9: domain -> contracts "
            "violates must_not_depend_on",
            report,
        )
        self.assertIn("1 boundary violation(s) found.", report)

    def test_multiple_violations_count(self):
        report = format_report([_violation(), _violation(line=12)])
        self.assertIn("2 boundary violation(s) found.", report)

    def test_parse_error_text(self):
        report = format_report(
            [
                _violation(
                    rule_kind="parse_error",
                    source_module="",
                    target_module="",
                    file_path="src/domain/broken.py",
                    line=3,
                )
            ]
        )
        self.assertIn(
            "src/domain/broken.py:3: parse_error: "
            "could not parse file (syntax error)",
            report,
        )

    def test_format_violation_single_finding(self):
        line = format_violation(_violation())
        self.assertEqual(
            line,
            "src/domain/thing.py:9: domain -> contracts "
            "violates must_not_depend_on",
        )


class FormatReportJsonTests(unittest.TestCase):
    def test_empty_input_emits_empty_array(self):
        self.assertEqual(json.loads(format_report_json([])), [])

    def test_returns_a_string(self):
        self.assertIsInstance(format_report_json([]), str)

    def test_single_violation_carries_all_five_fields(self):
        payload = json.loads(format_report_json([_violation()]))
        self.assertEqual(len(payload), 1)
        element = payload[0]
        self.assertEqual(
            sorted(element.keys()), sorted(_CONTRACT_FIELDS)
        )
        self.assertEqual(element["source_module"], "domain")
        self.assertEqual(element["target_module"], "contracts")
        self.assertEqual(element["rule_kind"], "must_not_depend_on")
        self.assertEqual(element["file_path"], "src/domain/thing.py")
        self.assertEqual(element["line"], 9)

    def test_element_shape_mirrors_contract(self):
        element = json.loads(format_report_json([_violation()]))[0]
        contract_fields = tuple(
            f.name for f in dataclasses.fields(BoundaryViolation)
        )
        self.assertEqual(sorted(element.keys()), sorted(contract_fields))

    def test_multiple_violations_serialize_in_order(self):
        payload = json.loads(
            format_report_json([_violation(line=1), _violation(line=2)])
        )
        self.assertEqual([e["line"] for e in payload], [1, 2])

    def test_parse_error_serializes_with_rule_kind(self):
        payload = json.loads(
            format_report_json(
                [
                    _violation(
                        rule_kind="parse_error",
                        file_path="src/domain/broken.py",
                        line=3,
                    )
                ]
            )
        )
        self.assertEqual(payload[0]["rule_kind"], "parse_error")


if __name__ == "__main__":
    unittest.main()
