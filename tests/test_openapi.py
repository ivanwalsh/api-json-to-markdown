import subprocess
import sys
import unittest

from docgen import SpecError, from_openapi, generate_markdown, is_openapi, load_spec
from tests import EXAMPLE_SPEC, EXPECTED, PROJECT_ROOT

OPENAPI_EXAMPLE = PROJECT_ROOT / "examples" / "library_openapi.json"


def openapi_doc(paths=None, **top_level):
    """A small valid OpenAPI 3 document. Tests change parts of it on purpose."""
    document = {
        "openapi": "3.0.3",
        "info": {"title": "Test API", "version": "1.0.0", "description": "For tests."},
        "servers": [{"url": "https://api.example.test"}],
        "paths": paths if paths is not None else {
            "/ping": {
                "get": {
                    "summary": "Check the service is up",
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    document.update(top_level)
    return document


def one_operation(**operation):
    """Paths holding a single GET /items operation built from the given fields."""
    operation.setdefault("summary", "List items")
    operation.setdefault("responses", {"200": {"description": "OK"}})
    return {"/items": {"get": operation}}


class DetectionTests(unittest.TestCase):
    def test_openapi_is_detected(self):
        self.assertTrue(is_openapi(openapi_doc()))

    def test_our_own_format_is_not_openapi(self):
        self.assertFalse(is_openapi(load_spec(EXAMPLE_SPEC)))

    def test_swagger_2_is_refused_with_a_clear_message(self):
        with self.assertRaises(SpecError) as ctx:
            from_openapi({"swagger": "2.0"})
        self.assertIn("Swagger 2.0", str(ctx.exception))

    def test_unsupported_version_is_refused(self):
        with self.assertRaises(SpecError) as ctx:
            from_openapi(openapi_doc(openapi="4.0.0"))
        self.assertIn('"4.0.0" is not supported', str(ctx.exception))


class LibraryExampleTests(unittest.TestCase):
    def test_openapi_example_matches_golden_file(self):
        # Two different input formats, one identical output.
        expected = (EXPECTED / "library_api.md").read_text(encoding="utf-8")
        actual = generate_markdown(load_spec(OPENAPI_EXAMPLE))
        self.assertEqual(actual, expected)


    def test_command_line_accepts_openapi_file(self):
        result = subprocess.run(
            [sys.executable, "-m", "docgen", "--check", str(OPENAPI_EXAMPLE)],
            cwd=PROJECT_ROOT, capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("No warnings", result.stdout)

class InfoTests(unittest.TestCase):
    """These check _convert_info, the part of the converter you write."""

    def test_info_and_first_server_are_mapped(self):
        spec = from_openapi(openapi_doc(servers=[
            {"url": "https://first.example.test"},
            {"url": "https://second.example.test"},
        ]))
        self.assertEqual(spec["name"], "Test API")
        self.assertEqual(spec["version"], "1.0.0")
        self.assertEqual(spec["description"], "For tests.")
        self.assertEqual(spec["base_url"], "https://first.example.test")

    def test_missing_description_becomes_empty_text(self):
        spec = from_openapi(openapi_doc(info={"title": "Test API", "version": "1.0.0"}))
        self.assertEqual(spec["description"], "")

    def test_missing_servers_reported_by_validator(self):
        document = openapi_doc()
        del document["servers"]
        with self.assertRaises(SpecError) as ctx:
            generate_markdown(document)
        self.assertIn("base_url", str(ctx.exception))


class EndpointTests(unittest.TestCase):
    def endpoint(self, **operation):
        return from_openapi(openapi_doc(paths=one_operation(**operation)))["endpoints"][0]

    def test_operation_id_used_when_summary_missing(self):
        endpoint = from_openapi(openapi_doc(paths={"/items": {"get": {
            "operationId": "listItems",
            "responses": {"200": {"description": "OK"}},
        }}}))["endpoints"][0]
        self.assertEqual(endpoint["summary"], "listItems")

    def test_no_summary_or_operation_id_is_reported(self):
        document = openapi_doc(paths={"/items": {"get": {
            "responses": {"200": {"description": "OK"}},
        }}})
        with self.assertRaises(SpecError) as ctx:
            generate_markdown(document)
        self.assertIn("endpoints[0].summary", str(ctx.exception))

    def test_paths_and_methods_keep_file_order(self):
        document = openapi_doc(paths={
            "/b": {"post": {"summary": "B post", "responses": {"201": {"description": "OK"}}},
                   "get": {"summary": "B get", "responses": {"200": {"description": "OK"}}}},
            "/a": {"get": {"summary": "A get", "responses": {"200": {"description": "OK"}}}},
        })
        titles = [f'{e["method"]} {e["path"]}' for e in from_openapi(document)["endpoints"]]
        self.assertEqual(titles, ["POST /b", "GET /b", "GET /a"])

    def test_unsupported_methods_are_skipped(self):
        document = openapi_doc(paths={"/items": {
            "head": {"summary": "Head", "responses": {"200": {"description": "OK"}}},
            "get": {"summary": "Get", "responses": {"200": {"description": "OK"}}},
        }})
        endpoints = from_openapi(document)["endpoints"]
        self.assertEqual([e["method"] for e in endpoints], ["GET"])

    def test_path_level_parameters_are_shared_and_can_be_overridden(self):
        document = openapi_doc(paths={"/items/{id}": {
            "parameters": [
                {"name": "id", "in": "path", "required": True, "schema": {"type": "string"},
                 "description": "Shared"},
                {"name": "X-Trace", "in": "header", "schema": {"type": "string"}},
            ],
            "get": {
                "summary": "Get item",
                "parameters": [
                    {"name": "id", "in": "path", "required": True, "schema": {"type": "integer"},
                     "description": "Overridden"},
                ],
                "responses": {"200": {"description": "OK"}},
            },
        }})
        parameters = from_openapi(document)["endpoints"][0]["parameters"]
        self.assertEqual([p["name"] for p in parameters], ["id", "X-Trace"])
        self.assertEqual(parameters[0]["type"], "integer")
        self.assertEqual(parameters[0]["description"], "Overridden")

    def test_cookie_parameters_are_skipped(self):
        endpoint = self.endpoint(parameters=[
            {"name": "session", "in": "cookie", "schema": {"type": "string"}},
            {"name": "q", "in": "query", "schema": {"type": "string"}},
        ])
        self.assertEqual([p["name"] for p in endpoint["parameters"]], ["q"])

    def test_request_body_properties_become_body_parameters(self):
        endpoint = self.endpoint(requestBody={"content": {"application/json": {
            "schema": {
                "type": "object",
                "required": ["title"],
                "properties": {
                    "title": {"type": "string", "example": "Dubliners"},
                    "year": {"type": "integer"},
                },
            },
            "example": {"title": "Ulysses", "year": 1922},
        }}})
        self.assertEqual(endpoint["parameters"], [
            # The property's own example wins over the whole-body example.
            {"name": "title", "in": "body", "type": "string", "required": True, "example": "Dubliners"},
            # No example on the property, so it is borrowed from the whole-body example.
            {"name": "year", "in": "body", "type": "integer", "required": False, "example": 1922},
        ])

    def test_non_json_request_body_is_skipped(self):
        endpoint = self.endpoint(requestBody={"content": {"text/plain": {
            "schema": {"type": "string"},
        }}})
        self.assertNotIn("parameters", endpoint)

    def test_only_numeric_status_codes_are_kept(self):
        endpoint = self.endpoint(responses={
            "200": {"description": "OK"},
            "default": {"description": "Anything else"},
            "4XX": {"description": "Client error"},
        })
        self.assertEqual([r["status"] for r in endpoint["responses"]], [200])

    def test_openapi_31_nullable_type_list(self):
        endpoint = self.endpoint(parameters=[
            {"name": "q", "in": "query", "schema": {"type": ["string", "null"]}},
        ])
        self.assertEqual(endpoint["parameters"][0]["type"], "string")


class RefTests(unittest.TestCase):
    def test_ref_is_followed(self):
        document = openapi_doc(
            paths=one_operation(parameters=[{"$ref": "#/components/parameters/Limit"}]),
            components={"parameters": {"Limit": {
                "name": "limit", "in": "query", "schema": {"type": "integer"}, "example": 5,
            }}},
        )
        parameter = from_openapi(document)["endpoints"][0]["parameters"][0]
        self.assertEqual((parameter["name"], parameter["example"]), ("limit", 5))

    def test_missing_ref_target_is_reported(self):
        document = openapi_doc(paths=one_operation(
            parameters=[{"$ref": "#/components/parameters/Nope"}],
        ))
        with self.assertRaises(SpecError) as ctx:
            from_openapi(document)
        self.assertIn("#/components/parameters/Nope: reference not found", str(ctx.exception))

    def test_ref_to_another_file_is_refused(self):
        document = openapi_doc(paths=one_operation(
            parameters=[{"$ref": "other.json#/Limit"}],
        ))
        with self.assertRaises(SpecError) as ctx:
            from_openapi(document)
        self.assertIn("only references inside the same file", str(ctx.exception))

    def test_circular_ref_is_reported(self):
        document = openapi_doc(
            paths=one_operation(parameters=[{"$ref": "#/components/parameters/A"}]),
            components={"parameters": {
                "A": {"$ref": "#/components/parameters/B"},
                "B": {"$ref": "#/components/parameters/A"},
            }},
        )
        with self.assertRaises(SpecError) as ctx:
            from_openapi(document)
        self.assertIn("circular", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
