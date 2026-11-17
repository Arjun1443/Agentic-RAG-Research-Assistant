import os
from pathlib import Path

import chromadb
import re
from collections import Counter


DB_PATH = str(Path(__file__).resolve().parents[1] / "data" / "chroma_db")
COLLECTION_NAME = "research_documents"


def _tokens(text):
    return re.findall(r"[a-z0-9]{2,}", text.lower())


def _keyword_score(query, text):
    query_tokens = Counter(_tokens(query))
    text_tokens = Counter(_tokens(text))
    if not query_tokens:
        return 0.0
    return sum(min(count, text_tokens[token]) for token, count in query_tokens.items()) / sum(query_tokens.values())


def _rrf(rank, weight):
    return weight / (60 + rank)


# ============================================================
# GET CHROMADB COLLECTION
# ============================================================

def get_collection():
    """
    Connect to the existing ChromaDB collection.
    """

    client = chromadb.PersistentClient(
        path=DB_PATH
    )

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME
    )

    return collection


# ============================================================
# INTERNAL: FORMAT CHROMA RESULTS
# ============================================================

def _format_results(results):
    """
    Convert ChromaDB query results into the format used
    throughout the project.
    """

    retrieved_documents = []

    documents = results.get(
        "documents",
        [[]]
    )[0]

    metadatas = results.get(
        "metadatas",
        [[]]
    )[0]

    distances = results.get(
        "distances",
        [[]]
    )[0] if results.get("distances") else []

    for index, (document, metadata) in enumerate(
        zip(
            documents,
            metadatas
        )
    ):

        distance = None

        if index < len(distances):
            distance = distances[index]

        retrieved_documents.append(
            {
                "text": document,

                "source": metadata.get(
                    "source",
                    "Unknown"
                ),

                "page": metadata.get(
                    "page",
                    "Unknown"
                ),

                "_distance": distance
            }
        )

    return retrieved_documents


# ============================================================
# SEARCH ONE SPECIFIC DOCUMENT
# ============================================================

def _search_single_document(
    collection,
    query,
    top_k,
    source
):
    """
    Search only one specific document.
    """

    results = collection.query(
        query_texts=[query],
        n_results=max(top_k * 3, 10),
        where={
            "source": source
        }
    )

    semantic = _format_results(results)
    return _hybrid_rerank(query, semantic, top_k)


def _hybrid_rerank(query, semantic_results, top_k):
    keyword_results = sorted(
        semantic_results,
        key=lambda item: _keyword_score(query, item["text"]),
        reverse=True,
    )
    ranks = {}
    for rank, item in enumerate(semantic_results, 1):
        ranks[(item["source"], item["page"], item["text"])] = _rrf(rank, 1.0)
    for rank, item in enumerate(keyword_results, 1):
        key = (item["source"], item["page"], item["text"])
        ranks[key] = ranks.get(key, 0.0) + _rrf(rank, 0.8) + _keyword_score(query, item["text"]) * 0.2
    return [
        {key: value for key, value in item.items() if not key.startswith("_")}
        for item in sorted(
            semantic_results,
            key=lambda item: ranks[(item["source"], item["page"], item["text"])],
            reverse=True,
        )[:top_k]
    ]


# ============================================================
# SEARCH ALL DOCUMENTS
# ============================================================

def _search_all_documents(
    collection,
    query,
    top_k
):
    """
    Search each indexed document independently.

    This prevents one document from dominating the top-k
    results in cross-document questions.
    """

    documents = list_indexed_documents()

    if not documents:
        return []


    # --------------------------------------------------------
    # Determine how many chunks to retrieve from each paper.
    #
    # Example:
    # 2 documents + top_k=4
    # → 2 chunks from each.
    #
    # 3 documents + top_k=3
    # → 1 chunk from each.
    # --------------------------------------------------------

    per_document = max(
        1,
        top_k // len(documents)
    )


    all_results = []


    for source in documents:

        try:

            results = _search_single_document(
                collection=collection,
                query=query,
                top_k=per_document,
                source=source
            )

            all_results.extend(
                results
            )

        except Exception:
            # Ignore a document-level retrieval failure
            # and continue searching other documents.
            continue


    # --------------------------------------------------------
    # If integer division gave fewer than top_k results,
    # retrieve additional global results as a supplement.
    # --------------------------------------------------------

    if len(all_results) < top_k:

        try:

            global_results = collection.query(
                query_texts=[query],
                n_results=top_k
            )

            extra_results = _format_results(
                global_results
            )

            existing_keys = {
                (
                    item["source"],
                    item["page"],
                    item["text"]
                )
                for item in all_results
            }

            for item in extra_results:

                key = (
                    item["source"],
                    item["page"],
                    item["text"]
                )

                if key not in existing_keys:

                    all_results.append(item)

                    existing_keys.add(
                        key
                    )

                if len(all_results) >= top_k:
                    break

        except Exception:
            pass


    # --------------------------------------------------------
    # Sort by semantic distance if available.
    # Lower distance = more relevant in Chroma's
    # default distance-based results.
    # --------------------------------------------------------

    with_distance = [
        item
        for item in all_results
        if item.get("_distance") is not None
    ]

    without_distance = [
        item
        for item in all_results
        if item.get("_distance") is None
    ]


    with_distance.sort(
        key=lambda item: item["_distance"]
    )


    final_results = _hybrid_rerank(query, with_distance + without_distance, top_k)


    # --------------------------------------------------------
    # Remove internal distance field before returning.
    # --------------------------------------------------------

    cleaned_results = []

    for item in final_results[:top_k]:

        cleaned_results.append(
            {
                "text": item["text"],
                "source": item["source"],
                "page": item["page"]
            }
        )

    return cleaned_results


