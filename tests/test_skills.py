"""The generic skill subsystem: parsing SKILL.md, discovery, and running an
invoked skill as a scoped sub-agent — all with a stubbed client, no network."""

import copy
from types import SimpleNamespace as NS

from harness import Agent, Skill, Tool, discover_skills, parse_skill

ADD = Tool("add", "adds two ints", {"type": "object"}, lambda a, b: str(a + b))
SEARCH = Tool("web_search", "searches", {"type": "object"}, lambda query: "[]")


class FakeClient:
    """Yields scripted responses; records every request (parent and child)."""

    def __init__(self, responses):
        self._responses = iter(responses)
        self.requests = []
        self.messages = NS(create=self._create)

    def _create(self, **request):
        self.requests.append(copy.deepcopy(request))
        return next(self._responses)


def text(content):
    return NS(stop_reason="end_turn", content=[NS(type="text", text=content)])


def tool_use(*calls):
    return NS(
        stop_reason="tool_use",
        content=[
            NS(type="tool_use", id=f"t{i}", name=n, input=kw)
            for i, (n, kw) in enumerate(calls)
        ],
    )


# ---- parsing -------------------------------------------------------------

def test_front_matter_supplies_name_description_model_and_tools():
    skill = parse_skill(
        '---\n'
        'name: news-summary\n'
        'description: "Check the wires."\n'
        'model: claude-opus-4-8\n'
        'tools: web_search, fetch_feed\n'
        '---\n'
        '\n'
        'Body instructions here.\n'
    )
    assert skill.name == "news-summary"
    assert skill.description == "Check the wires."
    assert skill.model == "claude-opus-4-8"
    assert skill.tools == ("web_search", "fetch_feed")
    assert skill.instructions == "Body instructions here."


def test_bracketed_tools_list_parses():
    skill = parse_skill("---\nname: s\ntools: [a, b]\n---\nx")
    assert skill.tools == ("a", "b")


def test_comment_and_blank_lines_in_front_matter_are_ignored():
    skill = parse_skill("---\n# a banner comment\n\nname: s\n---\nbody")
    assert skill.name == "s"


def test_no_front_matter_falls_back_to_folder_name_and_first_line():
    skill = parse_skill("# My Skill\n\nDoes a thing.", fallback_name="my-skill")
    assert skill.name == "my-skill"
    assert skill.description == "My Skill"  # heading, hashes stripped
    assert skill.instructions.startswith("# My Skill")


def test_tool_name_is_sanitised_for_the_api():
    assert Skill("news summary!", "", "").tool_name == "news_summary"
    assert Skill("news-summary", "", "").tool_name == "news-summary"


# ---- discovery -----------------------------------------------------------

def test_discover_reads_every_skill_folder_sorted(tmp_path):
    (tmp_path / "beta").mkdir()
    (tmp_path / "beta" / "SKILL.md").write_text("---\nname: beta\n---\nb")
    (tmp_path / "alpha").mkdir()
    (tmp_path / "alpha" / "SKILL.md").write_text("---\nname: alpha\n---\na")
    skills = discover_skills(tmp_path)
    assert [s.name for s in skills] == ["alpha", "beta"]


def test_discover_missing_dir_is_empty(tmp_path):
    assert discover_skills(tmp_path / "nope") == []


# ---- the agent exposes skills as tools -----------------------------------

def test_skill_is_advertised_as_a_tool_with_its_description():
    skill = Skill("news", "Check the wires.", "orders")
    agent = Agent(model="m", client=FakeClient([]), skills=[skill])
    assert "news" in agent.tools
    assert agent.tools["news"].description == "Check the wires."


def test_invoking_a_skill_runs_it_as_a_scoped_sub_agent():
    skill = Skill(
        name="news",
        description="Check the wires.",
        instructions="You check the news. Use web_search.",
        model="skill-model",
        tools=("web_search", "add"),
    )
    # parent: asks for the skill -> gets its result -> answers.
    # child:  one turn, returns prose.
    client = FakeClient(
        [tool_use(("news", {"request": "any quakes today?"})), text("sub found X"), text("done")]
    )
    agent = Agent(
        model="parent-model", client=client, tools=[ADD, SEARCH], skills=[skill]
    )
    assert agent.send("go") == "done"

    # Three API calls: parent, child, parent-again.
    assert len(client.requests) == 3
    child = client.requests[1]
    # The child ran under the skill's own instructions and model.
    assert child["system"] == "You check the news. Use web_search."
    assert child["model"] == "skill-model"
    assert child["messages"][0]["content"] == "any quakes today?"
    # It got exactly the local tools it named — both resolve keylessly.
    assert sorted(t.get("name") for t in child["tools"]) == ["add", "web_search"]
    # The skill's own result flowed back as the tool_result the parent saw.
    parent_second = client.requests[2]["messages"][-1]["content"]
    assert parent_second[0]["content"] == "sub found X"


def test_server_tools_ride_in_the_request_when_configured():
    """The server-tool plumbing still works for a project that has a key and
    registers one (SERVER_TOOLS is empty by default — see harness/skills.py)."""
    server = {"type": "web_search_20250305", "name": "web_search", "max_uses": 5}
    client = FakeClient([text("ok")])
    Agent(model="m", client=client, server_tools=[server]).send("go")
    assert server in client.requests[0]["tools"]


def test_skill_sub_agent_has_no_skills_of_its_own():
    """A skill can't recurse into another: the sub-agent carries none."""
    inner = Skill("inner", "d", "i")
    outer = Skill("outer", "d", "o", tools=())
    client = FakeClient([tool_use(("outer", {"request": "x"})), text("r"), text("done")])
    agent = Agent(model="m", client=client, skills=[inner, outer])
    agent.send("go")
    child_tools = client.requests[1].get("tools", [])
    assert child_tools == []  # no local tools named, and no skill tools leak in
