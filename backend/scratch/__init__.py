"""Learner-owned Scratch workspaces for Code Quest.

Scratch execution reuses the existing Python and SQLite engines, but never
enters challenge grading or learning-progress mutation.
"""

from .errors import ScratchError

__all__ = ["ScratchError"]
