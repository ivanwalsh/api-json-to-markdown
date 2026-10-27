# AI Documentation Lab

A small educational tool that reads a fictional API specification written in JSON and generates Markdown documentation. The code is plain, deterministic Python: the same input always gives byte-for-byte the same output.

Requirements: Python 3.10 or later. Standard library only, nothing to install.

## Quick start

Run these from this folder:

```
python -m docgen examples/library_api.json output/library_api.md   # write a file
python -m docgen examples/library_api.json                         # print to screen
python -m unittest -v                                              # run all tests
```

Exit codes: `0` success, `1` the spec is invalid, `2` the file could not be read.

## How it works

```
JSON file -> load -> validate -> normalize -> render -> Markdown file
```

| Step | Module | Job |
|---|---|---|
| Load | `docgen/loader.py` | Read the file, parse JSON. Broken JSON reports line and column. |
| Validate | `docgen/validator.py` | Check every schema rule and report all problems at once. |
| Normalize | `docgen/normalizer.py` | Uppercase methods, fill defaults, sort responses, drop unknown fields. |
| Render | `docgen/renderer.py` | Build Markdown text. Never touches files. |
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

**Endpoint:** `method` (GET, POST, PUT, PATCH or DELETE, any case), `path` (starts with `/`), `summary` (required), `description` (optional), `parameters` (optional list), `responses` (non-empty list). Each method and path pair must be unique.

**Parameter:** `name` (unique per endpoint), `in` (path, query, header or body), `type` (string, integer, number, boolean, array or object), `required` (true or false, default false), `description` (optional).

**Response:** `status` (integer 100 to 599, unique per endpoint), `description` (required), `example` (any JSON, optional).

Unknown fields are ignored. Endpoints and parameters keep the author's order. Responses are sorted by status code.

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
