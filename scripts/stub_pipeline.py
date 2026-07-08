"""Stage stub honouring PRD §13.3 — stands in for slices V1 and V2.

Writes `data/` from a hand-authored store fixture (PRD §13.6), applies the
scenario's feed-failure overrides, re-stamps freshness relative to now,
validates everything against `schemas/`, and prints a single-line JSON
verdict as its last stdout line. Exit codes per §13.3: 0 published or quiet
(including degraded), 3 deliberate abort-blind. Deterministic; never calls
a model. At integration, the real V1/V2 stages replace this command —
workflows only depend on the manifest, the verdict line, and the exit code.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jsonschema import Draft202012Validator

import health

REPO_ROOT = Path(__file__).resolve().parent.parent

SCENARIOS = {
    "eventful": {"fixture": "eventful", "down": []},
    "quiet": {"fixture": "quiet", "down": []},
    "gdacs-down": {"fixture": "eventful", "down": ["gdacs"]},
    "both-down": {"fixture": "eventful", "down": ["gdacs", "usgs"]},
}

# Fresh feeds get re-stamped this far behind `now`.
FRESH_LAG = {"gdacs": timedelta(minutes=1), "usgs": timedelta(minutes=1), "reliefweb": timedelta(minutes=20)}
DOWN_LAG = timedelta(hours=2)


def _validate(instance: dict, schema_name: str) -> None:
    schema = json.loads((REPO_ROOT / "schemas" / f"{schema_name}.schema.json").read_text())
    Draft202012Validator(schema).validate(instance)


def run(scenario: str, data_dir: Path, fixtures_dir: Path, now: datetime) -> int:
    spec = SCENARIOS[scenario]
    store = fixtures_dir / spec["fixture"] / "store"
    manifest = json.loads((store / "manifest.json").read_text())

    # Re-stamp the fixture's freshness relative to now; apply failures.
    manifest["run_utc"] = now.isoformat()
    for name, feed in manifest["feeds"].items():
        if name in spec["down"]:
            feed["status"] = "down"
            feed["last_success_utc"] = (now - DOWN_LAG).isoformat()
        else:
            feed["status"] = "ok"
            feed["last_success_utc"] = (now - FRESH_LAG[name]).isoformat()

    # Carry deploy state across runs (idempotent deploys read/write it).
    old_manifest = data_dir / "manifest.json"
    if old_manifest.exists():
        previous = json.loads(old_manifest.read_text())
        if "deploy_state" in previous:
            manifest["deploy_state"] = previous["deploy_state"]

    verdict = health.evaluate(manifest, now)
    events = sorted((store / "events").glob("*.json")) if (store / "events").exists() else []

    def emit() -> None:
        print(json.dumps({"verdict": manifest["verdict"], "health": verdict}))
        if output := os.environ.get("GITHUB_OUTPUT"):
            with open(output, "a") as fh:
                fh.write(f"verdict={manifest['verdict']}\n")
                fh.write(f"health={verdict['status']}\n")

    if verdict["status"] == "abort":
        # Blind morning: touch nothing; the previous store and sitrep stay live.
        emit()
        return health.ABORT_EXIT_CODE

    # The stub honours the contract it stands in for: validate before writing.
    _validate(manifest, "manifest")
    for path in events:
        _validate(json.loads(path.read_text()), "event")

    events_dir = data_dir / "events"
    if events_dir.exists():
        shutil.rmtree(events_dir)
    events_dir.mkdir(parents=True)
    for path in events:
        shutil.copy(path, events_dir / path.name)
    (data_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    emit()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), required=True)
    parser.add_argument("--data", type=Path, default=REPO_ROOT / "data")
    parser.add_argument("--fixtures", type=Path, default=REPO_ROOT / "tests" / "fixtures")
    parser.add_argument("--now", type=datetime.fromisoformat, default=None)
    args = parser.parse_args(argv)
    now = args.now or datetime.now(timezone.utc)
    return run(args.scenario, args.data, args.fixtures, now)


if __name__ == "__main__":
    sys.exit(main())
