import tempfile
import unittest
from pathlib import Path

from docgen import SpecError, generate_markdown, load_spec
from tests import EXPECTED, PROJECT_ROOT

YAML_EXAMPLE = PROJECT_ROOT / "examples" / "library_openapi.yaml"


def load_text(text, filename):
    """Write text to a temporary file with the given name, then load it."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / filename
        path.write_text(text, encoding="utf-8")
        return load_spec(path)


class YamlLoadingTests(unittest.TestCase):
    def test_yaml_example_matches_golden_file(self):
        # Three input formats, one identical output.
        expected = (EXPECTED / "library_api.md").read_text(encoding="utf-8")
        actual = generate_markdown(load_spec(YAML_EXAMPLE))
        self.assertEqual(actual, expected)

    def test_yml_ending_also_works(self):
        self.assertEqual(load_text("name: Test API\n", "spec.yml"), {"name": "Test API"})

    def test_ending_is_not_case_sensitive(self):
        self.assertEqual(load_text("name: Test API\n", "SPEC.YAML"), {"name": "Test API"})

    def test_json_files_are_still_read_as_json(self):
        self.assertEqual(load_text('{"name": "Test API"}', "spec.json"), {"name": "Test API"})

    def test_dates_stay_as_text(self):
        # Plain YAML would turn this into a date object, which can't be shown as JSON.
        self.assertEqual(load_text("due: 2026-11-15\n", "spec.yaml"), {"due": "2026-11-15"})

    def test_invalid_yaml_reports_line_and_column(self):
        with self.assertRaises(SpecError) as ctx:
            load_text("name: Test API\nendpoints: [1, 2\nversion: 1\n", "spec.yaml")
        message = str(ctx.exception)
        self.assertIn("Invalid YAML at line", message)
        self.assertIn("column", message)

    def test_yaml_cannot_run_code(self):
        # The safe loader refuses Python-specific tags instead of running them.
        with self.assertRaises(SpecError):
            load_text("x: !!python/object/apply:os.system ['echo hi']\n", "spec.yaml")


if __name__ == "__main__":
    unittest.main()
