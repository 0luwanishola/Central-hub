"""Grading for phase-based challenges.

The public entry point is :func:`grade`, which returns a 7-tuple shaped like
``learning._run_challenge_code``:

``(output, correct, feedback, sql_columns, sql_rows, error_line, error_column)``

Every runner is graded against a private reference solution executed live on the
same data, never against copied expected text, which keeps datasets rotatable
and makes hardcoding useless.

Runners register by name through :func:`register_runner`, so new profiles (a
future ``python_ml`` with pandas/numpy, a browser runner, ...) plug in without
touching the engine.
"""

import ast
import re
from collections import Counter
from copy import deepcopy
from decimal import Decimal
from typing import Optional

try:
    from .. import datasets, guided_python, python_runner, sql_runner
except ImportError:  # pragma: no cover - backend modules can run as top-level modules
    import datasets
    import guided_python
    import python_runner
    import sql_runner


def _result(output="", correct=False, feedback="", sql_columns=None, sql_rows=None, error_line=None, error_column=None):
    return (output, correct, feedback, sql_columns, sql_rows, error_line, error_column)


def _normalize_text(text: str) -> str:
    return "\n".join(line.rstrip() for line in (text or "").splitlines()).strip()


def _normalize_value(value):
    if isinstance(value, float):
        return round(value, 6)
    return value


def _normalize_sql(source: str) -> str:
    without_block = re.sub(r"/\*.*?\*/", " ", source, flags=re.S)
    without_line = re.sub(r"--[^\n]*", " ", without_block)
    return re.sub(r"\s+", " ", without_line).strip().upper()


_SQL_FEATURES = {
    "join": r"\bJOIN\b",
    "left_join": r"\bLEFT\s+(?:OUTER\s+)?JOIN\b",
    "group": r"\bGROUP\s+BY\b",
    "having": r"\bHAVING\b",
    "cte": r"\bWITH\b",
    "recursive": r"\bWITH\s+RECURSIVE\b",
    "window": r"\bOVER\s*\(",
    "case": r"\bCASE\b",
    "subquery": r"\(\s*SELECT\b",
    "order": r"\bORDER\s+BY\b",
    "distinct": r"\bDISTINCT\b",
    "exists": r"\bEXISTS\s*\(",
    "union": r"\bUNION\b",
    "cast": r"\bCAST\s*\(",
    "coalesce": r"\bCOALESCE\s*\(",
    "like": r"\bLIKE\b",
    "between": r"\bBETWEEN\b",
    "is_null": r"\bIS\s+(?:NOT\s+)?NULL\b",
    "default": r"\bDEFAULT\b",
    "limit": r"\bLIMIT\b",
    "in": r"\bIN\s*\(",
    "index": r"\bCREATE\s+(?:UNIQUE\s+)?INDEX\b",
    "references": r"\bREFERENCES\b",
    "check": r"\bCHECK\s*\(",
    "not_null": r"NOT\s+NULL",
    "unique": r"\bUNIQUE\b",
    "primary_key": r"PRIMARY\s+KEY",
    "strftime": r"\bSTRFTIME\s*\(",
    "julianday": r"\bJULIANDAY\s*\(",
    "explain": r"\bEXPLAIN\b",
    "insert": r"\bINSERT\b",
    "update": r"\bUPDATE\b",
    "delete": r"\bDELETE\b",
    "create_table": r"\bCREATE\s+TABLE\b",
    "alter": r"\bALTER\s+TABLE\b",
    "drop": r"\bDROP\s+TABLE\b",
    "json": r"\bJSON_[A-Z_]*\s*\(",
    "json_arrow": r"->>?",
    "collate": r"\bCOLLATE\b",
    "where": r"\bWHERE\b",
    "substr": r"\bSUBSTR\s*\(",
    "trim": r"\bTRIM\s*\(",
    "upper": r"\bUPPER\s*\(",
    "replace": r"\bREPLACE\s*\(",
}

_PY_FEATURES = {
    "for": (ast.For,),
    "while": (ast.While,),
    "if": (ast.If,),
    "function": (ast.FunctionDef,),
    "comprehension": (ast.ListComp, ast.DictComp, ast.SetComp),
    "dict": (ast.Dict,),
    "set": (ast.Set,),
    "fstring": (ast.JoinedStr,),
    "slice": (ast.Slice,),
    "try": (ast.Try,),
    "raise": (ast.Raise,),
    "assert": (ast.Assert,),
    "break": (ast.Break,),
    "continue": (ast.Continue,),
    "tuple": (ast.Tuple,),
}


