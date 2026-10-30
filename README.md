# API JSON to Markdown

Turn a JSON API spec into clear, ready-to-publish Markdown docs.

You describe your API's endpoints, parameters and responses in one JSON file. The tool checks it, flags gaps in the documentation, and writes a Markdown reference with a table of contents, parameter tables, copy-and-paste curl examples and response samples. It's plain, deterministic Python: the same input always gives byte-for-byte the same output.

Requirements: Python 3.10 or later. Standard library only, nothing to install.

> **Note:** the input is this tool's own simplified JSON format (see [Spec schema](#spec-schema)), not OpenAPI or Swagger. OpenAPI support is planned.

## Get the code

```
git clone https://github.com/ivanwalsh/api-json-to-markdown.git
cd api-json-to-markdown
```

## Quick start

Run these from the project folder:

```
python -m docgen examples/library_api.json output/library_api.md   # write a file
python -m docgen examples/library_api.json                         # print to screen
python -m docgen --check examples/library_api.json                 # quality check only
python -m unittest -v                                              # run all tests
```

On Linux and macOS, use `python3` wherever this file says `python`.

Exit codes: `0` success, `1` the spec is invalid, `2` the file could not be read, `3` `--check` found quality warnings.

## How it works

```
JSON file -> load -> validate -> normalize -> render -> Markdown file
                                           -> check  -> quality warnings
```

| Step | Module | Job |
|---|---|---|
| Load | `docgen/loader.py` | Read the file, parse JSON. Broken JSON reports line and column. |
| Validate | `docgen/validator.py` | Check every schema rule and report all problems at once. |
| Normalize | `docgen/normalizer.py` | Uppercase methods, fill defaults, sort responses, drop unknown fields. |
| Render | `docgen/renderer.py` | Build Markdown text. Never touches files. |
| Curl | `docgen/curl.py` | Build the example curl command for each endpoint. Called by the renderer. |
| Check | `docgen/checker.py` | Find valid but unhelpful docs. Warnings only, never changes the Markdown. |
| Write | `docgen/__main__.py` | Command line handling, save with `\n` line endings. |

`docgen/errors.py` holds the two error types: `SpecError` (bad spec) and `SpecFileError` (cannot read file).

## Folder layout

```
docgen/            the application package
examples/          library_api.json, the fictional Community Library API
output/            generated docs (safe to delete, regenerated on demand)
tests/
  fixtures/        small valid and invalid JSON files
  expected/        golden Markdown that the output must match exactly
  test_*.py        unittest suites
```

## Spec schema

**Top level:** `name` (string, required), `version` (string, required), `description` (string, optional), `base_url` (string starting with http:// or https://, required), `endpoints` (non-empty list, required).

**Endpoint:** `method` (GET, POST, PUT, PATCH or DELETE, any case), `path` (starts with `/`), `summary` (required), `description` (optional), `tag` (optional; groups the table of contents), `parameters` (optional list), `responses` (non-empty list). Each method and path pair must be unique.

**Parameter:** `name` (unique per endpoint), `in` (path, query, header or body), `type` (string, integer, number, boolean, array or object), `required` (true or false, default false), `description` (optional), `example` (any JSON, optional; used in the curl command).

**Response:** `status` (integer 100 to 599, unique per endpoint), `description` (required), `example` (any JSON, optional).

Unknown fields are ignored. Endpoints and parameters keep the author's order. Responses are sorted by status code.

## Example requests

Every endpoint gets a copy-and-paste curl command, built from `base_url`, the method, the path and the parameter examples:

```bash
curl -X POST 'https://api.example-library.test/loans' \
  -H 'Content-Type: application/json' \
  -d '{"book_id": 7, "member_id": 301}'
```

| `in` | Where it goes |
|---|---|
| `path` | Replaces `{name}` in the URL |
| `query` | Added after `?`, URL-encoded |
| `header` | Added as `-H 'Name: value'` |
| `body` | Collected into one JSON object sent with `-d` |

A required parameter with no `example` appears as a placeholder like `<book_id>`. An optional one with no example is left out.

## Quality check

The validator asks "can we build docs from this?" The quality check asks "are these docs any good?" Its findings are warnings: the docs are still built and the exit code stays 0. Use `--check` to run the check on its own; it writes nothing and exits 3 if it finds anything.

| Code | Warns when |
|---|---|
| `summary-style` | A summary is over 80 characters or ends with a full stop |
| `missing-description` | An endpoint has no description |
| `description-style` | An endpoint description doesn't end with a full stop |
| `missing-param-description` | A parameter has no description |
| `missing-param-example` | A required parameter has no example (the curl command will show a placeholder) |
| `path-param-required` | A path parameter isn't marked `required: true` |
| `unused-path-param` | A parameter says `in: path` but the path has no `{name}` for it |
| `undeclared-path-param` | The path has `{name}` but no matching parameter with `in: path` |
| `no-success-response` | An endpoint has no 2xx response |
| `success-without-example` | A 2xx response (other than 204 No Content) has no example |

Example output:

```
  - endpoints[1] (GET /books/{id}): no description [missing-description]
1 warning(s)
```

During normal generation, warnings go to standard error, so they never end up inside Markdown printed to the screen.

## Determinism rules

- No timestamps, random values or machine paths in the output.
- JSON examples use sorted keys and two-space indentation.
- `|` in table cells is escaped; line breaks in headings and cells are collapsed.
- Empty optional sections are left out.
- Output ends with exactly one newline.

## Updating the golden file

If you change the renderer on purpose, the golden test will fail. That is expected. Regenerate, read the diff carefully, then replace the golden file:

```
python -m docgen examples/library_api.json output/library_api.md
diff tests/expected/library_api.md output/library_api.md
cp output/library_api.md tests/expected/library_api.md
```

Only copy it across once you are sure the new output is what you want.

## About

Built as a learning project, step by step, with a test for every rule. No AI is involved in generating the docs: every line of output comes from the spec, so the results are predictable and easy to review.
