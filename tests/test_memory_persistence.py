import json
from types import SimpleNamespace

import pytest
from fastapi_app import blob_store, main
from fastapi_app.storage import Storage
from fastapi.testclient import TestClient
from src.request_scope import scope


@pytest.fixture
def remote(monkeypatch):
    values={}
    class FakeBlob:
        def put_blob(self,key,body,**kwargs):
            if key in values: raise ValueError('Already exists')
            values[key]=bytes(body)
        def get_blob(self,key,**kwargs):
            return SimpleNamespace(body=values[key])
        def query_blobs(self,prefix):
            return iter([SimpleNamespace(pathname=p) for p in values if p.startswith(prefix)])
        def delete_blob(self,keys,**kwargs):
            for key in [keys] if isinstance(keys,str) else keys: values.pop(key,None)
    monkeypatch.setattr(blob_store,'_client',lambda:FakeBlob())
    return values


def test_chats_survive_fresh_storage_and_are_separate(remote):
    first=blob_store.BlobStorage()
    first.save_chat(42,1,'My topic',{'answer':'My answer','conversation_id':'one'})
    first.save_chat(43,1,'Other user',{'answer':'Private'})
    fresh=blob_store.BlobStorage()
    assert len(fresh.history(42,1))==1
    assert fresh.history(42,1)[0]['question']=='My topic'
    assert fresh.history(42,2)==[]


def test_document_commit_contains_vectors_and_can_rehydrate(remote,tmp_path):
    token=scope.set((42,7))
    try:
        pdf=tmp_path/'paper.pdf';pdf.write_bytes(b'%PDF-test')
        class Collection:
            def get(self,**kwargs):
                return {'ids':['one'],'documents':['Evidence text'],'metadatas':[{'source':'paper.pdf','page':1}],'embeddings':[[0.1,0.2]]}
        blob_store.persist_document('paper.pdf',pdf,Collection())
        assert blob_store.document_records()[0]['source']=='paper.pdf'
        class EmptyCollection:
            def get(self,**kwargs):return {'ids':[],'metadatas':[]}
            def upsert(self,**kwargs):self.saved=kwargs
        rebuilt=EmptyCollection();blob_store.hydrate(rebuilt)
        assert rebuilt.saved['embeddings']==[[0.1,0.2]]
        restored=tmp_path/'new'/'paper.pdf';blob_store.restore_pdf('paper.pdf',restored)
        assert restored.read_bytes()==b'%PDF-test'
    finally:scope.reset(token)


def test_followup_receives_only_selected_conversation(tmp_path,monkeypatch):
    storage=Storage(tmp_path/'test.sqlite3')
    monkeypatch.setattr(main,'STORAGE',storage)
    calls=[]
    def workflow(question,source,on_event=None,mode='simple',conversation=None):
        calls.append(conversation)
        return {'plan':{'question':question},'answer':'Answer to '+question,'sources':[],'critique':{'status':'PASS'}}
    monkeypatch.setattr(main,'run_supervisor',workflow)
    with TestClient(main.app) as client:
        assert client.post('/api/research',json={'question':'Explain BERT','conversation_id':'one'}).status_code==200
        assert client.post('/api/research',json={'question':'What are its limitations?','conversation_id':'one'}).status_code==200
        assert calls[1][0]['question']=='Explain BERT'
        assert client.post('/api/research',json={'question':'Different topic','conversation_id':'two'}).status_code==200
        assert calls[2]==[]
        assert len(client.get('/api/history?conversation_id=one').json())==2

def test_account_and_session_survive_new_storage_instance(remote):
    first=blob_store.BlobStorage()
    user=first.register('persistent-user','a-long-test-password')
    token, signed_in=first.login('persistent-user','a-long-test-password')
    assert signed_in==user
    second=blob_store.BlobStorage()
    assert second.user_for_token(token)==user
    workspace=second.add_workspace(user,'Research')
    assert first.workspace_owned_by(user,workspace)
    assert not first.workspace_owned_by(user+1,workspace)


def test_document_index_restores_without_embedding_download(remote,tmp_path):
    token=scope.set((42,7))
    try:
        pdf=tmp_path/'paper.pdf';pdf.write_bytes(b'%PDF test content')
        class Original:
            def get(self,**kwargs):
                return {'ids':['one'],'documents':['Text'],'metadatas':[{'source':'paper.pdf','page':1}],'embeddings':[[0.1,0.2]]}
        blob_store.persist_document('paper.pdf',pdf,Original())
        class ColdCollection:
            received=None
            def get(self,**kwargs):return {'metadatas':[]}
            def upsert(self,**payload):self.received=payload
        cold=ColdCollection();blob_store.hydrate(cold)
        assert cold.received['embeddings']==[[0.1,0.2]]
        restored=tmp_path/'new-instance'/'paper.pdf'
        blob_store.restore_pdf('paper.pdf',restored)
        assert restored.read_bytes()==pdf.read_bytes()
        assert blob_store.document_records()[0]['source']=='paper.pdf'
    finally:
        scope.reset(token)
