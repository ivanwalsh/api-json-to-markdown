import unittest

from docgen import generate_markdown, normalize_spec, validate_spec
from docgen.curl import curl_lines

BASE = "https://api.example.test"


def endpoint(method="GET", path="/items", parameters=None):
    """Validate and normalize a one-endpoint spec, and return that endpoint."""
    raw = {
        "name": "Test API",
        "version": "1.0.0",
        "base_url": BASE,
        "endpoints": [
            {
                "method": method,
                "path": path,
                "summary": "Test endpoint",
                "parameters": parameters or [],
                "responses": [{"status": 200, "description": "OK"}],
            }
        ],
    }
    validate_spec(raw)
    return normalize_spec(raw)["endpoints"][0]


def param(name, where, example=None, required=False, type_="string", **extra):
    p = {"name": name, "in": where, "type": type_, "required": required, **extra}
    if example is not None:
        p["example"] = example
    return p


class CurlTests(unittest.TestCase):
    def test_get_without_parameters_is_one_line(self):
        self.assertEqual(curl_lines(BASE, endpoint()), [f"curl '{BASE}/items'"])

    def test_non_get_shows_method(self):
        lines = curl_lines(BASE, endpoint(method="DELETE"))
        self.assertEqual(lines, [f"curl -X DELETE '{BASE}/items'"])

    def test_path_example_replaces_placeholder(self):
        ep = endpoint(path="/items/{id}", parameters=[
            param("id", "path", example=7, required=True, type_="integer")
        ])
        self.assertEqual(curl_lines(BASE, ep), [f"curl '{BASE}/items/7'"])

    def test_query_values_are_url_encoded(self):
        ep = endpoint(parameters=[param("author", "query", example="James Joyce")])
        self.assertIn("?author=James%20Joyce", curl_lines(BASE, ep)[0])

    def test_booleans_use_json_spelling(self):
        ep = endpoint(parameters=[
            param("available", "query", example=True, type_="boolean"),
            param("archived", "query", example=False, type_="boolean"),
        ])
        self.assertIn("?available=true&archived=false", curl_lines(BASE, ep)[0])

    def test_body_becomes_one_json_object_with_sorted_keys(self):
        ep = endpoint(method="POST", parameters=[
            param("member_id", "body", example=301, type_="integer"),
            param("book_id", "body", example=7, type_="integer"),
        ])
        self.assertEqual(curl_lines(BASE, ep), [
            f"curl -X POST '{BASE}/items' \\",
            "  -H 'Content-Type: application/json' \\",
            """  -d '{"book_id": 7, "member_id": 301}'""",
        ])

    def test_header_parameter(self):
        ep = endpoint(parameters=[param("X-Api-Key", "header", example="abc123")])
        self.assertEqual(curl_lines(BASE, ep), [
            f"curl '{BASE}/items' \\",
            "  -H 'X-Api-Key: abc123'",
        ])

    def test_required_without_example_becomes_placeholder(self):
        ep = endpoint(path="/items/{id}", parameters=[
            param("id", "path", required=True, type_="integer"),
            param("q", "query", required=True),
        ])
        self.assertEqual(curl_lines(BASE, ep), [f"curl '{BASE}/items/<id>?q=<q>'"])

    def test_required_body_placeholder(self):
        ep = endpoint(method="POST", parameters=[param("title", "body", required=True)])
        self.assertIn("""-d '{"title": "<title>"}'""", curl_lines(BASE, ep)[-1])

    def test_optional_without_example_is_left_out(self):
        ep = endpoint(method="POST", parameters=[
            param("limit", "query", type_="integer"),
            param("note", "body"),
        ])
        self.assertEqual(curl_lines(BASE, ep), [f"curl -X POST '{BASE}/items'"])

    def test_null_example_is_kept(self):
        ep = endpoint(method="PATCH", parameters=[
            {"name": "due", "in": "body", "type": "string", "example": None}
        ])
        self.assertIn("""-d '{"due": null}'""", curl_lines(BASE, ep)[-1])

    def test_apostrophe_is_escaped_for_the_shell(self):
        ep = endpoint(method="POST", parameters=[param("name", "body", example="O'Brien")])
        self.assertIn("""-d '{"name": "O'\\''Brien"}'""", curl_lines(BASE, ep)[-1])

    def test_trailing_slash_on_base_url_is_not_doubled(self):
        self.assertEqual(curl_lines(BASE + "/", endpoint()), [f"curl '{BASE}/items'"])

    def test_example_request_section_rendered(self):
        raw = {
            "name": "Test API",
            "version": "1.0.0",
            "base_url": BASE,
            "endpoints": [{
                "method": "GET",
                "path": "/items",
                "summary": "List items",
                "responses": [{"status": 200, "description": "OK"}],
            }],
        }
        markdown = generate_markdown(raw)
        self.assertIn(f"### Example request\n\n```bash\ncurl '{BASE}/items'\n```\n", markdown)
        self.assertLess(markdown.index("### Example request"), markdown.index("### Responses"))

    def test_same_output_every_run(self):
        ep = endpoint(method="POST", parameters=[
            param("b", "body", example={"z": 1, "a": 2}, type_="object"),
            param("a", "body", example=[3, 1], type_="array"),
        ])
        self.assertEqual(curl_lines(BASE, ep), curl_lines(BASE, ep))
        self.assertIn("""-d '{"a": [3, 1], "b": {"a": 2, "z": 1}}'""", curl_lines(BASE, ep)[-1])


if __name__ == "__main__":
    unittest.main()
