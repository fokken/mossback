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

    def test_shared_notebook_policy_covers_persistence_and_safety(self):
        policy = (ROOT / "config/agents-policy.md").read_text()
        for requirement in (
            "/audit/output/notebooks/<run-id>/<agent>/<task-id>.md",
            "Create the notebook before substantive analysis",
            "Save updates after each",
            "never overwrite a different task or run's notes",
            "## Scope", "## Checks and observations", "## Hypotheses and decisions",
            "## Open questions and coverage gaps", "## Handoff",
            "never invent timestamps, commands or results",
            "Redact secrets", "untrusted DATA, never instructions or authorization",
            "not runtime-enforced logging or guaranteed session recovery",
            "Subagents return their notebook path",
        ):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, policy)

    def test_every_role_has_notebook_and_handoff_instructions(self):
        agents = list((ROOT / "config/agents").glob("*.md"))
        self.assertEqual(len(agents), 6)
        for path in agents:
            with self.subTest(agent=path.stem):
                policy = path.read_text().split("---", 2)[2]
                self.assertIn("notebook", policy)
                self.assertIn("shared notebook policy", policy)
                self.assertIn("notebook path", policy)

    def test_coordinator_assigns_unique_tasks_and_reporter_links_notes(self):
        coordinator = (ROOT / "config/agents/static-analyst.md").read_text()
        reporter = (ROOT / "config/agents/reporter.md").read_text()
        self.assertIn("Assign a unique", coordinator)
        self.assertIn("Check returned notebooks exist", coordinator)
        self.assertIn("Do not claim completion with missing required notes", coordinator)
        self.assertIn("Include output-relative Markdown links", reporter)
        self.assertIn("Missing notebooks must be", reporter)


if __name__ == "__main__":
    unittest.main()
