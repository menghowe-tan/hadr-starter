"""Level 2 — standing orders.

Level 1 was a chat loop: read input, send the messages array, print the
reply. Level 2 adds a system prompt read from a text file and prepended to
every request — this is all CLAUDE.md is.
"""

from __future__ import annotations

import os
from pathlib import Path

import anthropic

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")


class Agent:
    def __init__(
        self,
        model: str | None = None,
        system: str | None = None,
        client: anthropic.Anthropic | None = None,
        max_tokens: int = 16000,
    ):
        self.client = client or anthropic.Anthropic()
        self.model = model or DEFAULT_MODEL
        self.system = system
        self.max_tokens = max_tokens
        self.messages: list[dict] = []

    @classmethod
    def with_system_file(cls, path: str | Path, **kwargs) -> "Agent":
        """Standing orders from a text file (a goal.md, a CLAUDE.md, ...)."""
        return cls(system=Path(path).read_text(), **kwargs)

    def send(self, user_input: str) -> str:
        """One turn: append the user message, call the model, return its text."""
        self.messages.append({"role": "user", "content": user_input})
        request: dict = dict(
            model=self.model,
            max_tokens=self.max_tokens,
            thinking={"type": "adaptive"},
            messages=self.messages,
        )
        if self.system is not None:
            request["system"] = self.system
        response = self.client.messages.create(**request)
        if response.stop_reason == "refusal":
            self.messages.pop()
            return "[the model declined this request]"
        # Echo the full content (including thinking blocks) back into history.
        self.messages.append({"role": "assistant", "content": response.content})
        return "".join(b.text for b in response.content if b.type == "text")
