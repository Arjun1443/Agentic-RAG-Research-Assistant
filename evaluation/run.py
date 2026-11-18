"""Run a reproducible PDF retrieval and generation benchmark from the repo root."""
import argparse
from contextlib import redirect_stdout
import json
import os
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
from time import perf_counter

import fitz
import jax
import jax.numpy as jnp
import numpy as np
from tokenizers import Tokenizer
from transformers import AutoTokenizer

from src import request_scope
from src.agents.supervisor import create_supervisor_plan, run_supervisor
from src.inference import research_backend
from src.ingestion.vector_store import add_pdf_to_vector_database
from src.retriever import search_documents


CITATION = re.compile(r"\[([^\[\]\n]+\.pdf),\s*p\.\s*(\d+)\]", re.IGNORECASE)


@jax.jit
def ranking_metrics(hits, relevant_count):
    positions = jnp.arange(1, hits.size + 1, dtype=jnp.float32)
    return (
        jnp.sum(hits) / relevant_count,
        jnp.max(jnp.where(hits, 1 / positions, 0.0)),
    )


def score_pages(results, gold, k):
    pages = [(row["source"], row["page"]) for row in results[:k]]
    seen = set()
    hits = np.zeros(k, dtype=bool)
    for index, page in enumerate(pages):
        hits[index] = page in gold and page not in seen
        seen.add(page)
    recall, mrr = ranking_metrics(hits, len(gold))
    return {
        "page_recall_at_k": float(recall),
        "page_reciprocal_rank": float(mrr),
        "pages": pages,
    }


def cite_scores(answer, gold, retrieved):
    citations = [(source, int(page)) for source, page in CITATION.findall(answer)]
    unique_citations = set(citations)
    return {
        "citations": citations,
        "citation_gold_page_precision": (
            sum(page in gold for page in citations) / len(citations) if citations else None
        ),
        "citation_gold_page_recall": len(unique_citations & gold) / len(gold),
        "citation_retrieved_page_fraction": (
            sum(page in retrieved for page in citations) / len(citations) if citations else None
        ),
    }


def ingest_fixture(root, documents):
    for filename, pages in documents.items():
        path = root / filename
        with fitz.open() as pdf:
            for text in pages:
                pdf.new_page().insert_textbox(fitz.Rect(50, 60, 545, 750), text, fontsize=12)
            pdf.save(path)
        add_pdf_to_vector_database(path, filename)


def run_benchmark(fixture, backends, tokenizer_name):
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_name, use_fast=True, trust_remote_code=False)
    encoder = getattr(tokenizer, "backend_tokenizer", None)
    if not isinstance(encoder, Tokenizer):
        raise ValueError("Choose a model with a Hugging Face fast tokenizer.")
    rows = []
    for case in fixture["cases"]:
        question = case["question"]
        gold = {tuple(page) for page in case["pages"]}
        k = create_supervisor_plan(question)["settings"]["top_k"]
        row = {"question": question, "k": k, "gold_pages": case["pages"], "retrieval": {}, "generation": {}}
        for ranking in ("semantic", "hybrid"):
            started = perf_counter()
            passages = search_documents(question, top_k=k, ranking=ranking)
            elapsed = perf_counter() - started
            row["retrieval"][ranking] = {
                **score_pages(passages, gold, k),
                "retrieval_seconds": round(elapsed, 4),
                "evidence_text_tokens": sum(
                    len(encoded.ids) for encoded in encoder.encode_batch(
                        [item["text"] for item in passages], add_special_tokens=False
                    )
                ),
            }
        for backend in backends:
            os.environ["RAG_BACKEND"] = backend
            os.environ["RAG_CRITIC_BACKEND"] = backend
            _, model, _, _ = research_backend("synthesis")
            started = perf_counter()
            result = run_supervisor(question)
            elapsed = perf_counter() - started
            answer = result["answer"]
            retrieved = {(item["source"], item["page"]) for item in result["research"]}
            row["generation"][backend] = {
                "model": model,
                "workflow_seconds": round(elapsed, 4),
                "tracked_tokenizer_output_tokens": len(encoder.encode(answer, add_special_tokens=False).ids),
                "critic_status": result["critique"]["status"],
                "answer": answer,
                **cite_scores(answer, gold, retrieved),
            }
        rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tokenizer", required=True, help="Hugging Face model ID or local tokenizer directory")
    parser.add_argument("--backends", nargs="+", choices=["vllm", "sglang"], default=[])
    parser.add_argument("--fixture", type=Path, default=Path(__file__).with_name("sample.json"))
    args = parser.parse_args()
    if os.getenv("VERCEL") or os.getenv("BLOB_READ_WRITE_TOKEN"):
        parser.error("Use an offline workspace shell without Vercel Blob credentials.")
    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    with TemporaryDirectory() as directory, redirect_stdout(sys.stderr):
        request_scope.ROOT = Path(directory)
        for backend in args.backends:
            os.environ["RAG_BACKEND"] = backend
            research_backend("synthesis")
        ingest_fixture(Path(directory), fixture["documents"])
        rows = run_benchmark(fixture, args.backends, args.tokenizer)
    print(json.dumps({"tokenizer": args.tokenizer, "jax_device": jax.default_backend(), "cases": rows}, indent=2))


if __name__ == "__main__":
    main()
