"""End-to-end tests for the Code Quest Scratch workspaces.

Run from ``backend/`` with the project virtualenv:

    .venv/Scripts/python.exe -m unittest discover -s tests -v

These tests exercise the real FastAPI app (lifespan included) against temporary
learning and SQL workspace roots, so they never touch the developer's data.
Challenges remain covered by a small regression check; the bulk of this file
verifies the Scratch contract in ``code-quest-workspaces.md``.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

import learning
import main
import python_runner
import sql_runner
from scratch import limits, sql_workspaces

PYTHON_RUN = "/api/learning/scratch/python/run"
SQL_CREATE = "/api/learning/scratch/sql/workspaces"
SQL_RUN = "/api/learning/scratch/sql/run"
SQL_RESET = "/api/learning/scratch/sql/reset"


class ScratchApiTestCase(unittest.TestCase):
    """Shared app, temporary roots, and learner helpers."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory(prefix="cq_scratch_tests_")
        root = Path(cls._temporary.name)
        cls._original_db_path = learning.DB_PATH
        learning.DB_PATH = root / "learning.sqlite3"
        sql_workspaces.configure_root(root / "sql_scratch")
        cls._client_context = TestClient(main.app)
        cls.client = cls._client_context.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._client_context.__exit__(None, None, None)
        learning.DB_PATH = cls._original_db_path
        cls._temporary.cleanup()

    # -- helpers ---------------------------------------------------------

    def new_learner(self) -> str:
        response = self.client.post("/api/learning/session", json={})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["learner_id"]

    def session_state(self, learner_id: str) -> dict:
        response = self.client.post("/api/learning/session", json={"learner_id": learner_id})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def create_workspace(self, learner_id: str, base: str = "blank") -> dict:
        response = self.client.post(SQL_CREATE, json={"learner_id": learner_id, "base": base})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def run_sql(self, learner_id: str, workspace_id: str, sql: str):
        return self.client.post(SQL_RUN, json={"learner_id": learner_id, "workspace_id": workspace_id, "sql": sql})

    def run_python(self, code: str, **extra):
        body = {"code": code, **extra}
        return self.client.post(PYTHON_RUN, json=body)

    def workspace_object(self, workspace_id: str):
        with sql_workspaces._registry_lock:
            return sql_workspaces._workspaces[workspace_id]

    def expire_workspace(self, workspace_id: str) -> None:
        workspace = self.workspace_object(workspace_id)
        with sql_workspaces._registry_lock:
            workspace.last_used -= limits.SQL_WORKSPACE_TTL_SECONDS + 1


