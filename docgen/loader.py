"""Step 1: read a spec file from disk and parse the JSON.

This module only turns text into Python data (dicts, lists, strings,
numbers). It does not check whether the data makes sense; that is the
validator's job.
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
    return parse_spec(text)


def parse_spec(text):
    """Parse JSON text. Broken JSON becomes a SpecError with its position."""
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise SpecError(
            f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from None