def _sql_has_feature(normalized: str, feature: str) -> bool:
    pattern = _SQL_FEATURES.get(feature)
    if pattern is None:
        return True
    return re.search(pattern, normalized) is not None


def _py_has_feature(tree: ast.AST, feature: str) -> bool:
    if feature in {"and", "or"}:
        wanted = ast.And if feature == "and" else ast.Or
        return any(isinstance(node, ast.BoolOp) and isinstance(node.op, wanted) for node in ast.walk(tree))
    if feature == "if":
        if any(isinstance(node, ast.If) for node in ast.walk(tree)):
            return True
        # A comprehension filter (`... for x in data if test`) is also a condition.
        return any(isinstance(node, ast.comprehension) and node.ifs for node in ast.walk(tree))
    if feature.startswith("method:"):
        method = feature.split(":", 1)[1]
        return any(
            isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == method
            for node in ast.walk(tree)
        )
    if feature.startswith("call:"):
        name = feature.split(":", 1)[1]
        return any(
            isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == name
            for node in ast.walk(tree)
        )
    node_types = _PY_FEATURES.get(feature)
    if node_types is None:
        return True
    return any(isinstance(node, node_types) for node in ast.walk(tree))


def _readable(feature: str) -> str:
    return feature.split(":", 1)[1].replace("_", " ") if ":" in feature else feature.replace("_", " ")


def _missing_feature_message(challenge: dict, feature: str) -> str:
    overrides = challenge.get("checks", {}).get("messages", {})
    if feature in overrides:
        return overrides[feature]
    return f"This task wants you to use {_readable(feature)}. Try that in your solution."


def _sql_limits(challenge: dict) -> dict:
    limits = challenge.get("limits", {})
    return {
        "row_cap": limits.get("rows", 100),
        "step_cap": limits.get("steps", 2_000_000),
        "time_cap_ms": limits.get("time_ms", 1_500),
    }


# --------------------------------------------------------------------------- sqlite


def _grade_sqlite(challenge: dict, source: str):
    checks = challenge.get("checks", {})
    mode = challenge.get("mode", sql_runner.READONLY)
    dataset_spec = challenge.get("dataset", {})
    dataset_id = dataset_spec.get("id")
    size = dataset_spec.get("size", "small")
    limits = _sql_limits(challenge)

    normalized = _normalize_sql(source)
    for feature in checks.get("required", []):
        if not _sql_has_feature(normalized, feature):
            return _result(feedback=_missing_feature_message(challenge, feature))
    for feature in checks.get("forbidden", []):
        if _sql_has_feature(normalized, feature):
            message = checks.get("messages", {}).get(feature)
            return _result(feedback=message or f"This task does not need {_readable(feature)} in the solution.")

    try:
        connection = datasets.connect(dataset_id, size)
    except datasets.UnknownDataset:
        return _result(feedback="This challenge points at a dataset that no longer exists.")

    if mode == sql_runner.SCRATCH:
        # Constraint lessons rely on foreign keys actually being enforced.
        connection.execute("PRAGMA foreign_keys = ON")

    try:
        try:
            outcome = sql_runner.execute(connection, source, mode=mode, **limits)
        except sql_runner.SqlRunError as exc:
            return _result(feedback=exc.message)

        final_checks = checks.get("final", [])
        if final_checks:
            for evaluation in sql_runner.run_check_queries(connection, final_checks):
                if not evaluation["passed"]:
                    message = evaluation["entry"].get("message", "The database state is not quite right yet.")
                    return _result(feedback=message)

        learner_result = outcome.result

        reference_connection = datasets.connect(dataset_id, size)
        if mode == sql_runner.SCRATCH:
            reference_connection.execute("PRAGMA foreign_keys = ON")
        try:
            reference_outcome = sql_runner.execute(
                reference_connection,
                challenge["reference"],
                mode=mode,
                row_cap=max(limits["row_cap"], 500),
                step_cap=max(limits["step_cap"], 500_000),
                time_cap_ms=max(limits["time_cap_ms"], 3_000),
            )
        except sql_runner.SqlRunError:
            return _result(feedback="This challenge has a configuration problem. Please report it.")
        reference_result = reference_outcome.result

        if reference_result is not None and reference_result.columns:
            if learner_result is None or not learner_result.columns:
                return _result(feedback="This task expects a query that returns rows.")
            mismatched = _compare_sql_results(learner_result, reference_result, ordered=checks.get("ordered", False))
            if mismatched:
                return _result(
                    output=_render_sql_preview(learner_result),
                    sql_columns=learner_result.columns,
                    sql_rows=learner_result.rows,
                    feedback=mismatched,
                )

        output = _render_sql_preview(learner_result)
        return _result(
            output=output,
            correct=True,
            sql_columns=learner_result.columns if learner_result else None,
            sql_rows=learner_result.rows if learner_result else None,
            feedback=challenge["coding"].get("success", "Nice work!"),
        )
    finally:
        try:
            connection.close()
        except Exception:
            pass


