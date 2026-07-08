"""ReliefWeb lane: umbrella "disasters", not physical events (PRD §6, §9).

A ReliefWeb disaster is a country-level umbrella that may cover several
physical events; the store models event↔umbrella *links*, never a foreign
key. Umbrellas are the pipeline's only source of the ``Reported`` provenance
label — everything GDACS/USGS says about impact is a model estimate.

Built RSS-first behind the ``ReliefWebSource`` interface: the RSS feed needs
no appname approval but carries only the ~20 latest disasters and no
structured fields — country and GLIDE are parsed out of the HTML-escaped
``description``. ``ReliefWebAPI`` is the slot the approved-appname
implementation drops into (PRD decision #11); it is deliberately
unimplemented in this slice.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Protocol

from pipeline import fetch, merge

# Umbrella↔event linking reuses the tier-3 window (PRD §6): same hazard +
# country within 24 h is a *possible* link; only a GLIDE match is confirmed.
LINK_WINDOW_SECONDS = 24 * 3600

_TAG_DIV = re.compile(
    r'<div class="tag (?P<tag>country|glide)">\s*(?:[^:<]*:)?\s*(?P<value>.*?)\s*</div>',
    re.IGNORECASE | re.DOTALL,
)
_FIRST_P = re.compile(r"<p>(?P<body>.*?)</p>", re.IGNORECASE | re.DOTALL)
_ANY_TAG = re.compile(r"<[^>]+>")

# GLIDE prefixes are hazard codes; GDACS's six map straight across.
_GLIDE_HAZARDS = {"EQ", "TC", "FL", "VO", "DR", "WF"}


class ReliefWebSource(Protocol):
    """One ReliefWeb lane: returns ``(umbrellas, fetched_at, status)``."""

    def fetch(self, replay_dir: Path | None = None) -> tuple[list[dict], str, str]: ...


class ReliefWebRSS:
    """The interim lane: https://reliefweb.int/disasters/rss.xml (no appname)."""

    def fetch(self, replay_dir: Path | None = None) -> tuple[list[dict], str, str]:
        xml_text, fetched_at, status = fetch.fetch_reliefweb_rss(replay_dir)
        if xml_text is None:
            return [], fetched_at, status
        try:
            umbrellas = parse_rss(xml_text)
        except ET.ParseError:
            return [], fetched_at, fetch.STATUS_DOWN
        return umbrellas, fetched_at, status


class ReliefWebAPI:
    """Adapter slot for the approved-appname API lane (out of scope in V2)."""

    def __init__(self, appname: str):
        self.appname = appname

    def fetch(self, replay_dir: Path | None = None) -> tuple[list[dict], str, str]:
        raise NotImplementedError(
            "ReliefWeb API lane lands when the appname is approved (PRD §9); "
            "use ReliefWebRSS meanwhile."
        )


def _utc_from_rfc822(value: str) -> str | None:
    try:
        moment = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).isoformat()


def _strip_tags(fragment: str) -> str:
    return re.sub(r"\s+", " ", _ANY_TAG.sub(" ", fragment)).strip()


def parse_item(title: str, link: str, pub_date: str | None, description: str) -> dict:
    """One RSS ``<item>`` → one umbrella record.

    ``description`` is the *unescaped* HTML fragment (ElementTree already
    undoes the feed's entity escaping): country from the ``tag country``
    div, GLIDE from the ``tag glide`` div, prose from the first ``<p>``.
    """
    countries: list[str] = []
    glide = None
    for match in _TAG_DIV.finditer(description or ""):
        value = _strip_tags(match.group("value"))
        if match.group("tag").lower() == "glide":
            glide = value or None
        elif value:
            countries.append(value)
    body = _FIRST_P.search(description or "")
    prefix = (glide or "").split("-", 1)[0].upper()
    slug = link.rstrip("/").rsplit("/", 1)[-1] if link else None
    return {
        "umbrella_id": slug or glide or title,
        "title": title,
        "url": link or None,
        "glide": glide,
        "hazard": prefix if prefix in _GLIDE_HAZARDS else None,
        "country": ", ".join(countries) or None,
        "published_at": _utc_from_rfc822(pub_date) if pub_date else None,
        "summary": _strip_tags(body.group("body")) if body else None,
    }


def parse_rss(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    umbrellas = []
    for item in root.iter("item"):
        umbrellas.append(
            parse_item(
                title=(item.findtext("title") or "").strip(),
                link=(item.findtext("link") or "").strip(),
                pub_date=item.findtext("pubDate"),
                description=item.findtext("description") or "",
            )
        )
    return umbrellas


def _within_window(event: dict, umbrella: dict) -> bool:
    occurred, published = event.get("occurred_at"), umbrella.get("published_at")
    if not occurred or not published:
        return False
    delta = abs(
        datetime.fromisoformat(occurred).timestamp()
        - datetime.fromisoformat(published).timestamp()
    )
    return delta <= LINK_WINDOW_SECONDS


def link_umbrellas(events: list[dict], umbrellas: list[dict]) -> None:
    """Attach event↔umbrella links, in place; many-to-many by design.

    Confirmed by GLIDE equality (tier 1); otherwise a *possible* link when
    hazard + country match inside the tier-3 window. One umbrella may link
    to several physical events; the events stay separate.
    """
    for event in events:
        links = []
        for umbrella in umbrellas:
            confidence = None
            if event.get("glide") and umbrella.get("glide") == event["glide"]:
                confidence = "confirmed"
            elif (
                umbrella.get("hazard")
                and umbrella["hazard"] == event.get("hazard")
                and merge.countries_overlap(event.get("country"), umbrella.get("country"))
                and _within_window(event, umbrella)
            ):
                confidence = "possible"
            if confidence:
                links.append(
                    {
                        "umbrella_id": umbrella["umbrella_id"],
                        "title": umbrella["title"],
                        "url": umbrella.get("url"),
                        "glide": umbrella.get("glide"),
                        "confidence": confidence,
                    }
                )
        event["umbrellas"] = sorted(links, key=lambda u: (u["umbrella_id"] or ""))
