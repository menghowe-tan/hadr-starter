`usgs.json` and `reliefweb.xml` copied verbatim from `../eventful/`;
`gdacs.json` is deliberately absent so `scripts.pipeline.fetch` reports
GDACS `down` (degraded, not abort — USGS still fresh). Used by the
monitor/sitrep workflows' `workflow_dispatch` scenario input to exercise
the degraded banner end to end.
