import pytest

from fastapi_app.diagram_render import pdf_for, png_for, svg_for
from fastapi_app.storage import Storage
from src.agents import diagram_agent


def test_diagram_generation_repairs_invalid_mermaid(monkeypatch):
    responses = iter(
        [
            {
                "title": "Invalid",
                "mermaid_source": "flowchart TD\nA[Only one node]",
                "assumptions": [],
                "source_references": [],
            },
            {
                "title": "Workflow",
                "mermaid_source": "flowchart TD\nA[Start] --> B[End]",
                "assumptions": ["The process is sequential."],
                "source_references": [],
            },
        ]
    )
    monkeypatch.setattr(diagram_agent, "_request", lambda prompt: next(responses))

    result = diagram_agent.generate_diagram("A small workflow", "flowchart")

    assert result.title == "Workflow"
    assert "-->" in result.mermaid_source


def test_mermaid_rejects_unsafe_actions():
    with pytest.raises(diagram_agent.DiagramError):
        diagram_agent.validate_mermaid(
            "flowchart TD\nA[Start] --> B[End]\nclick B \"javascript:alert(1)\"",
            "flowchart",
        )


def test_mermaid_normalizes_common_qwen_output(monkeypatch):
    monkeypatch.setattr(
        diagram_agent,
        "_request",
        lambda prompt: {"mermaid_source": "```mermaid\n graph TD\n A[Start] -.-> B[End]\n```"},
    )
    result = diagram_agent.generate_diagram(
        "A short workflow",
        "flowchart",
        [],
    )
    assert result.mermaid_source.startswith("flowchart TD")
    assert "-.->" in result.mermaid_source
def test_diagram_versions_and_owner_checks(tmp_path):
    storage = Storage(tmp_path / "research.sqlite3")
    diagram = {
        "title": "Workflow",
        "diagram_type": "flowchart",
        "prompt": "A workflow",
        "mermaid_source": "flowchart TD\nA[Start] --> B[End]",
        "assumptions": [],
        "source_references": [{"source": "paper.pdf", "page": "1"}],
    }

    saved = storage.save_diagram(0, 0, diagram)
    saved["title"] = "Renamed"
    storage.update_diagram(0, saved["id"], saved)

    assert len(storage.diagram_versions(0, saved["id"])) == 2
    assert storage.diagram(99, saved["id"]) is None


def test_controlled_exports_are_generated():
    source = "flowchart TD\nA[Start] --> B[End]"
    assert "<svg" in svg_for(source, "Workflow")
    assert png_for(source, "Workflow").startswith(b"\x89PNG")
    assert pdf_for(source, "Workflow").startswith(b"%PDF")
