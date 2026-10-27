"""Build a copy-and-paste curl command for one endpoint.

Like the renderer, this module never touches files: it takes a base URL
and a normalized endpoint, and returns the command as a list of lines.

How each parameter is used:
    path    replaces {name} in the URL
    query   added after "?", URL-encoded (a space becomes %20)
    header  added as -H 'Name: value'
    body    collected into one JSON object sent with -d

A parameter with an example uses it. A required parameter without one
appears as a placeholder like <book_id>. An optional parameter without
one is left out to keep the command short.

Determinism rules followed here:
    - parameters keep the author's order (body JSON uses sorted keys)
    - JSON values are written the same way every time
    - shell quoting is applied with one fixed rule
"""

import json
from urllib.parse import quote


def curl_lines(base_url, endpoint):
    """Return the curl command for `endpoint` as a list of lines."""
    path = endpoint["path"]
    query = []
    headers = []
    body = {}

    for parameter in endpoint["parameters"]:
        value = _sample_value(parameter)
        if value is LEAVE_OUT:
            continue  # optional and no example
        name = parameter["name"]
        location = parameter["in"]

        if location == "path":
            path = path.replace("{" + name + "}", _url_part(value))
        elif location == "query":
            query.append(f"{quote(name, safe='')}={_url_part(value)}")
        elif location == "header":
            headers.append(f"{name}: {_text(value)}")
        elif location == "body":
            body[name] = value.raw if isinstance(value, Placeholder) else value

    url = base_url.rstrip("/") + path
    if query:
        url += "?" + "&".join(query)

    first = "curl"
    if endpoint["method"] != "GET":  # GET is curl's default
        first += f" -X {endpoint['method']}"
    first += " " + _shell_quote(url)

    options = [f"-H {_shell_quote(h)}" for h in headers]
    if body:
        options.append(f"-H {_shell_quote('Content-Type: application/json')}")
        options.append(f"-d {_shell_quote(_json(body))}")

    # One option per line, joined with a trailing backslash.
    lines = [first] + ["  " + option for option in options]
    return [line + " \\" for line in lines[:-1]] + [lines[-1]]


class Placeholder:
    """Stands in for a required value the spec gave no example for."""

    def __init__(self, name):
        self.raw = f"<{name}>"


# A unique marker meaning "skip this parameter". We can't use None for
# this, because null is a legitimate JSON example value.
LEAVE_OUT = object()


def _sample_value(parameter):
    """The value to show, a Placeholder, or LEAVE_OUT."""
    if parameter["has_example"]:
        return parameter["example"]
    if parameter["required"]:
        return Placeholder(parameter["name"])
    return LEAVE_OUT


def _text(value):
    """Turn a value into plain text: strings as-is, everything else as JSON.

    This is why a boolean shows as `true`, not Python's `True`.
    """
    if isinstance(value, Placeholder):
        return value.raw
    if isinstance(value, str):
        return value
    return _json(value)


def _url_part(value):
    """Text that is safe inside a URL. Placeholders stay readable."""
    if isinstance(value, Placeholder):
        return value.raw
    return quote(_text(value), safe="")


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _shell_quote(text):
    """Wrap text in single quotes for bash.

    Inside single quotes bash treats everything literally, except a
    single quote itself. That is written as '\\'' : close the quote, add
    an escaped quote, then reopen. So O'Brien becomes 'O'\\''Brien'.
    """
    return "'" + text.replace("'", "'\\''") + "'"
