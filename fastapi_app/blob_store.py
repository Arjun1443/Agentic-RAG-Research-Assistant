"""Private, immutable records for serverless persistence.

Records have independent keys: concurrent chats cannot overwrite each other.
Document manifests are committed only after their PDF and index payload exist.
"""
import hashlib
import json
import os
import secrets
import time
from datetime import datetime, timezone

from src.request_scope import scope, guest_user
from .storage import Storage


def enabled():
    return bool(os.getenv('BLOB_READ_WRITE_TOKEN') or os.getenv('BLOB_STORE_ID'))


def _client():
    from vercel.blob import sync
    return sync


def read(path):
    return _client().get_blob(path, access='private').body


def read_json(path):
    return json.loads(read(path))


def write(path, data):
    return _client().put_blob(path, data, access='private', add_random_suffix=False, allow_overwrite=False)


def write_json(path, value):
    write(path, json.dumps(value).encode())


def objects(prefix):
    return list(_client().query_blobs(prefix=prefix))


def records(prefix):
    return [read_json(item.pathname) for item in objects(prefix) if item.pathname.endswith('.json')]


def _id():
    return int(time.time() * 1000) * 1000 + secrets.randbelow(1000)


def _now():
    return datetime.now(timezone.utc).isoformat()


def document_prefix():
    user, workspace = scope.get()
    return f'research/documents/{user}/{workspace}/'


def document_key(source):
    return document_prefix() + hashlib.sha256(source.encode()).hexdigest() + '.json'


def document_records():
    return records(document_prefix())


def persist_document(source, pdf_path, collection):
    data = collection.get(where={'source':source}, include=['documents','metadatas','embeddings'])
    vectors = data.get('embeddings')
    data['embeddings'] = vectors.tolist() if hasattr(vectors, 'tolist') else vectors
    identifier = secrets.token_hex(16)
    root = f'research/assets/{scope.get()[0]}/{scope.get()[1]}/{identifier}'
    pdf_key, chunks_key = root + '.pdf', root + '.json'
    write(pdf_key, pdf_path.read_bytes())
    write_json(chunks_key, data)
    metadata = {'source':source, 'pages':len({m['page'] for m in data['metadatas']}),
                'chunks':len(data['ids']), 'pdf_key':pdf_key,'chunks_key':chunks_key,
                'created_at':_now(), 'document_hash':hashlib.sha256(pdf_path.read_bytes()).hexdigest()}
    # No manifest is visible to the library until all assets are durable.
    write_json(document_key(source), metadata)
    return metadata


def restore_pdf(source, destination):
    record = read_json(document_key(source))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(read(record['pdf_key']))


def hydrate(collection):
    remote = document_records()
    local = collection.get(include=['metadatas'])
    hashes = {m['source']:m.get('document_hash') for m in local['metadatas'] if m}
    names = set(hashes)
    remote_names = {d['source'] for d in remote}
    for source in names - remote_names:
        collection.delete(where={'source':source})
    for document in remote:
        if hashes.get(document['source']) != document.get('document_hash'):
            if document['source'] in names: collection.delete(where={'source':document['source']})
            payload = read_json(document['chunks_key'])
            collection.upsert(ids=payload['ids'], documents=payload['documents'], metadatas=payload['metadatas'], embeddings=payload['embeddings'])


def remove_document(source):
    record = read_json(document_key(source))
    _client().delete_blob(document_key(source))
    _client().delete_blob([record['pdf_key'],record['chunks_key']])


