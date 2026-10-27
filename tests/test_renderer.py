import copy
import unittest

from docgen import generate_markdown, load_spec, normalize_spec
from tests import EXAMPLE_SPEC, EXPECTED


def reverse_key_order(value):
    """Return a copy of JSON data with every object's keys in reverse order.

    Lists keep their order, because list order is meaningful.
    """
    if isinstance(value, dict):
        return {k: reverse_key_order(value[k]) for k in reversed(list(value))}
    if isinstance(value, list):
        return [reverse_key_order(item) for item in value]
    return value


def tiny_spec(**endpoint_overrides):
    endpoint = {
        "method": "GET",
        "path": "/ping",
        "summary": "Check the service is up",
        "responses": [{"status": 200, "description": "Service is up"}],
    }
    endpoint.update(endpoint_overrides)
    return {
        "name": "Tiny API",
        "version": "0.1.0",
        "base_url": "https://tiny.example.test",
        "endpoints": [endpoint],
    }


class GoldenFileTests(unittest.TestCase):
    def test_example_matches_golden_file(self):
        expected = (EXPECTED / "library_api.md").read_text(encoding="utf-8")
        actual = generate_markdown(load_spec(EXAMPLE_SPEC))
        self.assertEqual(actual, expected)


class DeterminismTests(unittest.TestCase):
    def test_same_input_same_output(self):
        spec = load_spec(EXAMPLE_SPEC)
        self.assertEqual(generate_markdown(spec), generate_markdown(spec))

    def test_key_order_does_not_change_output(self):
        spec = load_spec(EXAMPLE_SPEC)
        reordered = reverse_key_order(spec)
        self.assertNotEqual(list(spec), list(reordered))  # really reordered
        self.assertEqual(generate_markdown(spec), generate_markdown(reordered))

    def test_ends_with_exactly_one_newline(self):
        markdown = generate_markdown(tiny_spec())
        self.assertTrue(markdown.endswith("\n"))
        self.assertFalse(markdown.endswith("\n\n"))
        self.assertNotIn("\r", markdown)


class RenderingRulesTests(unittest.TestCase):
    def test_optional_sections_left_out_when_empty(self):
        markdown = generate_markdown(tiny_spec())
        self.assertNotIn("### Parameters", markdown)
        self.assertNotIn("```", markdown)  # no examples, so no code blocks

    def test_pipe_characters_are_escaped_in_tables(self):
        spec = tiny_spec(
            parameters=[
                {"name": "mode", "in": "query", "type": "string", "description": "a | b"}
            ]
        )
        markdown = generate_markdown(spec)
        self.assertIn("| mode | query | string | no | a \\| b |", markdown)

    def test_responses_sorted_by_status(self):
        spec = tiny_spec(
            responses=[
                {"status": 404, "description": "Not found"},
                {"status": 200, "description": "OK"},
            ]
        )
        markdown = generate_markdown(spec)
        self.assertLess(markdown.index("#### 200: OK"), markdown.index("#### 404: Not found"))

    def test_endpoints_keep_author_order(self):
        markdown = generate_markdown(load_spec(EXAMPLE_SPEC))
        self.assertLess(markdown.index("## POST /members"), markdown.index("## POST /loans"))

    def test_method_uppercased_and_anchor_built(self):
        markdown = generate_markdown(tiny_spec(method="get", path="/books/{id}"))
        self.assertIn("- [GET /books/{id}](#get-booksid): Check the service is up", markdown)
        self.assertIn("## GET /books/{id}", markdown)

    def test_example_with_backticks_gets_longer_fence(self):
        spec = tiny_spec(
            responses=[{"status": 200, "description": "OK", "example": "``` tricky"}]
        )
        markdown = generate_markdown(spec)
        self.assertIn("````json", markdown)

    def test_normalize_does_not_change_input(self):
        spec = tiny_spec(method="get")
        before = copy.deepcopy(spec)
        normalize_spec(spec)
        self.assertEqual(spec, before)


if __name__ == "__main__":
    unittest.main()
