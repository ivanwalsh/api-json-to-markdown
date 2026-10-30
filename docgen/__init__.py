"""docgen: turn a JSON API spec into Markdown documentation.

The pipeline, one module per step:

    loader.load_spec       file  -> Python data
    openapi.prepare_spec          convert OpenAPI to our format (if needed)
    validator.validate_spec       check the data (raises SpecError)
    normalizer.normalize_spec     fill defaults, fix ordering
    renderer.render_markdown      data  -> Markdown text
    checker.check_spec            data  -> quality warnings (optional)

generate_markdown() below runs steps 2 to 5 in one call.
"""

from .checker import QualityWarning, check_spec
from .errors import SpecError, SpecFileError
from .loader import load_spec, parse_spec
from .normalizer import normalize_spec
from .openapi import from_openapi, is_openapi, prepare_spec
from .renderer import render_markdown
from .validator import validate_spec


def generate_markdown(raw_spec):
    """Convert (if OpenAPI), validate, normalize and render. Returns Markdown text."""
    spec = prepare_spec(raw_spec)
    validate_spec(spec)
    return render_markdown(normalize_spec(spec))


__all__ = [
    "QualityWarning",
    "SpecError",
    "SpecFileError",
    "check_spec",
    "from_openapi",
    "generate_markdown",
    "is_openapi",
    "load_spec",
    "normalize_spec",
    "parse_spec",
    "prepare_spec",
    "render_markdown",
    "validate_spec",
]
