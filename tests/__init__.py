"""Tests for docgen. Run them all from the project folder with:

    python -m unittest -v
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = PROJECT_ROOT / "tests" / "fixtures"
EXPECTED = PROJECT_ROOT / "tests" / "expected"
EXAMPLE_SPEC = PROJECT_ROOT / "examples" / "library_api.json"
