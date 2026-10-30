"""Step 4: turn a normalized spec into Markdown text.

The renderer builds a list of lines and joins them at the end. It never
reads or writes files, which makes it easy to test.

Determinism rules followed here:
- no dates, random values or machine-specific paths
- JSON examples printed with sorted keys and fixed indentation
- "\n" line endings and exactly one newline at the end
- empty optional sections are left out, never printed empty
"""

import json

from .curl import curl_lines

# Table of contents heading for endpoints without a tag, when others have one.
OTHER_GROUP = "Other"


def render_markdown(spec):
    lines = [f"# {_one_line(spec['name'])}", ""]

    if spec["description"]:
        lines += [spec["description"], ""]

    lines += [
        f"- **Version:** {_one_line(spec['version'])}",
        f"- **Base URL:** `{spec['base_url']}`",
        "",
        "## Endpoints",
        "",
    ]

    anchors = _make_anchors(_endpoint_title(e) for e in spec["endpoints"])

    # Collect the table of contents entries, grouped by tag. A dictionary
    # keeps keys in the order they were first added, so groups appear in
    # the order their tag first appears in the spec.
    groups = {}
    for endpoint, anchor in zip(spec["endpoints"], anchors):
        title = _endpoint_title(endpoint)
        entry = f"- [{title}](#{anchor}): {_one_line(endpoint['summary'])}"
        groups.setdefault(endpoint["tag"], []).append(entry)

    if list(groups) == [""]:
        # No endpoint has a tag: a plain list, exactly as before tags existed.
        lines += groups[""] + [""]
    else:
        # Untagged endpoints (tag "") go in a group of their own, at the end.
        untagged = groups.pop("", [])
        if untagged:
            groups.setdefault(OTHER_GROUP, []).extend(untagged)
        for tag, entries in groups.items():
            lines += [f"### {_one_line(tag)}", ""] + entries + [""]

    for endpoint in spec["endpoints"]:
        lines += _render_endpoint(endpoint, spec["base_url"])

    # Join, then make sure the file ends with exactly one newline.
    return "\n".join(lines).rstrip("\n") + "\n"


def _render_endpoint(endpoint, base_url):
    lines = [
        f"## {_endpoint_title(endpoint)}",
        "",
        _one_line(endpoint["summary"]),
        "",
    ]

    if endpoint["description"]:
        lines += [endpoint["description"], ""]

    if endpoint["parameters"]:
        lines += [
            "### Parameters",
            "",
            "| Name | In | Type | Required | Description |",
            "|---|---|---|---|---|",
        ]
        for p in endpoint["parameters"]:
            cells = [
                p["name"],
                p["in"],
                p["type"],
                "yes" if p["required"] else "no",
                p["description"],
            ]
            lines.append(_table_row(cells))
        lines.append("")

    lines += ["### Example request", ""]
    lines += _code_block("\n".join(curl_lines(base_url, endpoint)), "bash")
    lines.append("")

    lines += ["### Responses", ""]
    for response in endpoint["responses"]:
        lines += [f"#### {response['status']}: {_one_line(response['description'])}", ""]
        if response["has_example"]:
            lines += _code_block(_format_example(response["example"]), "json")
            lines.append("")

    return lines


# --- Small helpers ----------------------------------------------------------


def _endpoint_title(endpoint):
    return f"{endpoint['method']} {endpoint['path']}"


def _one_line(text):
    """Collapse line breaks so text is safe inside a heading or list item."""
    return " ".join(text.split())


def _table_row(cells):
    """Build one Markdown table row, escaping characters that break tables."""
    safe = [_one_line(cell).replace("|", "\\|") for cell in cells]
    return "| " + " | ".join(safe) + " |"


def _format_example(example):
    """Pretty-print JSON the same way every time, whatever the input key order."""
    return json.dumps(example, indent=2, sort_keys=True, ensure_ascii=False)


def _code_block(text, language):
    """Wrap text in a fenced code block.

    The fence is made longer than any run of backticks inside the text,
    so an example containing ``` cannot close the block early.
    """
    longest = 0
    run = 0
    for ch in text:
        run = run + 1 if ch == "`" else 0
        longest = max(longest, run)
    fence = "`" * max(3, longest + 1)
    return [f"{fence}{language}", text, fence]


def _slugify(text):
    """Make a GitHub-style heading anchor: "GET /books/{id}" -> "get-booksid"."""
    kept = [ch for ch in text.lower() if ch.isalnum() or ch in " -_"]
    return "".join(kept).replace(" ", "-")


def _make_anchors(titles):
    """Slugify each title, adding -1, -2 ... if two would clash (as GitHub does)."""
    counts = {}
    anchors = []
    for title in titles:
        slug = _slugify(title)
        if slug in counts:
            counts[slug] += 1
            anchors.append(f"{slug}-{counts[slug]}")
        else:
            counts[slug] = 0
            anchors.append(slug)
    return anchors
