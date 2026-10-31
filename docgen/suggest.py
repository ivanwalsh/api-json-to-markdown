"""AI-drafted descriptions: find gaps, ask an AI for drafts, apply the ones a human accepts.

The AI never touches the Markdown. It only proposes text for missing
descriptions in the spec, and a person decides what goes in:

    1. find_gaps()          endpoints and parameters with no description
    2. suggest()            ask the AI for a draft of each, using the rules
                            in docgen/prompts/, and collect review entries
    3. (a human edits the review file and sets "accepted": true)
    4. apply_suggestions()  write only the accepted drafts into the spec

The rest of the pipeline is unchanged, so the same spec still produces
the same Markdown, every time.

Privacy: suggest() sends parts of the spec to the AI service. Only use
it on fictional or public specs, never on confidential ones.
"""

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from .errors import ServiceError

PROMPTS_FOLDER = Path(__file__).parent / "prompts"
ENDPOINT_RULES = PROMPTS_FOLDER / "endpoint_description.md"
PARAMETER_RULES = PROMPTS_FOLDER / "parameter_description.md"

# The exact fallback text each prompt tells the AI to send when the facts
# aren't enough. A suggestion matching one of these can never be applied.
ENDPOINT_FALLBACK = "Insufficient information to describe this endpoint."
PARAMETER_FALLBACK = "Insufficient information to describe this parameter"

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-haiku-5-5"  # small and fast, which suits short descriptions
MAX_TOKENS = 200

PRIVACY_NOTE = (
    "Sending parts of this spec to Anthropic's API to draft descriptions. "
    "Only use --suggest on fictional or public specs."
)


# --- 1. Find the gaps ------------------------------------------------------------


def find_gaps(spec):
    """Return (endpoint_index, parameter_index) pairs for each missing description.

    parameter_index is None when the endpoint's own description is missing.
    The spec must already have passed validate_spec().
    """
    gaps = []
    for e_index, endpoint in enumerate(spec["endpoints"]):
        if not endpoint.get("description", "").strip():
            gaps.append((e_index, None))
        for p_index, parameter in enumerate(endpoint.get("parameters", [])):
            if not parameter.get("description", "").strip():
                gaps.append((e_index, p_index))
    return gaps


# --- 2. Ask the AI for drafts ----------------------------------------------------


def suggest(spec, ask, on_progress=None):
    """Draft a description for every gap. Returns a list of review entries.

    `ask` is a function taking (rules, facts) and returning the AI's text.
    The real one is ask_claude(); tests pass a fake, so they never use the
    network.
    """
    endpoint_rules = ENDPOINT_RULES.read_text(encoding="utf-8")
    parameter_rules = PARAMETER_RULES.read_text(encoding="utf-8")

    entries = []
    for e_index, p_index in find_gaps(spec):
        endpoint = spec["endpoints"][e_index]
        location = _location(endpoint, e_index, p_index)
        if on_progress:
            on_progress(location)

        if p_index is None:
            facts = endpoint_facts(spec, endpoint)
            draft = _clean(ask(endpoint_rules, facts))
            note = _endpoint_note(draft)
        else:
            parameter = endpoint["parameters"][p_index]
            facts = parameter_facts(spec, endpoint, parameter)
            draft = _clean(ask(parameter_rules, facts))
            note = _parameter_note(draft)

        entry = {
            "location": location,
            "method": endpoint["method"].upper(),
            "path": endpoint["path"],
        }
        if p_index is not None:
            entry["parameter"] = endpoint["parameters"][p_index]["name"]
        entry["suggestion"] = draft
        entry["accepted"] = False
        if note:
            entry["note"] = note
        entries.append(entry)
    return entries


def endpoint_facts(spec, endpoint):
    """The facts about one endpoint that the AI is allowed to use."""
    lines = [
        f"API: {spec['name']}" + (f" - {spec['description']}" if spec.get("description") else ""),
        f"Endpoint: {endpoint['method'].upper()} {endpoint['path']}",
        f"Summary: {endpoint['summary']}",
    ]
    if endpoint.get("tag"):
        lines.append(f"Group: {endpoint['tag']}")

    parameters = endpoint.get("parameters", [])
    if parameters:
        lines.append("Parameters:")
        for parameter in parameters:
            lines.append("  - " + _parameter_line(parameter))

    lines.append("Responses:")
    for response in endpoint["responses"]:
        line = f"  - {response['status']}: {response['description']}"
        if "example" in response:
            line += f" (example: {json.dumps(response['example'], ensure_ascii=False)})"
        lines.append(line)
    return "\n".join(lines)


def parameter_facts(spec, endpoint, parameter):
    """The endpoint's facts, plus which parameter to describe."""
    return (
        endpoint_facts(spec, endpoint)
        + "\n\nParameter to describe: "
        + _parameter_line(parameter, include_description=False)
    )


def _parameter_line(parameter, include_description=True):
    required = "required" if parameter.get("required") else "optional"
    line = f"{parameter['name']} ({parameter['in']}, {parameter['type']}, {required})"
    if include_description and parameter.get("description"):
        line += f": {parameter['description']}"
    if "example" in parameter:
        line += f" (example: {json.dumps(parameter['example'], ensure_ascii=False)})"
    return line


