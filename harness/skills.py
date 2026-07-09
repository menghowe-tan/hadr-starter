"""Skills — reusable capabilities the agent can invoke, discovered from disk.

A *skill* is a folder with a ``SKILL.md``: some front-matter (name,
description, which model, which tools it may use) and a body of standing
orders for that one job. The harness discovers them, advertises each to the
model as a tool (progressive disclosure — the model sees only name and
description until it invokes one), and runs an invoked skill as a nested
agent turn scoped to that skill's instructions and tools.

Nothing here is project-specific: point ``discover_skills`` at any folder of
``SKILL.md`` files and the same generic runner in ``harness/agent.py`` runs
them. A project adds a capability by dropping in a folder, never by editing
the harness.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Anthropic server tools a skill may name in its front-matter ``tools:`` list.
# These resolve server-side (the API runs them, we never see a local call), so
# the harness only has to hand the API the right param. A skill names one the
# same way it names a local tool; the runner in agent.py splits them apart.
#
# Empty by default: server tools require a live ``ANTHROPIC_API_KEY`` (and its
# billing), so nothing is wired here. A project that wants server-side
# execution and has a key can register one, e.g.:
#     SERVER_TOOLS["web_search"] = {"type": "web_search_20250305",
#                                   "name": "web_search", "max_uses": 5}
# This repo instead ships a keyless local ``web_search`` tool
# (``agent/tools.py``), so a skill's ``tools: web_search`` resolves to that and
# needs no key.
SERVER_TOOLS: dict[str, dict] = {}

# A tool name the model can call must match this (Anthropic's constraint too).
_TOOL_NAME = re.compile(r"[^a-zA-Z0-9_-]+")


@dataclass(frozen=True)
class Skill:
    """One discovered capability: front-matter plus the SKILL.md body."""

    name: str
    description: str
    instructions: str
    model: str | None = None
    tools: tuple[str, ...] = ()
    path: Path | None = None

    @property
    def tool_name(self) -> str:
        """A safe tool name to advertise this skill under."""
        return _TOOL_NAME.sub("_", self.name).strip("_") or "skill"


def _parse_front_matter(text: str) -> tuple[dict, str]:
    """Split a leading ``---`` front-matter block from the body.

    A deliberately small parser — no YAML dependency. It reads ``key: value``
    lines (skipping blanks and ``#`` comments), strips matching quotes, and
    understands the one shape a skill needs beyond scalars: an inline list,
    ``tools: [a, b]`` or ``tools: a, b``. Keys it doesn't recognise are
    ignored, so a richer YAML front-matter (as some installed skills carry)
    still parses for the fields we use.
    """
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return {}, text
    meta: dict = {}
    for line in lines[1:end]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        meta[key.strip()] = _coerce(value.strip())
    body = "\n".join(lines[end + 1 :]).strip()
    return meta, body


def _coerce(value: str):
    value = value.strip()
    if value[:1] in "\"'" and value[-1:] == value[:1] and len(value) >= 2:
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    if "," in value:
        return [part.strip().strip("\"'") for part in value.split(",") if part.strip()]
    return value


def parse_skill(text: str, *, path: Path | None = None, fallback_name: str = "") -> Skill:
    """Build a :class:`Skill` from ``SKILL.md`` text.

    Front-matter supplies ``name``/``description``/``model``/``tools``. When
    absent, the name falls back to the folder name and the description to the
    first non-blank body line (the ``# heading`` or first sentence), so a
    bare SKILL.md still loads.
    """
    meta, body = _parse_front_matter(text)
    name = str(meta.get("name") or fallback_name or "skill").strip()

    tools = meta.get("tools") or ()
    if isinstance(tools, str):
        tools = [tools]
    tools = tuple(t for t in tools if t)

    description = str(meta.get("description") or "").strip()
    if not description:
        first = next((ln.strip() for ln in body.splitlines() if ln.strip()), "")
        description = first.lstrip("# ").strip()

    model = meta.get("model")
    return Skill(
        name=name,
        description=description,
        instructions=body,
        model=str(model).strip() if model else None,
        tools=tools,
        path=path,
    )


def load_skill(skill_md: str | Path) -> Skill:
    """Load one ``SKILL.md`` file into a :class:`Skill`."""
    path = Path(skill_md)
    return parse_skill(
        path.read_text(), path=path.parent, fallback_name=path.parent.name
    )


def discover_skills(root: str | Path) -> list[Skill]:
    """Find every ``<root>/*/SKILL.md`` and load it. Missing root → ``[]``.

    Sorted by name so a fixed skills folder always yields a fixed tool order.
    """
    base = Path(root)
    if not base.is_dir():
        return []
    skills = [load_skill(p) for p in sorted(base.glob("*/SKILL.md"))]
    return sorted(skills, key=lambda s: s.name)
