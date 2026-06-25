"""Harness tooling: read observed structure from the CodeGraph index.

Iteration 9a. The harness's boundary checking reads import edges from the
CodeGraph index (`.codegraph/codegraph.db`) instead of re-parsing source with
Python `ast`. CodeGraph already indexes multiple languages, so this is the
polyglot, deduplicated observed source the iter-7 retro pointed to.

The CLI is search-oriented (no bulk export), so this reads the SQLite DB
directly, guarded by its `schema_versions` table: if the schema version is not
the one this adapter was built against, it raises rather than silently
mis-reading. The DB is opened read-only so a check never mutates the index.

`imports` edges resolve source-file -> target-file for every language CodeGraph
indexes, so the observation is `(source_file, target_file, line)` with no
language-specific dotted-vs-relative import parsing. The caller maps both files
to modules via the domain `BoundaryRuleSet`.
"""

import os
import sqlite3
from dataclasses import dataclass
from typing import List, Tuple

# The max `schema_versions.version` this adapter was built against. A different
# version means CodeGraph changed its store; fail loud instead of guessing.
EXPECTED_SCHEMA = 5


class CodegraphIndexError(Exception):
    """Raised when the CodeGraph index is missing or its schema is unrecognized
    (a could-not-run condition the caller maps to exit 2)."""


@dataclass(frozen=True)
class ImportObservation:
    source_file: str
    target_file: str
    line: int


@dataclass(frozen=True)
class SignatureNode:
    qualified_name: str
    name: str
    kind: str
    signature: str
    file_path: str
    language: str


def _connect_ro(db_path: str) -> sqlite3.Connection:
    if not os.path.isfile(db_path):
        raise CodegraphIndexError(
            "no CodeGraph index at %s; run `codegraph init`/`sync`" % (db_path,)
        )
    try:
        return sqlite3.connect("file:%s?mode=ro" % (db_path,), uri=True)
    except sqlite3.Error as exc:
        raise CodegraphIndexError("could not open %s: %s" % (db_path, exc))


def _check_schema(conn: sqlite3.Connection) -> None:
    try:
        row = conn.execute("SELECT max(version) FROM schema_versions").fetchone()
    except sqlite3.Error as exc:
        raise CodegraphIndexError("index has no readable schema_versions: %s" % (exc,))
    version = row[0] if row else None
    if version != EXPECTED_SCHEMA:
        raise CodegraphIndexError(
            "CodeGraph index schema version %r != expected %d; this adapter was "
            "built against %d (a CodeGraph upgrade may have changed the store)"
            % (version, EXPECTED_SCHEMA, EXPECTED_SCHEMA)
        )


def observed_import_edges(
    db_path: str = ".codegraph/codegraph.db",
) -> List[ImportObservation]:
    """Return the cross-file import edges from the CodeGraph index, deduped, with
    self-file edges dropped. Language-agnostic (files, not dotted names)."""
    conn = _connect_ro(db_path)
    try:
        _check_schema(conn)
        rows = conn.execute(
            """
            SELECT DISTINCT s.file_path, t.file_path, e.line
            FROM edges e
            JOIN nodes s ON s.id = e.source
            JOIN nodes t ON t.id = e.target
            WHERE e.kind = 'imports'
              AND s.file_path IS NOT NULL
              AND t.file_path IS NOT NULL
              AND s.file_path != t.file_path
            """
        ).fetchall()
    except sqlite3.Error as exc:
        raise CodegraphIndexError("could not read import edges: %s" % (exc,))
    finally:
        conn.close()
    return [
        ImportObservation(source_file=s, target_file=t, line=line)
        for (s, t, line) in rows
    ]


_SIGNATURE_SQL = """
SELECT qualified_name, name, kind, signature, file_path, language
FROM nodes
WHERE kind IN ('method', 'function')
  AND signature IS NOT NULL
  AND file_path IS NOT NULL
"""


def observed_signature_nodes(db_path: str = ".codegraph/codegraph.db") -> Tuple[SignatureNode, ...]:
    """Read method/function signatures from the CodeGraph index, schema-guarded
    and read-only. `qualified_name` carries `Class::method` (the language-neutral
    separator CodeGraph uses); a free function has a bare qualified name. The
    caller groups by class and maps `file_path` to a layer."""
    conn = _connect_ro(db_path)
    try:
        _check_schema(conn)
        rows = conn.execute(_SIGNATURE_SQL).fetchall()
    finally:
        conn.close()
    return tuple(
        SignatureNode(
            qualified_name=qn,
            name=name,
            kind=kind,
            signature=sig,
            file_path=fp,
            language=lang or "",
        )
        for qn, name, kind, sig, fp, lang in rows
    )
