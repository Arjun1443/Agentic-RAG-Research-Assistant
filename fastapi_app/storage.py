import hashlib
import json
import secrets
import sqlite3
from pathlib import Path


class Storage:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS workspaces (
                    id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
                    name TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS chats (
                    id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
                    workspace_id INTEGER, question TEXT NOT NULL, result_json TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS diagrams (
                    id INTEGER PRIMARY KEY,
                    workspace_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    title TEXT NOT NULL,
                    diagram_type TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    mermaid_source TEXT NOT NULL,
                    assumptions_json TEXT NOT NULL,
                    source_references_json TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS diagram_versions (
                    id INTEGER PRIMARY KEY,
                    diagram_id INTEGER NOT NULL REFERENCES diagrams(id) ON DELETE CASCADE,
                    version INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    diagram_type TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    mermaid_source TEXT NOT NULL,
                    assumptions_json TEXT NOT NULL,
                    source_references_json TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(diagram_id, version)
                );
                """
            )

    @staticmethod
    def _hash(password):
        return hashlib.sha256(password.encode()).hexdigest()

    def register(self, username, password):
        with sqlite3.connect(self.path) as db:
            try:
                cursor = db.execute("INSERT INTO users(username,password_hash) VALUES(?,?)", (username, self._hash(password)))
            except sqlite3.IntegrityError as exc:
                raise ValueError("Username already exists.") from exc
            return cursor.lastrowid

    def login(self, username, password):
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT id,password_hash FROM users WHERE username=?", (username,)).fetchone()
            if not row or row[1] != self._hash(password):
                raise ValueError("Invalid credentials.")
            token = secrets.token_urlsafe(32)
            db.execute("INSERT INTO sessions(token,user_id) VALUES(?,?)", (token, row[0]))
            return token, row[0]

    def user_for_token(self, token):
        if not token:
            return 0
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT user_id FROM sessions WHERE token=?", (token,)).fetchone()
            return row[0] if row else 0

    def add_workspace(self, user_id, name):
        with sqlite3.connect(self.path) as db:
            cursor = db.execute("INSERT INTO workspaces(user_id,name) VALUES(?,?)", (user_id, name))
            return cursor.lastrowid

    def workspaces(self, user_id):
        with sqlite3.connect(self.path) as db:
            return [{"id": row[0], "name": row[1], "created_at": row[2]} for row in db.execute(
                "SELECT id,name,created_at FROM workspaces WHERE user_id=? ORDER BY id DESC", (user_id,)
            )]

    def save_chat(self, user_id, workspace_id, question, result):
        with sqlite3.connect(self.path) as db:
            cursor = db.execute(
                "INSERT INTO chats(user_id,workspace_id,question,result_json) VALUES(?,?,?,?)",
                (user_id, workspace_id, question, json.dumps(result)),
            )
            return cursor.lastrowid

    def history(self, user_id, workspace_id=None):
        query = "SELECT id,workspace_id,question,result_json,created_at FROM chats WHERE user_id=?"
        args = [user_id]
        if workspace_id is not None:
            query += " AND workspace_id=?"
            args.append(workspace_id)
        query += " ORDER BY id DESC LIMIT 50"
        with sqlite3.connect(self.path) as db:
            return [
                {"id": row[0], "workspace_id": row[1], "question": row[2], "result": json.loads(row[3]), "created_at": row[4]}
                for row in db.execute(query, args)
            ]

    def workspace_owned_by(self, user_id, workspace_id):
        if workspace_id == 0 and user_id == 0:
            return True
        with sqlite3.connect(self.path) as db:
            return db.execute(
                "SELECT 1 FROM workspaces WHERE id=? AND user_id=?",
                (workspace_id, user_id),
            ).fetchone() is not None

    @staticmethod
    def _diagram_from_row(row):
        return {
            "id": row[0],
            "workspace_id": row[1],
            "title": row[2],
            "diagram_type": row[3],
            "prompt": row[4],
            "mermaid_source": row[5],
            "assumptions": json.loads(row[6]),
            "source_references": json.loads(row[7]),
            "created_at": row[8],
            "updated_at": row[9],
        }

    def save_diagram(self, user_id, workspace_id, diagram):
        values = (
            workspace_id,
            user_id,
            diagram["title"],
            diagram["diagram_type"],
            diagram["prompt"],
            diagram["mermaid_source"],
            json.dumps(diagram.get("assumptions", [])),
            json.dumps(diagram.get("source_references", [])),
        )
        with sqlite3.connect(self.path) as db:
            cursor = db.execute(
                """
                INSERT INTO diagrams(
                    workspace_id,user_id,title,diagram_type,prompt,mermaid_source,
                    assumptions_json,source_references_json
                ) VALUES(?,?,?,?,?,?,?,?)
                """,
                values,
            )
            diagram_id = cursor.lastrowid
            db.execute(
                """
                INSERT INTO diagram_versions(
                    diagram_id,version,title,diagram_type,prompt,mermaid_source,
                    assumptions_json,source_references_json
                ) VALUES(?,?,?,?,?,?,?,?)
                """,
                (diagram_id, 1, *values[2:]),
            )
        return self.diagram(user_id, diagram_id)

    def diagrams(self, user_id, workspace_id):
        with sqlite3.connect(self.path) as db:
            rows = db.execute(
                """
                SELECT id,workspace_id,title,diagram_type,prompt,mermaid_source,
                       assumptions_json,source_references_json,created_at,updated_at
                FROM diagrams WHERE user_id=? AND workspace_id=? ORDER BY updated_at DESC
                """,
                (user_id, workspace_id),
            ).fetchall()
        return [self._diagram_from_row(row) for row in rows]

    def diagram(self, user_id, diagram_id):
        with sqlite3.connect(self.path) as db:
            row = db.execute(
                """
                SELECT id,workspace_id,title,diagram_type,prompt,mermaid_source,
                       assumptions_json,source_references_json,created_at,updated_at
                FROM diagrams WHERE id=? AND user_id=?
                """,
                (diagram_id, user_id),
            ).fetchone()
        return self._diagram_from_row(row) if row else None

    def update_diagram(self, user_id, diagram_id, diagram):
        current = self.diagram(user_id, diagram_id)
        if not current:
            return None
        with sqlite3.connect(self.path) as db:
            version = db.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 FROM diagram_versions WHERE diagram_id=?",
                (diagram_id,),
            ).fetchone()[0]
            values = (
                diagram["title"],
                diagram["diagram_type"],
                diagram["prompt"],
                diagram["mermaid_source"],
                json.dumps(diagram.get("assumptions", [])),
                json.dumps(diagram.get("source_references", [])),
            )
            db.execute(
                """
                UPDATE diagrams SET title=?,diagram_type=?,prompt=?,mermaid_source=?,
                    assumptions_json=?,source_references_json=?,updated_at=CURRENT_TIMESTAMP
                WHERE id=? AND user_id=?
                """,
                (*values, diagram_id, user_id),
            )
            db.execute(
                """
                INSERT INTO diagram_versions(
                    diagram_id,version,title,diagram_type,prompt,mermaid_source,
                    assumptions_json,source_references_json
                ) VALUES(?,?,?,?,?,?,?,?)
                """,
                (diagram_id, version, *values),
            )
        return self.diagram(user_id, diagram_id)

    def diagram_versions(self, user_id, diagram_id):
        if not self.diagram(user_id, diagram_id):
            return None
        with sqlite3.connect(self.path) as db:
            rows = db.execute(
                """
                SELECT id,version,title,diagram_type,prompt,mermaid_source,
                       assumptions_json,source_references_json,created_at
                FROM diagram_versions WHERE diagram_id=? ORDER BY version DESC
                """,
                (diagram_id,),
            ).fetchall()
        return [
            {
                "id": row[0], "version": row[1], "title": row[2],
                "diagram_type": row[3], "prompt": row[4],
                "mermaid_source": row[5], "assumptions": json.loads(row[6]),
                "source_references": json.loads(row[7]), "created_at": row[8],
            }
            for row in rows
        ]

    def restore_diagram(self, user_id, diagram_id, version):
        versions = self.diagram_versions(user_id, diagram_id)
        match = next((item for item in versions or [] if item["version"] == version), None)
        if not match:
            return None
        return self.update_diagram(user_id, diagram_id, match)