def _render_sql_preview(result) -> str:
    if result is None or not result.columns:
        return ""
    lines = [" | ".join(str(column) for column in result.columns)]
    for row in result.rows[:20]:
        lines.append(" | ".join("NULL" if value is None else str(value) for value in row))
    return "\n".join(lines)


def _compare_sql_results(learner, reference, *, ordered: bool) -> Optional[str]:
    learner_columns = [str(column).lower() for column in learner.columns]
    reference_columns = [str(column).lower() for column in reference.columns]
    if learner_columns != reference_columns:
        expected = ", ".join(str(column) for column in reference.columns)
        return f"The result columns don't match yet. This task expects columns: {expected}."
    if len(learner.rows) != len(reference.rows):
        return f"This task expects {len(reference.rows)} row(s); your query returned {len(learner.rows)}."
    learner_rows = [[_normalize_value(value) for value in row] for row in learner.rows]
    reference_rows = [[_normalize_value(value) for value in row] for row in reference.rows]
    if ordered:
        for index, (got, expected) in enumerate(zip(learner_rows, reference_rows), start=1):
            if got != expected:
                return f"Row {index} doesn't match yet. Check the filters and the requested sort order."
        return None
    got_counts = Counter(tuple(row) for row in learner_rows)
    expected_counts = Counter(tuple(row) for row in reference_rows)
    if got_counts != expected_counts:
        return "The rows are close, but some values don't match the task yet."
    return None


# --------------------------------------------------------------------------- guided python


def _guided_environment(dataset_spec: dict) -> Optional[dict]:
    """Build interpreter variables from a dataset spec.

    ``variables`` maps a variable name to either ``"table"`` (rows as dicts) or
    ``"table:Column"`` (a flat list of that column's values).
    """
    variables = dataset_spec.get("variables", {})
    parsed = []
    base_tables = []
    for variable, spec in variables.items():
        if isinstance(spec, str) and ":" in spec:
            table, column = spec.split(":", 1)
        else:
            table, column = spec, None
        parsed.append((variable, table, column))
        base_tables.append(table)
    try:
        data = datasets.table_rows(
            dataset_spec["id"],
            list(dict.fromkeys(base_tables)),
            dataset_spec.get("size", "small"),
            dataset_spec.get("rows", 200),
        )
    except datasets.UnknownDataset:
        return None
    environment: dict = {}
    for variable, table, column in parsed:
        rows = data.get(table, [])
        environment[variable] = [row[column] for row in rows] if column else rows
    for key, value in dataset_spec.get("constants", {}).items():
        environment[key] = value
    return environment


