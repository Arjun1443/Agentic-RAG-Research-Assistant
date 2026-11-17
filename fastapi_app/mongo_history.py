"""Optional MongoDB chat persistence; delegate accounts and documents unchanged."""
import os
from datetime import datetime, timezone
from uuid import uuid4


class MongoHistoryStorage:
    def __init__(self, base, collection=None):
        self.base = base
        self.client = None
        if collection is None:
            from pymongo import MongoClient
            self.client = MongoClient(
                os.environ["MONGODB_URI"], serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000, socketTimeoutMS=10000,
            )
            collection = self.client[os.getenv("MONGODB_DATABASE", "research_assistant")]["chats"]
        self.collection = collection
        self._indexed = False

    def __getattr__(self, name):
        return getattr(self.base, name)

    def _ensure_indexes(self):
        if not self._indexed:
            self.collection.create_index([("user_id", 1), ("workspace_id", 1), ("created_at", -1)])
            self.collection.create_index([("user_id", 1), ("created_at", -1)])
            self._indexed = True

    def save_chat(self, user_id, workspace_id, question, result):
        self._ensure_indexes()
        identifier = uuid4().hex
        self.collection.insert_one({
            "_id": identifier, "id": identifier, "user_id": user_id,
            "workspace_id": workspace_id or 0, "question": question,
            "result": result,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return identifier

    def history(self, user_id, workspace_id=None):
        self._ensure_indexes()
        query = {"user_id": user_id}
        if workspace_id is not None:
            query["workspace_id"] = workspace_id
        rows = list(self.collection.find(query, {"_id": 0, "user_id": 0}).sort("created_at", -1).limit(200))
        # Keep pre-MongoDB conversations visible without rewriting legacy storage.
        rows.extend(self.base.history(user_id, workspace_id))
        def timestamp(row):
            value = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
            return value.replace(tzinfo=value.tzinfo or timezone.utc).timestamp()
        return sorted(rows, key=timestamp, reverse=True)[:200]


def with_mongo_history(base):
    return MongoHistoryStorage(base) if os.getenv("MONGODB_URI", "").strip() else base
