"""Deploy out/ to the external host — deterministic, idempotent, no model.

Host decision (PRD §12, decided in slice V3): Netlify, driven through the
CLI so this file is the single swap point if the host changes. Credentials
come from NETLIFY_AUTH_TOKEN + NETLIFY_SITE_ID (Actions secrets). A
content hash of out/ is kept in data/manifest.json (deploy_state), so
re-deploying identical content is a no-op.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent


def preserve_live_sitrep(out_dir: Path) -> None:
    """A Netlify deploy replaces the whole site. When the monitor loop deploys
    a dashboard-only out/, mirror the currently-live sitrep in first so the
    previous sitrep stays live (PRD §7). Best-effort: first deploys have none."""
    site_url = os.environ.get("NETLIFY_SITE_URL")
    if not site_url or (out_dir / "sitrep" / "index.html").exists():
        return
    try:
        response = httpx.get(
            f"{site_url.rstrip('/')}/sitrep/index.html", timeout=15, follow_redirects=True
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        print(f"no live sitrep to preserve ({exc})", file=sys.stderr)
        return
    (out_dir / "sitrep").mkdir(parents=True, exist_ok=True)
    (out_dir / "sitrep" / "index.html").write_text(response.text)
    print("preserved live sitrep into out/sitrep/")


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(str(path.relative_to(root)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "out")
    parser.add_argument("--data", type=Path, default=REPO_ROOT / "data")
    parser.add_argument(
        "--dry-run", action="store_true", help="hash + decide, but never call the host"
    )
    args = parser.parse_args(argv)

    if not args.out.is_dir() or not any(args.out.rglob("*")):
        print("nothing to deploy: out/ is empty", file=sys.stderr)
        return 1

    if not args.dry_run:
        preserve_live_sitrep(args.out)
    current = tree_hash(args.out)
    manifest_path = args.data / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    if manifest.get("deploy_state", {}).get("out_hash") == current:
        print(f"deploy skipped: content unchanged ({current[:12]})")
        return 0

    token = os.environ.get("NETLIFY_AUTH_TOKEN")
    site = os.environ.get("NETLIFY_SITE_ID")
    if args.dry_run or not (token and site):
        if not args.dry_run:
            print(
                "deploy skipped: NETLIFY_AUTH_TOKEN / NETLIFY_SITE_ID not set "
                "(add them to Actions secrets to go live)",
                file=sys.stderr,
            )
        print(f"would deploy {args.out} ({current[:12]})")
        return 0

    subprocess.run(
        ["npx", "--yes", "netlify-cli", "deploy", "--prod", "--dir", str(args.out)],
        check=True,
        env=os.environ | {"NETLIFY_AUTH_TOKEN": token, "NETLIFY_SITE_ID": site},
    )
    if manifest:
        manifest.setdefault("deploy_state", {})["out_hash"] = current
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"deployed {args.out} ({current[:12]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
