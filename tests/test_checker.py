import unittest

from docgen import check_spec, load_spec, normalize_spec, validate_spec
from tests import EXAMPLE_SPEC, FIXTURES


def clean_endpoint(**overrides):
    """An endpoint that passes every quality rule. Tests break it on purpose."""
    endpoint = {
        "method": "GET",
        "path": "/books/{id}",
        "summary": "Get one book",
        "description": "Returns a single book by its id.",
        "parameters": [
            {"name": "id", "in": "path", "type": "integer", "required": True,
             "description": "The book's id"}
        ],
        "responses": [
            {"status": 200, "description": "Book found", "example": {"id": 7}},
            {"status": 404, "description": "No book with that id"},
        ],
    }
    endpoint.update(overrides)
    return endpoint


def warnings_for(*endpoints):
    """Validate, normalize and check a spec built from these endpoints."""
    raw = {
        "name": "Test API",
        "version": "1.0.0",
        "base_url": "https://test.example.test",
        "endpoints": list(endpoints),
    }
    validate_spec(raw)  # the checker only ever sees valid specs
    return check_spec(normalize_spec(raw))


def codes(warnings):
    return [w.code for w in warnings]


class CheckerTests(unittest.TestCase):
    def test_clean_spec_has_no_warnings(self):
        self.assertEqual(warnings_for(clean_endpoint()), [])

    def test_missing_description(self):
        endpoint = clean_endpoint()
        del endpoint["description"]
        self.assertEqual(codes(warnings_for(endpoint)), ["missing-description"])

    def test_missing_param_description(self):
        endpoint = clean_endpoint()
        del endpoint["parameters"][0]["description"]
        self.assertEqual(codes(warnings_for(endpoint)), ["missing-param-description"])

    def test_undeclared_path_param(self):
        found = warnings_for(clean_endpoint(parameters=[]))
        self.assertEqual(codes(found), ["undeclared-path-param"])
        self.assertIn("{id}", found[0].message)

    def test_path_param_declared_in_query_still_undeclared(self):
        endpoint = clean_endpoint()
        endpoint["parameters"][0]["in"] = "query"
        self.assertEqual(codes(warnings_for(endpoint)), ["undeclared-path-param"])

    def test_unused_path_param(self):
        found = warnings_for(clean_endpoint(path="/books"))
        self.assertEqual(codes(found), ["unused-path-param"])
        self.assertEqual(found[0].location, "endpoints[0].parameters[0]")

    def test_path_param_required(self):
        endpoint = clean_endpoint()
        endpoint["parameters"][0]["required"] = False
        self.assertEqual(codes(warnings_for(endpoint)), ["path-param-required"])

    def test_no_success_response(self):
        endpoint = clean_endpoint(
            responses=[{"status": 404, "description": "No book with that id"}]
        )
        self.assertEqual(codes(warnings_for(endpoint)), ["no-success-response"])

    def test_200_without_example_is_flagged(self):
        endpoint = clean_endpoint(responses=[{"status": 200, "description": "OK"}])
        found = warnings_for(endpoint)
        self.assertEqual(codes(found), ["success-without-example"])
        self.assertEqual(found[0].location, "endpoints[0] response 200")

    def test_204_without_example_is_not_flagged(self):
        endpoint = clean_endpoint(
            method="DELETE",
            responses=[{"status": 204, "description": "Deleted"}],
        )
        self.assertEqual(warnings_for(endpoint), [])

    def test_summary_ending_with_full_stop(self):
        found = warnings_for(clean_endpoint(summary="Get one book."))
        self.assertEqual(codes(found), ["summary-style"])
        self.assertIn("full stop", found[0].message)

    def test_summary_too_long(self):
        found = warnings_for(clean_endpoint(summary="x" * 81))
        self.assertEqual(codes(found), ["summary-style"])
        self.assertIn("81 characters", found[0].message)

    def test_summary_of_exactly_80_is_fine(self):
        self.assertEqual(warnings_for(clean_endpoint(summary="x" * 80)), [])

    def test_warning_text_format(self):
        found = warnings_for(clean_endpoint(parameters=[]))
        self.assertEqual(
            str(found[0]),
            'endpoints[0]: path uses {id} but no parameter "id" has "in": "path" '
            "[undeclared-path-param]",
        )

    def test_warnings_in_stable_spec_order(self):
        first = clean_endpoint()
        del first["description"]
        # 81 characters AND ends with a full stop: breaks both summary rules.
        second = clean_endpoint(path="/members/{id}", summary="x" * 80 + ".")
        found = warnings_for(first, second)
        self.assertEqual(
            [(w.location, w.code) for w in found],
            [
                ("endpoints[0]", "missing-description"),
                ("endpoints[1].summary", "summary-style"),
                ("endpoints[1].summary", "summary-style"),
            ],
        )
        self.assertEqual(found, warnings_for(first, second))  # same every run

    def test_library_example_is_clean(self):
        # The example is the project's showcase, so it must stay warning-free.
        found = check_spec(normalize_spec(load_spec(EXAMPLE_SPEC)))
        self.assertEqual([str(w) for w in found], [])

    def test_minimal_fixture_has_known_warnings(self):
        # valid_minimal.json is deliberately imperfect, so tests can rely on it.
        found = check_spec(normalize_spec(load_spec(FIXTURES / "valid_minimal.json")))
        self.assertEqual(
            [(w.location, w.code) for w in found],
            [
                ("endpoints[0]", "missing-description"),
                ("endpoints[0] response 200", "success-without-example"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
