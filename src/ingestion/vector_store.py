from src.request_scope import data_dir, documents_dir
import os
from pathlib import Path

import chromadb

from .pdf_loader import load_pdf
from .text_splitter import create_chunks
from .document_identity import file_sha256, normalized_text_hash, semantic_signature


DB_PATH = str(Path(__file__).resolve().parents[2] / "data" / "chroma_db")
COLLECTION_NAME = "research_documents"


def get_chroma_collection():

    client = chromadb.PersistentClient(
        path=str(data_dir() / "chroma_db")
    )

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME
    )

    return collection


def add_pdf_to_vector_database(
    pdf_path,
    source_name=None
):
    """
    Load one PDF, create chunks, and add them to ChromaDB.

    Existing documents are preserved.
    """

    if not os.path.exists(pdf_path):

        raise FileNotFoundError(
            f"PDF not found: {pdf_path}"
        )

    if source_name is None:

        source_name = os.path.basename(
            pdf_path
        )

    print(
        f"\nLoading PDF: {source_name}"
    )

    pages = load_pdf(
        pdf_path
    )
    full_text = "\n".join(page["text"] for page in pages)
    document_hash = file_sha256(pdf_path)
    text_hash = normalized_text_hash(full_text)
    signature = semantic_signature(full_text)

    print(
        f"Loaded {len(pages)} pages."
    )

    print(
        "\nCreating text chunks..."
    )

    chunks = create_chunks(
        pages
    )

    print(
        f"Created {len(chunks)} chunks."
    )

    collection = get_chroma_collection()

    documents = []
    metadatas = []
    ids = []

    for index, chunk in enumerate(chunks):

        documents.append(
            chunk["text"]
        )

        metadatas.append(
            {
                "source": source_name,
                "page": chunk["page_number"],
                "document_hash": document_hash,
                "text_hash": text_hash,
                "semantic_signature": signature,
            }
        )

        safe_source = (
            source_name
            .replace(" ", "_")
            .replace(".", "_")
        )

        ids.append(
            f"{safe_source}_chunk_{index}"
        )

    print(
        "\nAdding chunks to ChromaDB..."
    )

    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )

    print(
        "\nPDF added successfully!"
    )

    print(
        f"Source: {source_name}"
    )

    print(
        f"Chunks added: {len(chunks)}"
    )

    print(
        f"Total documents in database: "
        f"{collection.count()}"
    )

    return {
        "source": source_name,
        "pages": len(pages),
        "chunks": len(chunks),
        "total_documents": collection.count()
    }


def create_vector_database():
    """
    Backward-compatible function for the original
    Transformer paper setup.
    """

    pdf_path = (
        "data/documents/"
        "transformer_paper.pdf"
    )

    return add_pdf_to_vector_database(
        pdf_path=pdf_path,
        source_name="transformer_paper.pdf"
    )


if __name__ == "__main__":

    create_vector_database()