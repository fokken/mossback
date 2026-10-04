"""Check documentation navigation and fenced blocks; not a Mermaid renderer."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DocumentationTests(unittest.TestCase):
    def test_local_links_and_fences(self):
        documents = [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md")),
                     *sorted((ROOT / "config").rglob("README.md")),
                     *sorted((ROOT / "mcp").rglob("README.md"))]
        for document in documents:
            text = document.read_text()
            with self.subTest(document=document.name):
                self.assertEqual(sum(line.startswith("```") for line in text.splitlines()) % 2, 0)
                for target in re.findall(r"\]\(([^)]+)\)", text):
                    if "://" in target or target.startswith("#"):
                        continue
                    self.assertTrue((document.parent / target.split("#", 1)[0]).exists(), target)
                for target in re.findall(r'<img\b[^>]*\bsrc="([^"]+)"', text):
                    if "://" not in target:
                        self.assertTrue((document.parent / target).is_file(), target)

    def test_architecture_and_workflow_diagrams_present(self):
        architecture = (ROOT / "docs/architecture.md").read_text()
        workflow = (ROOT / "docs/operator-workflow.md").read_text()
        self.assertIn("```mermaid\nflowchart", architecture)
        self.assertIn("```mermaid\nsequenceDiagram", workflow)
        self.assertIn("not mounted into analyzer", (ROOT / "README.md").read_text())

    def test_sequence_diagrams_avoid_unescaped_semicolons(self):
        for document in (ROOT / "docs").glob("*.md"):
            for diagram in re.findall(r"```mermaid\n(.*?)```", document.read_text(), re.DOTALL):
                if diagram.startswith("sequenceDiagram"):
                    # Mermaid uses bare semicolons as statement separators.
                    text = re.sub(r"#(?:[0-9]+|[A-Za-z]+);", "", diagram)
                    self.assertNotIn(";", text, document.name)


if __name__ == "__main__":
    unittest.main()
