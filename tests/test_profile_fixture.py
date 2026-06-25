import os
import unittest

from scripts.detect_profile import compute_profile_seed

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(REPO_ROOT, "examples", "flask-mini")


class ProfileFixtureTest(unittest.TestCase):
    """Headline proof of iteration 8: detection names the framework's own
    layers, not the self-host's baked DDD ontology."""

    def test_detection_names_flask_layers_not_ddd(self):
        seed = compute_profile_seed(FIXTURE, FIXTURE)
        self.assertEqual(seed.language, "python")
        self.assertEqual(seed.framework_guess, "python/flask")
        self.assertEqual(
            seed.candidate_layers, ("blueprints", "models", "services")
        )
        for ddd_layer in ("domain", "contracts", "adapters", "application"):
            self.assertNotIn(ddd_layer, seed.candidate_layers)


if __name__ == "__main__":
    unittest.main()
