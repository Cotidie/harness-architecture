import unittest

from scripts.codegraph_index import ImportObservation
from scripts.codegraph_scanner import scan_imports_from_index
from src.domain.boundaries.boundary_rule_set import BoundaryRuleSet


def _rule_set():
    return BoundaryRuleSet.from_rules(
        [
            {
                "name": "domain",
                "path_glob": "src/domain/**",
                "may_depend_on": (),
                "must_not_depend_on": ("adapters",),
                "may_only_depend_on": (),
            },
            {
                "name": "adapters",
                "path_glob": "src/adapters/**",
                "may_depend_on": ("domain",),
                "must_not_depend_on": (),
                "may_only_depend_on": (),
            },
        ]
    )


class CodegraphScannerTest(unittest.TestCase):
    def test_maps_observations_to_import_edges(self):
        edges_in = [
            ImportObservation("src/adapters/io.py", "src/domain/core.py", 5),
            ImportObservation("src/domain/core.py", "src/adapters/io.py", 3),
        ]
        result = scan_imports_from_index(_rule_set(), edges=edges_in)
        pairs = {(e.source_module, e.imported_module) for e in result.edges}
        self.assertIn(("adapters", "domain"), pairs)
        self.assertIn(("domain", "adapters"), pairs)
        self.assertEqual(result.matched_file_count, 2)
        self.assertEqual(result.parse_failures, [])
        # ImportEdge carries the source file + line for reporting.
        adapters_edge = next(e for e in result.edges if e.source_module == "adapters")
        self.assertEqual(adapters_edge.file_path, "src/adapters/io.py")
        self.assertEqual(adapters_edge.line, 5)

    def test_drops_edges_to_unmapped_target(self):
        edges_in = [
            ImportObservation("src/adapters/io.py", "vendor/lib/x.py", 7),
        ]
        result = scan_imports_from_index(_rule_set(), edges=edges_in)
        self.assertEqual(result.edges, [])
        # source still mapped -> counted as a matched file
        self.assertEqual(result.matched_file_count, 1)

    def test_drops_and_uncounts_unmapped_source(self):
        edges_in = [
            ImportObservation("vendor/lib/x.py", "src/domain/core.py", 1),
        ]
        result = scan_imports_from_index(_rule_set(), edges=edges_in)
        self.assertEqual(result.edges, [])
        self.assertEqual(result.matched_file_count, 0)


if __name__ == "__main__":
    unittest.main()
