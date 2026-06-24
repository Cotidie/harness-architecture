"""Adapter: load and validate boundaries.yaml into ModuleRule contracts.

This is the ONLY module that imports PyYAML. It performs the IO (reading the
YAML file) and produces the official `ModuleRule` contract instances. It does
not build the domain object directly: the application layer maps these
contracts into the domain `BoundaryRuleSet` inputs.
"""

from typing import Tuple

import yaml

from src.contracts.boundaries.module_rule import ModuleRule


class BoundariesConfigError(Exception):
    """Raised when boundaries.yaml is missing required structure."""


def load_module_rules(boundaries_path: str) -> Tuple[ModuleRule, ...]:
    try:
        with open(boundaries_path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except FileNotFoundError as exc:
        raise BoundariesConfigError(
            "boundaries file not found: %s" % (boundaries_path,)
        ) from exc
    except OSError as exc:
        raise BoundariesConfigError(
            "could not read boundaries file %s: %s"
            % (boundaries_path, exc)
        ) from exc
    except yaml.YAMLError as exc:
        raise BoundariesConfigError(
            "boundaries file is not valid YAML: %s" % (exc,)
        ) from exc

    if not isinstance(data, dict):
        raise BoundariesConfigError(
            "boundaries file must be a mapping at the top level"
        )
    modules = data.get("modules")
    if not isinstance(modules, dict) or not modules:
        raise BoundariesConfigError(
            "boundaries file must contain a non-empty 'modules' mapping"
        )

    rules = []
    for name, spec in modules.items():
        if not isinstance(spec, dict):
            raise BoundariesConfigError(
                "module %r must map to a spec object" % (name,)
            )
        path_glob = spec.get("path")
        if not isinstance(path_glob, str) or not path_glob:
            raise BoundariesConfigError(
                "module %r requires a non-empty 'path' glob" % (name,)
            )
        rules.append(
            ModuleRule(
                name=str(name),
                path_glob=path_glob,
                may_depend_on=tuple(spec.get("may_depend_on", []) or []),
                must_not_depend_on=tuple(
                    spec.get("must_not_depend_on", []) or []
                ),
                may_only_depend_on=tuple(
                    spec.get("may_only_depend_on", []) or []
                ),
            )
        )
    return tuple(rules)
