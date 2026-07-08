"""Level 3 — one tool.

Levels so far: (1) a chat loop — read input, send the messages array,
print the reply; (2) standing orders — a system prompt from a text file.
Level 3 registers a tool: the model asks, your code runs it, and the
result goes back into the messages.

The harness stays generic — a `Tool` is a name, a description, a JSON
schema, and a plain function. Projects define their own and pass them in.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import anthropic

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")


@dataclass(frozen=True)
class Tool:
    """A capability the model may request: schema for the model, fn for us."""

    name: str
    description: str
    input_schema: dict
    fn: Callable[..., str]

    def to_param(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


class Agent:
    def __init__(
        self,
        model: str | None = None,
        system: str | None = None,
        tools: list[Tool] | None = None,
        client: anthropic.Anthropic | None = None,
        max_tokens: int = 16000,
    ):
        self.client = client or anthropic.Anthropic()
        self.model = model or DEFAULT_MODEL
        self.system = system
        self.tools = {t.name: t for t in (tools or [])}
        self.max_tokens = max_tokens
        self.messages: list[dict] = []

    @classmethod
    def with_system_file(cls, path: str | Path, **kwargs) -> "Agent":
        """Standing orders from a text file (a goal.md, a CLAUDE.md, ...)."""
        return cls(system=Path(path).read_text(), **kwargs)

    def send(self, user_input: str) -> str:
        """One turn: append the user message, call the model, return its text."""
        self.messages.append({"role": "user", "content": user_input})
        response = self._create()
        if response.stop_reason == "tool_use":
            self.messages.append({"role": "assistant", "content": response.content})
            self.messages.append({"role": "user", "content": self._run_tools(response)})
            response = self._create()
        if response.stop_reason == "refusal":
            return "[the model declined this request]"
        # Echo the full content (including thinking blocks) back into history.
        self.messages.append({"role": "assistant", "content": response.content})
        return "".join(b.text for b in response.content if b.type == "text")

    def _create(self):
        request: dict = dict(
            model=self.model,
            max_tokens=self.max_tokens,
            thinking={"type": "adaptive"},
            messages=self.messages,
        )
        if self.system is not None:
            request["system"] = self.system
        if self.tools:
            request["tools"] = [t.to_param() for t in self.tools.values()]
        return self.client.messages.create(**request)

    def _run_tools(self, response) -> list[dict]:
        """Execute every tool_use block; all results go back in one message."""
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            results.append(self._run_tool(block))
        return results

    def _run_tool(self, block) -> dict:
        result: dict = {"type": "tool_result", "tool_use_id": block.id}
        tool = self.tools.get(block.name)
        if tool is None:
            return result | {"content": f"unknown tool: {block.name}", "is_error": True}
        try:
            return result | {"content": tool.fn(**block.input)}
        except Exception as exc:  # the model gets the error and can adapt
            return result | {"content": f"{type(exc).__name__}: {exc}", "is_error": True}
