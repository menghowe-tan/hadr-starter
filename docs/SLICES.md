# Slices

**Derived from:** `docs/PRD.md` + `docs/product-design.md` · **Date:** 2026-07-08

Produced with the slicing step (F) of
[bguiz/build-agent-skills](https://github.com/bguiz/build-agent-skills)
`build-2-plan-specs`, adapted inline: the shaping sub-skills are not
installed, and the shape was already selected in the PRD (§3 pipeline) with
the product design (§4 anatomy, §5 components) standing in for the
breadboard. Slicing criterion kept verbatim: **vertical implementation
increments, each ending in demo-able UI.**

| Slice | Name | Ends in (the demo) | PRD coverage |
|---|---|---|---|
| V1 | Quiet or not, replayable | Skeleton sitrep page (eventful or all-quiet) rendered from replay fixtures; second identical run stays quiet | §5 gate, §7 quiet, §8 time, §11 fixtures |
| V2 | One event, one story | The real layered sitrep document — merge confidence, ▲△▽✕ change notes, Estimated/Reported labels, model-written summary | §4 #5 supersession, §6 identity, §9 dossier answers, design §4–§5 |
| V3 | The daily agent (unattended at 08:30) | Sitrep + Leaflet map live on the external host from a scheduled Actions run; loud failure when blind | §3 render/deploy, §7 degraded/abort, design §2–§3, §6 |

Ordering rationale: V1 makes the deterministic spine testable and demoable on
Day 2 morning (fixtures are the PRD's own Day-1 carry-over); V2 adds the
product's intelligence and its full face; V3 removes the human. Each slice is
filed as a GitHub issue with the repo's slice template; detail lives in
`docs/SLICE-V1.md` … `SLICE-V3.md`.

**Which slice makes it daily?** V3. Fetching is built in V1 and the sitrep
in V2, but both stay human-triggered until V3 enables the scheduled workflow
that fetches, gates, and publishes every morning. The schedule cannot land
earlier without breaking the repo's architectural rule: the workflow stays
disabled until both the deterministic gate (V1) and the model step (V2)
exist.
