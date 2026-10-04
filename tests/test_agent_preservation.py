"""Regression checks for agent output preservation instructions, not enforcement."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AgentPreservationTests(unittest.TestCase):
    def test_shared_policy_covers_exports_and_safety(self):
        policy = (ROOT / "config/agents-policy.md").read_text()
        for requirement in (
            "Save important outputs incrementally",
            "/audit/output/scripts/<run-id>/<agent>/",
            "/audit/output/artifacts/<run-id>/<agent>/manifest.json",
            "tool/version and generation command",
            "Redact credentials and tokens",
            "Preservation does not authorize execution",
            "preservation failures explicitly",
        ):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, policy)

    def test_coordinator_and_reporter_check_preservation(self):
        coordinator = (ROOT / "config/agents/static-analyst.md").read_text()
        reporter = (ROOT / "config/agents/reporter.md").read_text()
        self.assertIn("save reusable scripts", coordinator)
        self.assertIn("Check the output", coordinator)
        self.assertIn("Check specialists' preservation manifests", reporter)
        self.assertIn("without\nexecuting saved scripts", reporter)


if __name__ == "__main__":
    unittest.main()