def _reduced_environment(environment: dict) -> Optional[dict]:
    lists = [value for value in environment.values() if isinstance(value, list)]
    if not lists or any(len(value) < 6 for value in lists):
        return None
    return {name: value[: max(1, len(value) // 2)] if isinstance(value, list) else value for name, value in environment.items()}


def _grade_guided(challenge: dict, source: str):
    checks = challenge.get("checks", {})
    dataset_spec = challenge.get("dataset")
    environment: dict = {}
    if dataset_spec:
        built = _guided_environment(dataset_spec)
        if built is None:
            return _result(feedback="This challenge points at a dataset that no longer exists.")
        environment = deepcopy(built)

    max_steps = checks.get("steps", 30_000)
    try:
        output = guided_python.run(source, environment, max_steps=max_steps)
    except guided_python.GuidedError as exc:
        return _result(output="", feedback=exc.message, error_line=exc.line, error_column=exc.column)

    if checks.get("required"):
        try:
            tree = ast.parse(source)
        except SyntaxError:
            tree = None
        if tree is not None:
            for feature in checks["required"]:
                if not _py_has_feature(tree, feature):
                    return _result(output=output, feedback=_missing_feature_message(challenge, feature))

    try:
        expected = guided_python.run(challenge["reference"], deepcopy(environment), max_steps=max_steps)
    except guided_python.GuidedError:
        return _result(output=output, feedback="This challenge has a configuration problem. Please report it.")

    if _normalize_text(output) != _normalize_text(expected):
        if len(_normalize_text(output).splitlines()) != len(_normalize_text(expected).splitlines()):
            return _result(
                output=output,
                feedback="Almost! The number of output lines doesn't match the task yet. Check your loop or print statements.",
            )
        return _result(
            output=output,
            feedback="Your program ran, but the output doesn't match the task yet. Compare it line by line with what the task asks for.",
        )

    if checks.get("reduce_data", True) and environment:
        reduced = _reduced_environment(environment)
        if reduced:
            try:
                learner_reduced = guided_python.run(source, deepcopy(reduced), max_steps=max_steps)
                reference_reduced = guided_python.run(challenge["reference"], deepcopy(reduced), max_steps=max_steps)
            except guided_python.GuidedError:
                learner_reduced = reference_reduced = None
            if learner_reduced is not None and reference_reduced is not None and _normalize_text(learner_reduced) != _normalize_text(reference_reduced):
                return _result(
                    output=output,
                    feedback="That works on the sample shown, but not on a different sample. Compute the answer from the data instead of printing a fixed result.",
                )

    return _result(output=output, correct=True, feedback=challenge["coding"].get("success", "Nice work!"))


# --------------------------------------------------------------------------- real python


def _grade_real(challenge: dict, source: str):
    checks = challenge.get("checks", {})
    timeout = checks.get("timeout_s", challenge.get("timeout_s", 8))
    dataset_spec = challenge.get("dataset")
    fixtures = challenge.get("fixtures")

    try:
        learner = python_runner.run_python(source, timeout_s=timeout, dataset=dataset_spec, fixtures=fixtures)
    except python_runner.PythonRunError as exc:
        return _result(feedback=exc.message, error_line=exc.line)

    output = learner["output"]
    if learner["timed_out"]:
        return _result(output=output, feedback=learner["error"] or "This program ran too long and was stopped.")
    if learner["error"]:
        return _result(output=output, feedback=f"Your program stopped with an error: {learner['error']}", error_line=learner["error_line"])

    if checks.get("required"):
        try:
            tree = ast.parse(source)
        except SyntaxError:
            tree = None
        if tree is not None:
            for feature in checks["required"]:
                if not _py_has_feature(tree, feature):
                    return _result(output=output, feedback=_missing_feature_message(challenge, feature))

    try:
        reference = python_runner.run_python(challenge["reference"], timeout_s=timeout, dataset=dataset_spec, fixtures=fixtures)
    except python_runner.PythonRunError:
        return _result(output=output, feedback="This challenge has a configuration problem. Please report it.")
    if reference["error"]:
        return _result(output=output, feedback="This challenge has a configuration problem. Please report it.")

    if _normalize_text(output) != _normalize_text(reference["output"]):
        return _result(
            output=output,
            feedback="Your program ran, but the output doesn't match the task yet. Compare it line by line with what the task asks for.",
        )

    for file_name in checks.get("files", []):
        learner_file = learner["files"].get(file_name)
        if learner_file is None:
            return _result(output=output, feedback=f"The task asks for a file named {file_name}, but it wasn't created.")
        expected_file = reference["files"].get(file_name)
        if _normalize_text(learner_file) != _normalize_text(expected_file):
            return _result(output=output, feedback=f"{file_name} was created, but its content doesn't match the task yet.")

    return _result(output=output, correct=True, feedback=challenge["coding"].get("success", "Nice work!"))


# --------------------------------------------------------------------------- registry


RUNNERS: dict = {}


def register_runner(name: str, grading_function) -> None:
    RUNNERS[name] = grading_function


register_runner("sqlite", _grade_sqlite)
register_runner("python_guided", _grade_guided)
register_runner("python_real", _grade_real)


def grade(challenge: dict, source: str):
    runner = RUNNERS.get(challenge.get("runner"))
    if runner is None:
        return _result(feedback="This challenge has an unknown runner configured.")
    return runner(challenge, source)
