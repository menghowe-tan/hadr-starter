"""Terminal entrypoint: `python -m harness.cli` for a REPL, `--once` for one shot."""

from __future__ import annotations

import argparse
import sys

from .agent import DEFAULT_MODEL, Agent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="harness", description=__doc__)
    parser.add_argument("--model", help=f"model id (default: {DEFAULT_MODEL})")
    parser.add_argument("--once", metavar="PROMPT", help="send one prompt and exit")
    parser.add_argument(
        "--system", metavar="FILE", help="standing orders: system prompt text file"
    )
    args = parser.parse_args(argv)

    if args.system:
        agent = Agent.with_system_file(args.system, model=args.model)
    else:
        agent = Agent(model=args.model)

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