def _location(endpoint, e_index, p_index):
    location = f"endpoints[{e_index}] ({endpoint['method'].upper()} {endpoint['path']})"
    if p_index is not None:
        location += f".parameters[{p_index}]"
    return location


def _clean(text):
    """Trim spaces and any quotation marks the AI wrapped around its answer."""
    text = text.strip()
    for quote in ('"', "'", "`", "“"):
        closing = "”" if quote == "“" else quote
        if len(text) >= 2 and text.startswith(quote) and text.endswith(closing):
            text = text[1:-1].strip()
    return text


def _endpoint_note(draft):
    if draft == ENDPOINT_FALLBACK:
        return "The AI found too little information. Write this one yourself."
    if not draft.endswith("."):
        return "Doesn't end with a full stop."
    return None


def _parameter_note(draft):
    if draft == PARAMETER_FALLBACK:
        return "The AI found too little information. Write this one yourself."
    if draft.endswith("."):
        return "Ends with a full stop, but parameter descriptions shouldn't."
    return None


# --- The real AI call ------------------------------------------------------------


def ask_claude(rules, facts):
    """Send the rules and facts to Anthropic's API and return the reply text.

    Uses only the standard library. The API key is read from the
    ANTHROPIC_API_KEY environment variable, never from the code. Set
    DOCGEN_MODEL to try a different model.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise ServiceError(
            "No API key found. Set it for this terminal session with: "
            "export ANTHROPIC_API_KEY='your-key-here'"
        )

    body = {
        "model": os.environ.get("DOCGEN_MODEL", DEFAULT_MODEL),
        "max_tokens": MAX_TOKENS,
        "system": rules,
        "messages": [{"role": "user", "content": facts + "\n\nWrite the description."}],
    }
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": API_VERSION,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            reply = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ServiceError(
            f"The AI service returned an error ({exc.code}): {_error_message(exc)}"
        ) from None
    except urllib.error.URLError as exc:
        raise ServiceError(f"Could not reach the AI service: {exc.reason}") from None

    parts = [block.get("text", "") for block in reply.get("content", []) if block.get("type") == "text"]
    return "".join(parts)


def _error_message(http_error):
    """Pull a readable message out of an API error response."""
    try:
        details = json.loads(http_error.read().decode("utf-8"))
        return details["error"]["message"]
    except (ValueError, KeyError, TypeError):
        return http_error.reason


# --- 4. Apply the accepted drafts ------------------------------------------------


def review_path(spec_path):
    """concerto_api.json -> concerto_api.suggestions.json, in the same folder."""
    spec_path = Path(spec_path)
    return spec_path.with_name(spec_path.stem + ".suggestions.json")


def apply_suggestions(spec, entries):
    """Write accepted drafts into the spec (changed in place).

    Returns (applied, skipped): two lists of human-readable messages.
    An entry is skipped if it wasn't accepted, is a fallback, is empty, no
    longer matches the spec, or its description has been filled in since.
    """
    applied, skipped = [], []
    if not isinstance(entries, list):
        raise ValueError("the review file should contain a list of suggestions")

    for number, entry in enumerate(entries, start=1):
        label = entry.get("location", f"suggestion {number}") if isinstance(entry, dict) else f"suggestion {number}"
        if not isinstance(entry, dict) or entry.get("accepted") is not True:
            continue  # rejected, or still waiting for review

        text = entry.get("suggestion")
        if not isinstance(text, str) or not text.strip():
            skipped.append(f"{label}: accepted, but the suggestion is empty")
            continue
        text = text.strip()
        if text in (ENDPOINT_FALLBACK, PARAMETER_FALLBACK):
            skipped.append(f"{label}: accepted, but it's the 'insufficient information' placeholder")
            continue

        target = _find_target(spec, entry)
        if target is None:
            skipped.append(f"{label}: no longer matches the spec (was it moved or renamed?)")
            continue
        if target.get("description", "").strip():
            skipped.append(f"{label}: already has a description, so it was left alone")
            continue

        # Put the description where a person would write it, not at the end.
        place_after = ENDPOINT_DESCRIPTION_AFTER if "parameter" not in entry else PARAMETER_DESCRIPTION_AFTER
        _insert(target, "description", text, place_after)
        applied.append(f"{label}: {text}")
    return applied, skipped


# Where a new description goes: straight after the last of these keys that exists.
ENDPOINT_DESCRIPTION_AFTER = ("method", "path", "summary", "tag")
PARAMETER_DESCRIPTION_AFTER = ("name", "in", "type", "required")


def _insert(target, key, value, after_keys):
    """Set target[key] = value, placed straight after the last of after_keys present.

    Dictionaries keep their keys in order, so this rebuilds the dictionary
    in place with the new key in the right position.
    """
    target.pop(key, None)
    items = list(target.items())
    position = 0
    for index, (existing, _) in enumerate(items):
        if existing in after_keys:
            position = index + 1
    items.insert(position, (key, value))
    target.clear()
    target.update(items)


def _find_target(spec, entry):
    """Find the endpoint, or parameter, an entry refers to, by method, path and name."""
    for endpoint in spec.get("endpoints", []):
        if endpoint.get("method", "").upper() != entry.get("method") or endpoint.get("path") != entry.get("path"):
            continue
        if "parameter" not in entry:
            return endpoint
        for parameter in endpoint.get("parameters", []):
            if parameter.get("name") == entry["parameter"]:
                return parameter
        return None
    return None
