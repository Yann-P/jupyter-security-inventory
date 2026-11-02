"""Tests for scripts/5_classify.py. A fake model stands in for DeepSeek or OpenAI."""

import importlib
import json
from types import SimpleNamespace

classify = importlib.import_module("5_classify")

GOOD_ANSWER = json.dumps(
    {
        "rationale": "pyproject.toml publishes it",
        "kind": "package",
        "deploys_live_service": None,
        "security_boundary": None,
    }
)


class FakeModel:
    """Gives these answers, one per request, and remembers the requests."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.requests = []
        self.chat = SimpleNamespace(completions=self)

    def create(self, **request):
        self.requests.append(request)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.answers.pop(0)))])


def test_ask_asks_again_when_the_answer_is_empty_or_invalid():
    model = FakeModel("", '{"kind": "not a kind"}', GOOD_ANSWER)
    assert classify.ask(model, "deepseek-flash", "evidence").kind == "package"
    assert len(model.requests) == 3


def test_ask_rejects_free_text_longer_than_the_site_should_show():
    too_long = json.loads(GOOD_ANSWER) | {"security_boundary": "authenticates users " * 20}
    model = FakeModel(json.dumps(too_long), GOOD_ANSWER)
    assert classify.ask(model, "deepseek-flash", "evidence").security_boundary is None
    assert len(model.requests) == 2


def test_thinking_is_turned_off_for_deepseek_only():
    deepseek, openai = FakeModel(GOOD_ANSWER), FakeModel(GOOD_ANSWER)
    classify.ask(deepseek, "deepseek-flash", "evidence")
    classify.ask(openai, "some-openai-model", "evidence")
    assert deepseek.requests[0]["reasoning_effort"] == "none"
    assert "reasoning_effort" not in openai.requests[0]
