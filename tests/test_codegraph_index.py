import os
import sqlite3
import tempfile
import unittest

from scripts.codegraph_index import (
    EXPECTED_SCHEMA,
    CodegraphIndexError,
    observed_import_edges,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL_DB = os.path.join(REPO_ROOT, ".codegraph", "codegraph.db")


def _build_db(path, schema_version=EXPECTED_SCHEMA, with_edges=True):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE schema_versions (version INTEGER, applied_at INTEGER, description TEXT);
        CREATE TABLE nodes (id TEXT, kind TEXT, name TEXT, file_path TEXT);
        CREATE TABLE edges (id TEXT, source TEXT, target TEXT, kind TEXT, line INTEGER);
        """
    )
    conn.execute(
        "INSERT INTO schema_versions VALUES (1, 0, 'init')"
    )
    conn.execute(
        "INSERT INTO schema_versions VALUES (?, 0, 'latest')", (schema_version,)
    )
    nodes = [
        ("n1", "file", "a", "src/adapters/io.py"),
        ("n2", "file", "b", "src/domain/core.py"),
        ("n3", "import", "x", "src/adapters/io.py"),  # self-file import node
    ]
    conn.executemany("INSERT INTO nodes VALUES (?,?,?,?)", nodes)
    if with_edges:
        edges = [
            # real cross-file import: adapters/io.py -> domain/core.py at line 5
            ("e1", "n1", "n2", "imports", 5),
            # duplicate target rows for same edge (file + class) collapse to one
            ("e2", "n1", "n2", "imports", 5),
            # self-file edge (source == target file) must be dropped
            ("e3", "n1", "n3", "imports", 1),
            # a non-import edge must be ignored
            ("e4", "n1", "n2", "calls", 9),
        ]
        conn.executemany("INSERT INTO edges VALUES (?,?,?,?,?)", edges)
    conn.commit()
    conn.close()


class CodegraphIndexTest(unittest.TestCase):
    def test_yields_dedup_cross_file_import_edges(self):
        with tempfile.TemporaryDirectory() as d:
            db = os.path.join(d, "codegraph.db")
            _build_db(db)
            edges = observed_import_edges(db)
        self.assertEqual(len(edges), 1)
        obs = edges[0]
        self.assertEqual(obs.source_file, "src/adapters/io.py")
        self.assertEqual(obs.target_file, "src/domain/core.py")
        self.assertEqual(obs.line, 5)

    def test_missing_db_raises(self):
        with self.assertRaises(CodegraphIndexError):
            observed_import_edges("/no/such/codegraph.db")

    def test_unrecognized_schema_raises(self):
        with tempfile.TemporaryDirectory() as d:
            db = os.path.join(d, "codegraph.db")
            _build_db(db, schema_version=EXPECTED_SCHEMA + 99)
            with self.assertRaises(CodegraphIndexError):
                observed_import_edges(db)

    @unittest.skipUnless(os.path.isfile(REAL_DB), "no real .codegraph index")
    def test_real_index_smoke(self):
        edges = observed_import_edges(REAL_DB)
        self.assertTrue(edges, "expected some import edges in the real index")
        # every observation is a cross-file pair
        self.assertTrue(all(e.source_file != e.target_file for e in edges))


if __name__ == "__main__":
    unittest.main()
