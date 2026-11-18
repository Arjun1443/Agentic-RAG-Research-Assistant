import json

import httpx
from openai import OpenAI

from src import inference
from src.agents import supervisor


def test_research_routes_generation_and_critique_to_configured_engines(monkeypatch):
    calls = []

    def respond(request):
        body = json.loads(request.content)
        calls.append((request.url.host, request.url.path, body["model"]))
        content = (
            "CRITIC VERDICT:\nPASS"
            if request.url.host == "critic.example"
            else "Study A used mAP50 [study-a.pdf, p. 2]."
        )
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    def client(**kwargs):
        return OpenAI(http_client=httpx.Client(transport=httpx.MockTransport(respond)), **kwargs)

    for key, value in {
        "RAG_BACKEND": "vllm",
        "RAG_CRITIC_BACKEND": "sglang",
        "VLLM_BASE_URL": "https://generation.example/v1",
        "VLLM_API_KEY": "test-generation",
        "VLLM_MODEL": "generation-model",
        "SGLANG_BASE_URL": "https://critic.example/v1",
        "SGLANG_API_KEY": "test-critic",
        "SGLANG_MODEL": "critic-model",
    }.items():
        monkeypatch.setenv(key, value)

    monkeypatch.setattr(inference, "OpenAI", client)
    monkeypatch.setattr(supervisor, "run_research_agent", lambda **_: [
        {"source": "study-a.pdf", "page": 2, "text": "Study A used mAP50."}
    ])
    result = supervisor.run_supervisor("Which metric did study A use?")
    assert result["critique"]["status"] == "PASS"
    assert result["answer"].endswith("[study-a.pdf, p. 2].")
    assert calls == [
        ("generation.example", "/v1/chat/completions", "generation-model"),
        ("critic.example", "/v1/chat/completions", "critic-model"),
        ("generation.example", "/v1/chat/completions", "generation-model"),
    ]
