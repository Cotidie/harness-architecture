import unittest

from src.domain.boundaries.boundary_rule_set import BoundaryRuleSet


def _sample_rule_set():
    return BoundaryRuleSet.from_rules(
        [
            {
                "name": "domain",
                "path_glob": "sample/domain/**",
                "may_depend_on": ("shared",),
                "must_not_depend_on": ("application", "adapters", "contracts"),
            },
            {
                "name": "contracts",
                "path_glob": "sample/contracts/**",
                "may_depend_on": ("shared",),
                "must_not_depend_on": ("application", "domain", "adapters"),
            },
            {
                "name": "application",
                "path_glob": "sample/application/**",
                "may_depend_on": ("domain", "contracts", "shared"),
                "must_not_depend_on": ("adapters",),
            },
        ]
    )


class ModuleForPathTests(unittest.TestCase):
    def test_maps_file_path_to_module(self):
        rs = _sample_rule_set()
        self.assertEqual(
            rs.module_for_path("sample/domain/route_risk_policy.py"), "domain"
        )
        self.assertEqual(
            rs.module_for_path("sample/contracts/route_dto.py"), "contracts"
        )

    def test_maps_dotted_import_path_to_module(self):
        rs = _sample_rule_set()
        self.assertEqual(
            rs.module_for_path("sample/contracts/route_dto"), "contracts"
        )

    def test_returns_none_for_unmatched_path(self):
        rs = _sample_rule_set()
        self.assertIsNone(rs.module_for_path("other/place/thing.py"))

    def test_most_specific_glob_wins(self):
        rs = BoundaryRuleSet.from_rules(
            [
                {
                    "name": "broad",
                    "path_glob": "sample/**",
                    "may_depend_on": (),
                    "must_not_depend_on": (),
                },
                {
                    "name": "narrow",
                    "path_glob": "sample/domain/**",
                    "may_depend_on": (),
                    "must_not_depend_on": (),
                },
            ]
        )
        self.assertEqual(rs.module_for_path("sample/domain/x.py"), "narrow")


class CheckTests(unittest.TestCase):
    def test_flags_forbidden_pair(self):
        rs = _sample_rule_set()
        violations = rs.check(
            source_module="domain",
            target_module="contracts",
            file_path="sample/domain/route_risk_policy.py",
            line=9,
        )
        self.assertEqual(len(violations), 1)
        v = violations[0]
        self.assertEqual(v.source_module, "domain")
        self.assertEqual(v.target_module, "contracts")
        self.assertEqual(v.rule_kind, "must_not_depend_on")
        self.assertEqual(v.file_path, "sample/domain/route_risk_policy.py")
        self.assertEqual(v.line, 9)

    def test_does_not_flag_allowed_pair(self):
        rs = _sample_rule_set()
        violations = rs.check(
            source_module="application",
            target_module="domain",
            file_path="sample/application/plan_route.py",
            line=4,
        )
        self.assertEqual(violations, [])

    def test_does_not_flag_self_module(self):
        rs = _sample_rule_set()
        violations = rs.check(
            source_module="domain",
            target_module="domain",
            file_path="sample/domain/route_risk_policy.py",
            line=10,
        )
        self.assertEqual(violations, [])

    def test_unknown_source_module_is_ignored(self):
        rs = _sample_rule_set()
        self.assertEqual(
            rs.check(
                source_module=None,
                target_module="contracts",
                file_path="x.py",
                line=1,
            ),
            [],
        )


