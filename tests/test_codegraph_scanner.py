import os
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
        result = observed_domain_from_index("src/domain", nodes=nodes, class_nodes=())
        self.assertEqual(result, {"Foo": {"bar": "(x: int) -> int", "_hidden": "()"}})
        # adapters file excluded by domain_dir; free function excluded (no "::")
        self.assertNotIn("Other", result)
        self.assertNotIn("free_fn", result.get("Foo", {}))

    def test_observed_domain_from_index_seeds_methodless_public_class(self):
        # Regression: a public domain class with no method nodes (a value object,
        # e.g. a frozen dataclass) must be observed as present-with-no-methods,
        # not absent. Private classes stay excluded; classes outside domain_dir
        # are excluded.
        from scripts.codegraph_index import ClassNode, SignatureNode
        from scripts.codegraph_scanner import observed_domain_from_index
        sig_nodes = (
            SignatureNode("Foo::bar", "bar", "method", "(self, x: int) -> int",
                          "src/domain/foo.py", "python"),
        )
        class_nodes = (
            ClassNode("Foo", "Foo", "src/domain/foo.py", "python"),
            ClassNode("Valueless", "Valueless", "src/domain/foo.py", "python"),
            ClassNode("_Private", "_Private", "src/domain/foo.py", "python"),
            ClassNode("Outside", "Outside", "src/adapters/x.py", "python"),
        )
        result = observed_domain_from_index(
            "src/domain", nodes=sig_nodes, class_nodes=class_nodes
        )
        self.assertEqual(result, {"Foo": {"bar": "(x: int) -> int"}, "Valueless": {}})
        self.assertIn("Valueless", result)
        self.assertEqual(result["Valueless"], {})
        self.assertNotIn("_Private", result)
        self.assertNotIn("Outside", result)


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REAL_DB = os.path.join(REPO_ROOT, ".codegraph", "codegraph.db")


class RealRepoDomainObserverTest(unittest.TestCase):
    @unittest.skipUnless(os.path.isfile(_REAL_DB), "no real .codegraph index")
    def test_methodless_value_object_is_observed(self):
        # BoundaryDecision is a frozen dataclass value object with no method
        # nodes. Before the class-seeding fix it was invisible to the observer
        # (so declaring it read as a missing class). It must now be present.
        # The index stores repo-relative file paths, so mirror how the harness
        # calls the observer: from the repo root, with a relative domain_dir.
        from scripts.codegraph_scanner import observed_domain_from_index
        cwd = os.getcwd()
        os.chdir(REPO_ROOT)
        try:
            observed = observed_domain_from_index("src/domain", db_path=_REAL_DB)
        finally:
            os.chdir(cwd)
        self.assertIn("BoundaryDecision", observed)
        self.assertEqual(observed["BoundaryDecision"], {})
        self.assertIn("BoundaryRuleSet", observed)
        # private helper class is excluded
        self.assertNotIn("_ModuleEntry", observed)


if __name__ == "__main__":
    unittest.main()
