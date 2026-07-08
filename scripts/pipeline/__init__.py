"""Deterministic HADR pipeline: fetch → normalise → gate → diff → render.

Everything in this package is pure Python and never calls a model
(CLAUDE.md; PRD §3). It decides *whether* the model wakes up — the model
itself arrives in slice V2.
"""