# ============================================================
# SEARCH DOCUMENTS
# ============================================================

def search_documents(
    query,
    top_k=5,
    source=None
):
    """
    Search the vector database.

    If source is provided:
        search only that specific document.

    If source is None:
        perform balanced retrieval across all indexed
        documents so that cross-document questions have
        evidence from multiple papers.
    """

    collection = get_collection()


    if source:

        return _search_single_document(
            collection=collection,
            query=query,
            top_k=top_k,
            source=source
        )


    return _search_all_documents(
        collection=collection,
        query=query,
        top_k=top_k
    )


# ============================================================
# LIST INDEXED DOCUMENTS
# ============================================================

def list_indexed_documents():
    """
    Return all unique document names stored in ChromaDB.
    """

    collection = get_collection()

    data = collection.get(
        include=["metadatas"]
    )

    documents = set()

    for metadata in data.get(
        "metadatas",
        []
    ):

        if metadata:

            source = metadata.get(
                "source"
            )

            if source:

                documents.add(
                    source
                )

    return sorted(
        documents
    )


# ============================================================
# CHECK DOCUMENT EXISTENCE
# ============================================================

def document_exists(
    source_name
):
    """
    Check whether a document is already indexed.
    """

    collection = get_collection()

    data = collection.get(
        where={
            "source": source_name
        },
        limit=1
    )

    return bool(
        data.get(
            "ids",
            []
        )
    )


def find_duplicate_document(document_hash=None, text_hash=None, sample_text=None, threshold=0.92):
    collection = get_collection()
    data = collection.get(include=["documents", "metadatas"])
    documents = data.get("documents", [])
    metadatas = data.get("metadatas", [])
    for metadata in metadatas:
        if metadata and document_hash and metadata.get("document_hash") == document_hash:
            return {"source": metadata.get("source"), "kind": "exact_hash", "score": 1.0}
        if metadata and text_hash and metadata.get("text_hash") == text_hash:
            return {"source": metadata.get("source"), "kind": "text_hash", "score": 1.0}
    if sample_text and documents:
        nearest = collection.query(query_texts=[sample_text], n_results=1)
        distance = (nearest.get("distances") or [[]])[0]
        if distance and distance[0] <= (1 - threshold):
            nearest_meta = (nearest.get("metadatas") or [[]])[0]
            if nearest_meta:
                return {"source": nearest_meta[0].get("source"), "kind": "semantic", "score": round(1 - distance[0], 4)}
    return None


# ============================================================
# DOCUMENT STATISTICS
# ============================================================

def get_document_statistics(
    source_name=None
):
    """
    Return statistics for the whole database or
    one specific document.
    """

    collection = get_collection()

    if source_name:

        data = collection.get(
            where={
                "source": source_name
            },
            include=[
                "metadatas"
            ]
        )

        chunk_count = len(
            data.get(
                "ids",
                []
            )
        )

        pages = set()

        for metadata in data.get(
            "metadatas",
            []
        ):

            if metadata:

                page = metadata.get(
                    "page"
                )

                if page is not None:

                    pages.add(
                        page
                    )

        return {
            "source": source_name,
            "chunks": chunk_count,
            "pages": len(pages)
        }


    return {
        "total_chunks": collection.count(),
        "documents": len(
            list_indexed_documents()
        )
    }


# ============================================================
# DELETE DOCUMENT
# ============================================================

def delete_document(
    source_name
):
    """
    Remove all chunks belonging to one document
    from ChromaDB.

    Also removes the original uploaded PDF when
    that file exists locally.
    """

    collection = get_collection()

    data = collection.get(
        where={
            "source": source_name
        }
    )

    ids = data.get(
        "ids",
        []
    )

    if not ids:

        return {
            "deleted": False,
            "source": source_name,
            "chunks_removed": 0,
            "message": (
                "Document was not found in ChromaDB."
            )
        }


    collection.delete(
        ids=ids
    )


    pdf_path = os.path.join(
        "data",
        "documents",
        source_name
    )

    file_removed = False


    if os.path.exists(pdf_path):

        try:

            os.remove(
                pdf_path
            )

            file_removed = True

        except OSError:

            file_removed = False


    return {
        "deleted": True,
        "source": source_name,
        "chunks_removed": len(ids),
        "file_removed": file_removed,
        "message": (
            "Document removed successfully."
        )
    }


# ============================================================
# COMMAND-LINE TEST
# ============================================================

if __name__ == "__main__":

    print("\nIndexed Documents:")
    print("=" * 70)

    documents = list_indexed_documents()


    if documents:

        for document in documents:

            stats = get_document_statistics(
                document
            )

            print(
                f"📄 {document}"
            )

            print(
                f"   Pages: {stats['pages']}"
            )

            print(
                f"   Chunks: {stats['chunks']}"
            )

    else:

        print(
            "No documents indexed."
        )


    print(
        "\nRetriever module loaded successfully."
    )


    # --------------------------------------------------------
    # Example balanced multi-document search
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("MULTI-DOCUMENT SEARCH TEST")
    print("=" * 70)


    test_query = (
        "What are the main differences between "
        "BERT and the Transformer architecture?"
    )


    print(
        f"\nQuery: {test_query}"
    )


    results = search_documents(
        query=test_query,
        top_k=4,
        source=None
    )


    for index, result in enumerate(
        results,
        start=1
    ):

        print(
            "\n" + "-" * 70
        )

        print(
            f"Result {index}"
        )

        print(
            f"Source: {result['source']}"
        )

        print(
            f"Page: {result['page']}"
        )

        print(
            result["text"][:1000]
        )