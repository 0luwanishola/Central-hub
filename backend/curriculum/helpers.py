"""Factories that keep phase packs consistent and compact."""

from typing import Optional


def challenge(
    id: str,
    title: str,
    topic: str,
    brief: str,
    starter: str,
    reference: str,
    *,
    hints: list[str],
    success: str,
    plan: Optional[list[str]] = None,
    predict: Optional[dict] = None,
    concept: Optional[str] = None,
    difficulty: str = "beginner",
    xp: int = 15,
    runner: str = "python_guided",
    language: str = "python",
    dataset: Optional[dict] = None,
    checks: Optional[dict] = None,
    mode: Optional[str] = None,
    limits: Optional[dict] = None,
    fixtures: Optional[list[dict]] = None,
    capstone: bool = False,
    capstone_rubric: Optional[list[str]] = None,
) -> dict:
    item = {
        "id": id,
        "title": title,
        "topic": topic,
        "difficulty": difficulty,
        "xp": 40 if capstone else xp,
        "runner": runner,
        "coding": {
            "language": language,
            "task": brief,
            "starter_code": starter,
            "hints": hints,
            "plan": list(plan or []),
            "success": success,
        },
        "checks": dict(checks or {}),
        "reference": reference,
    }
    if concept:
        item["concept"] = concept
    if predict:
        item["predict"] = predict
    if dataset:
        item["dataset"] = dataset
    if mode:
        item["mode"] = mode
    if limits:
        item["limits"] = limits
    if fixtures:
        item["fixtures"] = fixtures
    if capstone:
        item["capstone"] = True
    if capstone_rubric:
        item["capstone_rubric"] = capstone_rubric
    return item


def phase(id: str, name: str, arc: str, summary: str, challenges: list[dict]) -> dict:
    return {"id": id, "name": name, "arc": arc, "summary": summary, "challenges": challenges}


def path(id: str, name: str, summary: str, language: str, phases: list[dict]) -> dict:
    flat: list[dict] = []
    for item in phases:
        for ch in item["challenges"]:
            ch["phase_id"] = item["id"]
            flat.append(ch)
    return {"id": id, "name": name, "summary": summary, "language": language, "phases": phases, "challenges": flat}
