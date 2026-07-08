# Product Design — HADR Monitor

**Status:** Draft for review · **Date:** 2026-07-08 · **Derives from:** `docs/PRD.md`

How the PRD's decisions become interface: one identity across every surface
the agent produces — the mailable morning sitrep, the map page, and the
failure alert — plus the component language, tokens and copy rules that
Day-2 slices build against.

> A rendered version of this spec (with all components shown live) is
> published as an artifact; this file is the source of truth for design
> decisions, per the same convention as `docs/PRD.md`.

## 1. Design principles

Each principle is a PRD decision restated as a design obligation.

| Principle | Meaning in the interface | PRD |
|---|---|---|
| **Trust is the product** | A quiet report proves the pipeline ran. Every page carries run stamp, feed health and generation footer — silence is always accounted for. | §7 |
| **Estimates never dress as facts** | Every impact figure wears an `Estimated` or `Reported` label. A bare number is a rendering bug. | §5 |
| **Change outranks state** | What moved since the last report is more prominent than what merely is. Escalations lead the page; downgrades whisper. | §4 #5 |
| **Three readers, one page** | Layered, not siloed: prose for the lay reader, tiles and map for leadership, sourced detail for the analyst — in that vertical order. | §2 |
| **State the blindness** | Every sitrep ends with what the agent cannot see. Implied omniscience is a design defect. | §10 |

## 2. Surfaces

| Surface | Medium | Constraints |
|---|---|---|
| **Morning sitrep** | Self-contained HTML document, deployed to the external host and mailable | Inline styles only; zero external requests; must read in email clients — single column under 720 px, no JS required for content |
| **Map page** | Leaflet + OSM tiles on the external host | External tiles accepted at view time; degrades to the marker list if tiles fail |
| **Failure alert** | GitHub Actions failure → notification | Not a page. Plain text: what broke, since when, what the last good run was |

The committed JSON store is not a surface — it is the single source both
pages render from, so they can never disagree.

## 3. The four morning states

The PRD's run semantics (§7) give the product exactly four mornings. Each has
a distinct visual signature at the very top of the page, before any content —
the reader should know which morning it is without scrolling.

1. **Eventful — the default.** Sitrep as designed: summary → tiles → map →
   ranked events, escalations pinned to the top of the event list.
2. **All quiet — a first-class page, not an empty one.** The page still
   renders in full: run stamp, feed health with last-success times, the
   gate's counts (fetched / gated out), continuing situations in their
   unchanged state, and the blindness footer. Quiet must be checkable, or it
   reads as broken.
3. **Degraded — one feed lost, coverage continues.** An orange banner above
   the summary names what is *lost*, not just what failed — readers think in
   hazards, not feeds: "GDACS unreachable since 04:12 UTC. Earthquake
   coverage continues via USGS; cyclone, flood and drought coverage is blind
   this morning." Affected hazard sections repeat it inline; the feed chip
   goes red.
4. **Abort — no sitrep exists.** This state is an alert, not a page. The
   previous sitrep stays live at its URL with its own date clearly stamped —
   a stale report must never impersonate today's. Alert copy: what broke,
   since when, link to the last good run.

## 4. Sitrep anatomy

Six zones, fixed order. The vertical order *is* the layering: each reader
stops scrolling when their layer ends.

