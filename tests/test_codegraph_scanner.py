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

    def test_normalize_signature_strips_self_and_collapses_space(self):
        from scripts.codegraph_scanner import normalize_signature
        self.assertEqual(
            normalize_signature("(self,  path: str)  -> Optional[str]"),
            "(path: str) -> Optional[str]",
        )
        self.assertEqual(normalize_signature("(self)"), "()")
        self.assertEqual(normalize_signature("(cls, x: int)"), "(x: int)")
        # a free function with a leading non-receiver arg is untouched (besides spacing)
        self.assertEqual(normalize_signature("(rules:  Iterable)"), "(rules: Iterable)")

    def test_observed_domain_from_index_groups_methods_by_class(self):
        from scripts.codegraph_index import SignatureNode
        from scripts.codegraph_scanner import observed_domain_from_index
        nodes = (
            SignatureNode("Foo::bar", "bar", "method", "(self, x: int) -> int",
                          "src/domain/foo.py", "python"),
            SignatureNode("Foo::_hidden", "_hidden", "method", "(self)",
                          "src/domain/foo.py", "python"),
            SignatureNode("free_fn", "free_fn", "function", "(a: int)",
                          "src/domain/foo.py", "python"),
            SignatureNode("Other::baz", "baz", "method", "(self)",
                          "src/adapters/other.py", "python"),
        )
        result = observed_domain_from_index("src/domain", nodes=nodes)
        self.assertEqual(result, {"Foo": {"bar": "(x: int) -> int", "_hidden": "()"}})
        # adapters file excluded by domain_dir; free function excluded (no "::")
        self.assertNotIn("Other", result)
        self.assertNotIn("free_fn", result.get("Foo", {}))


if __name__ == "__main__":
    unittest.main()
