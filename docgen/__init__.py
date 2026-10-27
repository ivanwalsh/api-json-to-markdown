"""docgen: turn a JSON API spec into Markdown documentation.

The pipeline, one module per step:

    loader.load_spec       file  -> Python data
    validator.validate_spec       check the data (raises SpecError)
    normalizer.normalize_spec     fill defaults, fix ordering
    renderer.render_markdown      data  -> Markdown text

generate_markdown() below runs steps 2 to 4 in one call.
"""

from .errors import SpecError, SpecFileError
from .loader import load_spec, parse_spec
from .normalizer import normalize_spec
from .renderer import render_markdown
from .validator import validate_spec


def generate_markdown(raw_spec):
    """Validate, normalize and render parsed spec data. Returns Markdown text."""
    validate_spec(raw_spec)
    return render_markdown(normalize_spec(raw_spec))


__all__ = [
    "SpecError",
    "SpecFileError",
    "generate_markdown",
    "load_spec",
    "normalize_spec",
    "parse_spec",
    "render_markdown",
    "validate_spec",
]
