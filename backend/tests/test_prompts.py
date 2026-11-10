import pytest
from jinja2.exceptions import UndefinedError

from app import prompts


@pytest.mark.parametrize("name", ["answer", "grade", "rewrite", "check"])
def test_every_prompt_renders_its_own_sample(name):
    prompt = prompts.load(name)
    messages = prompt.render(**prompt.sample)
    assert messages[0]["role"] == "system"
    assert messages[-1]["role"] == "user"
    assert "temperature" in prompt.parameters


def test_answer_prompt_numbers_the_passages():
    prompt = prompts.load("answer")
    messages = prompt.render(question="Q?", passages=[{"number": 7, "source": "a.md", "page": 2, "text": "Fact."}])
    assert "[7] (a.md, page 2)" in messages[0]["content"]
    assert messages[1]["content"] == "Q?"


def test_missing_inputs_fail_loudly():
    with pytest.raises(UndefinedError):
        prompts.load("answer").render(question="Q?")
