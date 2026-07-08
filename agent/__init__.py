"""The generative layer — everything that wakes a model lives here.

Deterministic pipeline code lives in ``scripts/`` and never calls a model
(CLAUDE.md); this package sits on the other side of that line. The gate
decides *whether* the model wakes (PRD §3); ``agent.daily`` is the daily
sitrep entrypoint. The reusable, project-agnostic tool-calling loop lives
in ``harness/``; this package holds the HADR-specific wiring on top of it.
"""
