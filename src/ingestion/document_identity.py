import hashlib
import re
from pathlib import Path


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized_text_hash(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def semantic_signature(text: str) -> str:
    tokens = sorted(set(re.findall(r"[a-z0-9]{3,}", text.lower())))
    return hashlib.sha256(" ".join(tokens).encode("utf-8")).hexdigest()