| Zone | Contents | Reader |
|---|---|---|
| Top bar | Identity, run stamp (SGT + UTC + run #), feed-health chips | Everyone |
| Summary | Plain-language prose, serif, no acronyms or feed names — the whole story in five sentences | Lay reader |
| At a glance | Stat tiles: Red / Orange / Editorial / Changed | Leadership |
| Map | Overnight picture; static image in the mailed document, linking to the live map page | Leadership |
| Events | Severity-ranked cards, escalations first — full sourcing, change notes, confidence tags | Analyst |
| Quieter + blindness | Downgrades, withdrawals, aged-out notes; then coverage limits and the generation footer | Analyst |

**Ranking rule:** escalated events first (newest escalation on top), then by
alert level Red → Orange → editorial Green, then by modeled exposure.
Deterministic — the script orders, the model writes.

## 5. Component library

Semantic colour (alert levels) is reserved for event state — the accent blue
never signals severity.

### Alert chips

`RED` / `ORANGE` / `GREEN` pills in the GDACS colours. A Green event appears
**only** with an `EDITORIAL` companion chip — the gate never admits bare
Greens, so the pair documents why it's here (PRD §5).

### Provenance labels

- `Estimated` = model output (GDACS score, PAGER).
- `Reported` = ground truth via ReliefWeb or a named authority.
- `Reported: none` = explicitly no confirmed figures yet.

When estimate and report disagree, show both — disagreement between different
models is information, not an error (PRD §9, USGS 3).

### Change notes — the supersession policy made visible

| Glyph | Note | Placement |
|---|---|---|
| ▲ | ESCALATED (e.g. Orange → Red, with time) | Card pinned to top of event list |
| △ | REVISED (magnitude, PAGER, location) | On the event card |
| △ | UPDATED (new episode on a continuing event) | On the event card |
| ▽ | DOWNGRADED | "Noted, quieter" zone — reported once, then dropped |
| ✕ | WITHDRAWN | "Noted, quieter" zone; **only after the detail endpoint confirms deletion** — aged-out events are never called withdrawn (PRD §7) |

A first-time event carries `New` in place of a change note.

### Merge confidence — the identity tiers, surfaced

- `merge: confirmed (GLIDE)`
- `merge: high (Δt 3 min · Δd 12 km)` — tier-2 tags show their evidence so an
  analyst can audit the merge at a glance
- `merge: possible` — rendered as two cards with a cross-reference line,
  never silently combined (PRD §6)
- `merge: single-source`

### Feed health chips

One per feed, always visible. Green dot = fetched this run; orange = degraded
(stale cache, fallback lane); red = unreachable. The timestamp shown is the
last *success*, not the last attempt.

### Event card — fixed field order

1. Chips — alert level (+ editorial) + hazard code
2. Title — human place-name first, magnitude second
3. Meta — time SGT · UTC, coordinates, depth/track, PAGER
4. Impact — figures with provenance labels
5. Change note — omitted only for first-time events
6. Sources — feed ids, GLIDE, merge confidence

Field order is invariant so analysts can scan down a column of cards.

## 6. Map page

Full-bleed Leaflet map with the same top bar as the sitrep, so the two
surfaces are visibly one product. Markers use the alert palette; everything
else stays quiet.

- **Interactions:** click marker → popup (title, chips, headline figure, link
  into the sitrep's event card anchor).
- **Cyclones** draw the forecast track as a dashed polyline with the current
  centre marked — the point alone is misleading 500 km offshore (PRD §4 #3).
  Track, not cone: cones imply a certainty model we don't have.
- **No clustering** at this event volume; if two markers collide, offset with
  a leader line, don't hide.
- **Failure mode:** if OSM tiles don't load, the marker layer renders on a
  plain graticule ground with a notice — the data never disappears with the
  basemap.

## 7. Design tokens

Light and dark are both first-class; every value ships as a CSS custom
property. Semantic colours are re-derived for dark, not inverted.

| Token | Light | Dark |
|---|---|---|
| Accent (operational blue) | `#0E5FA8` | `#7FB3E3` |
| Red alert | `#C0392B` | `#E08578` |
| Orange | `#B85B08` | `#EDA75B` |
| Green | `#2E7D32` | `#7CC47F` |
| Ground | `#F4F7FA` | `#0F151C` |
| Surface | `#FFFFFF` | `#161E27` |
| Ink | `#1B2733` | `#D9E2EB` |
| Muted | `#5B6B7A` | `#8FA0B0` |
| Line | `#D7DEE6` | `#2B3846` |
| Wash | `#EAF1F7` | `#1B2836` |

Neutrals are blue-biased toward the accent — no pure greys. The accent never
carries severity; alert colours never decorate chrome.

### Type roles

| Role | Stack | Used for |
|---|---|---|
| Briefing voice | Charter, "Bitstream Charter", "Sitka Text", Cambria, Georgia, serif | Summary prose **only** — the visual cue that "this part is written for you" |
| Interface | Seravek, "Gill Sans Nova", Ubuntu, Calibri, "DejaVu Sans", sans-serif | Headings, cards, controls |
| Data | ui-monospace, "SF Mono", "Cascadia Code", Menlo, Consolas, monospace | Timestamps, ids, coordinates, labels — with `tabular-nums` wherever numerics align |

## 8. Copy rules

| Rule | Say | Not |
|---|---|---|
| Summary layer: people and places, no jargon | A strong earthquake struck the coast of southern Peru | M6.3 EQ, GDACS Orange, PAGER Yellow |
| Magnitude follows geography | …near Camaná, Peru (magnitude 6.3) | M 6.3 event at 16.8°S 72.6°W |
| Estimates hedge, reports don't | Moderate casualties are *possible* (Estimated) | 180,000 people affected |
| Echoes aren't corroboration | GDACS and USGS carry the same detection | Confirmed by two independent sources |
| Degradation names the lost hazards | Cyclone and flood coverage is blind this morning | GDACS API returned HTTP 503 |
| Quiet is a statement, not an absence | All quiet — no events cleared the gate; all feeds healthy | *(empty page)* |

## 9. Accessibility & constraints

- **Colour is never the only channel:** alert chips carry their level as
  text; change notes pair glyph + word (▲ ESCALATED); feed dots pair with
  status text.
- **Motion:** the map's pulse on Red markers and smooth scrolling honour
  `prefers-reduced-motion`; the mailed document has no motion at all.
- **Email reality:** the sitrep document uses inline styles, system fonts, no
  JS for content, and holds a single column under 720 px. The interactive map
  is linked, never embedded.
- **Themes:** hosted pages honour `prefers-color-scheme` with token-level
  overrides; the mailed document ships light-only (email client dark-mode
  transforms are untrustworthy) — a deliberate single-theme choice.
- **Keyboard:** map markers are reachable via an offscreen event list
  mirroring the marker order; focus states visible throughout.

## 10. Open design items

- Static map image in the mailed document: pre-rendered PNG at build time vs.
  skip-and-link. Recommend pre-rendered — leadership reads the mail, not the
  host.
- Cyclone track visual on the map page: forecast cone vs. simple dashed
  track. Start with the track (see §6).
- How many mornings of history the sitrep links back to (prev/next navigation
  on the host) — proposal: 14, matching the committed store's practical diff
  window.
