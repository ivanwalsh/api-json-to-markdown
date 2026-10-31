"""Tests for AI-drafted descriptions.

None of these tests use the internet. Instead of the real AI, they pass in
a *fake*: a small stand-in that gives fixed answers and remembers what it
was asked. That keeps the tests fast, free and the same every run.
"""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from docgen import jsonwriter, suggest
from docgen.errors import ServiceError
from tests import EXAMPLE_SPEC, PROJECT_ROOT


def is_parameter_rules(rules):
    """True for the parameter prompt. Checks its title, the one line unique to it."""
    return rules.startswith("# Rules for writing API parameter descriptions")


class FakeAI:
    """Pretends to be the AI. Returns `answer` and records every request."""

    def __init__(self, answer="Returns something useful."):
        self.answer = answer
        self.requests = []  # a list of (rules, facts) pairs

    def __call__(self, rules, facts):
        self.requests.append((rules, facts))
        return self.answer(rules, facts) if callable(self.answer) else self.answer


def spec_with_gaps():
    """A small spec with one missing endpoint description and one missing parameter description."""
    return {
        "name": "Concerto API",
        "version": "1.0.0",
        "description": "A fictional classical music service.",
        "base_url": "https://api.concerto.test",
        "endpoints": [
            {
                "method": "GET",
                "path": "/recordings/{id}",
                "summary": "Get one recording",
                "tag": "Recordings",
                "parameters": [
                    {"name": "id", "in": "path", "type": "integer", "required": True, "example": 21},
                ],
                "responses": [
                    {"status": 200, "description": "Recording found", "example": {"id": 21, "period": "Baroque"}},
                    {"status": 404, "description": "No recording with that id"},
                ],
            },
            {
                "method": "POST",
                "path": "/playlists",
                "summary": "Create a playlist",
                "description": "Creates a new, empty playlist.",
                "parameters": [
                    {"name": "name", "in": "body", "type": "string", "required": True,
                     "description": "The playlist's title"},
                ],
                "responses": [{"status": 201, "description": "Playlist created"}],
            },
        ],
    }


class FindGapsTests(unittest.TestCase):
    def test_finds_missing_endpoint_and_parameter_descriptions(self):
        self.assertEqual(suggest.find_gaps(spec_with_gaps()), [(0, None), (0, 0)])

    def test_blank_description_counts_as_missing(self):
        spec = spec_with_gaps()
        spec["endpoints"][1]["description"] = "   "
        self.assertIn((1, None), suggest.find_gaps(spec))

    def test_complete_spec_has_no_gaps(self):
        spec = json.loads(EXAMPLE_SPEC.read_text(encoding="utf-8"))
        self.assertEqual(suggest.find_gaps(spec), [])


class FactsTests(unittest.TestCase):
    def test_endpoint_facts_include_what_the_ai_may_use(self):
        spec = spec_with_gaps()
        facts = suggest.endpoint_facts(spec, spec["endpoints"][0])
        for expected in [
            "API: Concerto API - A fictional classical music service.",
            "Endpoint: GET /recordings/{id}",
            "Summary: Get one recording",
            "Group: Recordings",
            "id (path, integer, required) (example: 21)",
            '200: Recording found (example: {"id": 21, "period": "Baroque"})',
            "404: No recording with that id",
        ]:
            self.assertIn(expected, facts)

    def test_parameter_facts_name_the_parameter_to_describe(self):
        spec = spec_with_gaps()
        endpoint = spec["endpoints"][0]
        facts = suggest.parameter_facts(spec, endpoint, endpoint["parameters"][0])
        self.assertTrue(facts.endswith("Parameter to describe: id (path, integer, required) (example: 21)"))