class MayOnlyDependOnTests(unittest.TestCase):
    def _rule_set(self):
        return BoundaryRuleSet.from_rules(
            [
                {
                    "name": "application",
                    "path_glob": "sample/application/**",
                    "may_depend_on": (),
                    "must_not_depend_on": (),
                    "may_only_depend_on": ("domain", "contracts"),
                },
                {
                    "name": "domain",
                    "path_glob": "sample/domain/**",
                    "may_depend_on": (),
                    "must_not_depend_on": (),
                },
                {
                    "name": "contracts",
                    "path_glob": "sample/contracts/**",
                    "may_depend_on": (),
                    "must_not_depend_on": (),
                },
                {
                    "name": "adapters",
                    "path_glob": "sample/adapters/**",
                    "may_depend_on": (),
                    "must_not_depend_on": (),
                },
            ]
        )

    def test_target_on_allowlist_is_allowed(self):
        rs = self._rule_set()
        self.assertEqual(
            rs.check(
                source_module="application",
                target_module="domain",
                file_path="sample/application/plan_route.py",
                line=3,
            ),
            [],
        )

    def test_known_target_not_on_allowlist_is_flagged(self):
        rs = self._rule_set()
        violations = rs.check(
            source_module="application",
            target_module="adapters",
            file_path="sample/application/plan_route.py",
            line=4,
        )
        self.assertEqual(len(violations), 1)
        v = violations[0]
        self.assertEqual(v.source_module, "application")
        self.assertEqual(v.target_module, "adapters")
        self.assertEqual(v.rule_kind, "may_only_depend_on")
        self.assertEqual(v.file_path, "sample/application/plan_route.py")
        self.assertEqual(v.line, 4)

    def test_unknown_target_is_ignored(self):
        # An import resolving to no known module (stdlib / third party) is not
        # flagged even when the source has a non-empty allowlist.
        rs = self._rule_set()
        self.assertEqual(
            rs.check(
                source_module="application",
                target_module=None,
                file_path="sample/application/plan_route.py",
                line=5,
            ),
            [],
        )

    def test_self_reference_is_ignored(self):
        rs = self._rule_set()
        self.assertEqual(
            rs.check(
                source_module="application",
                target_module="application",
                file_path="sample/application/plan_route.py",
                line=6,
            ),
            [],
        )

    def test_module_without_allowlist_key_is_unaffected(self):
        rs = self._rule_set()
        # `domain` declares no may_only_depend_on, so any edge is allowed by it.
        self.assertEqual(
            rs.check(
                source_module="domain",
                target_module="adapters",
                file_path="sample/domain/route_risk_policy.py",
                line=7,
            ),
            [],
        )

    def test_empty_allowlist_is_opt_out(self):
        # Chosen semantics (patch section 11): an empty `may_only_depend_on`
        # list is treated as opt-out, leaving behavior unchanged. So a known
        # target is NOT flagged when the allowlist is present but empty.
        rs = BoundaryRuleSet.from_rules(
            [
                {
                    "name": "application",
                    "path_glob": "sample/application/**",
                    "may_depend_on": (),
                    "must_not_depend_on": (),
                    "may_only_depend_on": (),
                },
                {
                    "name": "adapters",
                    "path_glob": "sample/adapters/**",
                    "may_depend_on": (),
                    "must_not_depend_on": (),
                },
            ]
        )
        self.assertEqual(
            rs.check(
                source_module="application",
                target_module="adapters",
                file_path="sample/application/plan_route.py",
                line=8,
            ),
            [],
        )

    def test_must_not_depend_on_still_works_with_allowlist(self):
        # Regression: must_not_depend_on behavior is unchanged. A module that
        # declares both can produce two findings for the same edge (one per
        # distinct rule_kind).
        rs = BoundaryRuleSet.from_rules(
            [
                {
                    "name": "application",
                    "path_glob": "sample/application/**",
                    "may_depend_on": (),
                    "must_not_depend_on": ("adapters",),
                    "may_only_depend_on": ("domain",),
                },
                {
                    "name": "adapters",
                    "path_glob": "sample/adapters/**",
                    "may_depend_on": (),
                    "must_not_depend_on": (),
                },
                {
                    "name": "domain",
                    "path_glob": "sample/domain/**",
                    "may_depend_on": (),
                    "must_not_depend_on": (),
                },
            ]
        )
        violations = rs.check(
            source_module="application",
            target_module="adapters",
            file_path="sample/application/plan_route.py",
            line=9,
        )
        kinds = sorted(v.rule_kind for v in violations)
        self.assertEqual(kinds, ["may_only_depend_on", "must_not_depend_on"])


class FactoryInvariantTests(unittest.TestCase):
    def test_frozen_cannot_mutate(self):
        rs = _sample_rule_set()
        with self.assertRaises(Exception):
            rs.rules = ()

    def test_rejects_missing_name(self):
        with self.assertRaises(ValueError):
            BoundaryRuleSet.from_rules(
                [
                    {
                        "name": "",
                        "path_glob": "sample/domain/**",
                        "may_depend_on": (),
                        "must_not_depend_on": (),
                    }
                ]
            )

    def test_rejects_missing_path_glob(self):
        with self.assertRaises(ValueError):
            BoundaryRuleSet.from_rules(
                [
                    {
                        "name": "domain",
                        "path_glob": "",
                        "may_depend_on": (),
                        "must_not_depend_on": (),
                    }
                ]
            )

    def test_rejects_duplicate_module_names(self):
        with self.assertRaises(ValueError):
            BoundaryRuleSet.from_rules(
                [
                    {
                        "name": "domain",
                        "path_glob": "sample/domain/**",
                        "may_depend_on": (),
                        "must_not_depend_on": (),
                    },
                    {
                        "name": "domain",
                        "path_glob": "sample/other/**",
                        "may_depend_on": (),
                        "must_not_depend_on": (),
                    },
                ]
            )


if __name__ == "__main__":
    unittest.main()
