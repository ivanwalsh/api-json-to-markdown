"""Custom error types for the documentation generator.

Having our own error types lets the command line tell the difference
between "your spec has problems" (exit code 1) and "I could not even
open the file" (exit code 2).
"""


class SpecError(Exception):
    """The spec cannot be used: the JSON is broken or validation failed.

    `problems` is a list with one human-readable message per issue, so a
    user can fix everything in one pass instead of one error at a time.
    """

    def __init__(self, problems):
        if isinstance(problems, str):
            problems = [problems]
        self.problems = list(problems)
        super().__init__("\n".join(self.problems))


class SpecFileError(Exception):
    """The spec file could not be read (missing, a folder, no permission)."""
