"""Command line entry point (step 5: write the result).

Usage:
    python -m docgen SPEC.json              print Markdown to the screen
    python -m docgen SPEC.json OUTPUT.md    write Markdown to a file
    python -m docgen --check SPEC.json      quality check only, write nothing

Exit codes:
    0  success (warnings during normal generation do not change this)
    1  the spec is invalid (broken JSON or failed validation)
    2  the spec file could not be read
    3  --check found quality warnings

Where messages go: Markdown printed to the screen goes to "standard
output"; errors and warnings during generation go to "standard error",
so they never end up mixed into a Markdown file. In --check mode the
warnings are the whole report, so they go to standard output.
"""

import argparse
import sys
from pathlib import Path

from .checker import check_spec
from .errors import SpecError, SpecFileError
from .loader import load_spec
from .normalizer import normalize_spec
from .renderer import render_markdown
from .validator import validate_spec

EXIT_OK = 0
EXIT_INVALID_SPEC = 1
EXIT_FILE_ERROR = 2
EXIT_WARNINGS = 3


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m docgen",
        description="Generate Markdown documentation from a JSON API spec.",
    )
    parser.add_argument("spec", help="path to the JSON spec file")
    parser.add_argument(
        "output", nargs="?", help="Markdown file to write (default: print it)"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="run the quality check only and write nothing",
    )
    args = parser.parse_args(argv)

    if args.check and args.output:
        parser.error("--check does not write files, so leave out OUTPUT")

    try:
        raw = load_spec(args.spec)
        validate_spec(raw)
    except SpecFileError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_FILE_ERROR
    except SpecError as exc:
        print(f"The spec has {len(exc.problems)} problem(s):", file=sys.stderr)
        for problem in exc.problems:
            print(f"  - {problem}", file=sys.stderr)
        return EXIT_INVALID_SPEC

    spec = normalize_spec(raw)
    warnings = check_spec(spec)

    if args.check:
        for warning in warnings:
            print(f"  - {warning}")
        if warnings:
            print(f"{len(warnings)} warning(s)")
            return EXIT_WARNINGS
        print("No warnings")
        return EXIT_OK

    markdown = render_markdown(spec)
    if args.output:
        write_markdown(markdown, args.output)
        print(f"Wrote {args.output}")
    else:
        sys.stdout.write(markdown)

    if warnings:
        print(f"{len(warnings)} quality warning(s):", file=sys.stderr)
        for warning in warnings:
            print(f"  - {warning}", file=sys.stderr)
    return EXIT_OK


def write_markdown(markdown, path):
    """Save Markdown as UTF-8 with "\n" line endings on every operating system."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    sys.exit(main())
