"""Application: the boundary-lint use case.

Orchestrates the boundary check by mapping the contract data produced by the
adapters (ModuleRule, ImportEdge) into plain domain inputs, delegating the
decision to the domain `BoundaryRuleSet`, and mapping the domain results back
onto `BoundaryViolation` contracts.

This layer depends only on `domain` and `contracts` (allowed edges). It does NOT
import any adapter: the adapter (CLI) performs the IO and passes the loaded
contracts in. The domain never sees the contract classes; the mapping happens
here.
"""

from typing import List, Sequence

from src.contracts.boundaries.boundary_violation import BoundaryViolation
from src.contracts.boundaries.import_edge import ImportEdge
from src.contracts.boundaries.module_rule import ModuleRule
from src.domain.boundaries.boundary_rule_set import BoundaryRuleSet


class LintBoundaries:
    def build_rule_set(
        self, module_rules: Sequence[ModuleRule]
    ) -> BoundaryRuleSet:
        # Map ModuleRule contracts into plain domain inputs (no contract class
        # crosses into the domain object).
        plain_rules = [
            {
                "name": rule.name,
                "path_glob": rule.path_glob,
                "may_depend_on": tuple(rule.may_depend_on),
                "must_not_depend_on": tuple(rule.must_not_depend_on),
            }
            for rule in module_rules
        ]
        return BoundaryRuleSet.from_rules(plain_rules)

    def run(
        self,
        module_rules: Sequence[ModuleRule],
        import_edges: Sequence[ImportEdge],
        parse_failures: Sequence[BoundaryViolation] = (),
    ) -> List[BoundaryViolation]:
        rule_set = self.build_rule_set(module_rules)
        violations: List[BoundaryViolation] = []
        for edge in import_edges:
            decisions = rule_set.check(
                source_module=edge.source_module,
                target_module=edge.imported_module,
                file_path=edge.file_path,
                line=edge.line,
            )
            for decision in decisions:
                violations.append(
                    BoundaryViolation(
                        source_module=decision.source_module,
                        target_module=decision.target_module,
                        rule_kind=decision.rule_kind,
                        file_path=decision.file_path,
                        line=decision.line,
                    )
                )
        # Orchestration policy (patch section 5): a parse failure is a
        # reportable finding that joins the single findings stream, so it
        # counts toward "violations found" (exit 1), not could-not-run.
        violations.extend(parse_failures)
        return violations
