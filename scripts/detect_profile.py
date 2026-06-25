"""Harness tooling: seed a convention profile from a repo (iteration 8).

A committed, deterministic detector that proposes the SEED for
`.architecture/profile.yaml`. It is intentionally humble and FRAMEWORK-AGNOSTIC:
it detects the language, reports the raw manifest dependencies verbatim, and
lists the candidate top-level layers. It does NOT classify the framework (no
built-in list of frameworks to match against) and does NOT map layers to roles.
Both of those would bake an enumeration the harness must not own: there are too
many frameworks, and a directory-name-to-role heuristic is just a smaller baked
ontology. Naming the project (a free-text label) and mapping roles is the
human's confirm step (detect-then-confirm).

This is the mechanical half of the Surveyor's profile seeding, committed and
unit-tested like `scripts/drift_scan.py` and `scripts/intended_diff.py`.
"""

import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

CODE_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
}

@dataclass(frozen=True)
class ProfileSeed:
    language: str
    manifests_found: Tuple[str, ...]
    libs: Tuple[str, ...]
    candidate_layers: Tuple[str, ...]


def _parse_requirements(path: str) -> List[str]:
    libs: List[str] = []
    with open(path, "r", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            name = re.split(r"[=<>!~\[ ;]", line, maxsplit=1)[0].strip().lower()
            if name:
                libs.append(name)
    return libs


def _parse_package_json(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    libs: List[str] = []
    for key in ("dependencies", "devDependencies"):
        section = data.get(key) or {}
        if isinstance(section, dict):
            libs.extend(str(name).lower() for name in section)
    return libs


def _parse_jvm_manifest(path: str) -> List[str]:
    # Best-effort: pull dotted/hyphenated artifact-ish tokens. Good enough to
    # spot "spring" / "spring-boot"; full POM parsing is out of scope.
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read().lower()
    return re.findall(r"[a-z][a-z0-9.\-]{2,}", text)


def _collect_manifests(target_dir: str) -> Tuple[List[str], List[str]]:
    found: List[str] = []
    libs: List[str] = []
    candidates = {
        "requirements.txt": _parse_requirements,
        "package.json": _parse_package_json,
        "pom.xml": _parse_jvm_manifest,
        "build.gradle": _parse_jvm_manifest,
    }
    for name, parser in candidates.items():
        path = os.path.join(target_dir, name)
        if os.path.isfile(path):
            found.append(name)
            try:
                libs.extend(parser(path))
            except (OSError, ValueError, json.JSONDecodeError):
                # A malformed manifest still counts as "found"; it just yields
                # no libs rather than aborting detection.
                pass
    return found, libs


def _language_from_manifests(manifests: List[str]) -> Optional[str]:
    if "requirements.txt" in manifests:
        return "python"
    if "package.json" in manifests:
        return "javascript"
    if "pom.xml" in manifests or "build.gradle" in manifests:
        return "java"
    return None


def _language_from_extensions(source_dir: str) -> Optional[str]:
    counts: Dict[str, int] = {}
    for _root, _dirs, files in os.walk(source_dir):
        for name in files:
            ext = os.path.splitext(name)[1]
            lang = CODE_EXTENSIONS.get(ext)
            if lang:
                counts[lang] = counts.get(lang, 0) + 1
    if not counts:
        return None
    return max(counts, key=counts.get)


def _candidate_layers(source_dir: str) -> Tuple[str, ...]:
    if not os.path.isdir(source_dir):
        return ()
    layers: List[str] = []
    for child in sorted(os.listdir(source_dir)):
        if child.startswith((".", "_")):
            continue
        child_path = os.path.join(source_dir, child)
        if not os.path.isdir(child_path):
            continue
        if _dir_has_code(child_path):
            layers.append(child)
    return tuple(layers)


def _dir_has_code(path: str) -> bool:
    for _root, _dirs, files in os.walk(path):
        for name in files:
            if os.path.splitext(name)[1] in CODE_EXTENSIONS:
                return True
    return False


def compute_profile_seed(target_dir: str, source_dir: str) -> ProfileSeed:
    manifests, libs = _collect_manifests(target_dir)
    language = _language_from_manifests(manifests) or _language_from_extensions(
        source_dir
    ) or "unknown"
    return ProfileSeed(
        language=language,
        manifests_found=tuple(manifests),
        libs=tuple(sorted(set(libs))),
        candidate_layers=_candidate_layers(source_dir),
    )


def format_seed(seed: ProfileSeed) -> str:
    lines = ["# Profile seed (detect-then-confirm). Edit and save into profile.yaml.", ""]
    lines.append("label:    # free-text human note for this project; NOTHING branches on it")
    lines.append("language: %s" % (seed.language,))
    lines.append("detected_from:")
    for manifest in seed.manifests_found or ["(no manifest; inferred from file extensions)"]:
        lines.append("  - %s" % (manifest,))
    if seed.libs:
        lines.append("# manifest dependencies detected (verbatim, for your reference):")
        for lib in seed.libs:
            lines.append("#   - %s" % (lib,))
    lines.append("# candidate layers detected (map each to a role below):")
    for layer in seed.candidate_layers or ["(none detected)"]:
        lines.append("#   - %s" % (layer,))
    lines.append("roles:   # confirm: map each role to one of the candidate layers")
    lines.append("  behavior_layer: ")
    lines.append("  boundary_shape_layer: ")
    lines.append("  entrypoint_layer: ")
    lines.append("  io_layer: ")
    lines.append("")
    return "\n".join(lines)


def main(argv: List[str]) -> int:
    if not argv:
        sys.stderr.write(
            "usage: python -m scripts.detect_profile <target_dir> [source_dir]\n"
        )
        return 2
    target_dir = argv[0]
    source_dir = argv[1] if len(argv) > 1 else target_dir
    seed = compute_profile_seed(target_dir, source_dir)
    print(format_seed(seed))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
