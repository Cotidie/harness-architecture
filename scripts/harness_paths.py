"""Harness tooling: resolve the deterministic checks' paths from the profile.

The committed checks (boundaries linter, drift_scan, intended_diff) used to
hardcode `src/`. This resolver reads `.architecture/profile.yaml`'s `source_root`
and builds the concrete paths each check needs, so the harness targets the
project's real layout on any repo, not just this self-host. The intended-layer
YAML files keep fixed names under the architecture directory.
"""

import os
from dataclasses import dataclass

import yaml


class HarnessPathsError(Exception):
    """Raised when the profile cannot be resolved into check paths (a
    could-not-run condition the caller maps to exit 2)."""


@dataclass(frozen=True)
class Paths:
    source_dir: str
    boundaries: str
    contracts: str
    domain_model: str


def resolve_paths(repo_root: str = ".", arch_dir: str = ".architecture") -> Paths:
    arch = os.path.join(repo_root, arch_dir)
    profile_path = os.path.join(arch, "profile.yaml")
    if not os.path.isfile(profile_path):
        raise HarnessPathsError(
            "no profile at %s; run the surveyor to seed the convention profile"
            % (profile_path,)
        )
    with open(profile_path, "r", encoding="utf-8") as handle:
        profile = yaml.safe_load(handle) or {}
    source_root = profile.get("source_root")
    if not isinstance(source_root, str) or not source_root:
        raise HarnessPathsError(
            "profile %s has no `source_root`; add it (the code root the checks "
            "target, relative to the repo root)" % (profile_path,)
        )
    return Paths(
        source_dir=os.path.join(repo_root, source_root),
        boundaries=os.path.join(arch, "boundaries.yaml"),
        contracts=os.path.join(arch, "contracts.yaml"),
        domain_model=os.path.join(arch, "domain-model.yaml"),
    )
