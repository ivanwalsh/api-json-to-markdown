"""Step 1: read a spec file from disk and parse the JSON or YAML.

This module only turns text into Python data (dicts, lists, strings,
numbers). It does not check whether the data makes sense; that is the
validator's job.

Files ending in .yaml or .yml are read as YAML. That needs the PyYAML
package, which is loaded only when a YAML file is opened, so JSON users
never need it. Everything else is read as JSON.
"""

import json
from pathlib import Path

from .errors import SpecError, SpecFileError


def load_spec(path):
    """Read the file at `path` and return the parsed JSON data."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise SpecFileError(f"File not found: {path}") from None
    except IsADirectoryError:
        raise SpecFileError(f"Expected a file but found a folder: {path}") from None
    except UnicodeDecodeError:
        raise SpecError(f"{path} is not valid UTF-8 text") from None
    except OSError as exc:
        raise SpecFileError(f"Could not read {path}: {exc.strerror}") from None
    if path.suffix.lower() in YAML_SUFFIXES:
        return parse_yaml(text)
    return parse_spec(text)


def parse_spec(text):
    """Parse JSON text. Broken JSON becomes a SpecError with its position."""
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise SpecError(
            f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from None


YAML_SUFFIXES = (".yaml", ".yml")


def parse_yaml(text):
    """Parse YAML text. Broken YAML becomes a SpecError with its position."""
    try:
        import yaml  # loaded here, not at the top, so JSON users never need it
    except ImportError:
        raise SpecFileError(
            "Reading YAML files needs the PyYAML package. Install it with "
            "'sudo dnf install python3-pyyaml' (Fedora) or 'pip install pyyaml'."
        ) from None
    try:
        # A *safe* loader only reads data. The ordinary one can run code
        # hidden in a file, which matters for specs someone else sent you.
        return yaml.load(text, Loader=_safe_loader_without_dates(yaml))
    except yaml.MarkedYAMLError as exc:
        mark = exc.problem_mark
        raise SpecError(
            f"Invalid YAML at line {mark.line + 1}, column {mark.column + 1}: {exc.problem}"
        ) from None
    except yaml.YAMLError as exc:
        raise SpecError(f"Invalid YAML: {exc}") from None


def _safe_loader_without_dates(yaml):
    """A safe YAML loader that keeps dates like 2026-11-15 as plain text.

    Plain YAML turns them into date objects, which can't be shown as JSON
    examples. Keeping them as text matches what a JSON file would give.
    """

    class Loader(yaml.SafeLoader):
        pass

    # Copy the rules YAML uses to guess types, minus the one for dates.
    Loader.yaml_implicit_resolvers = {
        first_char: [rule for rule in rules if rule[0] != "tag:yaml.org,2002:timestamp"]
        for first_char, rules in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }
    return Loader
