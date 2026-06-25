"""Harness tooling: a CodeGraph-backed scanner producing the ScanResult contract.

Iteration 9a. Drop-in replacement for the Python-`ast` `scan_imports` as the
OBSERVED source of import edges for the harness's boundary checking. It takes
cross-file import observations from the CodeGraph index and maps each file to a
module via the UNCHANGED domain `BoundaryRuleSet`, emitting the same
`ImportEdge` / `ScanResult` contract the use case already consumes. Polyglot: the
observations are file -> file, so no language-specific import parsing lives here.

The sample boundaries linter CLI keeps its `ast` scanner; this is the harness's
observed source, not the dogfood's.
"""

from typing import List, Optional, Sequence

from scripts.codegraph_index import ImportObservation, observed_import_edges

from src.adapters.boundaries.python_import_scanner import ScanResult
from src.contracts.boundaries.import_edge import ImportEdge
from src.domain.boundaries.boundary_rule_set import BoundaryRuleSet


def scan_imports_from_index(
    rule_set: BoundaryRuleSet,
    edges: Optional[Sequence[ImportObservation]] = None,
    db_path: str = ".codegraph/codegraph.db",
) -> ScanResult:
    """Produce a ScanResult from CodeGraph import observations.

    `edges` is the dependency-injection seam: tests pass observations directly;
    the harness leaves it None to read from the CodeGraph index at `db_path`
    (which raises CodegraphIndexError if the index is missing or stale).

    `matched_file_count` counts the distinct source files that map to a module
    (the loud-fail guard against a boundaries.yaml whose globs match nothing).
    Note: a mapped file with zero imports does not appear in the index's import
    edges, so it is not counted; that is acceptable for the guard (its job is to
    catch a total glob/layout mismatch, which still yields zero here).

    `parse_failures` is always empty: CodeGraph already parsed the tree, so there
    is no per-file SyntaxError to recover the way the `ast` scanner does.
    """
    if edges is None:
        edges = observed_import_edges(db_path)

    import_edges: List[ImportEdge] = []
    matched_sources = set()
    for obs in edges:
        source_module = rule_set.module_for_path(obs.source_file)
        if source_module is None:
            continue
        matched_sources.add(obs.source_file)
        imported_module = rule_set.module_for_path(obs.target_file)
        if imported_module is None:
            continue
        import_edges.append(
            ImportEdge(
                source_module=source_module,
                imported_module=imported_module,
                file_path=obs.source_file,
                line=obs.line,
            )
        )

    return ScanResult(
        edges=import_edges,
        parse_failures=[],
        matched_file_count=len(matched_sources),
    )
