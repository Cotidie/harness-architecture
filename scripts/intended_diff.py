"""Harness tooling: deterministic intended-vs-observed diff (contracts + domain).

The keystone of iteration 7. It reads the curated INTENDED layer as data
(`contracts.yaml`, `domain-model.yaml`), extracts the OBSERVED signatures from a
source tree with `ast`, and diffs them. No CodeGraph, no network: like
`scripts/drift_scan.py`, the scan is deterministic from source, so it is
committed, unit-tested, and runnable in a gate.

Diff semantics:

  Contracts (strict, both directions -- the contract seam must be complete):
    - a `contracts.yaml` entry with no matching class under `src/contracts/`
      -> missing class;
    - a declared field missing, an undeclared observed field, or a type-string
      mismatch -> field mismatch;
    - a contract class observed under `src/contracts/` but absent from
      `contracts.yaml` -> undeclared contract.

  Domain (one-directional, lenient -- the YAML curates KEY classes only):
    - a `domain-model.yaml` entry with no matching class under `src/domain/`
      -> missing class;
    - a declared method whose observed signature differs -> signature mismatch;
    - a domain class observed but not declared -> info only, NOT drift.

`has_drift` is true when any strict-drift list is non-empty (info excluded).
Exit code: 1 when drift, 0 when ALIGNED, 2 when it could not run.
"""

import ast
import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import yaml


@dataclass(frozen=True)
class DiffReport:
    declared_contracts: Tuple[str, ...]
    observed_contracts: Tuple[str, ...]
    missing_classes: Tuple[str, ...]
    field_mismatches: Tuple[str, ...]
    undeclared_contracts: Tuple[str, ...]
    signature_mismatches: Tuple[str, ...]
    info_only: Tuple[str, ...]

    @property
    def has_drift(self) -> bool:
        return bool(
            self.missing_classes
            or self.field_mismatches
            or self.undeclared_contracts
            or self.signature_mismatches
        )


def _norm(text: str) -> str:
    """Whitespace-normalize a type/signature string so cosmetic spacing does
    not read as drift. Comparison stays literal otherwise (by design)."""
    return " ".join(text.split())


def _is_dataclass(node: ast.ClassDef) -> bool:
    for dec in node.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Name) and target.id == "dataclass":
            return True
        if isinstance(target, ast.Attribute) and target.attr == "dataclass":
            return True
    return False


def _fmt_arg(arg: ast.arg) -> str:
    if arg.annotation is not None:
        return "%s: %s" % (arg.arg, ast.unparse(arg.annotation))
    return arg.arg


def _format_signature(func) -> str:
    a = func.args
    posonly = list(getattr(a, "posonlyargs", []))
    positional = posonly + list(a.args)
    defaults = list(a.defaults)
    first_default = len(positional) - len(defaults)
    parts: List[str] = []
    for idx, arg in enumerate(positional):
        rendered = _fmt_arg(arg)
        if idx >= first_default:
            rendered += "=" + ast.unparse(defaults[idx - first_default])
        parts.append(rendered)
        if posonly and idx == len(posonly) - 1:
            parts.append("/")
    if a.vararg is not None:
        parts.append("*" + _fmt_arg(a.vararg))
    elif a.kwonlyargs:
        parts.append("*")
    for kwarg, kwd in zip(a.kwonlyargs, a.kw_defaults):
        rendered = _fmt_arg(kwarg)
        if kwd is not None:
            rendered += "=" + ast.unparse(kwd)
        parts.append(rendered)
    if a.kwarg is not None:
        parts.append("**" + _fmt_arg(a.kwarg))
    sig = "(" + ", ".join(parts) + ")"
    if func.returns is not None:
        sig += " -> " + ast.unparse(func.returns)
    return _norm(sig)


def _iter_python_files(target_dir: str):
    for root, _dirs, files in os.walk(target_dir):
        for name in sorted(files):
            if name.endswith(".py"):
                yield os.path.join(root, name)


