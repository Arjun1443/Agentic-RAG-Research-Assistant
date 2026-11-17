from types import SimpleNamespace
import pytest
from fastapi_app import writer


def fake_model(monkeypatch, content='A clear proposed approach.', finish='stop'):
    calls = []
    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content), finish_reason=finish)])
    monkeypatch.setattr(writer, 'get_groq_client', lambda: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    return calls


def test_topic_only_draft_and_natural_style(monkeypatch):
    calls = fake_model(monkeypatch)
    result = writer.generate_section('Emergency vehicle detection', 'Introduction')
    assert result['text'] == 'A clear proposed approach.'
    assert result['sources'] == [] and not result['evidence_based']
    assert 'Natural, clear prose' in calls[0]['messages'][0]['content']
    assert 'Emergency vehicle detection' in calls[0]['messages'][1]['content']
    assert 'Never invent' in calls[0]['messages'][0]['content']


def test_style_length_and_sources(monkeypatch):
    calls = fake_model(monkeypatch)
    evidence = [{'source': 'paper.pdf', 'page': 3, 'text': 'Evidence'}]
    result = writer.generate_section('Topic', 'Methodology', 'Explain the steps', 'simple', 'detailed', evidence)
    assert result['evidence_based'] and result['sources'] == evidence
    assert 'Plain English' in calls[0]['messages'][0]['content']
    assert calls[0]['max_tokens'] == 2300
    assert 'paper.pdf' in calls[0]['messages'][1]['content']


@pytest.mark.parametrize('content,finish', [('', 'stop'), ('unfinished', 'length')])
def test_empty_or_truncated_drafts_are_not_returned(monkeypatch, content, finish):
    fake_model(monkeypatch, content, finish)
    with pytest.raises(ValueError):
        writer.generate_section('Topic', 'Abstract')
