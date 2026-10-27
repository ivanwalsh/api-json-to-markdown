"""Documentation quality check: find things that are valid but unhelpful.

The validator asks "can we build docs from this?" The checker asks "are
these docs any good?" Its findings are warnings: they never stop the
Markdown from being built, and they never change the Markdown.

Call check_spec() on a *normalized* spec (see normalizer.py). Warnings
come back in a fixed order: endpoint by endpoint, in the author's order,
and in the same rule order within each endpoint. Same input, same
warnings, every time.

Rules:
    summary-style              summary over 80 characters or ends with "."
    missing-description        endpoint has no description
    missing-param-description  parameter has no description
    path-param-required        path parameter not marked required
    unused-path-param          path parameter not used in the path
    undeclared-path-param      {name} in the path has no path parameter
    no-success-response        endpoint has no 2xx response
    success-without-example    2xx response (not 204) has no example
"""

import re
from dataclasses import dataclass

MAX_SUMMARY_LENGTH = 80

# Matches {id} or {book_id} in a path and captures the name inside.
PATH_PLACEHOLDER = re.compile(r"\{([^{}/]+)\}")


@dataclass(frozen=True)
class QualityWarning:
    """One finding: where it is, what is wrong, and which rule found it."""

    location: str
    message: str
    code: str

    def __str__(self):
        return f"{self.location}: {self.message} [{self.code}]"


def check_spec(spec):
    """Return a list of QualityWarning for a normalized spec (empty if clean)."""
    warnings = []
    for index, endpoint in enumerate(spec["endpoints"]):
        warnings += _check_endpoint(endpoint, f"endpoints[{index}]")
    return warnings


def _check_endpoint(endpoint, where):
    found = []

    def warn(location, message, code):
        found.append(QualityWarning(location, message, code))

    # --- Summary and description -------------------------------------------
    summary = endpoint["summary"]
    if len(summary) > MAX_SUMMARY_LENGTH:
        warn(
            f"{where}.summary",
            f"summary is {len(summary)} characters (keep it to {MAX_SUMMARY_LENGTH} or fewer)",
            "summary-style",
        )
    if summary.endswith("."):
        warn(f"{where}.summary", "summary should not end with a full stop", "summary-style")

    if not endpoint["description"]:
        warn(where, "no description", "missing-description")

    # --- Parameters ----------------------------------------------------------
    names_in_path = PATH_PLACEHOLDER.findall(endpoint["path"])
    declared_path_params = set()

    for p_index, parameter in enumerate(endpoint["parameters"]):
        p_where = f"{where}.parameters[{p_index}]"
        name = parameter["name"]

        if not parameter["description"]:
            warn(p_where, f'parameter "{name}" has no description', "missing-param-description")

        if parameter["in"] == "path":
            declared_path_params.add(name)
            if not parameter["required"]:
                warn(
                    p_where,
                    f'path parameter "{name}" should be marked required',
                    "path-param-required",
                )
            if name not in names_in_path:
                warn(
                    p_where,
                    f'path parameter "{name}" does not appear in the path '
                    f'{endpoint["path"]}',
                    "unused-path-param",
                )

    for name in names_in_path:
        if name not in declared_path_params:
            warn(
                where,
                f'path uses {{{name}}} but no parameter "{name}" has "in": "path"',
                "undeclared-path-param",
            )

    # --- Responses -----------------------------------------------------------
    statuses = [r["status"] for r in endpoint["responses"]]
    if not any(200 <= s <= 299 for s in statuses):
        warn(where, "no success (2xx) response", "no-success-response")

    for response in endpoint["responses"]:
        status = response["status"]
        # 204 means "No Content", so it should not have an example.
        if 200 <= status <= 299 and status != 204 and not response["has_example"]:
            warn(
                f"{where} response {status}",
                "success response has no example",
                "success-without-example",
            )

    return found
