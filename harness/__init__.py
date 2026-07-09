"""A minimal, reusable agent harness.

No project-specific imports live in this package — wire your own system
prompt and tools in from outside. Built in five working checkpoints; see
the git history ("harness level N" commits).
"""

from .agent import DEFAULT_MODEL, Agent, Tool
from .skills import Skill, discover_skills, load_skill, parse_skill

__all__ = [
    "Agent",
    "DEFAULT_MODEL",
    "Tool",
    "Skill",
    "discover_skills",
    "load_skill",
    "parse_skill",
]
