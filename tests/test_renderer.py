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


def tagged_spec(*tags):
    """A spec with one endpoint per tag, in the order given. None means no tag."""
    endpoints = []
    for number, tag in enumerate(tags):
        endpoint = {
            "method": "GET",
            "path": f"/item{number}",
            "summary": f"Item {number}",
            "responses": [{"status": 200, "description": "OK"}],
        }
        if tag is not None:
            endpoint["tag"] = tag
        endpoints.append(endpoint)
    return {
        "name": "Tagged API",
        "version": "1.0.0",
        "base_url": "https://tagged.example.test",
        "endpoints": endpoints,
    }


def table_of_contents(markdown):
    """Return just the lines between '## Endpoints' and the first endpoint section."""
    after = markdown.split("## Endpoints\n\n", 1)[1]
    return after.split("\n## ", 1)[0].strip().splitlines()


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
        # No response examples, so no JSON code blocks. (The curl block is
        # always present, so we look for ```json specifically.)
        self.assertNotIn("```json", markdown)

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


class TagGroupingTests(unittest.TestCase):
    def test_no_tags_gives_plain_list(self):
        toc = table_of_contents(generate_markdown(tagged_spec(None, None)))
        self.assertEqual(toc, [
            "- [GET /item0](#get-item0): Item 0",
            "- [GET /item1](#get-item1): Item 1",
        ])

    def test_groups_follow_first_appearance_order(self):
        # Tags appear as B, A, B: groups must be B then A, not alphabetical.
        toc = table_of_contents(generate_markdown(tagged_spec("B", "A", "B")))
        self.assertEqual(toc, [
            "### B",
            "",
            "- [GET /item0](#get-item0): Item 0",
            "- [GET /item2](#get-item2): Item 2",
            "",
            "### A",
            "",
            "- [GET /item1](#get-item1): Item 1",
        ])

    def test_untagged_endpoints_go_in_other_at_end(self):
        # If some endpoints don't have a tag, the untagged ones go in an Other group at the end.
        toc = table_of_contents(generate_markdown(tagged_spec(None, "A")))
        self.assertEqual(toc, [
            "### A",
            "",
            "- [GET /item1](#get-item1): Item 1",
            "",
            "### Other",
            "",
            "- [GET /item0](#get-item0): Item 0",
        ])

    def test_endpoint_sections_keep_author_order(self):
        # Grouping changes the table of contents only, never the sections.
        markdown = generate_markdown(tagged_spec("B", "A", "B"))
        self.assertLess(markdown.index("## GET /item1"), markdown.index("## GET /item2"))


if __name__ == "__main__":
    unittest.main()
