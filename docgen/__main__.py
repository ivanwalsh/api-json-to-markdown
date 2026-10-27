"""Command line entry point (step 5: write the result).

Usage:
    python -m docgen SPEC.json              print Markdown to the screen
    python -m docgen SPEC.json OUTPUT.md    write Markdown to a file

Exit codes:
    0  success
    1  the spec is invalid (broken JSON or failed validation)
    2  the spec file could not be read
"""

import argparse
import sys
from pathlib import Path

from . import generate_markdown, load_spec
from .errors import SpecError, SpecFileError


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m docgen",
        description="Generate Markdown documentation from a JSON API spec.",
    )
    parser.add_argument("spec", help="path to the JSON spec file")
    parser.add_argument(
        "output", nargs="?", help="Markdown file to write (default: print it)"
    )
    args = parser.parse_args(argv)

    try:
        markdown = generate_markdown(load_spec(args.spec))
    except SpecFileError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except SpecError as exc:
        print(f"The spec has {len(exc.problems)} problem(s):", file=sys.stderr)
        for problem in exc.problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    if args.output:
        write_markdown(markdown, args.output)
        print(f"Wrote {args.output}")
    else:
        sys.stdout.write(markdown)
    return 0


def write_markdown(markdown, path):
    """Save Markdown as UTF-8 with "\n" line endings on every operating system."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    sys.exit(main())