def _observed_contracts(contracts_dir: str) -> Dict[str, Dict[str, str]]:
    observed: Dict[str, Dict[str, str]] = {}
    if not os.path.isdir(contracts_dir):
        return observed
    for path in _iter_python_files(contracts_dir):
        with open(path, "r", encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and _is_dataclass(node):
                fields: Dict[str, str] = {}
                for stmt in node.body:
                    if isinstance(stmt, ast.AnnAssign) and isinstance(
                        stmt.target, ast.Name
                    ):
                        fields[stmt.target.id] = _norm(ast.unparse(stmt.annotation))
                observed[node.name] = fields
    return observed


def _observed_domain(domain_dir: str) -> Dict[str, Dict[str, str]]:
    observed: Dict[str, Dict[str, str]] = {}
    if not os.path.isdir(domain_dir):
        return observed
    for path in _iter_python_files(domain_dir):
        with open(path, "r", encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                methods: Dict[str, str] = {}
                for stmt in node.body:
                    if isinstance(
                        stmt, (ast.FunctionDef, ast.AsyncFunctionDef)
                    ) and not stmt.name.startswith("_"):
                        methods[stmt.name] = _format_signature(stmt)
                observed[node.name] = methods
    return observed


def _load_yaml_list(path: str, key: str) -> List[dict]:
    with open(path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if data is None:
        return []
    if not isinstance(data, dict) or key not in data:
        raise ValueError("%s must be a mapping with a %r key" % (path, key))
    entries = data[key] or []
    if not isinstance(entries, list):
        raise ValueError("%s: %r must be a list" % (path, key))
    return entries


def compute_diff(
    target_dir: str, contracts_file: str, domain_file: str
) -> DiffReport:
    contracts_dir = os.path.join(target_dir, "contracts")
    domain_dir = os.path.join(target_dir, "domain")

    declared_contracts = _load_yaml_list(contracts_file, "contracts")
    declared_domain = _load_yaml_list(domain_file, "domain_classes")

    observed_contracts = _observed_contracts(contracts_dir)
    observed_domain = _observed_domain(domain_dir)

    missing_classes: List[str] = []
    field_mismatches: List[str] = []
    undeclared_contracts: List[str] = []
    signature_mismatches: List[str] = []
    info_only: List[str] = []

    declared_contract_names = set()
    for entry in declared_contracts:
        name = entry["name"]
        declared_contract_names.add(name)
        declared_fields = {
            field: _norm(str(ftype))
            for field, ftype in (entry.get("fields") or {}).items()
        }
        if name not in observed_contracts:
            missing_classes.append(name)
            continue
        observed_fields = observed_contracts[name]
        for field, declared_type in declared_fields.items():
            if field not in observed_fields:
                field_mismatches.append(
                    "%s.%s: declared but not in code" % (name, field)
                )
            elif observed_fields[field] != declared_type:
                field_mismatches.append(
                    "%s.%s: declared %r, code has %r"
                    % (name, field, declared_type, observed_fields[field])
                )
        for field in observed_fields:
            if field not in declared_fields:
                field_mismatches.append(
                    "%s.%s: in code but not declared" % (name, field)
                )

    for name in sorted(observed_contracts):
        if name not in declared_contract_names:
            undeclared_contracts.append(name)

    declared_domain_names = set()
    for entry in declared_domain:
        name = entry["name"]
        declared_domain_names.add(name)
        declared_methods = {
            method: _norm(str(sig))
            for method, sig in (entry.get("methods") or {}).items()
        }
        if name not in observed_domain:
            missing_classes.append(name)
            continue
        observed_methods = observed_domain[name]
        for method, declared_sig in declared_methods.items():
            if method not in observed_methods:
                signature_mismatches.append(
                    "%s.%s: declared but not in code" % (name, method)
                )
            elif observed_methods[method] != declared_sig:
                signature_mismatches.append(
                    "%s.%s: declared %r, code has %r"
                    % (name, method, declared_sig, observed_methods[method])
                )

    for name in sorted(observed_domain):
        if name not in declared_domain_names:
            info_only.append(name)

    return DiffReport(
        declared_contracts=tuple(sorted(declared_contract_names)),
        observed_contracts=tuple(sorted(observed_contracts)),
        missing_classes=tuple(missing_classes),
        field_mismatches=tuple(field_mismatches),
        undeclared_contracts=tuple(undeclared_contracts),
        signature_mismatches=tuple(signature_mismatches),
        info_only=tuple(info_only),
    )


def format_report(report: DiffReport) -> str:
    lines = ["# Intended-vs-observed diff", ""]
    lines.append(
        "Declared contracts: "
        + (", ".join(report.declared_contracts) or "(none)")
    )
    lines.append(
        "Observed contracts: "
        + (", ".join(report.observed_contracts) or "(none)")
    )
    lines.append("")

    def _section(title: str, items: Tuple[str, ...]) -> None:
        lines.append("## %s" % title)
        if items:
            lines.extend("- %s" % item for item in items)
        else:
            lines.append("- none")
        lines.append("")

    _section("Missing classes (declared, not in code)", report.missing_classes)
    _section("Field mismatches", report.field_mismatches)
    _section(
        "Undeclared contracts (in code, not in contracts.yaml)",
        report.undeclared_contracts,
    )
    _section("Domain signature mismatches", report.signature_mismatches)
    if report.info_only:
        _section(
            "Info: domain classes in code, not curated in domain-model.yaml",
            report.info_only,
        )

    verdict = (
        "DRIFT: intended and observed disagree; reconcile the YAML or the code "
        "(human/Architect decision)."
        if report.has_drift
        else "ALIGNED: intended layer matches observed code. Report only."
    )
    lines.append("## Verdict")
    lines.append(verdict)
    lines.append("")
    return "\n".join(lines)


def main(argv: List[str]) -> int:
    if len(argv) < 3:
        sys.stderr.write(
            "usage: python -m scripts.intended_diff "
            "<target_dir> <contracts.yaml> <domain-model.yaml>\n"
        )
        return 2
    target_dir, contracts_file, domain_file = argv[0], argv[1], argv[2]
    try:
        report = compute_diff(target_dir, contracts_file, domain_file)
    except (FileNotFoundError, OSError, ValueError, yaml.YAMLError) as exc:
        sys.stderr.write("error: %s\n" % (exc,))
        return 2
    print(format_report(report))
    return 1 if report.has_drift else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
