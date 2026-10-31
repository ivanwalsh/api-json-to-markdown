"""Command line entry point (step 5: write the result).

Usage:
    python -m docgen SPEC.json              print Markdown to the screen
    python -m docgen SPEC.json OUTPUT.md    write Markdown to a file
    python -m docgen --check SPEC.json      quality check only, write nothing
    python -m docgen --suggest SPEC.json    ask an AI to draft missing descriptions
    python -m docgen --apply-suggestions SPEC.json
                                            write the drafts you accepted into the spec

Exit codes:
    0  success (warnings during normal generation do not change this)
    1  the spec is invalid (broken JSON or failed validation)
    2  the spec file could not be read, or the AI service could not be used
    3  --check found quality warnings

Where messages go: Markdown printed to the screen goes to "standard
output"; errors and warnings during generation go to "standard error",
so they never end up mixed into a Markdown file. In --check mode the
warnings are the whole report, so they go to standard output.
"""

import argparse
import json
import sys
from pathlib import Path

from .checker import check_spec
from . import jsonwriter, suggest
from .errors import ServiceError, SpecError, SpecFileError
from .loader import load_spec, parse_spec
from .normalizer import normalize_spec
from .openapi import is_openapi, prepare_spec
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
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="run the quality check only and write nothing",
    )
    mode.add_argument(
        "--suggest",
        action="store_true",
        help="ask an AI to draft missing descriptions into a review file",
    )
    mode.add_argument(
        "--apply-suggestions",
        action="store_true",
        help="write the accepted drafts from the review file into the spec",
    )
    args = parser.parse_args(argv)

    if args.check and args.output:
        parser.error("--check does not write files, so leave out OUTPUT")
    for flag, used in (("--suggest", args.suggest), ("--apply-suggestions", args.apply_suggestions)):
        if used and args.output:
            parser.error(f"{flag} does not write Markdown, so leave out OUTPUT")

    if args.suggest or args.apply_suggestions:
        return run_suggestions(args)

    try:
        raw = prepare_spec(load_spec(args.spec))  # converts OpenAPI if needed
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


def run_suggestions(args):
    """Handle --suggest and --apply-suggestions."""
    spec_path = Path(args.spec)
    review = suggest.review_path(spec_path)
    try:
        raw = load_spec(spec_path)
        if spec_path.suffix.lower() != ".json" or is_openapi(raw):
            raise SpecFileError(
                "AI suggestions only work on docgen's own JSON format for now, "
                "not on OpenAPI or YAML files."
            )
        validate_spec(raw)

        if args.suggest:
            return _suggest(raw, spec_path, review)
        return _apply(raw, spec_path, review)
    except (SpecFileError, ServiceError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_FILE_ERROR
    except SpecError as exc:
        print(f"The spec has {len(exc.problems)} problem(s):", file=sys.stderr)
        for problem in exc.problems:
            print(f"  - {problem}", file=sys.stderr)
        return EXIT_INVALID_SPEC


def _suggest(raw, spec_path, review):
    if not suggest.find_gaps(raw):
        print("No missing descriptions. Nothing to suggest.")
        return EXIT_OK
    if review.exists():
        raise SpecFileError(
            f"{review} already exists. Apply it with --apply-suggestions, "
            "or delete it, before asking for new suggestions."
        )

    print(suggest.PRIVACY_NOTE, file=sys.stderr)
    entries = suggest.suggest(
        raw,
        ask=suggest.ask_claude,
        on_progress=lambda where: print(f"  drafting {where}", file=sys.stderr),
    )
    # One field per line, so the review file is easy to read and edit by hand.
    review.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")

    print(f"Wrote {len(entries)} suggestion(s) to {review}")
    print('Open it, set "accepted": true on the ones you want (edit the wording if you like), then run:')
    print(f"  python3 -m docgen --apply-suggestions {spec_path}")
    return EXIT_OK


def _apply(raw, spec_path, review):
    if not review.exists():
        raise SpecFileError(f"No review file found. Run --suggest first to create {review}")
    try:
        entries = parse_spec(review.read_text(encoding="utf-8"))
        applied, skipped = suggest.apply_suggestions(raw, entries)
    except (SpecError, ValueError) as exc:
        raise SpecFileError(f"{review} could not be used: {exc}") from None

    for message in skipped:
        print(f"  skipped {message}", file=sys.stderr)
    if not applied:
        print("No accepted suggestions to apply. Nothing changed.")
        return EXIT_OK

    validate_spec(raw)  # never write a spec the tool itself would reject
    spec_path.write_text(jsonwriter.dumps(raw), encoding="utf-8", newline="\n")
    review.unlink()

    for message in applied:
        print(f"  applied {message}")
    print(f"Updated {spec_path} with {len(applied)} description(s). Review the change with: git diff {spec_path}")
    return EXIT_OK


def write_markdown(markdown, path):
    """Save Markdown as UTF-8 with "\n" line endings on every operating system."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    sys.exit(main())