class SuggestTests(unittest.TestCase):
    def test_each_kind_of_gap_gets_its_own_rules(self):
        fake = FakeAI(lambda rules, facts: "The recording's id" if is_parameter_rules(rules) else "Returns one recording.")
        suggest.suggest(spec_with_gaps(), ask=fake)
        rules_used = [rules for rules, _ in fake.requests]
        self.assertFalse(is_parameter_rules(rules_used[0]))
        self.assertTrue(is_parameter_rules(rules_used[1]))

    def test_review_entries_are_built_and_start_unaccepted(self):
        answers = iter(["Returns a single recording, including its musical period.", "The recording's id"])
        entries = suggest.suggest(spec_with_gaps(), ask=FakeAI(lambda r, f: next(answers)))
        self.assertEqual(entries, [
            {
                "location": "endpoints[0] (GET /recordings/{id})",
                "method": "GET",
                "path": "/recordings/{id}",
                "suggestion": "Returns a single recording, including its musical period.",
                "accepted": False,
            },
            {
                "location": "endpoints[0] (GET /recordings/{id}).parameters[0]",
                "method": "GET",
                "path": "/recordings/{id}",
                "parameter": "id",
                "suggestion": "The recording's id",
                "accepted": False,
            },
        ])

    def test_quotes_around_the_answer_are_removed(self):
        entries = suggest.suggest(spec_with_gaps(), ask=FakeAI('  "Returns one recording."  '))
        self.assertEqual(entries[0]["suggestion"], "Returns one recording.")

    def test_fallback_answer_gets_a_note(self):
        entries = suggest.suggest(spec_with_gaps(), ask=FakeAI(suggest.ENDPOINT_FALLBACK))
        self.assertIn("too little information", entries[0]["note"])

    def test_missing_full_stop_gets_a_note(self):
        entries = suggest.suggest(spec_with_gaps(), ask=FakeAI("Returns one recording"))
        self.assertEqual(entries[0]["note"], "Doesn't end with a full stop.")

    def test_parameter_with_full_stop_gets_a_note(self):
        entries = suggest.suggest(spec_with_gaps(), ask=FakeAI("The recording's id."))
        self.assertIn("shouldn't", entries[1]["note"])


class ApplyTests(unittest.TestCase):
    def entries(self):
        return suggest.suggest(spec_with_gaps(), ask=FakeAI(lambda r, f: (
            "The recording's id" if is_parameter_rules(r) else "Returns one recording.")))

    def test_only_accepted_suggestions_are_applied(self):
        spec, entries = spec_with_gaps(), self.entries()
        entries[0]["accepted"] = True  # endpoint accepted, parameter left as false
        applied, skipped = suggest.apply_suggestions(spec, entries)
        self.assertEqual(len(applied), 1)
        self.assertEqual(skipped, [])
        self.assertEqual(spec["endpoints"][0]["description"], "Returns one recording.")
        self.assertNotIn("description", spec["endpoints"][0]["parameters"][0])

    def test_description_goes_where_a_person_would_write_it(self):
        spec, entries = spec_with_gaps(), self.entries()
        for entry in entries:
            entry["accepted"] = True
        suggest.apply_suggestions(spec, entries)
        endpoint = spec["endpoints"][0]
        self.assertEqual(list(endpoint), ["method", "path", "summary", "tag", "description", "parameters", "responses"])
        self.assertEqual(list(endpoint["parameters"][0]), ["name", "in", "type", "required", "description", "example"])

    def test_edited_wording_is_what_gets_applied(self):
        spec, entries = spec_with_gaps(), self.entries()
        entries[0]["accepted"] = True
        entries[0]["suggestion"] = "Returns one recording, with its period and length."
        suggest.apply_suggestions(spec, entries)
        self.assertEqual(spec["endpoints"][0]["description"], "Returns one recording, with its period and length.")

    def test_fallback_is_never_applied_even_if_accepted(self):
        spec, entries = spec_with_gaps(), self.entries()
        entries[0].update(accepted=True, suggestion=suggest.ENDPOINT_FALLBACK)
        applied, skipped = suggest.apply_suggestions(spec, entries)
        self.assertEqual(applied, [])
        self.assertIn("placeholder", skipped[0])

    def test_description_written_since_is_left_alone(self):
        spec, entries = spec_with_gaps(), self.entries()
        entries[0]["accepted"] = True
        spec["endpoints"][0]["description"] = "My own words."
        applied, skipped = suggest.apply_suggestions(spec, entries)
        self.assertEqual(spec["endpoints"][0]["description"], "My own words.")
        self.assertIn("already has a description", skipped[0])

    def test_renamed_endpoint_is_skipped(self):
        spec, entries = spec_with_gaps(), self.entries()
        entries[0]["accepted"] = True
        spec["endpoints"][0]["path"] = "/tracks/{id}"
        applied, skipped = suggest.apply_suggestions(spec, entries)
        self.assertEqual(applied, [])
        self.assertIn("no longer matches", skipped[0])


