"""Adapter: scan a Python tree and emit resolved ImportEdge contracts.

Walks the target directory, parses each file with `ast`, collects module-level
absolute imports, maps the source file and each imported dotted name to a module
via the rule path globs (delegated to the domain `BoundaryRuleSet`), and emits
one `ImportEdge` per import that resolves to a known module. Imports that map to
no module (stdlib / third party / external) are ignored.

Robustness (patch linter-hardening): the target directory is validated up front
(a missing path or a non-directory raises for the CLI to catch), the number of
`.py` files actually attributed to a module is tracked so the CLI can loud-fail
a zero-match tree, and a per-file `SyntaxError` is recovered into a
`BoundaryViolation` parse-failure finding (rule_kind="parse_error") rather than
aborting the whole scan.

Scope limitation (patch section 11): only module-level absolute imports are
resolved. Relative imports and function-local imports are not tracked.
"""

import ast
import os
from dataclasses import dataclass
from typing import List

from src.contracts.boundaries.boundary_violation import BoundaryViolation
from src.contracts.boundaries.import_edge import ImportEdge
from src.domain.boundaries.boundary_rule_set import BoundaryRuleSet


@dataclass(frozen=True)
class ScanResult:
    """The outcome of a scan: resolved edges, parse failures, and a count.

    `matched_file_count` is the number of `.py` files attributed to a module
    (whether or not they parsed); the CLI uses it to loud-fail a tree that
    matches no module glob. `parse_failures` are reportable findings carried as
    the official `BoundaryViolation` contract, never as a raw dict/list.
    """

    edges: List[ImportEdge]
    parse_failures: List[BoundaryViolation]
    matched_file_count: int


def _dotted_to_path(dotted: str) -> str:
    return dotted.replace(".", "/")


def _imports_in_file(tree: ast.AST):
    """Yield (dotted_name, line) for each module-level absolute import."""
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, node.lineno
        elif isinstance(node, ast.ImportFrom):
            # level > 0 means a relative import; out of scope.
            if node.level and node.level > 0:
                continue
            if node.module:
                yield node.module, node.lineno


def scan_imports(target_dir: str, rule_set: BoundaryRuleSet) -> ScanResult:
    if not os.path.exists(target_dir):
        raise FileNotFoundError(
            "target directory does not exist: %s" % (target_dir,)
        )
    if not os.path.isdir(target_dir):
        raise NotADirectoryError(
            "target path is not a directory: %s" % (target_dir,)
        )

    edges: List[ImportEdge] = []
    parse_failures: List[BoundaryViolation] = []
    matched_file_count = 0

    for root, _dirs, files in os.walk(target_dir):
        for filename in sorted(files):
            if not filename.endswith(".py"):
                continue
            file_path = os.path.join(root, filename)
            normalized_path = file_path.replace("\\", "/")
            source_module = rule_set.module_for_path(normalized_path)
            if source_module is None:
                continue
            matched_file_count += 1
            with open(file_path, "r", encoding="utf-8") as handle:
                source = handle.read()
            try:
                tree = ast.parse(source, filename=file_path)
            except SyntaxError as exc:
                # Recover: emit a parse-failure finding and keep scanning.
                parse_failures.append(
                    BoundaryViolation(
                        source_module=source_module,
                        target_module=source_module,
                        rule_kind="parse_error",
                        file_path=normalized_path,
                        line=exc.lineno or 0,
                    )
                )
                continue
            for dotted, line in _imports_in_file(tree):
                imported_module = rule_set.module_for_path(
                    _dotted_to_path(dotted)
                )
                if imported_module is None:
                    continue
                edges.append(
                    ImportEdge(
                        source_module=source_module,
                        imported_module=imported_module,
                        file_path=normalized_path,
                        line=line,
                    )
                )

    return ScanResult(
        edges=edges,
        parse_failures=parse_failures,
        matched_file_count=matched_file_count,
    )
