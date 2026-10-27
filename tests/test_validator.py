import copy
import unittest

from docgen import SpecError, load_spec, validate_spec
from tests import EXAMPLE_SPEC, FIXTURES


def valid_spec():
    """A fresh copy of a small valid spec that each test can break on purpose."""
    return {
        "name": "Tiny API",
        "version": "0.1.0",
        "base_url": "https://tiny.example.test",
        "endpoints": [
            {
                "method": "GET",
                "path": "/ping",
                "summary": "Check the service is up",
                "responses": [{"status": 200, "description": "Service is up"}],
            }
        ],
    }


class ValidatorTests(unittest.TestCase):
    def assertProblems(self, spec):
        """Validate `spec`, expect failure, and return the list of problems."""
        with self.assertRaises(SpecError) as ctx:
            validate_spec(spec)
        return ctx.exception.problems

    # --- Valid input ----------------------------------------------------

    def test_example_spec_is_valid(self):
        validate_spec(load_spec(EXAMPLE_SPEC))  # must not raise

    def test_minimal_fixture_is_valid(self):
        validate_spec(load_spec(FIXTURES / "valid_minimal.json"))

    def test_unknown_fields_are_ignored(self):
        spec = valid_spec()
        spec["x-owner"] = "docs team"
        spec["endpoints"][0]["tags"] = ["health"]
        validate_spec(spec)  # forgiving: no error

    # --- The planned invalid-input tests ------------------------------------

    def test_missing_name(self):
        problems = self.assertProblems(load_spec(FIXTURES / "invalid_missing_name.json"))
        self.assertEqual(problems, ["name: required field is missing"])

    def test_bad_method(self):
        problems = self.assertProblems(load_spec(FIXTURES / "invalid_bad_method.json"))
        self.assertEqual(len(problems), 1)
        self.assertTrue(problems[0].startswith("endpoints[0].method:"))
        self.assertIn('"FETCH"', problems[0])

    def test_empty_endpoints(self):
        problems = self.assertProblems(load_spec(FIXTURES / "invalid_empty_endpoints.json"))
        self.assertEqual(problems, ["endpoints: must contain at least one endpoint"])

    def test_wrong_type(self):
        problems = self.assertProblems(load_spec(FIXTURES / "invalid_wrong_type.json"))
        self.assertEqual(problems, ["version: must be a string, got integer"])

    def test_multiple_errors_reported_together(self):
        problems = self.assertProblems(load_spec(FIXTURES / "invalid_multiple_errors.json"))
        self.assertEqual(len(problems), 3)
        joined = "\n".join(problems)
        self.assertIn("name: must not be empty", joined)
        self.assertIn("base_url:", joined)
        self.assertIn("endpoints[0].path:", joined)

    # --- Extra edge cases -----------------------------------------------

    def test_top_level_must_be_object(self):
        problems = self.assertProblems([1, 2, 3])
        self.assertIn("must be a JSON object", problems[0])

    def test_status_true_is_not_an_integer(self):
        spec = valid_spec()
        spec["endpoints"][0]["responses"][0]["status"] = True
        problems = self.assertProblems(spec)
        self.assertIn("must be an integer, got boolean", problems[0])

    def test_status_out_of_range(self):
        spec = valid_spec()
        spec["endpoints"][0]["responses"][0]["status"] = 999
        problems = self.assertProblems(spec)
        self.assertIn("between 100 and 599", problems[0])

    def test_duplicate_endpoint(self):
        spec = valid_spec()
        twin = copy.deepcopy(spec["endpoints"][0])
        twin["method"] = "get"  # lowercase still counts as the same endpoint
        spec["endpoints"].append(twin)
        problems = self.assertProblems(spec)
        self.assertIn("duplicate endpoint GET /ping", problems[0])

    def test_bad_parameter_location_and_type(self):
        spec = valid_spec()
        spec["endpoints"][0]["parameters"] = [
            {"name": "q", "in": "cookie", "type": "text"}
        ]
        problems = self.assertProblems(spec)
        self.assertEqual(len(problems), 2)
        self.assertTrue(problems[0].startswith("endpoints[0].parameters[0].in:"))
        self.assertTrue(problems[1].startswith("endpoints[0].parameters[0].type:"))


if __name__ == "__main__":
    unittest.main()
