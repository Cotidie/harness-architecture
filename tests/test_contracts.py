import dataclasses
import unittest

from src.contracts.boundaries.module_rule import ModuleRule
from src.contracts.boundaries.import_edge import ImportEdge
from src.contracts.boundaries.boundary_violation import BoundaryViolation


class ModuleRuleTests(unittest.TestCase):
    def test_fields(self):
        rule = ModuleRule(
            name="domain",
            path_glob="src/domain/**",
            may_depend_on=("shared",),
            must_not_depend_on=("contracts",),
        )
        self.assertEqual(rule.name, "domain")
        self.assertEqual(rule.path_glob, "src/domain/**")
        self.assertEqual(rule.may_depend_on, ("shared",))
        self.assertEqual(rule.must_not_depend_on, ("contracts",))

    def test_frozen(self):
        rule = ModuleRule("domain", "src/domain/**", (), ())
        with self.assertRaises(dataclasses.FrozenInstanceError):
            rule.name = "other"

    def test_rejects_missing_fields(self):
        with self.assertRaises(TypeError):
            ModuleRule(name="domain")  # type: ignore[call-arg]

    def test_no_business_methods(self):
        public = [n for n in vars(ModuleRule) if not n.startswith("_")]
        self.assertEqual(public, [])


class ImportEdgeTests(unittest.TestCase):
    def test_fields(self):
        edge = ImportEdge(
            source_module="domain",
            imported_module="contracts",
            file_path="sample/domain/route_risk_policy.py",
            line=9,
        )
        self.assertEqual(edge.source_module, "domain")
        self.assertEqual(edge.imported_module, "contracts")
        self.assertEqual(edge.file_path, "sample/domain/route_risk_policy.py")
        self.assertEqual(edge.line, 9)

    def test_frozen(self):
        edge = ImportEdge("a", "b", "f.py", 1)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            edge.line = 2

    def test_rejects_missing_fields(self):
        with self.assertRaises(TypeError):
            ImportEdge(source_module="a")  # type: ignore[call-arg]

    def test_no_business_methods(self):
        public = [n for n in vars(ImportEdge) if not n.startswith("_")]
        self.assertEqual(public, [])


class BoundaryViolationTests(unittest.TestCase):
    def test_fields(self):
        v = BoundaryViolation(
            source_module="domain",
            target_module="contracts",
            rule_kind="must_not_depend_on",
            file_path="sample/domain/route_risk_policy.py",
            line=9,
        )
        self.assertEqual(v.source_module, "domain")
        self.assertEqual(v.target_module, "contracts")
        self.assertEqual(v.rule_kind, "must_not_depend_on")
        self.assertEqual(v.file_path, "sample/domain/route_risk_policy.py")
        self.assertEqual(v.line, 9)

    def test_frozen(self):
        v = BoundaryViolation("a", "b", "must_not_depend_on", "f.py", 1)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            v.line = 2

    def test_rejects_missing_fields(self):
        with self.assertRaises(TypeError):
            BoundaryViolation(source_module="a")  # type: ignore[call-arg]

    def test_no_business_methods(self):
        public = [n for n in vars(BoundaryViolation) if not n.startswith("_")]
        self.assertEqual(public, [])


if __name__ == "__main__":
    unittest.main()
