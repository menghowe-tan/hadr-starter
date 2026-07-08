# SLICE-V2 — One event, one story

## Goal

Records from all three feeds merge into single canonical events with visible
confidence; changes since the last run become ▲△▽✕ notes; the gated model
writes the plain-language layer; the render is the real, mailable sitrep
document from `docs/product-design.md`.

## Why this cut

V1 proves the spine; V2 adds everything that makes the report trustworthy
rather than a feed dump: identity (PRD §6), supersession (PRD §4 #5),
estimate-vs-report labelling (PRD §5), and the three-reader layering
(design §4). It ends in the product's actual face.

## Build plan

1. ReliefWeb RSS adapter behind a `ReliefWebSource` interface (HTML-escaped
   description parsing, GLIDE from `tag glide` div); API implementation slot
   for when the appname is approved.
2. Tiered merge per PRD §6: GLIDE → spatiotemporal (30 min / 100 km) →
   `possible` (shown, not merged); many-to-many event↔umbrella links;
   confidence tag on every merged event.
3. Supersession classifier: ESCALATED / REVISED / UPDATED / DOWNGRADED /
   WITHDRAWN — withdrawal asserted only after the per-event detail endpoint
   confirms deletion (vanished ≠ deleted, PRD §7).
4. Headless model step, strictly behind the gate: plain-language summary,
   editorial-Green promotion (label mandatory), change-note prose.
   Deterministic ranking stays in `scripts/` (escalations → level → exposure).
5. Full sitrep document render per `docs/product-design.md`: tokens,
   components (chips, provenance labels, change notes, confidence tags,
   feed-health chips), fixed card field order; self-contained HTML, inline
   styles, no external requests; all-quiet and degraded variants.
6. Extend fixtures: two consecutive mornings where an event escalates
   Orange→Red; a GDACS+USGS pair for the same quake; a ReliefWeb umbrella
   covering two events.

## Definition of done

Verifiable in two minutes:

- `uv run pytest` is green.
- Replay morning-1 then morning-2 fixtures → the sitrep leads with the
  ▲ ESCALATED card.
- The GDACS+USGS pair renders as one card with `merge: high (Δt … · Δd …)`.
- Every impact figure on the page carries `Estimated` or `Reported`.
- Quiet replay renders the all-quiet page with feed-health chips.
- The document opens standalone (no network) and holds one column at 600 px.

## Out of scope

The map page, hosting/deploy, GitHub Actions, the ReliefWeb API lane
(adapter slot only), alerting, history navigation. No prompt-tuning beyond
what the fixtures demand.

## Test plan

### End-to-end tests
- Two-morning escalation replay → ▲ card leads; downgrade lands in
  "Noted, quieter".
- Full render passes a no-external-requests check and validates as
  self-contained HTML.

### Integration tests
- ReliefWeb RSS fixture → GLIDE + country extracted from escaped HTML.
- GLIDE-tier and spatiotemporal-tier merges produce tagged canonical events;
  `possible` pairs stay separate with cross-references.
- Umbrella maps many-to-many without collapsing distinct physical events.
- Model step is invoked only when the gate says CHANGED (spy/stub).

### Unit tests
- Supersession classification for each of the five note types.
- Withdrawal requires detail-endpoint confirmation; aged-out stays aged-out.
- Ranking comparator: escalation > level > exposure, stable across runs.
- Estimated/Reported labelling rule: a bare figure fails render validation.
