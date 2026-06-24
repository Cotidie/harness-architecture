"""Adapter: scan a Python tree and emit resolved ImportEdge contracts.

Walks the target directory, parses each file with `ast`, collects module-level
absolute imports, maps the source file and each imported dotted name to a module
via the rule path globs (delegated to the domain `BoundaryRuleSet`), and emits
one `ImportEdge` per import that resolves to a known module. Imports that map to
no module (stdlib / third party / external) are ignored.

Scope limitation (patch section 11): only module-level absolute imports are
resolved. Relative imports and function-local imports are not tracked.
"""

import ast
import os
from typing import List

from src.contracts.boundaries.import_edge import ImportEdge
from src.domain.boundaries.boundary_rule_set import BoundaryRuleSet


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


def scan_imports(
    target_dir: str, rule_set: BoundaryRuleSet
) -> List[ImportEdge]:
    edges: List[ImportEdge] = []
    for root, _dirs, files in os.walk(target_dir):
        for filename in sorted(files):
            if not filename.endswith(".py"):
                continue
            file_path = os.path.join(root, filename)
            normalized_path = file_path.replace("\\", "/")
            source_module = rule_set.module_for_path(normalized_path)
            if source_module is None:
                continue
            with open(file_path, "r", encoding="utf-8") as handle:
                source = handle.read()
            tree = ast.parse(source, filename=file_path)
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
    return edges
