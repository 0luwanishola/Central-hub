"""Targeted notes for common mistakes in failed submissions.

The detectors are deliberately conservative: each one fires only on patterns
that are almost always a real problem for the tasks in this app, so learners
can trust the notes instead of learning to ignore them. Notes are plain
sentences — they never include code from the reference solution.

``coach_notes`` is called by the learning engine after a submission fails; the
frontend shows the notes under the normal feedback message.
"""

from __future__ import annotations

import ast
import re
from typing import Optional

_SQL_NULL_COMPARE = re.compile(r"(?<![<>!=])=[ \t]*NULL\b|!=[ \t]*NULL\b|<>[ \t]*NULL\b", re.IGNORECASE)
_SQL_HAVING = re.compile(r"\bHAVING\b", re.IGNORECASE)
_SQL_GROUP_BY = re.compile(r"\bGROUP\s+BY\b", re.IGNORECASE)
_SQL_SELECT_STAR = re.compile(r"\bSELECT\s+\*", re.IGNORECASE)


def _sql_notes(query: str) -> list[str]:
    notes: list[str] = []
    if _SQL_NULL_COMPARE.search(query):
        notes.append("= NULL and != NULL never match any row in SQL — use IS NULL or IS NOT NULL.")
    if _SQL_HAVING.search(query) and not _SQL_GROUP_BY.search(query):
        notes.append("HAVING filters grouped results, so it needs a GROUP BY first (use WHERE for plain row filters).")
    if _SQL_SELECT_STAR.search(query):
        notes.append("The checker compares columns exactly — if the task names specific columns, replace SELECT * with that list in order.")
    return notes


def _python_notes(code: str, reference: Optional[str]) -> list[str]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []  # the runner already reports syntax errors with a line number

    notes: list[str] = []

    none_compare = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        for op, comparator in zip(node.ops, node.comparators):
            if isinstance(op, (ast.Eq, ast.NotEq)) and isinstance(comparator, ast.Constant) and comparator.value is None:
                none_compare = True
    if none_compare:
        notes.append("Check for None with `is None` / `is not None` — `== None` is a common source of quiet bugs.")

    if reference and "return" in reference:
        has_return = any(isinstance(node, ast.Return) for node in ast.walk(tree))
        print_only_function = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            prints = any(
                isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name) and inner.func.id == "print"
                for inner in ast.walk(node)
            )
            returns = any(isinstance(inner, ast.Return) for inner in ast.walk(node))
            if prints and not returns:
                print_only_function = True
        if print_only_function and not has_return:
            notes.append("This task expects a value back — printing inside a function doesn't return anything. Finish the function with return.")
    return notes


def coach_notes(
    language: str,
    code: str,
    *,
    starter: Optional[str] = None,
    reference: Optional[str] = None,
) -> list[str]:
    """Return targeted notes for a failed submission (empty when nothing fires)."""
    if starter is not None and code.strip() == starter.strip():
        return ["This is still the starter code — write your solution before checking."]

    if language == "sql":
        notes = _sql_notes(code)
    elif language == "python":
        notes = _python_notes(code, reference)
    else:
        notes = []

    unique: list[str] = []
    for note in notes:
        if note not in unique:
            unique.append(note)
    return unique
