# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Require English documentation entry points throughout maintained Python code.

Run ``python tools/check_code_docs.py`` from any working directory. This checks
presence, not accuracy or language: reviewers must assess explanations, examples
and scientific reasoning using CONTRIBUTING.md and the code guide.
"""

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CODE_DIRECTORIES = ("src", "tests", "benchmarks", "tools")
DocumentedNode = ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef


def is_overload(node: DocumentedNode) -> bool:
    """Identify typing overload declarations whose implementation holds the docs.

    Overload stubs describe alternate signatures, not executable behavior.
    Support both imported overload and qualified typing.overload decorators.
    """
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    return any(
        (isinstance(item, ast.Name) and item.id == "overload")
        or (isinstance(item, ast.Attribute) and item.attr == "overload")
        for item in node.decorator_list
    )


def missing_docs(path: Path) -> list[str]:
    """Return location-labelled missing docstrings for a UTF-8 Python file.

    Include nested callbacks, fixtures and private helpers: future maintainers
    need their intent as much as public API intent. Empty strings do not count.
    Syntax errors propagate so invalid source cannot pass this check.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    failures: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue
        if is_overload(node):
            continue
        documentation = ast.get_docstring(node)
        if not documentation or not documentation.strip():
            line = getattr(node, "lineno", 1)
            name = getattr(node, "name", "<module>")
            failures.append(
                f"{path.relative_to(PROJECT_ROOT)}:{line}: missing docstring: {name}"
            )
    return failures


def main() -> int:
    """Check maintained code and return a nonzero status for missing explanations.

    CI and pre-commit invoke this entry point. Generated files, virtual
    environments and private caches lie outside the four checked directories.
    """
    failures: list[str] = []
    files = 0
    for directory in CODE_DIRECTORIES:
        for path in sorted((PROJECT_ROOT / directory).rglob("*.py")):
            failures.extend(missing_docs(path))
            files += 1
    if failures:
        print("\n".join(failures))
        return 1
    print(f"Documentation presence checked in {files} Python files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
