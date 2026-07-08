"""The reusable harness loop, exercised with a stubbed client — no API, no network."""

import copy
from types import SimpleNamespace as NS

import pytest

from harness import Agent, Tool

ADD = Tool("add", "adds two ints", {"type": "object"}, lambda a, b: str(a + b))
BOOM = Tool("boom", "always raises", {"type": "object"}, lambda: 1 / 0)


class FakeClient:
    """Yields scripted responses; records every request it was sent."""

    def __init__(self, responses):
        self._responses = iter(responses)
        self.requests = []
        self.messages = NS(create=self._create)

    def _create(self, **request):
        # snapshot: the agent mutates its messages list after the call
        self.requests.append(copy.deepcopy(request))
        return next(self._responses)


def text(content):
    return NS(stop_reason="end_turn", content=[NS(type="text", text=content)])


def tool_use(*calls):
    return NS(
        stop_reason="tool_use",
        content=[NS(type="tool_use", id=f"t{i}", name=n, input=kw) for i, (n, kw) in enumerate(calls)],
    )


def test_chat_returns_text_and_keeps_history():
    client = FakeClient([text("hello")])
    agent = Agent(model="m", client=client)
    assert agent.send("hi") == "hello"
    assert [m["role"] for m in agent.messages] == ["user", "assistant"]


def test_system_prompt_prepended_from_file(tmp_path):
    orders = tmp_path / "goal.md"
    orders.write_text("stand by")
    client = FakeClient([text("ok")])
    Agent.with_system_file(orders, model="m", client=client).send("hi")
    assert client.requests[0]["system"] == "stand by"


def test_no_system_key_when_unset():
    client = FakeClient([text("ok")])
    Agent(model="m", client=client).send("hi")
    assert "system" not in client.requests[0]


def test_tool_roundtrip_and_loop_until_end_turn():
    client = FakeClient([tool_use(("add", {"a": 2, "b": 3})), tool_use(("add", {"a": 5, "b": 5})), text("10")])
    agent = Agent(model="m", tools=[ADD], client=client)
    assert agent.send("go") == "10"
    # two tool rounds happened before the final answer
    assert len(client.requests) == 3
    assert client.requests[0]["tools"][0]["name"] == "add"


def test_parallel_tool_results_land_in_one_user_message():
    client = FakeClient([tool_use(("add", {"a": 1, "b": 1}), ("add", {"a": 2, "b": 2})), text("done")])
    agent = Agent(model="m", tools=[ADD], client=client)
    agent.send("go")
    results = client.requests[1]["messages"][-1]["content"]
    assert [r["content"] for r in results] == ["2", "4"]
    assert all(r["type"] == "tool_result" for r in results)


def test_tool_errors_return_is_error_not_raise():
    client = FakeClient([tool_use(("boom", {}), ("missing", {})), text("recovered")])
    agent = Agent(model="m", tools=[BOOM], client=client)
    assert agent.send("go") == "recovered"
    results = client.requests[1]["messages"][-1]["content"]
    assert results[0]["is_error"] and "ZeroDivisionError" in results[0]["content"]
    assert results[1]["is_error"] and "unknown tool" in results[1]["content"]


def test_pause_turn_resends():
    paused = NS(stop_reason="pause_turn", content=[NS(type="text", text="…")])
    client = FakeClient([paused, text("resumed")])
    assert Agent(model="m", client=client).send("go") == "resumed"


def test_refusal_reported_without_crash():
    refused = NS(stop_reason="refusal", content=[])
    client = FakeClient([refused])
    assert "declined" in Agent(model="m", client=client).send("go")


def test_max_iterations_guard():
    endless = [tool_use(("add", {"a": 1, "b": 1}))] * 3
    client = FakeClient(endless)
    agent = Agent(model="m", tools=[ADD], client=client, max_iterations=3)
    with pytest.raises(RuntimeError, match="3 rounds"):
        agent.send("go")