class BlobStorage:
    """Storage API backed by separate private records instead of /tmp SQLite."""
    def register(self, username, password):
        key = 'research/users/' + hashlib.sha256(username.encode()).hexdigest() + '.json'
        user = {'id':secrets.randbits(48)+1,'username':username,'password_hash':Storage._hash(password)}
        try:
            write_json(key, user)
        except Exception as exc:
            from vercel.blob import sync
            if isinstance(exc, sync.BlobError):
                try: read_json(key)
                except sync.BlobNotFoundError: raise exc
                raise ValueError('Username already exists.') from exc
            raise
        return user['id']

    def login(self, username, password):
        import hmac
        key='research/users/' + hashlib.sha256(username.encode()).hexdigest() + '.json'
        from vercel.blob import sync
        try: user=read_json(key)
        except sync.BlobNotFoundError: raise ValueError('Invalid credentials.')
        _, salt, expected=user['password_hash'].split('$')
        actual=hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),600000).hex()
        if not hmac.compare_digest(actual,expected): raise ValueError('Invalid credentials.')
        token=secrets.token_urlsafe(32)
        write_json('research/sessions/'+hashlib.sha256(token.encode()).hexdigest()+'.json',{'user_id':user['id'],'expires':time.time()+7*86400})
        return token,user['id']

    def user_for_token(self, token):
        if not token: return guest_user.get()
        from vercel.blob import sync
        try:
            session=read_json('research/sessions/'+hashlib.sha256(token.encode()).hexdigest()+'.json')
            return session['user_id'] if session.get('expires',0)>time.time() else 0
        except sync.BlobNotFoundError: return 0

    def logout(self, token):
        if token: _client().delete_blob('research/sessions/'+hashlib.sha256(token.encode()).hexdigest()+'.json')

    def add_workspace(self,user_id,name):
        identifier=_id()
        write_json(f'research/workspaces/{user_id}/{identifier}.json',{'id':identifier,'name':name,'created_at':_now()})
        return identifier

    def workspaces(self,user_id):
        return sorted(records(f'research/workspaces/{user_id}/'),key=lambda x:x['id'],reverse=True)

    def workspace_owned_by(self,user_id,workspace_id):
        return workspace_id==0 or any(w['id']==workspace_id for w in self.workspaces(user_id))

    def save_chat(self,user_id,workspace_id,question,result):
        identifier=_id()
        write_json(f'research/chats/{user_id}/{identifier}.json',{'id':identifier,'workspace_id':workspace_id or 0,'question':question,'result':result,'created_at':_now()})
        return identifier

    def history(self,user_id,workspace_id=None):
        rows=records(f'research/chats/{user_id}/')
        if workspace_id is not None: rows=[r for r in rows if r['workspace_id']==workspace_id]
        return sorted(rows,key=lambda x:x['id'],reverse=True)[:200]

    def save_diagram(self,user_id,workspace_id,diagram):
        identifier=_id()
        record=dict(diagram,id=identifier,workspace_id=workspace_id,created_at=_now(),updated_at=_now(),version=1)
        write_json(f'research/diagrams/{user_id}/{identifier}/1.json',record)
        return record

    def diagrams(self,user_id,workspace_id):
        latest={}
        for r in records(f'research/diagrams/{user_id}/'):
            if r['workspace_id']==workspace_id and r['version']>latest.get(r['id'],{}).get('version',0): latest[r['id']]=r
        return sorted(latest.values(),key=lambda x:x['updated_at'],reverse=True)

    def diagram(self,user_id,diagram_id):
        versions=self.diagram_versions(user_id,diagram_id)
        return versions[0] if versions else None

    def diagram_versions(self,user_id,diagram_id):
        return sorted(records(f'research/diagrams/{user_id}/{diagram_id}/'),key=lambda x:x['version'],reverse=True)

    def update_diagram(self,user_id,diagram_id,diagram):
        current=self.diagram(user_id,diagram_id)
        if not current:return None
        version=_id()
        record=dict(diagram,id=diagram_id,workspace_id=current['workspace_id'],created_at=current['created_at'],updated_at=_now(),version=version)
        write_json(f'research/diagrams/{user_id}/{diagram_id}/{version}.json',record)
        return record

    def restore_diagram(self,user_id,diagram_id,version):
        match=next((v for v in self.diagram_versions(user_id,diagram_id) if v['version']==version),None)
        return self.update_diagram(user_id,diagram_id,match) if match else None
