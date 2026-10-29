"""Curriculum structure and reference-solution checks for Code Quest.

Run from ``backend/`` with the project virtualenv:

    .venv/Scripts/python.exe -m unittest discover -s tests -v
"""

import unittest

import curriculum
import learning


class CurriculumStructureTests(unittest.TestCase):
    def test_required_paths_have_stable_languages(self) -> None:
        expected = {
            "python_path": "python",
            "sql_path": "sql",
            "case_files": "mixed",
        }
        for path_id, language in expected.items():
            with self.subTest(path=path_id):
                self.assertIn(path_id, curriculum.PATHS)
                self.assertEqual(curriculum.PATHS[path_id]["language"], language)

    def test_phase_and_challenge_ids_are_unique(self) -> None:
        challenge_ids: set[str] = set()
        for path_id, path in curriculum.PATHS.items():
            phase_ids: set[str] = set()
            for phase in path["phases"]:
                with self.subTest(path=path_id, phase=phase["id"]):
                    self.assertNotIn(phase["id"], phase_ids)
                    phase_ids.add(phase["id"])
            for challenge in path["challenges"]:
                with self.subTest(path=path_id, challenge=challenge["id"]):
                    self.assertNotIn(challenge["id"], challenge_ids)
                    challenge_ids.add(challenge["id"])

    def test_python_stages_follow_the_three_stage_roadmap(self) -> None:
        path = curriculum.PATHS["python_path"]
        stages = [phase.get("stage") for phase in path["phases"]]
        self.assertEqual(
            stages,
            ["Python Foundations"] * 6 + ["Practical Python"] * 3 + ["Python Engineering"] * 5,
        )

    def test_public_path_tracks_expose_stage_but_hide_references(self) -> None:
        tracks = {track["id"]: track for track in curriculum.public_path_tracks()}
        python_track = tracks["python_path"]
        self.assertEqual(python_track["phases"][0]["stage"], "Python Foundations")
        for challenge in python_track["challenges"]:
            self.assertNotIn("reference", challenge)
            self.assertNotIn("checks", challenge)
            self.assertNotIn("fixtures", challenge)

    def test_legacy_tracks_are_tagged_by_language(self) -> None:
        tracks = {track["id"]: track for track in learning._public_tracks()}
        self.assertEqual(tracks["python"]["language"], "python")
        self.assertEqual(tracks["sql"]["language"], "sql")
        self.assertEqual(tracks["case_files"]["language"], "mixed")


class PythonReferenceTests(unittest.TestCase):
    def grade(self, challenge_id: str):
        path = curriculum.PATHS["python_path"]
        challenge = next(item for item in path["challenges"] if item["id"] == challenge_id)
        return curriculum.grade_challenge(challenge, challenge["reference"])

    def test_representative_guided_reference_passes(self) -> None:
        output, correct, feedback, *_ = self.grade("py-01-01")
        self.assertTrue(correct, feedback)
        self.assertEqual(output.strip(), "Hello, coder!")

    def test_new_modules_reference_passes(self) -> None:
        output, correct, feedback, *_ = self.grade("py-07-06")
        self.assertTrue(correct, feedback)
        self.assertEqual(output.splitlines(), ["root: 7.0", "mean: 5.0"])

    def test_new_pathlib_json_reference_passes(self) -> None:
        output, correct, feedback, *_ = self.grade("py-08-06")
        self.assertTrue(correct, feedback)
        self.assertEqual(output.strip(), '{"rows": 60, "source": "reviews.csv"}')


if __name__ == "__main__":
    unittest.main()
