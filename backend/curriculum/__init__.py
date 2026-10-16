"""Phase-based learning paths.

A path is a sequence of phases; a phase is a small arc of challenges ending in a
capstone checkpoint. Content packs live in ``phases_*.py`` modules inside this
package and are discovered automatically: to add a new path (another language,
an ML track, a data-engineering track, ...) drop in a ``phases_<name>.py`` module
that exports a ``PATH`` dict built with the factories in ``helpers``. Nothing
else needs to change.

Optional module-level attributes:
  - ``ORDER``: int used to sort paths in the UI (lower first, default 100).

Grading is pluggable too: ``grading.RUNNERS`` maps runner names to grading
functions, and ``grading.register_runner`` adds new ones (for example a future
``python_ml`` runner with a pandas/numpy profile).

The server treats each path as a track whose challenges unlock strictly in
order: the next challenge unlocks when the previous one is completed, so a phase
unlocks when the previous phase's checkpoint is cleared.
"""

import importlib
import pkgutil

try:
    from .. import datasets
except ImportError:  # pragma: no cover - top-level module execution
    import datasets  # type: ignore

from .grading import RUNNERS, grade as grade_challenge, register_runner


def _discover_paths() -> dict:
    """Import every ``phases_*`` pack in this package and collect its PATH."""
    discovered = []
    for module_info in pkgutil.iter_modules(__path__):
        if not module_info.name.startswith("phases_"):
            continue
        module = importlib.import_module(f"{__name__}.{module_info.name}")
        path = getattr(module, "PATH", None)
        if path:
            discovered.append((getattr(module, "ORDER", 100), module_info.name, path))
    discovered.sort(key=lambda item: (item[0], item[1]))
    return {path["id"]: path for _, _, path in discovered}


PATHS = _discover_paths()
PATH_TRACK_IDS = set(PATHS)


def public_challenge(challenge: dict) -> dict:
    """Serialize one challenge for the learner (private keys never leave the server)."""
    public = {
        "id": challenge["id"],
        "phase_id": challenge.get("phase_id"),
        "title": challenge["title"],
        "topic": challenge["topic"],
        "difficulty": challenge["difficulty"],
        "xp": challenge["xp"],
        "runner": challenge["runner"],
        "coding": {key: value for key, value in challenge["coding"].items() if not key.startswith("_")},
    }
    for key in (
        "concept",
        "concept_example",
        "capstone",
        "capstone_rubric",
        "business_question",
        "metric_contract",
        "documentation_url",
    ):
        if key in challenge:
            public[key] = challenge[key]
    dataset_spec = challenge.get("dataset")
    if dataset_spec:
        try:
            dataset = datasets.get(dataset_spec["id"])
        except datasets.UnknownDataset:
            dataset = None
        if dataset is not None:
            public["dataset"] = {"id": dataset.id, "name": dataset.name}
            variables = dataset_spec.get("variables")
            if variables:
                sources = []
                for variable, spec in variables.items():
                    if isinstance(spec, str) and ":" in spec:
                        table, column = spec.split(":", 1)
                    else:
                        table, column = spec, None
                    source = {"name": table, "variable": variable, "limit": dataset_spec.get("rows", 200)}
                    if column:
                        source["column"] = column
                    sources.append(source)
                public["data_sources"] = sources
            else:
                public["data_sources"] = [{"name": table} for table in dataset_spec.get("tables", [])]
    return public


def public_path_tracks() -> list[dict]:
    tracks = []
    for path in PATHS.values():
        tracks.append(
            {
                "id": path["id"],
                "kind": "path",
                "curriculum_id": "path",
                "name": path["name"],
                "summary": path["summary"],
                "language": path["language"],
                "phases": [
                    {
                        "id": phase["id"],
                        "name": phase["name"],
                        "arc": phase["arc"],
                        "summary": phase["summary"],
                    }
                    for phase in path["phases"]
                ],
                "challenges": [public_challenge(challenge) for challenge in path["challenges"]],
            }
        )
    return tracks


def phase_offsets(track: dict) -> list[tuple[str, int, int]]:
    """(phase_id, start_index, challenge_count) for a flat path track."""
    offsets = []
    cursor = 0
    for phase in track["phases"]:
        count = len(phase["challenges"])
        offsets.append((phase["id"], cursor, count))
        cursor += count
    return offsets


def datasets_metadata() -> list[dict]:
    return datasets.all_metadata()
