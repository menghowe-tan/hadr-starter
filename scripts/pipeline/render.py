"""The sitrep document — the product's face (docs/product-design.md).

Self-contained, mailable HTML: inline styles only, system font stacks, no
scripts, no external requests, light-only (email dark-mode transforms are
untrustworthy — design §9), one column that holds under 720 px. Generated
views are never committed (CLAUDE.md); this writes into the gitignored
``reports/`` directory by default.

Six zones, fixed order (design §4): top bar → summary → at-a-glance → map
note → events → quieter + blindness. Deterministic throughout — the model's
words arrive pre-written in ``assessment`` (or not at all: the monitor loop
and the all-quiet morning render without a model).

Two hard rules enforced by ``validate_sitrep``:

- every impact figure carries ``Estimated`` / ``Reported`` /
  ``Reported: none`` — a bare number is a rendering bug (PRD §5);
- no element may request the network (design §2).

SGT appears here and only here (PRD §8): internally everything is UTC.
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from pipeline import rank

SGT = ZoneInfo("Asia/Singapore")

# Design tokens (design §7), light theme — the mailed document is
# deliberately single-theme.
ACCENT = "#0E5FA8"
RED = "#C0392B"
ORANGE = "#B85B08"
GREEN = "#2E7D32"
GROUND = "#F4F7FA"
SURFACE = "#FFFFFF"
INK = "#1B2733"
MUTED = "#5B6B7A"
LINE = "#D7DEE6"
WASH = "#EAF1F7"

SERIF = "Charter,'Bitstream Charter','Sitka Text',Cambria,Georgia,serif"
SANS = "Seravek,'Gill Sans Nova',Ubuntu,Calibri,'DejaVu Sans',sans-serif"
MONO = "ui-monospace,'SF Mono','Cascadia Code',Menlo,Consolas,monospace"

MONO_STYLE = f"font-family:{MONO};font-variant-numeric:tabular-nums"

# Change-note glyphs always pair with their word — colour and symbol are
# never the only channel (design §9).
GLYPHS = {
    "new": ("＋", "NEW"),
    "escalated": ("▲", "ESCALATED"),
    "revised": ("△", "REVISED"),
    "updated": ("△", "UPDATED"),
    "downgraded": ("▽", "DOWNGRADED"),
    "withdrawn": ("✕", "WITHDRAWN"),
    "aged-out": ("○", "AGED OUT"),
}
_NOTE_COLOR = {"escalated": RED, "downgraded": MUTED, "withdrawn": MUTED, "aged-out": MUTED}

HAZARD_NAMES = {
    "EQ": "earthquake",
    "TC": "tropical cyclone",
    "FL": "flood",
    "VO": "volcano",
    "DR": "drought",
    "WF": "wildfire",
}

VALID_IMPACT_LABELS = ("Estimated", "Reported", "Reported: none")

_USGS_TITLE_PREFIX = re.compile(r"^M\s[\d.]+\s+-\s+")


class RenderError(ValueError):
    """A rendering rule was violated (bare figure, external request)."""


def stamp(utc_iso: str) -> str:
    """Render a stored UTC instant as SGT with the UTC alongside."""
    moment = datetime.fromisoformat(utc_iso).astimezone(timezone.utc)
    sgt = moment.astimezone(SGT)
    return f"{sgt.strftime('%d %b %Y %H:%M')} SGT · {moment.strftime('%H:%M')} UTC"


def _esc(value) -> str:
    return html.escape(str(value)) if value is not None else ""


def _sources(record: dict) -> list[str]:
    return record.get("sources") or [record.get("source")]


def display_title(record: dict) -> str:
    """Human place-name first, magnitude second (design §8)."""
    titles = record.get("source_titles") or {record.get("source"): record.get("title")}
    place = None
    if titles.get("usgs"):
        place = _USGS_TITLE_PREFIX.sub("", titles["usgs"])
    base = place or titles.get("gdacs") or record.get("title") or record["event_id"]
    magnitude = record.get("magnitude")
    if record.get("hazard") == "EQ" and magnitude is not None:
        return f"{base} (magnitude {magnitude:g})"
    return base


# ---------------------------------------------------------------- chips ---


def _chip(text: str, color: str, filled: bool = True) -> str:
    if filled:
        style = f"background:{color};color:#fff;border:1px solid {color};"
    else:
        style = f"background:{WASH};color:{INK};border:1px solid {LINE};"
    return (
        f'<span style="display:inline-block;padding:1px 8px;border-radius:999px;'
        f"font-family:{SANS};font-size:11px;font-weight:600;letter-spacing:.06em;"
        f'{style}margin-right:6px;">{_esc(text)}</span>'
    )


def _alert_chips(record: dict, editorial: bool = False) -> str:
    """Alert-level chips. Semantic colour is reserved for event state; a
    GREEN chip appears only with its EDITORIAL companion (design §5) —
    events admitted by the USGS lane at lower GDACS levels carry no alert
    chip; their PAGER shows as an Estimated impact line instead."""
    chips = []
    level_rank = rank.display_level_rank(record)
    if editorial:
        chips.append(_chip("GREEN", GREEN))
        chips.append(_chip("EDITORIAL", ACCENT))
    elif level_rank >= 4:
        chips.append(_chip("RED", RED))
    elif level_rank >= 3:
        chips.append(_chip("ORANGE", ORANGE))
    chips.append(_chip(record.get("hazard") or "?", "", filled=False))
    return "".join(chips)


def _feed_chip(name: str, info: dict) -> str:
    status = info.get("status", "ok")
    dot_color = GREEN if status == "ok" else RED
    status_word = "ok" if status == "ok" else "down"
    fetched = info.get("fetched_at")
    when = stamp(fetched) if fetched else "no successful fetch yet"
    return (
        f'<span style="display:inline-block;border:1px solid {LINE};background:{SURFACE};'
        f'border-radius:999px;padding:2px 10px;margin:2px 6px 2px 0;font-size:11px;font-family:{SANS};">'
        f'<span style="color:{dot_color};">●</span> <strong>{_esc(name.upper())}</strong> '
        f'{_esc(status_word)} · <span style="{MONO_STYLE};">{_esc(when)}</span></span>'
    )


# --------------------------------------------------------------- impact ---


def impact_line(label: str, text: str, url: str | None = None) -> str:
    """One provenance-labelled impact line. A bare figure is a bug."""
    if label not in VALID_IMPACT_LABELS:
        raise RenderError(f"bare impact figure (label {label!r}): {text}")
    body = _esc(text)
    if url:
        body = f'<a href="{_esc(url)}" style="color:{ACCENT};">{body}</a>'
    return (
        f'<li data-impact="1" style="margin:2px 0;">'
        f'<span data-label="{_esc(label)}" style="font-family:{SANS};font-size:11px;'
        f"font-weight:600;letter-spacing:.04em;color:{MUTED};border:1px solid {LINE};"
        f'background:{WASH};border-radius:4px;padding:0 5px;margin-right:6px;">{_esc(label)}</span>'
        f'<span style="font-size:13px;">{body}</span></li>'
    )


def _impact_lines(record: dict) -> str:
    sources = _sources(record)
    lines = []
    if "gdacs" in sources and record.get("alert_score") is not None:
        level = record.get("alert_level") or "—"
        lines.append(
            impact_line(
                "Estimated",
                f"GDACS {level} alert, score {record['alert_score']:g} — modeled impact, not an observation",
            )
        )
    if "usgs" in sources:
        pager = record.get("pager")
        lines.append(
            impact_line(
                "Estimated",
                f"PAGER {pager if pager else 'pending'} — USGS modeled fatalities and losses"
                + ("" if pager else " (not yet issued)"),
            )
        )
    reported = [u for u in record.get("umbrellas") or []]
    if reported:
        for umbrella in reported:
            suffix = f" — GLIDE {umbrella['glide']}" if umbrella.get("glide") else ""
            qualifier = "" if umbrella["confidence"] == "confirmed" else " (possible match)"
            lines.append(
                impact_line(
                    "Reported",
                    f"{umbrella['title']} (ReliefWeb{suffix}){qualifier}",
                    umbrella.get("url"),
                )
            )
    else:
        lines.append(impact_line("Reported: none", "no confirmed ground reports linked yet"))
    return "".join(lines)


# ---------------------------------------------------------------- cards ---


def _coords(record: dict) -> str | None:
    lat, lon = record.get("lat"), record.get("lon")
    if lat is None or lon is None:
        return None
    return (
        f"{abs(lat):.3f}°{'N' if lat >= 0 else 'S'} {abs(lon):.3f}°{'E' if lon >= 0 else 'W'}"
    )


def _merge_line(record: dict) -> str:
    merge = record.get("merge") or {"confidence": "single-source", "evidence": None}
    confidence, evidence = merge.get("confidence"), merge.get("evidence") or {}
    if confidence == "confirmed":
        return f"merge: confirmed (GLIDE {evidence.get('glide')})"
    if confidence == "high":
        dt = evidence.get("dt_seconds") or 0
        dt_text = f"{dt:.0f} s" if dt < 60 else f"{dt / 60:.0f} min"
        return f"merge: high (Δt {dt_text} · Δd {evidence.get('dd_km', 0):.0f} km)"
    return "merge: single-source"


def _change_note(record: dict, change: dict | None, prose: str | None) -> str:
    if change is None:
        note = (
            f'<span style="color:{MUTED};">No change since the last report.</span>'
        )
    elif change["change"] == "new":
        note = f"<strong>New</strong> — first appearance in this report."
    else:
        glyph, word = GLYPHS[change["change"]]
        color = _NOTE_COLOR.get(change["change"], INK)
        detail = f" — {_esc(change['detail'])}" if change.get("detail") else ""
        note = f'<strong style="color:{color};">{glyph} {word}</strong>{detail}'
    block = (
        f'<p data-change-note="1" style="margin:8px 0 0;padding:6px 8px;background:{WASH};'
        f'border-radius:6px;font-size:13px;">{note}</p>'
    )
    if prose:
        block += (
            f'<p style="margin:6px 0 0;font-family:{SERIF};font-size:14px;'
            f'font-style:italic;color:{INK};">{_esc(prose)}</p>'
        )
    return block


def _sources_line(record: dict, store: dict[str, dict]) -> str:
    parts = [" · ".join(_esc(m) for m in record.get("members") or [record["event_id"]])]
    extra_aliases = len(record.get("ids") or []) - len(record.get("members") or [1])
    if extra_aliases > 0:
        parts[0] += f" (+{extra_aliases} alias{'es' if extra_aliases != 1 else ''})"
    if record.get("glide"):
        parts.append(f"GLIDE {_esc(record['glide'])}")
    parts.append(_esc(_merge_line(record)))
    if record.get("gate_reason"):
        parts.append(f"gate: {_esc(record['gate_reason'])}")
    line = (
        f'<p style="margin:8px 0 0;{MONO_STYLE};font-size:11px;color:{MUTED};">'
        + " · ".join(parts)
        + "</p>"
    )
    if record.get("feed_source") == "NEIC" and "usgs" in _sources(record):
        line += (
            f'<p style="margin:2px 0 0;font-size:11px;color:{MUTED};">'
            "GDACS and USGS carry the same NEIC detection — one source seen twice, "
            "not two independent confirmations.</p>"
        )
    for related_id in record.get("possible_related") or []:
        related = store.get(related_id)
        if related is None or related.get("status") not in ("active",):
            continue
        line += (
            f'<p style="margin:2px 0 0;font-size:11px;color:{MUTED};">merge: possible — '
            f'possibly related to <a href="#{_esc(related_id)}" style="color:{ACCENT};">'
            f"{_esc(display_title(related))}</a>; kept as separate events (never merged silently).</p>"
        )
    return line


def _event_card(
    record: dict,
    change: dict | None,
    prose: str | None,
    store: dict[str, dict],
    editorial_reason: str | None = None,
) -> str:
    meta_bits = [stamp(record["occurred_at"])]
    coords = _coords(record)
    if coords:
        meta_bits.append(coords)
    if record.get("depth_km") is not None:
        meta_bits.append(f"depth {record['depth_km']:g} km")
    if record.get("country"):
        meta_bits.append(_esc(record["country"]))

    card = [
        f'<article id="{_esc(record["event_id"])}" data-event-card="1" style="background:{SURFACE};'
        f'border:1px solid {LINE};border-radius:8px;padding:14px 16px;margin:0 0 12px;">',
        f'<p style="margin:0 0 6px;">{_alert_chips(record, editorial=editorial_reason is not None)}</p>',
        f'<h3 style="margin:0;font-family:{SANS};font-size:17px;">{_esc(display_title(record))}</h3>',
        f'<p style="margin:4px 0 0;{MONO_STYLE};font-size:11px;color:{MUTED};">'
        + " · ".join(meta_bits)
        + "</p>",
        f'<ul style="list-style:none;margin:8px 0 0;padding:0;">{_impact_lines(record)}</ul>',
    ]
    if editorial_reason is not None:
        card.append(
            f'<p style="margin:8px 0 0;padding:6px 8px;background:{WASH};border-radius:6px;'
            f'font-size:13px;"><strong style="color:{ACCENT};">Editorial</strong> — below the '
            f"deterministic gate; included by the model: {_esc(editorial_reason)}</p>"
        )
    else:
        card.append(_change_note(record, change, prose))
    card.append(_sources_line(record, store))
    card.append("</article>")
    return "".join(card)


# ---------------------------------------------------------------- zones ---


def _hazards_lost(manifest: dict) -> list[str]:
    """Degradation names the lost hazards, not the failed feeds (design §8)."""
    lost = []
    feeds = manifest.get("feeds", {})
    if feeds.get("gdacs", {}).get("status") == "down":
        lost.append(
            "GDACS is unreachable — cyclone, flood, volcano, drought and wildfire "
            "coverage is blind this morning; earthquake coverage continues via USGS."
        )
    if feeds.get("usgs", {}).get("status") == "down":
        lost.append(
            "USGS is unreachable — earthquake coverage continues via GDACS only, "
            "whose earthquake lane is itself USGS-derived and may lag."
        )
    if feeds.get("reliefweb", {}).get("status") == "down":
        lost.append(
            "ReliefWeb is unreachable — no ground-truth confirmations this morning; "
            "every impact figure is an estimate."
        )
    return lost


def _summary_text(manifest: dict, active: list[dict], assessment: dict | None) -> str:
    if assessment and assessment.get("summary"):
        return _esc(assessment["summary"])
    if manifest["verdict"] == "QUIET":
        if not active:
            return (
                "All quiet. No events cleared the gate this run — the pipeline ran and "
                "found nothing. Feed health above accounts for the silence."
            )
        return (
            f"All quiet — nothing changed since the last report. "
            f"{len(active)} continuing situation{'s' if len(active) != 1 else ''} "
            "below, in their unchanged state."
        )
    return (
        f"{len(active)} event{'s' if len(active) != 1 else ''} of record; "
        f"{len(manifest['changes'])} change{'s' if len(manifest['changes']) != 1 else ''} this run. "
        "This is the deterministic monitor view — the model-written summary appears "
        "in the daily sitrep."
    )


def _tiles(active: list[dict], editorial_count: int, changed_count: int) -> str:
    reds = sum(1 for r in active if rank.display_level_rank(r) >= 4)
    oranges = sum(1 for r in active if rank.display_level_rank(r) == 3)
    tiles = [("Red", reds, RED), ("Orange", oranges, ORANGE), ("Editorial", editorial_count, GREEN), ("Changed", changed_count, ACCENT)]
    cells = "".join(
        f'<div style="display:inline-block;min-width:104px;background:{SURFACE};'
        f'border:1px solid {LINE};border-top:3px solid {color};border-radius:8px;'
        f'padding:8px 12px;margin:0 8px 8px 0;vertical-align:top;">'
        f'<div style="{MONO_STYLE};font-size:22px;font-weight:700;">{count}</div>'
        f'<div style="font-size:11px;color:{MUTED};letter-spacing:.06em;">{_esc(label.upper())}</div></div>'
        for label, count, color in tiles
    )
    return f'<div style="margin:14px 0 4px;">{cells}</div>'


def _news_items(items: list[dict]) -> list[str]:
    """skills/news-summary/SKILL.md items — attributed, never a bare claim,
    and never mixed with the Estimated/Reported impact lines."""
    rendered = []
    for item in items:
        head = (
            f'<a href="{_esc(item["url"])}" style="color:{ACCENT};font-weight:600;'
            f'text-decoration:none;">{_esc(item["headline"] or item["url"])}</a>'
        )
        meta_bits = [item["source"]]
        if item.get("published_at"):
            meta_bits.append(item["published_at"])
        meta = f'<span style="{MONO_STYLE};font-size:11px;color:{MUTED};"> — {_esc(" · ".join(meta_bits))}</span>'
        related = ""
        if item.get("event_id"):
            related = (
                f' <a href="#{_esc(item["event_id"])}" style="font-size:11px;'
                f'color:{MUTED};">↳ related event</a>'
            )
        note = (
            f'<p style="margin:2px 0 0;font-size:13px;">{_esc(item["note"])}</p>'
            if item.get("note")
            else ""
        )
        rendered.append(f"<li style=\"margin:0 0 10px;\">{head}{meta}{related}{note}</li>")
    return rendered


def _quieter_items(manifest: dict, store: dict[str, dict]) -> list[str]:
    items = []
    for change in manifest["changes"]:
        kind = change["change"]
        if kind not in ("downgraded", "withdrawn", "aged-out"):
            continue
        record = store.get(change["event_id"])
        title = display_title(record) if record else change["event_id"]
        glyph, word = GLYPHS[kind]
        detail = {
            "downgraded": change.get("detail") or "alert level fell",
            "withdrawn": "deletion confirmed at the source's detail endpoint",
            "aged-out": "fell out of the feed window — not withdrawn (vanished ≠ deleted)",
        }[kind]
        items.append(
            f'<li style="margin:4px 0;font-size:13px;">'
            f'<strong style="color:{MUTED};">{glyph} {word}</strong> — '
            f"{_esc(title)} — {_esc(detail)}</li>"
        )
    return items


def _blindness_items(manifest: dict) -> list[str]:
    items = [
        "Tsunami warnings are not covered: the USGS tsunami flag only means a message "
        "exists; real warnings live with NOAA, a feed this agent does not have.",
        "Conflict, epidemic and displacement appear only through ReliefWeb's curated "
        "lag of days.",
        "The ReliefWeb lane reads the RSS feed (~20 latest disasters); older ground "
        "reports are invisible until the API appname is approved.",
    ]
    items.extend(_hazards_lost(manifest))
    return items


# ----------------------------------------------------------------- page ---


def render_sitrep(
    store: dict[str, dict],
    manifest: dict,
    assessment: dict | None = None,
    candidates: list[dict] | None = None,
    news: dict | None = None,
) -> str:
    changes_by_id = {c["event_id"]: c for c in manifest["changes"]}
    active = [r for r in store.values() if r.get("status") == "active"]
    ordered = rank.sitrep_order(active, changes_by_id)

    editorial = []
    if assessment:
        by_id = {c["event_id"]: c for c in (candidates or [])}
        for pick in assessment.get("editorial_greens", []):
            candidate = by_id.get(pick.get("event_id"))
            if candidate is not None:
                editorial.append((candidate, pick.get("reason") or "notable"))

    run_stamp = stamp(manifest["run_at"])
    sgt_date = (
        datetime.fromisoformat(manifest["run_at"]).astimezone(SGT).strftime("%A %d %B %Y")
    )
    feed_chips = "".join(
        _feed_chip(name, info) for name, info in manifest.get("feeds", {}).items()
    )
    change_prose = (assessment or {}).get("change_notes", {})

    h2 = (
        f'style="font-family:{SANS};font-size:13px;letter-spacing:.08em;'
        f'color:{MUTED};margin:24px 0 8px;text-transform:uppercase;"'
    )

    parts = [
        '<!doctype html><html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>HADR sitrep — {_esc(sgt_date)}</title></head>",
        f'<body style="margin:0;padding:0;background:{GROUND};color:{INK};font-family:{SANS};">',
        '<div style="max-width:720px;margin:0 auto;padding:20px 16px;">',
        # -- Zone 1: top bar -------------------------------------------------
        f'<div style="border-bottom:2px solid {ACCENT};padding-bottom:10px;">',
        f'<p style="margin:0;font-size:12px;letter-spacing:.14em;color:{ACCENT};'
        f'font-weight:700;">HADR MONITOR · DAILY SITREP</p>',
        f'<h1 style="margin:2px 0 4px;font-family:{SANS};font-size:22px;">{_esc(sgt_date)}</h1>',
        f'<p style="margin:0 0 8px;{MONO_STYLE};font-size:11px;color:{MUTED};">'
        f'run #{manifest.get("run_number", "?")} · {_esc(run_stamp)} · verdict {_esc(manifest["verdict"])}</p>',
        f"<div>{feed_chips}</div>",
        "</div>",
    ]

    lost = _hazards_lost(manifest)
    if lost:
        parts.append(
            f'<div data-degraded-banner="1" style="background:#FBEFE2;border:1px solid {ORANGE};'
            f'border-left:6px solid {ORANGE};border-radius:6px;padding:10px 12px;margin:14px 0 0;'
            f'font-size:13px;"><strong>Degraded coverage.</strong> '
            + " ".join(_esc(item) for item in lost)
            + "</div>"
        )

    # -- Zone 2: summary (the lay reader's whole page) -----------------------
    parts.append(
        f'<p data-summary="1" style="font-family:{SERIF};font-size:17px;line-height:1.55;'
        f'margin:18px 0 4px;">{_summary_text(manifest, active, assessment)}</p>'
    )

    # -- Zone 3: at a glance --------------------------------------------------
    parts.append(f"<h2 {h2}>At a glance</h2>")
    parts.append(_tiles(active, len(editorial), len(manifest["changes"])))
    parts.append(
        f'<p style="margin:0;{MONO_STYLE};font-size:11px;color:{MUTED};">'
        + " · ".join(
            f"{_esc(name)}: {info.get('count_fetched', 0)} fetched, "
            f"{info.get('count_gated', 0)} past the gate"
            for name, info in manifest.get("feeds", {}).items()
        )
        + "</p>"
    )

    # -- Zone 4: map (slice V3 ships the live page) ---------------------------
    parts.append(f"<h2 {h2}>Overnight picture</h2>")
    parts.append(
        f'<p style="margin:0;font-size:13px;color:{MUTED};border:1px dashed {LINE};'
        f'border-radius:8px;padding:10px 12px;background:{SURFACE};">'
        "The live map page ships in slice V3; coordinates for every event are on its "
        "card below. This document deliberately loads nothing from the network.</p>"
    )

    # -- Zone 5: events, severity-ranked, escalations first -------------------
    parts.append(f"<h2 {h2}>Events ({len(ordered) + len(editorial)})</h2>")
    if ordered or editorial:
        reds_oranges = [r for r in ordered if rank.display_level_rank(r) >= 3]
        others = [r for r in ordered if rank.display_level_rank(r) < 3]
        for record in reds_oranges:
            parts.append(
                _event_card(
                    record,
                    changes_by_id.get(record["event_id"]),
                    change_prose.get(record["event_id"]),
                    store,
                )
            )
        for candidate, reason in editorial:
            parts.append(_event_card(candidate, None, None, store, editorial_reason=reason))
        for record in others:
            parts.append(
                _event_card(
                    record,
                    changes_by_id.get(record["event_id"]),
                    change_prose.get(record["event_id"]),
                    store,
                )
            )
    else:
        parts.append(
            f'<p style="font-size:13px;color:{MUTED};">No events cleared the gate. '
            "The pipeline ran and found nothing — feed health above accounts for the "
            "silence.</p>"
        )

    # -- Zone 5b: news mentions (skills/news-summary/SKILL.md) ----------------
    # Always rendered, never silently omitted — a search that hasn't run,
    # or ran and found nothing, is a statement, not an absence (goal.md's
    # "all quiet" principle, applied to this skill too).
    parts.append(f"<h2 {h2}>News mentions</h2>")
    if news is None:
        parts.append(
            f'<p style="margin:0;font-size:13px;color:{MUTED};">The news-summary skill '
            "has not run yet — no web search has been recorded for this store.</p>"
        )
    else:
        checked = stamp(news["checked_at"]) if news.get("checked_at") else "unknown time"
        parts.append(
            f'<p style="margin:0 0 8px;font-size:12px;color:{MUTED};">Web search checked '
            f"{_esc(checked)} — unverified external reporting, not confirmed by this "
            "pipeline.</p>"
        )
        news_rows = _news_items(news.get("items") or [])
        if news_rows:
            parts.append(
                '<ul data-news="1" style="list-style:none;margin:0;padding:0;">'
                + "".join(news_rows)
                + "</ul>"
            )
        elif news.get("searched") is False:
            parts.append(
                f'<p style="font-size:13px;color:{MUTED};">The model did not search this '
                "run — nothing prompted it to look.</p>"
            )
        else:
            parts.append(
                f'<p style="font-size:13px;color:{MUTED};">No relevant coverage found in '
                "this search.</p>"
            )

    # -- Zone 6: quieter + blindness ------------------------------------------
    quieter = _quieter_items(manifest, store)
    parts.append(f"<h2 {h2}>Noted, quieter</h2>")
    if quieter:
        parts.append('<ul data-quieter="1" style="list-style:none;margin:0;padding:0;">' + "".join(quieter) + "</ul>")
    else:
        parts.append(
            f'<p style="font-size:13px;color:{MUTED};">No downgrades, withdrawals or '
            "aged-out events this report.</p>"
        )

    parts.append(f"<h2 {h2}>What this report cannot see</h2>")
    parts.append(
        '<ul style="margin:0;padding-left:18px;">'
        + "".join(
            f'<li style="font-size:13px;color:{MUTED};margin:4px 0;">{_esc(item)}</li>'
            for item in _blindness_items(manifest)
        )
        + "</ul>"
    )

    model_note = (
        "model summary included"
        if assessment
        else (
            "nothing changed — the model was not woken"
            if manifest["verdict"] == "QUIET"
            else "deterministic render — no model involved"
        )
    )
    parts.append(
        f'<p style="margin:20px 0 0;border-top:1px solid {LINE};padding-top:10px;'
        f'{MONO_STYLE};font-size:11px;color:{MUTED};">Generated {_esc(run_stamp)} · '
        f'mode {_esc(manifest.get("mode", "?"))} · deterministic pipeline decides, '
        f"the model only writes ({model_note}).</p>"
    )
    parts.append("</div></body></html>")

    page = "".join(parts)
    validate_sitrep(page)
    return page


# ----------------------------------------------------------- validation ---

_IMPACT_LI = re.compile(r'<li data-impact="1".*?</li>', re.S)
_LABEL = re.compile(r'data-label="([^"]*)"')
_EXTERNAL = (
    re.compile(r"<(script|link|img|iframe|video|audio|source|object|embed)\b", re.I),
    re.compile(r"@import", re.I),
    re.compile(r"url\s*\(", re.I),
)


def validate_sitrep(page: str) -> None:
    """The two hard rendering rules, enforced after the fact."""
    for pattern in _EXTERNAL:
        if pattern.search(page):
            raise RenderError(f"document is not self-contained: {pattern.pattern}")
    for match in _IMPACT_LI.finditer(page):
        label = _LABEL.search(match.group(0))
        if label is None or label.group(1) not in VALID_IMPACT_LABELS:
            raise RenderError(f"bare impact figure in rendered output: {match.group(0)[:120]}")


def write_sitrep(
    store: dict[str, dict],
    manifest: dict,
    out_path: Path,
    assessment: dict | None = None,
    candidates: list[dict] | None = None,
    news: dict | None = None,
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_sitrep(store, manifest, assessment, candidates, news))
    return out_path
