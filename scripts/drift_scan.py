"""Harness tooling: full-graph drift scan (modules AND edges).

A deterministic, committed replacement for the ad-hoc python the
`harness-feature` step 0b used to re-improvise each run. It reuses the
boundaries linter's scanner to compute the OBSERVED module-edge graph from a
source tree, then diffs it against the INTENDED graph declared in
`boundaries.yaml`:

  - undeclared module   : an observed top-level package described by no module
                          path glob;
  - unmaterialized module : a declared module with no matching source yet
                          (intended-ahead-of-observed; reported as info, not
                          drift);
  - undeclared edge     : an observed module -> module import whose target is in
                          neither `may_depend_on` nor `may_only_depend_on` of the
                          source. Forbidden edges (`must_not_depend_on`, or
                          outside a `may_only_depend_on` allow-list) are the
                          linter's job and are reported here as info, not as the
                          drift the linter would already miss.

Reports only. Resolving any finding is a human/Architect decision, never
automatic. Exit code is 0 when there is no drift (undeclared modules/edges) and
1 when drift exists, so the orchestrator can branch on it.
"""

import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

from src.adapters.boundaries.boundaries_config_loader import load_module_rules
from src.adapters.boundaries.python_import_scanner import scan_imports
from src.application.boundaries.lint_boundaries import LintBoundaries


@dataclass(frozen=True)
class DriftReport:
    """The outcome of one drift scan. `has_drift` covers only the structural
    drift the linter does not already catch (undeclared modules and edges)."""

    declared_modules: Tuple[str, ...]
    observed_modules: Tuple[str, ...]
    undeclared_modules: Tuple[str, ...]
    unmaterialized_modules: Tuple[str, ...]
    undeclared_edges: Tuple[Tuple[str, str], ...]
    forbidden_edges: Tuple[Tuple[str, str], ...]

    @property
    def has_drift(self) -> bool:
        return bool(self.undeclared_modules or self.undeclared_edges)


def _glob_prefix(path_glob: str) -> str:
    marker = path_glob.find("*")
    prefix = path_glob if marker == -1 else path_glob[:marker]
    return prefix.rstrip("/")


def compute_drift(target_dir: str, boundaries_file: str) -> DriftReport:
    module_rules = load_module_rules(boundaries_file)
    rule_set = LintBoundaries().build_rule_set(module_rules)

    declared = {rule.name: rule for rule in module_rules}

    # Declared allow-set per source module: anything reachable without tripping
    # the linter. may_only_depend_on, when present, is the exhaustive allow-list.
    allowed: Dict[str, Set[str]] = {}
    forbidden_decl: Dict[str, Set[str]] = {}
    for rule in module_rules:
        allowed[rule.name] = set(rule.may_depend_on) | set(rule.may_only_depend_on)
        forbidden_decl[rule.name] = set(rule.must_not_depend_on)

    # Observed top-level packages: each immediate child dir of target_dir that
    # holds at least one .py file, mapped to a module name via the path globs.
    observed_modules: Set[str] = set()
    undeclared_modules: List[str] = []
    if os.path.isdir(target_dir):
        for child in sorted(os.listdir(target_dir)):
            child_path = os.path.join(target_dir, child)
            if not os.path.isdir(child_path):
                continue
            if not _dir_has_python(child_path):
                continue
            probe = "%s/%s/__init__.py" % (
                target_dir.replace("\\", "/").rstrip("/"),
                child,
            )
            module_name = rule_set.module_for_path(probe)
            if module_name is None:
                undeclared_modules.append(child)
            else:
                observed_modules.add(module_name)

    # A declared module is materialized when its glob prefix exists on disk.
    unmaterialized_modules = [
        rule.name
        for rule in module_rules
        if not os.path.isdir(_glob_prefix(rule.path_glob))
    ]

    # Observed module -> module edges (self-edges ignored).
    scan = scan_imports(target_dir, rule_set)
    observed_edges: Set[Tuple[str, str]] = {
        (edge.source_module, edge.imported_module)
        for edge in scan.edges
        if edge.source_module != edge.imported_module
    }

    undeclared_edges: List[Tuple[str, str]] = []
    forbidden_edges: List[Tuple[str, str]] = []
    for source, target in sorted(observed_edges):
        if target in allowed.get(source, set()):
            continue
        if target in forbidden_decl.get(source, set()):
            forbidden_edges.append((source, target))
        elif source in declared and bool(declared[source].may_only_depend_on):
            # An exhaustive allow-list makes any unlisted target forbidden, not
            # merely undeclared; the linter already reports it.
            forbidden_edges.append((source, target))
        else:
            undeclared_edges.append((source, target))

    return DriftReport(
        declared_modules=tuple(sorted(declared)),
        observed_modules=tuple(sorted(observed_modules)),
        undeclared_modules=tuple(undeclared_modules),
        unmaterialized_modules=tuple(unmaterialized_modules),
        undeclared_edges=tuple(undeclared_edges),
        forbidden_edges=tuple(forbidden_edges),
    )


def _dir_has_python(path: str) -> bool:
    for _root, _dirs, files in os.walk(path):
        if any(name.endswith(".py") for name in files):
            return True
    return False


def format_report(report: DriftReport) -> str:
    lines = ["# Full-graph drift scan", ""]
    lines.append(
        "Declared modules: " + (", ".join(report.declared_modules) or "(none)")
    )
    lines.append(
        "Observed modules: " + (", ".join(report.observed_modules) or "(none)")
    )
    lines.append("")

    lines.append("## Undeclared modules (observed, not in boundaries.yaml)")
    if report.undeclared_modules:
        lines += ["- %s" % name for name in report.undeclared_modules]
    else:
        lines.append("- none")
    lines.append("")

    lines.append("## Undeclared edges (observed, not in any allow-list)")
    if report.undeclared_edges:
        lines += ["- %s -> %s" % (s, t) for s, t in report.undeclared_edges]
    else:
        lines.append("- none")
    lines.append("")

    if report.unmaterialized_modules:
        lines.append(
            "## Unmaterialized modules (declared, no source yet -- info only)"
        )
        lines += ["- %s" % name for name in report.unmaterialized_modules]
        lines.append("")

    if report.forbidden_edges:
        lines.append(
            "## Forbidden edges observed (info -- the linter already reports these)"
        )
        lines += ["- %s -> %s" % (s, t) for s, t in report.forbidden_edges]
        lines.append("")

    verdict = (
        "DRIFT: undeclared modules or edges exist; reconcile boundaries.yaml or "
        "the code (human/Architect decision)."
        if report.has_drift
        else "No accumulated off-path drift. Report only; no auto-fix."
    )
    lines.append("## Verdict")
    lines.append(verdict)
    lines.append("")
    return "\n".join(lines)


def main(argv: List[str]) -> int:
    if len(argv) < 2:
        sys.stderr.write(
            "usage: python -m scripts.drift_scan <target_dir> <boundaries_file>\n"
        )
        return 2
    target_dir, boundaries_file = argv[0], argv[1]
    report = compute_drift(target_dir, boundaries_file)
    print(format_report(report))
    return 1 if report.has_drift else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
