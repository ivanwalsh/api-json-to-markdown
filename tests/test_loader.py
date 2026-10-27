import unittest

from docgen import SpecError, SpecFileError, load_spec, parse_spec
from tests import EXAMPLE_SPEC, FIXTURES


class LoaderTests(unittest.TestCase):
    def test_valid_file_loads_as_dict(self):
        data = load_spec(EXAMPLE_SPEC)
        self.assertIsInstance(data, dict)
        self.assertEqual(data["name"], "Community Library API")

    def test_malformed_json_reports_line_and_column(self):
        with self.assertRaises(SpecError) as ctx:
            load_spec(FIXTURES / "invalid_malformed.json")
        message = str(ctx.exception)
        self.assertIn("Invalid JSON", message)
        self.assertIn("line", message)
        self.assertIn("column", message)

    def test_missing_file_raises_file_error(self):
        with self.assertRaises(SpecFileError) as ctx:
            load_spec(FIXTURES / "does_not_exist.json")
        self.assertIn("File not found", str(ctx.exception))

    def test_parse_spec_accepts_text(self):
        self.assertEqual(parse_spec('{"a": 1}'), {"a": 1})


if __name__ == "__main__":
    unittest.main()
