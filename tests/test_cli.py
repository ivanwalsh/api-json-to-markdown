"""Run the real command, `python -m docgen`, and check its exit codes."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests import EXAMPLE_SPEC, EXPECTED, FIXTURES, PROJECT_ROOT


def run_docgen(*args):
    return subprocess.run(
        [sys.executable, "-m", "docgen", *map(str, args)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


class CommandLineTests(unittest.TestCase):
    def test_valid_spec_writes_file_and_exits_0(self):
        # A temporary folder is created and removed automatically.
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "library_api.md"
            result = run_docgen(EXAMPLE_SPEC, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            expected = (EXPECTED / "library_api.md").read_text(encoding="utf-8")
            self.assertEqual(output.read_text(encoding="utf-8"), expected)
            # The example has quality warnings: shown, but exit code stays 0.
            self.assertIn("3 quality warning(s)", result.stderr)

    def test_no_output_path_prints_markdown(self):
        result = run_docgen(FIXTURES / "valid_minimal.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("# Tiny API\n"))
        # Warnings go to stderr, so the printed Markdown stays clean.
        self.assertNotIn("warning", result.stdout)
        self.assertIn("quality warning(s)", result.stderr)

    def test_check_clean_spec_exits_0(self):
        result = run_docgen("--check", FIXTURES / "valid_clean.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("No warnings", result.stdout)

    def test_check_with_warnings_exits_3_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            result = subprocess.run(
                [sys.executable, "-m", "docgen", "--check", str(EXAMPLE_SPEC)],
                cwd=folder,  # run somewhere empty so we can see nothing was written
                env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertIn("3 warning(s)", result.stdout)
            self.assertIn("[missing-description]", result.stdout)
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_check_refuses_output_path(self):
        result = run_docgen("--check", EXAMPLE_SPEC, "out.md")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--check does not write files", result.stderr)

    def test_check_still_reports_invalid_spec(self):
        result = run_docgen("--check", FIXTURES / "invalid_bad_method.json")
        self.assertEqual(result.returncode, 1)

    def test_invalid_spec_exits_1(self):
        result = run_docgen(FIXTURES / "invalid_multiple_errors.json")
        self.assertEqual(result.returncode, 1)
        self.assertIn("3 problem(s)", result.stderr)

    def test_missing_file_exits_2(self):
        result = run_docgen(FIXTURES / "does_not_exist.json")
        self.assertEqual(result.returncode, 2)
        self.assertIn("File not found", result.stderr)


if __name__ == "__main__":
    unittest.main()
