"""Write JSON in the same layout people use when writing specs by hand.

json.dumps(indent=2) puts every value on its own line, so writing a spec
back would turn each one-line parameter into five lines, and `git diff`
would show the whole file as changed. This writer keeps short things on
one line, the way the example specs are written:

    - anything that fits within WIDTH characters stays on one line
    - a list of objects always puts each object on its own line
    - everything else is spread over several lines, indented by 2

The library example spec comes back byte for byte identical, so after
applying suggestions, `git diff` shows only the lines that really changed.
"""

import json

WIDTH = 160


def dumps(value):
    """Return value as JSON text in the hand-written layout, ending in a newline."""
    return _format(value, indent=0, prefix_len=0) + "\n"


def _format(value, indent, prefix_len):
    one_line = json.dumps(value, ensure_ascii=False)
    is_container = isinstance(value, (dict, list))
    list_of_objects = isinstance(value, list) and any(isinstance(x, (dict, list)) for x in value)

    fits = indent + prefix_len + len(one_line) <= WIDTH
    if not is_container or not value or (fits and not list_of_objects):
        return one_line

    pad = " " * indent
    inner = " " * (indent + 2)
    if isinstance(value, dict):
        lines = []
        for key, item in value.items():
            key_text = json.dumps(key, ensure_ascii=False) + ": "
            lines.append(inner + key_text + _format(item, indent + 2, len(key_text)))
        return "{\n" + ",\n".join(lines) + "\n" + pad + "}"

    lines = [inner + _format(item, indent + 2, 0) for item in value]
    return "[\n" + ",\n".join(lines) + "\n" + pad + "]"
