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
| V3 | The always-on agent (monitor loop + daily sitrep) | Live dashboard redeployed by the ~5-min monitor loop; daily 08:30 SGT sitrep from its own scheduled run; loud failure when blind | §3 render/deploy, §7 degraded/abort, decisions #17–19, design §2–§3, §6 |

**Independence** *(revised 2026-07-08 — PRD §13, decision #20)*: the slices
share **contracts, not code**. The event schema, run manifest, stage CLIs,
assessment file and `out/` layout are frozen in PRD §13 and enforced by
`schemas/` + the contract fixtures (§13.6), which are Day-1 artefacts. V2
builds from store fixtures instead of V1's output; V3's workflows run
against stage stubs that honour the CLI contract. The three slices can
therefore proceed in parallel or in any order; the V1→V2→V3 numbering is the
recommended *demo and integration* order (V1 proves the spine cheapest, V3's
end-to-end story reads best last), not a build dependency. Each slice is
filed as a GitHub issue with the repo's slice template; detail lives in
`docs/SLICE-V1.md` … `SLICE-V3.md`.

**Which slice makes it run by itself?** V3. Fetching is built in V1 and the
sitrep in V2, but both stay human-triggered until V3 adds the two schedules
*(revised 2026-07-08 — PRD decisions #17–19)*: the **monitor loop** (~5-min
target) that keeps the dashboard fresh, and the **daily sitrep run** (08:30
SGT) that summarises the previous day. V3 is *implemented and demoed*
against stubs; **enabling** the sitrep schedule is the one integration
point: the workflow ships `.disabled` and flips on only when the real
deterministic gate (V1) and model step (V2) are wired in — the repo's
architectural rule, now a merge-and-flip step rather than a build
dependency (PRD §13.7).
