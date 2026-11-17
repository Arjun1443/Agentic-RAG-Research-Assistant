from io import BytesIO
from pathlib import Path
import zipfile

import fitz
import pytest
from fastapi.testclient import TestClient

from fastapi_app import main
from fastapi_app.storage import Storage
from fastapi_app.exports import export_text, latex_document
from src.request_scope import scope, data_dir


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "STORAGE", Storage(tmp_path / "test.sqlite3"))
    monkeypatch.setattr(main, "list_indexed_documents", lambda: [])
    with TestClient(main.app) as client:
        yield client


def sign_in(client, username):
    credentials={"username":username,"password":"test-password-123"}
    assert client.post("/api/auth/register",json=credentials).status_code == 200
    token=client.post("/api/auth/login",json=credentials).json()["token"]
    return {"Authorization":"Bearer " + token}


def test_workspace_ownership_and_logout(client):
    alice=sign_in(client,"alice")
    bob=sign_in(client,"bobby")
    workspace=client.post("/api/workspaces",headers=alice,json={"name":"Private"}).json()["id"]
    assert client.get("/api/documents",headers={**bob,"X-Workspace-Id":str(workspace)}).status_code == 403
    assert client.get(f"/api/workspaces/{workspace}/diagrams",headers=bob).status_code == 403
    assert client.get("/api/documents",headers={**alice,"X-Workspace-Id":str(workspace)}).status_code == 200
    assert client.post("/api/auth/logout",headers=alice).status_code == 204
    assert client.get("/api/history",headers=alice).status_code == 401


def test_default_workspaces_have_distinct_paths():
    first=scope.set((1,0))
    alice=data_dir()
    scope.reset(first)
    second=scope.set((2,0))
    bob=data_dir()
    scope.reset(second)
    assert alice != bob


def test_reports_are_complete_and_unicode_safe():
    text="Research α β\n" + ("Evidence " * 3000) + "\nEND_OF_DOCUMENT"
    content,_,_=export_text(text,"pdf")
    with fitz.open(stream=content,filetype="pdf") as doc:
        extracted="".join(p.get_text() for p in doc)
        assert len(doc)>1
        assert "END_OF_DOCUMENT" in extracted
    content,_,_=export_text(text,"docx")
    with zipfile.ZipFile(BytesIO(content)) as archive:
        assert b"END_OF_DOCUMENT" in archive.read("word/document.xml")
    tex=latex_document("# Test\nCosts $5 & rate 50%_value {x}\n" + r"\end{verbatim}")
    assert r"\$5" in tex and r"50\%\_value" in tex
    assert r"\begin{verbatim}" not in tex


def test_writing_export_formats(client):
    for format in ["pdf","docx","tex","md"]:
        response=client.post("/api/writing/export",json={"text":"# Project\nA complete draft.","format":format})
        assert response.status_code==200
        assert response.content
    assert client.post("/api/writing/export",json={"text":"Draft","format":"exe"}).status_code==400


def test_research_stream_error_is_actionable(client,monkeypatch):
    def fail(*args,**kwargs):
        raise ValueError("GROQ_API_KEY was not found")
    monkeypatch.setattr(main,"run_supervisor",fail)
    response=client.get("/api/research/stream",params={"question":"Summarize this paper"})
    assert '"event": "error"' in response.text
    assert "GROQ_API_KEY" in response.text


def test_history_is_scoped_and_report_is_owned(client):
    alice=sign_in(client,"alice")
    bob=sign_in(client,"bobby")
    alice_id=main.STORAGE.user_for_token(alice["Authorization"][7:])
    workspace=main.STORAGE.add_workspace(alice_id,"Second")
    result={"plan":{"question":"Question"},"answer":"Evidence","critique":{},"sources":[]}
    chat=main.STORAGE.save_chat(alice_id,workspace,"Question",result)
    assert client.get("/api/history",headers=alice).json()==[]
    assert len(client.get("/api/history",headers={**alice,"X-Workspace-Id":str(workspace)}).json())==1
    assert client.get(f"/api/reports/{chat}",headers=bob).status_code==404


def test_invalid_uploads_are_actionable(client,monkeypatch,tmp_path):
    monkeypatch.setattr(main,"document_exists",lambda name:False)
    monkeypatch.setattr(main,"documents_dir",lambda:tmp_path)
    assert client.post("/api/documents",files={"file":("bad.txt",b"text","text/plain")}).status_code==400
    assert client.post("/api/documents",files={"file":("empty.pdf",b"","application/pdf")}).status_code==400
    doc=fitz.open();doc.new_page();pdf=doc.tobytes();doc.close()
    response=client.post("/api/documents",files={"file":("scan.pdf",pdf,"application/pdf")})
    assert response.status_code==422
    assert "OCR" in response.json()["detail"]


def test_stream_saves_research_and_surfaces_failure(client, monkeypatch):
    def workflow(question, source, emit, mode, conversation=None):
        emit('research_completed', {'count': 1})
        return {'plan': {'question': question}, 'answer': 'Evidence-backed answer', 'critique': {'status': 'PASS'}, 'research': [{'source': 'paper.pdf', 'page': 1, 'text': 'Original passage'}], 'sources': [['paper.pdf', 1]], 'revision_rounds': 0}
    monkeypatch.setattr(main, 'run_supervisor', workflow)
    response = client.get('/api/research/stream', params={'question':'Explain this paper','mode':'technical'})
    assert '"event": "completed"' in response.text
    assert 'Original passage' in response.text
    assert len(client.get('/api/history').json()) == 1
    def broken(*args, **kwargs):
        raise RuntimeError('Provider quota reached. Retry later.')
    monkeypatch.setattr(main, 'run_supervisor', broken)
    response = client.get('/api/research/stream', params={'question':'Explain this paper'})
    assert '"event": "error"' in response.text
    assert 'Provider quota reached' in response.text


def test_discovery_parses_metadata_and_year(monkeypatch):
    from fastapi_app import discovery
    xml = b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/2401.01234v1</id><title> Evidence retrieval </title><summary>A grounded method.</summary><published>2024-01-01T00:00:00Z</published><author><name>A. Researcher</name></author></entry><entry><id>https://malicious.example/paper</id><title>Untrusted link</title></entry></feed>'''
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, size): return xml
    calls=[]
    def urlopen(request, timeout):
        calls.append(request.full_url)
        return Response()
    monkeypatch.setattr(discovery.urllib.request,'urlopen',urlopen)
    result=discovery.search_papers('retrieval generation',2024)
    assert len(result)==1
    assert result[0]['url']=='https://arxiv.org/abs/2401.01234v1'
    assert result[0]['authors']==['A. Researcher']
    assert '202401010000' in calls[0]
