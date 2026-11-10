from app.agent.brains import NOT_FOUND, LLMBrain


def run(service, question):
    return list(service.ask_events(question))


def test_answers_with_citations_from_the_right_document(service):
    answer = service.ask("How many days of annual leave do full-time employees get?")
    assert "24 days" in answer["answer"]
    assert answer["citations"]
    assert all(c["source"] == "northwind-employee-handbook.md" for c in answer["citations"])
    assert answer["grounded"] is True
    assert [s["name"] for s in answer["steps"]] == ["route", "retrieve", "grade", "generate", "cite", "check"]


def test_streams_steps_then_tokens_then_done(service):
    events = run(service, "What is the hotel limit per night in metro cities?")
    kinds = [e["type"] for e in events]
    assert kinds[0] == "step" and kinds[-1] == "done"
    assert "token" in kinds
    text = "".join(e["text"] for e in events if e["type"] == "token")
    assert "9,000" in text


def test_rewrites_the_search_when_nothing_relevant_is_found(service):
    answer = service.ask("vacation?")
    names = [s["name"] for s in answer["steps"]]
    assert "rewrite" in names
    assert answer["search_query"] and "annual leave" in answer["search_query"]


def test_refuses_instead_of_guessing(service):
    answer = service.ask("What is the capital of Australia?")
    assert answer["answer"] == NOT_FOUND
    assert answer["citations"] == []


def test_small_talk_and_empty_library_skip_retrieval(settings):
    from app.service import RagService

    empty = RagService(settings)
    assert [s["name"] for s in empty.ask("hello!")["steps"]] == ["route"]
    assert "library is empty" in empty.ask("What is the leave policy?")["answer"]


class FakeModel:
    name = "fake/model"

    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    def complete(self, messages, **parameters):
        self.prompts.append(messages)
        return self.replies.pop(0)

    def stream(self, messages, **parameters):
        self.prompts.append(messages)
        yield from ["Employees get 24 days ", "of annual leave [1]. Unknown [9]."]


def test_llm_brain_uses_the_prompty_prompts_and_tolerates_bad_json():
    passages = [{"number": 1, "text": "24 days"}, {"number": 2, "text": "laptops"}]
    model = FakeModel(['Sure! {"relevant": [1, 5]}', "not json", '{"grounded": false}', "  pets in office policy\n"])
    brain = LLMBrain(model)
    assert brain.grade("leave?", passages) == [1]
    assert brain.grade("leave?", passages) == [1, 2]
    assert brain.check("answer", passages) is False
    assert brain.rewrite("can I bring my dog?") == "pets in office policy"
    assert "relevant" in model.prompts[0][0]["content"]


def test_agent_with_an_llm_drops_invalid_citations(service):
    service.agent.brain = LLMBrain(FakeModel(['{"relevant": [1]}', '{"grounded": true}']))
    answer = service.ask("How much annual leave?")
    assert [c["number"] for c in answer["citations"]] == [1]
    assert answer["steps"][3]["detail"].startswith("Wrote the answer with fake/model")