class AskClaudeTests(unittest.TestCase):
    """Checks the real request is built correctly, without sending it."""

    def test_request_is_built_correctly(self):
        reply = io.BytesIO(json.dumps({"content": [{"type": "text", "text": "Returns one recording."}]}).encode())
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
             mock.patch("urllib.request.urlopen", return_value=reply) as urlopen:
            text = suggest.ask_claude("THE RULES", "THE FACTS")

        self.assertEqual(text, "Returns one recording.")
        request = urlopen.call_args.args[0]
        body = json.loads(request.data)
        self.assertEqual(request.full_url, suggest.API_URL)
        self.assertEqual(request.get_header("X-api-key"), "test-key")
        self.assertEqual(body["system"], "THE RULES")
        self.assertIn("THE FACTS", body["messages"][0]["content"])

    def test_missing_api_key_gives_a_clear_message(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
            with self.assertRaises(ServiceError) as ctx:
                suggest.ask_claude("rules", "facts")
        self.assertIn("export ANTHROPIC_API_KEY", str(ctx.exception))


class JsonWriterTests(unittest.TestCase):
    def test_library_spec_comes_back_identical(self):
        # So applying suggestions only shows the new lines in git diff.
        original = EXAMPLE_SPEC.read_text(encoding="utf-8")
        self.assertEqual(jsonwriter.dumps(json.loads(original)), original)


class CommandLineTests(unittest.TestCase):
    def run_docgen(self, *args, env=None):
        return subprocess.run(
            [sys.executable, "-m", "docgen", *map(str, args)],
            cwd=PROJECT_ROOT, capture_output=True, text=True, encoding="utf-8",
            env={**os.environ, **(env or {})},
        )

    def test_complete_spec_needs_no_suggestions(self):
        result = self.run_docgen("--suggest", EXAMPLE_SPEC)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Nothing to suggest", result.stdout)

    def test_openapi_files_are_refused_for_now(self):
        result = self.run_docgen("--suggest", PROJECT_ROOT / "examples" / "library_openapi.json")
        self.assertEqual(result.returncode, 2)
        self.assertIn("only work on docgen's own JSON format", result.stderr)

    def test_suggest_without_api_key_stops_before_writing(self):
        with tempfile.TemporaryDirectory() as folder:
            spec = Path(folder) / "gaps.json"
            spec.write_text(json.dumps(spec_with_gaps()), encoding="utf-8")
            result = self.run_docgen("--suggest", spec, env={"ANTHROPIC_API_KEY": ""})
            self.assertEqual(result.returncode, 2)
            self.assertIn("No API key found", result.stderr)
            self.assertFalse(suggest.review_path(spec).exists())

    def test_apply_writes_accepted_drafts_and_removes_review_file(self):
        with tempfile.TemporaryDirectory() as folder:
            spec = Path(folder) / "gaps.json"
            spec.write_text(jsonwriter.dumps(spec_with_gaps()), encoding="utf-8")
            entries = ApplyTests().entries()
            entries[0]["accepted"] = True
            review = suggest.review_path(spec)
            review.write_text(json.dumps(entries), encoding="utf-8")

            result = self.run_docgen("--apply-suggestions", spec)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Updated", result.stdout)
            self.assertFalse(review.exists())
            saved = json.loads(spec.read_text(encoding="utf-8"))
            self.assertEqual(saved["endpoints"][0]["description"], "Returns one recording.")

    def test_apply_without_review_file_explains_what_to_do(self):
        with tempfile.TemporaryDirectory() as folder:
            spec = Path(folder) / "gaps.json"
            shutil.copy(EXAMPLE_SPEC, spec)
            result = self.run_docgen("--apply-suggestions", spec)
            self.assertEqual(result.returncode, 2)
            self.assertIn("Run --suggest first", result.stderr)


if __name__ == "__main__":
    unittest.main()
