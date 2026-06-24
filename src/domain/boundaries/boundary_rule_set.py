"""Domain: the boundary-check business rule.

`BoundaryRuleSet` is a frozen domain value object that owns the
violation-detection behavior. It is constructed from already-validated plain
inputs (strings, tuples) supplied by the application layer, never from the
contract classes, so the intended `domain must_not_depend_on contracts` rule is
preserved. This module imports only the standard library.
"""

from dataclasses import dataclass
from typing import Iterable, List, Mapping, Optional, Tuple


@dataclass(frozen=True)
class _ModuleEntry:
    name: str
    path_glob: str
    may_depend_on: Tuple[str, ...]
    must_not_depend_on: Tuple[str, ...]
    may_only_depend_on: Tuple[str, ...]


@dataclass(frozen=True)
class BoundaryDecision:
    """A plain domain result describing one detected violation.

    This is a domain-owned value object (not a contract class). The application
    layer maps it onto the `BoundaryViolation` contract for output.
    """

    source_module: str
    target_module: str
    rule_kind: str
    file_path: str
    line: int


def _glob_prefix(path_glob: str) -> str:
    """Return the literal directory prefix of a `dir/**` style glob.

    The only glob form used by boundaries.yaml is a directory prefix followed by
    `**`. We reduce it to that literal prefix so path matching is deterministic
    and most-specific (longest prefix) wins.
    """
    marker = path_glob.find("*")
    prefix = path_glob if marker == -1 else path_glob[:marker]
    return prefix.rstrip("/")


@dataclass(frozen=True)
class BoundaryRuleSet:
    rules: Tuple[_ModuleEntry, ...]

    @staticmethod
    def from_rules(rules: Iterable[Mapping[str, object]]) -> "BoundaryRuleSet":
        entries: List[_ModuleEntry] = []
        seen = set()
        for raw in rules:
            name = raw.get("name")
            path_glob = raw.get("path_glob")
            if not name or not isinstance(name, str):
                raise ValueError("module rule requires a non-empty name")
            if not path_glob or not isinstance(path_glob, str):
                raise ValueError(
                    "module rule %r requires a non-empty path_glob" % (name,)
                )
            if name in seen:
                raise ValueError("duplicate module name %r" % (name,))
            seen.add(name)
            entries.append(
                _ModuleEntry(
                    name=name,
                    path_glob=path_glob,
                    may_depend_on=tuple(raw.get("may_depend_on", ()) or ()),
                    must_not_depend_on=tuple(
                        raw.get("must_not_depend_on", ()) or ()
                    ),
                    may_only_depend_on=tuple(
                        raw.get("may_only_depend_on", ()) or ()
                    ),
                )
            )
        if not entries:
            raise ValueError("a boundary rule set needs at least one module")
        return BoundaryRuleSet(rules=tuple(entries))

    def module_for_path(self, path: str) -> Optional[str]:
        """Return the module name a file or dotted-import path belongs to.

        Path globs are reduced to their literal directory prefix; the most
        specific (longest) matching prefix wins, so overlapping globs resolve
        deterministically. Returns None when nothing matches (stdlib / third
        party / external).
        """
        normalized = path.replace("\\", "/")
        best_name: Optional[str] = None
        best_len = -1
        for entry in self.rules:
            prefix = _glob_prefix(entry.path_glob)
            if normalized == prefix or normalized.startswith(prefix + "/"):
                if len(prefix) > best_len:
                    best_len = len(prefix)
                    best_name = entry.name
        return best_name

    def check(
        self,
        source_module: Optional[str],
        target_module: Optional[str],
        file_path: str,
        line: int,
    ) -> List[BoundaryDecision]:
        """Decide whether a source -> target module pair breaks a rule.

        Returns a list of `BoundaryDecision` results (empty when allowed). A
        pair is flagged when the target appears in the source module's
        `must_not_depend_on` list, and, separately, when the source declares a
        present, non-empty `may_only_depend_on` allowlist and the target is a
        known module absent from it. The allowlist is strictly opt-in: an absent
        or empty allowlist leaves behavior unchanged. Unknown target modules
        (stdlib / third party) and self-references are ignored, so a single edge
        can produce both a `must_not_depend_on` and a `may_only_depend_on`
        finding.
        """
        if not source_module or not target_module:
            return []
        if source_module == target_module:
            return []
        entry = self._entry(source_module)
        if entry is None:
            return []
        decisions: List[BoundaryDecision] = []
        if target_module in entry.must_not_depend_on:
            decisions.append(
                BoundaryDecision(
                    source_module=source_module,
                    target_module=target_module,
                    rule_kind="must_not_depend_on",
                    file_path=file_path,
                    line=line,
                )
            )
        if (
            entry.may_only_depend_on
            and self._entry(target_module) is not None
            and target_module not in entry.may_only_depend_on
        ):
            decisions.append(
                BoundaryDecision(
                    source_module=source_module,
                    target_module=target_module,
                    rule_kind="may_only_depend_on",
                    file_path=file_path,
                    line=line,
                )
            )
        return decisions

    def _entry(self, name: str) -> Optional[_ModuleEntry]:
        for entry in self.rules:
            if entry.name == name:
                return entry
        return None
