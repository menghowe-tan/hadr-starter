"""Level 1 — a chat loop.

Read input, send the messages array to the model, print the reply. The
`Agent` owns nothing but the conversation state and the client; everything
else (system prompt, tools) arrives in later levels.
"""

from __future__ import annotations

import os

import anthropic

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")


class Agent:
    def __init__(
        self,
        model: str | None = None,
        client: anthropic.Anthropic | None = None,
        max_tokens: int = 16000,
    ):
        self.client = client or anthropic.Anthropic()
        self.model = model or DEFAULT_MODEL
        self.max_tokens = max_tokens
        self.messages: list[dict] = []

    def send(self, user_input: str) -> str:
        """One turn: append the user message, call the model, return its text."""
        self.messages.append({"role": "user", "content": user_input})
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            thinking={"type": "adaptive"},
            messages=self.messages,
        )
        if response.stop_reason == "refusal":
            self.messages.pop()
            return "[the model declined this request]"
        # Echo the full content (including thinking blocks) back into history.
        self.messages.append({"role": "assistant", "content": response.content})
        return "".join(b.text for b in response.content if b.type == "text")
