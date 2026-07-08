"""The HADR agent: reusable harness + goal.md + this project's tools.

Headless entrypoint: `uv run python -m agent.main` runs one assessment
turn (the sitrep workflow's model step); `--once` overrides the prompt.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from harness import Agent

from .tools import TOOLS

REPO_ROOT = Path(__file__).resolve().parent.parent

ASSESS_PROMPT = (
    "Carry out your standing orders: fetch the feeds, assess the current "
    "situation, and report."
)


def build_agent(model: str | None = None, client=None) -> Agent:
    return Agent.with_system_file(
        REPO_ROOT / "goal.md", model=model, tools=TOOLS, client=client
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hadr-agent", description=__doc__)
    parser.add_argument("--model", help="model id override")
    parser.add_argument("--once", metavar="PROMPT", default=ASSESS_PROMPT)
    args = parser.parse_args(argv)
    print(build_agent(model=args.model).send(args.once))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
