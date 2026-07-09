"""The keyless web_search tool: parsing DuckDuckGo HTML and unwrapping its
redirect links — no network (the one live call is monkeypatched)."""

import json

from agent import tools
from agent.tools import _clean_ddg_url, _parse_ddg, web_search

# A trimmed sample of DuckDuckGo's HTML result list: two results, links
# wrapped in the usual ``/l/?uddg=`` redirect, plus one malformed anchor with
# no href that must be dropped.
SAMPLE = """
<div class="result results_links web-result">
  <div class="links_main">
    <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Freuters.com%2Fworld%2Fquake&rut=abc">
      Reuters: Magnitude 7.7 quake hits near Mandalay</a>
    <a class="result__snippet" href="//duckduckgo.com/l/?uddg=x">
      A powerful earthquake struck central Myanmar on Friday.</a>
  </div>
</div>
<div class="result results_links web-result">
  <div class="links_main">
    <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Faljazeera.com%2Fquake">
      Al Jazeera: Rescuers search for survivors</a>
    <a class="result__snippet">Hundreds feared trapped.</a>
  </div>
</div>
<div class="result"><a class="result__a">no href here</a></div>
"""


def test_clean_ddg_url_unwraps_the_redirect():
    wrapped = "//duckduckgo.com/l/?uddg=https%3A%2F%2Freuters.com%2Fa%3Fx%3D1&rut=z"
    assert _clean_ddg_url(wrapped) == "https://reuters.com/a?x=1"


def test_clean_ddg_url_passes_plain_urls_through():
    assert _clean_ddg_url("https://example.com/x") == "https://example.com/x"


def test_parse_ddg_extracts_title_url_snippet_and_drops_hrefless():
    results = _parse_ddg(SAMPLE, max_results=5)
    assert len(results) == 2  # the third, href-less anchor is dropped
    assert results[0] == {
        "title": "Reuters: Magnitude 7.7 quake hits near Mandalay",
        "url": "https://reuters.com/world/quake",
        "snippet": "A powerful earthquake struck central Myanmar on Friday.",
    }
    assert results[1]["url"] == "https://aljazeera.com/quake"
    assert results[1]["snippet"] == "Hundreds feared trapped."


def test_parse_ddg_respects_max_results():
    assert len(_parse_ddg(SAMPLE, max_results=1)) == 1


def test_web_search_posts_and_returns_json(monkeypatch):
    calls = {}

    class FakeResponse:
        text = SAMPLE

        def raise_for_status(self):
            calls["raised"] = True

    def fake_post(url, **kwargs):
        calls["url"] = url
        calls["query"] = kwargs["data"]["q"]
        assert "User-Agent" in kwargs["headers"]
        return FakeResponse()

    monkeypatch.setattr(tools.httpx, "post", fake_post)
    out = json.loads(web_search("Mandalay earthquake", max_results=2))
    assert calls["query"] == "Mandalay earthquake"
    assert out["result_count"] == 2
    assert out["results"][0]["url"] == "https://reuters.com/world/quake"
