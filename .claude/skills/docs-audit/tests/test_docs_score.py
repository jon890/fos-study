import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "docs_score.py"
SPEC = importlib.util.spec_from_file_location("docs_score", SCRIPT)
DOCS_SCORE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DOCS_SCORE)


class DocsScoreStructureTest(unittest.TestCase):

    def test_reports_broken_links_orphans_and_readme_omissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                "# 문서\n\n[연결 문서](linked.md)\n[깨진 링크](missing.md)\n",
                encoding="utf-8",
            )
            (root / "linked.md").write_text("# 연결 문서\n", encoding="utf-8")
            (root / "orphan.md").write_text("# 고아 문서\n", encoding="utf-8")

            result = DOCS_SCORE.measure(root)

            self.assertEqual(1, result["counts"]["broken_link"])
            self.assertEqual(1, result["counts"]["orphan_doc"])
            self.assertEqual(1, result["counts"]["readme_missing"])

    def test_clean_structure_has_no_structural_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                "# 문서\n\n[연결 문서](linked.md)\n",
                encoding="utf-8",
            )
            (root / "linked.md").write_text("# 연결 문서\n", encoding="utf-8")

            result = DOCS_SCORE.measure(root)

            self.assertEqual(0, result["counts"]["broken_link"])
            self.assertEqual(0, result["counts"]["orphan_doc"])
            self.assertEqual(0, result["counts"]["readme_missing"])

    def test_filename_text_is_not_treated_as_readme_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                "# 문서\n\nlinked.md를 설명하지만 링크하지 않는다.\n",
                encoding="utf-8",
            )
            (root / "linked.md").write_text("# 연결 문서\n", encoding="utf-8")

            result = DOCS_SCORE.measure(root)

            self.assertEqual(1, result["counts"]["readme_missing"])

    def test_cli_exit_code_matches_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# 문서\n", encoding="utf-8")

            clean = subprocess.run(
                [sys.executable, str(SCRIPT), "--root", str(root), "--json"],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, clean.returncode)

            (root / "orphan.md").write_text("# 고아 문서\n", encoding="utf-8")
            broken = subprocess.run(
                [sys.executable, str(SCRIPT), "--root", str(root), "--json"],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(1, broken.returncode)


if __name__ == "__main__":
    unittest.main()
