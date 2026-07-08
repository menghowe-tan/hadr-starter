Intentionally empty. `--replay tests/fixtures/both-down` finds none of
`gdacs.json`, `usgs.json` or `reliefweb.xml`; `scripts.pipeline.fetch`
reports every feed `down`, which trips `health.evaluate`'s abort path
(both real-time feeds down, PRD §7). Used by the monitor/sitrep workflows'
`workflow_dispatch` scenario input to exercise the abort-blind exit code
end to end.