class PythonScratchApiTests(ScratchApiTestCase):
    def test_run_shapes_result_and_returns_text_files(self) -> None:
        response = self.run_python(
            "print('hello scratch')\n"
            "with open('summary.txt', 'w', encoding='utf-8') as handle:\n"
            "    handle.write('kept for this response')\n",
            run_id="client-run-1",
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()

        self.assertEqual(body["run_id"], "client-run-1")
        self.assertEqual(body["status"], "completed")
        self.assertEqual(body["stdout"], "hello scratch\n")
        self.assertEqual(body["stderr"], "")
        self.assertIsNone(body["error"])
        self.assertIsNone(body["error_line"])
        self.assertIsNone(body["error_kind"])
        self.assertFalse(body["timed_out"])
        self.assertFalse(body["truncated"])
        self.assertEqual(len(body["files"]), 1)
        self.assertEqual(body["files"][0]["name"], "summary.txt")
        self.assertEqual(body["files"][0]["content"], "kept for this response")
        self.assertFalse(body["files"][0]["truncated"])
        self.assertEqual(body["files"][0]["size_bytes"], len("kept for this response"))
        self.assertEqual(body["skipped_files"], [])
        self.assertEqual(body["limits"]["timeout_seconds"], limits.PYTHON_TIMEOUT_SECONDS)
        self.assertEqual(body["limits"]["max_source_characters"], limits.PYTHON_MAX_SOURCE)

        for forbidden in ("xp", "progress", "correct", "feedback", "awarded_xp"):
            self.assertNotIn(forbidden, body)

    def test_validation_rejects_invalid_requests(self) -> None:
        cases = {
            "empty code": {"code": ""},
            "whitespace code": {"code": "   \n  "},
            "oversized code": {"code": "x" * (limits.PYTHON_MAX_SOURCE + 1)},
            "oversized run id": {"code": "print(1)", "run_id": "r" * 81},
            "client override": {"code": "print(1)", "timeout": 1},
            "missing code": {},
        }
        for label, body in cases.items():
            with self.subTest(label=label):
                response = self.client.post(PYTHON_RUN, json=body)
                self.assertEqual(response.status_code, 422, response.text)

    def test_diagnostics_distinguish_error_kinds(self) -> None:
        syntax = self.run_python("def broken(:\n    pass").json()
        self.assertEqual(syntax["status"], "error")
        self.assertEqual(syntax["error_kind"], "syntax")
        self.assertEqual(syntax["error_line"], 1)
        self.assertIn("Syntax error", syntax["error"])

        runtime = self.run_python("print('before')\n1 / 0").json()
        self.assertEqual(runtime["status"], "error")
        self.assertEqual(runtime["error_kind"], "runtime")
        self.assertEqual(runtime["error_line"], 2)
        self.assertEqual(runtime["stdout"], "before\n")

        sandbox = self.run_python("import subprocess").json()
        self.assertEqual(sandbox["status"], "error")
        self.assertEqual(sandbox["error_kind"], "sandbox")
        self.assertEqual(sandbox["error_line"], 1)

    def test_output_is_capped_and_flagged(self) -> None:
        body = self.run_python("print('x' * 25_000)").json()
        self.assertEqual(body["status"], "completed")
        self.assertEqual(len(body["stdout"]), limits.PYTHON_MAX_STDOUT)
        self.assertTrue(body["truncated"])

    def test_timeout_is_reported(self) -> None:
        with mock.patch.object(limits, "PYTHON_TIMEOUT_SECONDS", 0.25):
            body = self.run_python("while True:\n    pass").json()
        self.assertEqual(body["status"], "timeout")
        self.assertTrue(body["timed_out"])
        self.assertEqual(body["error_kind"], "timeout")
        self.assertIsNone(body["error_line"])

    def test_artifact_collection_bounds_and_binary_rejection(self) -> None:
        scratch = Path(tempfile.mkdtemp(prefix="cq_files_"))
        try:
            (scratch / "learner.py").write_text("print('seeded')", encoding="utf-8")
            (scratch / "harness.py").write_text("print('seeded')", encoding="utf-8")
            (scratch / "result.json").write_text("{}", encoding="utf-8")
            (scratch / "summary.txt").write_text("hello", encoding="utf-8")
            (scratch / "big.txt").write_text("x" * (limits.PYTHON_MAX_FILE_BYTES + 500), encoding="utf-8")
            (scratch / "binary.bin").write_bytes(b"\x00\x01\x02\x03")
            for index in range(12):
                (scratch / f"f{index:02d}.txt").write_text(str(index), encoding="utf-8")

            files, skipped = python_runner._collect_scratch_files(
                scratch, {"learner.py", "harness.py", "result.json"}
            )
        finally:
            for child in scratch.iterdir():
                child.unlink()
            scratch.rmdir()

        names = [item["name"] for item in files]
        self.assertNotIn("learner.py", names)
        self.assertNotIn("harness.py", names)
        self.assertNotIn("result.json", names)
        self.assertEqual(len(files), limits.PYTHON_MAX_FILES)
        big = next(item for item in files if item["name"] == "big.txt")
        self.assertTrue(big["truncated"])
        self.assertEqual(len(big["content"]), limits.PYTHON_MAX_FILE_BYTES)
        reasons = {item["name"]: item["reason"] for item in skipped}
        self.assertIn("binary.bin", reasons)
        self.assertIn("Only UTF-8 text", reasons["binary.bin"])
        self.assertTrue(any("count limit" in reason for reason in reasons.values()))

    def test_artifact_collection_rejects_long_names_and_symlinks(self) -> None:
        scratch = Path(tempfile.mkdtemp(prefix="cq_files_"))
        outside = scratch.parent / f"{scratch.name}-outside.txt"
        outside.write_text("do not return", encoding="utf-8")
        try:
            long_name = "n" * (limits.PYTHON_MAX_FILENAME + 10) + ".txt"
            (scratch / long_name).write_text("too long", encoding="utf-8")
            try:
                (scratch / "link.txt").symlink_to(outside)
            except OSError:
                linked = False
            else:
                linked = True

            files, skipped = python_runner._collect_scratch_files(scratch, set())
        finally:
            for child in scratch.iterdir():
                if child.is_symlink():
                    child.unlink()
                else:
                    child.unlink()
            scratch.rmdir()
            outside.unlink(missing_ok=True)

        self.assertEqual(files, [])
        reasons = {item["name"]: item["reason"] for item in skipped}
        self.assertTrue(any("too long" in reason for reason in reasons.values()))
        if linked:
            self.assertIn("Not a regular file", reasons.get("link.txt", ""))

    def test_scratch_does_not_mutate_progress(self) -> None:
        learner = self.new_learner()
        before = self.session_state(learner)
        review_before = self.client.post("/api/learning/review", json={"learner_id": learner}).json()

        self.assertEqual(self.run_python("print('nothing graded')").status_code, 200)
        workspace = self.create_workspace(learner)
        run = self.run_sql(learner, workspace["workspace_id"], "CREATE TABLE t(id INTEGER);\nINSERT INTO t VALUES (1);\nSELECT * FROM t;")
        self.assertEqual(run.status_code, 200, run.text)
        self.assertEqual(self.run_sql(learner, workspace["workspace_id"], "SELECT count(*) FROM t;").status_code, 200)
        reset = self.client.post(SQL_RESET, json={"learner_id": learner, "workspace_id": workspace["workspace_id"]})
        self.assertEqual(reset.status_code, 200, reset.text)

        after = self.session_state(learner)
        review_after = self.client.post("/api/learning/review", json={"learner_id": learner}).json()
        self.assertEqual(after["xp"], before["xp"])
        self.assertEqual(after["progress"], before["progress"])
        self.assertEqual(review_after, review_before)


class SqlScratchApiTests(ScratchApiTestCase):
    def test_workspace_lifecycle_and_persistence(self) -> None:
        learner = self.new_learner()
        workspace = self.create_workspace(learner, "blank")
        workspace_id = workspace["workspace_id"]
        self.assertEqual(workspace["base"], "blank")
        self.assertEqual(workspace["idle_ttl_seconds"], limits.SQL_WORKSPACE_TTL_SECONDS)
        self.assertEqual(workspace["limits"]["max_statements"], limits.SQL_MAX_STATEMENTS)

        created = self.run_sql(
            learner,
            workspace_id,
            "CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT NOT NULL);\n"
            "INSERT INTO notes (body) VALUES ('one'), ('two');\n"
            "SELECT id, body FROM notes ORDER BY id;",
        )
        self.assertEqual(created.status_code, 200, created.text)
        body = created.json()
        self.assertEqual(body["status"], "completed")
        self.assertEqual([item["kind"] for item in body["statements"]], ["CREATE TABLE", "INSERT", "SELECT"])
        self.assertEqual(body["statements"][1]["affected_rows"], 2)
        self.assertEqual(body["statements"][2]["rows"], [[1, "one"], [2, "two"]])
        self.assertEqual(body["summary"]["rows"], 2)
        self.assertFalse(body["truncated"])
        self.assertNotIn("xp", body)

        persisted = self.run_sql(learner, workspace_id, "SELECT count(*) AS n FROM notes;").json()
        self.assertEqual(persisted["statements"][0]["rows"], [[2]])

        reset = self.client.post(SQL_RESET, json={"learner_id": learner, "workspace_id": workspace_id})
        self.assertEqual(reset.status_code, 200, reset.text)
        self.assertEqual(reset.json()["base"], "blank")
        after_reset = self.run_sql(learner, workspace_id, "SELECT name FROM sqlite_master WHERE type = 'table';").json()
        self.assertEqual(after_reset["statements"][0]["rows"], [])

        deleted = self.client.delete(
            f"{SQL_CREATE}/{workspace_id}", params={"learner_id": learner}
        )
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertTrue(deleted.json()["deleted"])
        gone = self.run_sql(learner, workspace_id, "SELECT 1;")
        self.assertEqual(gone.status_code, 404, gone.text)

    def test_script_failure_rolls_back_every_statement(self) -> None:
        learner = self.new_learner()
        workspace = self.create_workspace(learner)
        workspace_id = workspace["workspace_id"]

        failed = self.run_sql(
            learner,
            workspace_id,
            "CREATE TABLE keep(x INTEGER);\n"
            "INSERT INTO keep VALUES (1);\n"
            "SELECT * FROM missing_table;",
        )
        self.assertEqual(failed.status_code, 200, failed.text)
        body = failed.json()
        self.assertEqual(body["status"], "error")
        self.assertEqual(body["error_statement"], 2)
        self.assertEqual(body["error_kind"], "sql")
        self.assertIn("missing_table", body["error"])
        self.assertEqual([item["kind"] for item in body["statements"]], ["CREATE TABLE", "INSERT"])
        self.assertEqual(body["workspace"]["base"], "blank")

        self.assertEqual(
            self.run_sql(learner, workspace_id, "SELECT name FROM sqlite_master WHERE name = 'keep';").json()["statements"][0]["rows"],
            [],
        )

    def test_validation_and_authorizer_policy(self) -> None:
        learner = self.new_learner()
        workspace = self.create_workspace(learner)
        workspace_id = workspace["workspace_id"]

        rejected = {
            "empty": "",
            "comments only": "-- nothing here\n/* still nothing */;",
            "too many statements": "SELECT 1;\n" * (limits.SQL_MAX_STATEMENTS + 1),
            "begin": "BEGIN;",
            "commit": "COMMIT;",
            "rollback": "ROLLBACK;",
            "savepoint": "SAVEPOINT one;",
            "pragma": "PRAGMA foreign_keys;",
            "attach": "ATTACH DATABASE 'other.sqlite3' AS other;",
            "vacuum": "VACUUM;",
        }
        for label, sql in rejected.items():
            with self.subTest(label=label):
                response = self.run_sql(learner, workspace_id, sql)
                self.assertEqual(response.status_code, 422, response.text)

        allowed = self.run_sql(learner, workspace_id, "SELECT 1 AS one;\nSELECT 2 AS two;")
        self.assertEqual(allowed.status_code, 200, allowed.text)
        self.assertEqual([item["rows"] for item in allowed.json()["statements"]], [[[1]], [[2]]])

        trigger = self.run_sql(
            learner,
            workspace_id,
            "CREATE TABLE trigger_target(x INTEGER);\n"
            "CREATE TRIGGER guard AFTER INSERT ON trigger_target BEGIN SELECT 1; END;",
        ).json()
        self.assertEqual(trigger["status"], "error")
        self.assertEqual(trigger["error_kind"], "policy")

        temp_table = self.run_sql(learner, workspace_id, "CREATE TEMP TABLE scratch_temp(x);").json()
        self.assertEqual(temp_table["status"], "error")
        self.assertEqual(temp_table["error_kind"], "policy")

        extension = self.run_sql(learner, workspace_id, "SELECT load_extension('anything');").json()
        self.assertEqual(extension["status"], "error")
        self.assertEqual(extension["error_kind"], "policy")

    def test_row_cell_and_response_bounds(self) -> None:
        learner = self.new_learner()
        workspace = self.create_workspace(learner)
        workspace_id = workspace["workspace_id"]

        rows = self.run_sql(
            learner,
            workspace_id,
            "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n WHERE x < 105) SELECT x FROM n;",
        ).json()
        self.assertEqual(len(rows["statements"][0]["rows"]), limits.SQL_MAX_ROWS)
        self.assertTrue(rows["statements"][0]["truncated"])
        self.assertTrue(rows["truncated"])

        cells = self.run_sql(learner, workspace_id, "SELECT hex(zeroblob(2100)) AS big;").json()
        cell = cells["statements"][0]["rows"][0][0]
        self.assertEqual(len(cell), limits.SQL_MAX_CELL_CHARS)
        self.assertTrue(cells["statements"][0]["truncated"])

        with mock.patch.object(limits, "SQL_MAX_RESPONSE_BYTES", 5_000):
            response = self.run_sql(learner, workspace_id, "SELECT hex(zeroblob(3000)) AS big;").json()
        self.assertTrue(response["truncated"])
        self.assertEqual(response["statements"][0]["rows"], [])

    def test_step_and_time_caps_are_enforced(self) -> None:
        learner = self.new_learner()
        workspace = self.create_workspace(learner)
        workspace_id = workspace["workspace_id"]

        with mock.patch.object(limits, "SQL_STEP_CAP", 10_000):
            stepped = self.run_sql(
                learner,
                workspace_id,
                "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n WHERE x < 100000) SELECT count(*) FROM n;",
            ).json()
        self.assertEqual(stepped["status"], "error")
        self.assertEqual(stepped["error_kind"], "step_limit")
        self.assertIn("too much work", stepped["error"])

        with (
            mock.patch.object(limits, "SQL_TIME_CAP_MS", 50),
            mock.patch.object(limits, "SQL_STEP_CAP", 10**12),
        ):
            timed = self.run_sql(
                learner,
                workspace_id,
                "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n WHERE x < 5000000) SELECT count(*) FROM n;",
            ).json()
        self.assertEqual(timed["status"], "timeout")
        self.assertEqual(timed["error_kind"], "timeout")
        self.assertIn("stopped", timed["error"])

    def test_workspace_quota_and_size_precheck(self) -> None:
        learner = self.new_learner()
        workspace = self.create_workspace(learner)
        workspace_id = workspace["workspace_id"]

        with mock.patch.object(limits, "SQL_WORKSPACE_MAX_BYTES", 1024 * 1024):
            quota = self.run_sql(
                learner,
                workspace_id,
                "CREATE TABLE big(payload BLOB);\n"
                "INSERT INTO big VALUES (zeroblob(900000));\n"
                "INSERT INTO big VALUES (zeroblob(900000));",
            ).json()
        self.assertEqual(quota["status"], "error")
        self.assertEqual(quota["error_kind"], "quota")
        self.assertIn("1 MB", quota["error"])

        with mock.patch.object(limits, "SQL_WORKSPACE_MAX_BYTES", 1024):
            precheck = self.run_sql(learner, workspace_id, "SELECT 1;")
        self.assertEqual(precheck.status_code, 409, precheck.text)
        self.assertIn("1 KB", precheck.json()["detail"])

    def test_workspace_cap_per_learner(self) -> None:
        learner = self.new_learner()
        created = [self.create_workspace(learner) for _ in range(limits.SQL_WORKSPACES_PER_LEARNER)]
        blocked = self.client.post(SQL_CREATE, json={"learner_id": learner, "base": "blank"})
        self.assertEqual(blocked.status_code, 409, blocked.text)
        self.assertIn(str(limits.SQL_WORKSPACES_PER_LEARNER), blocked.json()["detail"])

        deleted = self.client.delete(
            f"{SQL_CREATE}/{created[0]['workspace_id']}", params={"learner_id": learner}
        )
        self.assertEqual(deleted.status_code, 200, deleted.text)
        replacement = self.client.post(SQL_CREATE, json={"learner_id": learner, "base": "blank"})
        self.assertEqual(replacement.status_code, 200, replacement.text)

    def test_expiry_blocks_run_and_reset_but_allows_delete(self) -> None:
        learner = self.new_learner()
        workspace = self.create_workspace(learner)
        workspace_id = workspace["workspace_id"]
        self.expire_workspace(workspace_id)

        expired_run = self.run_sql(learner, workspace_id, "SELECT 1;")
        self.assertEqual(expired_run.status_code, 410, expired_run.text)
        expired_reset = self.client.post(SQL_RESET, json={"learner_id": learner, "workspace_id": workspace_id})
        self.assertEqual(expired_reset.status_code, 410, expired_reset.text)
        destroyed = self.client.delete(f"{SQL_CREATE}/{workspace_id}", params={"learner_id": learner})
        self.assertEqual(destroyed.status_code, 200, destroyed.text)

    def test_cleanup_removes_idle_workspaces(self) -> None:
        learner = self.new_learner()
        workspace = self.create_workspace(learner)
        workspace_id = workspace["workspace_id"]
        directory = self.workspace_object(workspace_id).directory
        self.assertTrue(directory.is_dir())

        self.expire_workspace(workspace_id)
        sql_workspaces.cleanup_expired()

        self.assertFalse(directory.exists())
        gone = self.run_sql(learner, workspace_id, "SELECT 1;")
        self.assertEqual(gone.status_code, 404, gone.text)

    def test_ownership_and_unknown_tokens_do_not_leak(self) -> None:
        owner = self.new_learner()
        intruder = self.new_learner()
        workspace = self.create_workspace(owner)
        workspace_id = workspace["workspace_id"]

        self.assertEqual(self.run_sql(intruder, workspace_id, "SELECT 1;").status_code, 404)
        self.assertEqual(
            self.client.post(SQL_RESET, json={"learner_id": intruder, "workspace_id": workspace_id}).status_code,
            404,
        )
        self.assertEqual(
            self.client.delete(f"{SQL_CREATE}/{workspace_id}", params={"learner_id": intruder}).status_code,
            404,
        )
        self.assertEqual(self.run_sql(owner, "z" * 40, "SELECT 1;").status_code, 404)
        self.assertEqual(
            self.client.post(SQL_RUN, json={"learner_id": "not-a-uuid", "workspace_id": workspace_id, "sql": "SELECT 1;"}).status_code,
            404,
        )
        self.assertEqual(self.run_sql(owner, "short", "SELECT 1;").status_code, 422)
        self.assertEqual(
            self.client.post(SQL_CREATE, json={"learner_id": "not-a-uuid", "base": "blank"}).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(SQL_CREATE, json={"learner_id": owner, "base": "not-a-dataset"}).status_code,
            422,
        )
        extra = self.client.post(
            SQL_RUN,
            json={"learner_id": owner, "workspace_id": workspace_id, "sql": "SELECT 1;", "timeout": 5},
        )
        self.assertEqual(extra.status_code, 422, extra.text)

    def test_dataset_base_isolation_and_reset(self) -> None:
        learner = self.new_learner()
        workspace = self.create_workspace(learner, "northwind")
        workspace_id = workspace["workspace_id"]
        self.assertEqual(workspace["base"], "northwind")
        self.assertEqual(workspace["base_name"], "Northwind")

        baseline = self.run_sql(learner, workspace_id, "SELECT count(*) AS n FROM customers;").json()
        customers = baseline["statements"][0]["rows"][0][0]
        self.assertGreater(customers, 0)

        self.run_sql(
            learner,
            workspace_id,
            "CREATE TABLE extra(id INTEGER);\nINSERT INTO extra VALUES (1);\nDELETE FROM customers;",
        )
        modified = self.run_sql(learner, workspace_id, "SELECT count(*) FROM customers;").json()
        self.assertEqual(modified["statements"][0]["rows"], [[0]])
        self.assertEqual(
            self.run_sql(learner, workspace_id, "SELECT count(*) FROM extra;").json()["statements"][0]["rows"],
            [[1]],
        )

        reset = self.client.post(SQL_RESET, json={"learner_id": learner, "workspace_id": workspace_id})
        self.assertEqual(reset.status_code, 200, reset.text)
        restored = self.run_sql(learner, workspace_id, "SELECT count(*) FROM customers;").json()
        self.assertEqual(restored["statements"][0]["rows"], [[customers]])
        missing = self.run_sql(learner, workspace_id, "SELECT * FROM extra;").json()
        self.assertEqual(missing["status"], "error")

        import datasets

        connection = datasets.connect("northwind")
        try:
            registry_customers = connection.execute("SELECT count(*) FROM customers").fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(registry_customers, customers)

    def test_restart_wipes_stale_workspace_files(self) -> None:
        learner = self.new_learner()
        workspace = self.create_workspace(learner)
        workspace_id = workspace["workspace_id"]
        root = sql_workspaces._root()

        sql_workspaces.initialize()

        self.assertEqual(list(root.iterdir()) if root.exists() else [], [])
        stale = self.run_sql(learner, workspace_id, "SELECT 1;")
        self.assertEqual(stale.status_code, 404, stale.text)


class SqlPolicyUnitTests(unittest.TestCase):
    """Statement splitting and policy checks that do not need the app."""

    def test_splitter_uses_sqlite_completeness_and_drops_comment_only_parts(self) -> None:
        source = (
            "SELECT ';' AS semi; -- a comment with ; inside\n"
            "/* a block ; comment */\n"
            "SELECT 2;\n"
            "-- trailing comment only\n"
        )
        statements = sql_runner.validate_workspace_script(source, max_statements=10)
        self.assertEqual(len(statements), 2)
        self.assertTrue(statements[0].startswith("SELECT ';'"))
        self.assertIn("SELECT 2;", statements[1])

    def test_splitter_rejects_incomplete_scripts_and_unknown_starts(self) -> None:
        with self.assertRaises(sql_runner.SqlRunError):
            sql_runner.validate_workspace_script("-- only a comment\n", max_statements=10)
        with self.assertRaises(sql_runner.SqlRunError):
            sql_runner.validate_workspace_script("SELECT 1;\n" * 3, max_statements=2)
        with self.assertRaises(sql_runner.SqlRunError):
            sql_runner.validate_workspace_script("SELECT 1; EXEC not_allowed();", max_statements=10)


class ChallengeRegressionTests(ScratchApiTestCase):
    def test_challenge_preview_still_works(self) -> None:
        learner = self.new_learner()
        session = self.session_state(learner)
        candidate = None
        for track in session["tracks"]:
            for index, challenge in enumerate(track["challenges"]):
                coding = challenge.get("coding") or {}
                if coding.get("language") == "python" and (coding.get("starter_code") or "").strip():
                    candidate = (track["id"], index, coding["starter_code"])
                    break
            if candidate:
                break
        self.assertIsNotNone(candidate, "no Python challenge with starter code found")

        track_id, level, starter = candidate
        response = self.client.post(
            "/api/learning/preview",
            json={"learner_id": learner, "track": track_id, "level": level, "code": starter},
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertIn("correct", body)
        self.assertIn("output", body)
        self.assertTrue(body["preview"])
        self.assertNotIn("xp_awarded", body)


if __name__ == "__main__":
    unittest.main()
