"""Terminal entrypoint: `python -m harness.cli` for a REPL, `--once` for one shot."""

from __future__ import annotations

import argparse
import sys

from .agent import DEFAULT_MODEL, Agent
from .skills import discover_skills


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="harness", description=__doc__)
    parser.add_argument("--model", help=f"model id (default: {DEFAULT_MODEL})")
    parser.add_argument("--once", metavar="PROMPT", help="send one prompt and exit")
    parser.add_argument(
        "--system", metavar="FILE", help="standing orders: system prompt text file"
    )
    parser.add_argument(
        "--skills",
        metavar="DIR",
        help="folder of <name>/SKILL.md skills to expose to the model",
    )
    args = parser.parse_args(argv)

    skills = discover_skills(args.skills) if args.skills else None
    if args.system:
        agent = Agent.with_system_file(args.system, model=args.model, skills=skills)
    else:
        agent = Agent(model=args.model, skills=skills)

    if args.once:
        print(agent.send(args.once))
        return 0

    interactive = sys.stdin.isatty()
    while True:
        try:
            line = input("> " if interactive else "").strip()
        except EOFError:
            return 0
        if not line:
            continue
        print(agent.send(line))


if __name__ == "__main__":
    raise SystemExit(main())
