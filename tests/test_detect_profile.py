import contextlib
import os
import tempfile
import textwrap
import unittest

from scripts.detect_profile import compute_profile_seed


@contextlib.contextmanager
def _tree(files):
    """Materialize {relpath: content} under a temp dir; yield its path."""
    with tempfile.TemporaryDirectory() as root:
        for relpath, content in files.items():
            full = os.path.join(root, relpath)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as handle:
                handle.write(content)
        yield root


class DetectProfileTest(unittest.TestCase):
    def test_flask_layout(self):
        with _tree(
            {
                "requirements.txt": "flask==3.0.0\njinja2\n",
                "blueprints/__init__.py": "",
                "blueprints/auth.py": "x = 1\n",
                "services/__init__.py": "",
                "services/user.py": "y = 2\n",
                "models/__init__.py": "",
                "models/user.py": "z = 3\n",
            }
        ) as root:
            seed = compute_profile_seed(root, root)
        self.assertEqual(seed.language, "python")
        self.assertEqual(seed.framework_guess, "python/flask")
        self.assertEqual(seed.candidate_layers, ("blueprints", "models", "services"))

    def test_self_host_like_no_web_framework(self):
        with _tree(
            {
                "requirements.txt": "pyyaml>=6.0\n",
                "src/domain/__init__.py": "",
                "src/domain/core.py": "x = 1\n",
                "src/adapters/__init__.py": "",
                "src/adapters/io.py": "y = 2\n",
                "src/contracts/__init__.py": "",
                "src/contracts/dto.py": "z = 3\n",
            }
        ) as root:
            seed = compute_profile_seed(root, os.path.join(root, "src"))
        self.assertEqual(seed.language, "python")
        self.assertEqual(seed.framework_guess, "python/unknown")
        self.assertEqual(seed.candidate_layers, ("adapters", "contracts", "domain"))

    def test_react_package_json(self):
        with _tree(
            {
                "package.json": '{"dependencies": {"react": "^18.0.0", "lodash": "*"}}',
                "components/__init__.js": "",
                "components/app.js": "export default 1;\n",
                "hooks/use_thing.js": "export const x = 1;\n",
            }
        ) as root:
            seed = compute_profile_seed(root, root)
        self.assertEqual(seed.language, "javascript")
        self.assertEqual(seed.framework_guess, "js/react")
        self.assertEqual(seed.candidate_layers, ("components", "hooks"))

    def test_no_manifest_infers_language_from_extensions(self):
        with _tree(
            {
                "pkg/__init__.py": "",
                "pkg/thing.py": "x = 1\n",
            }
        ) as root:
            seed = compute_profile_seed(root, root)
        self.assertEqual(seed.language, "python")
        self.assertEqual(seed.framework_guess, "python/unknown")
        self.assertEqual(seed.manifests_found, ())

    def test_pycache_and_codeless_dirs_excluded(self):
        with _tree(
            {
                "requirements.txt": "flask\n",
                "blueprints/__init__.py": "",
                "blueprints/__pycache__/x.pyc": "compiled",
                "docs/readme.md": "# not code\n",
                "assets/logo.svg": "<svg/>\n",
            }
        ) as root:
            seed = compute_profile_seed(root, root)
        self.assertEqual(seed.candidate_layers, ("blueprints",))

    def test_unknown_when_nothing_detectable(self):
        with _tree({"README.md": "# empty\n"}) as root:
            seed = compute_profile_seed(root, root)
        self.assertEqual(seed.language, "unknown")
        self.assertEqual(seed.framework_guess, "unknown")
        self.assertEqual(seed.candidate_layers, ())


if __name__ == "__main__":
    unittest.main()
