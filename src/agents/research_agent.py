from src.retriever import search_documents


DEFAULT_TOP_K = 3


def run_research_agent(
    question,
    top_k=DEFAULT_TOP_K,
    source=None
):
    """
    Research Agent.

    Retrieves the most relevant research document chunks.

    Parameters
    ----------
    question : str
        User's research question.

    top_k : int
        Number of chunks to retrieve.

    source : str or None
        If provided, retrieval is restricted to that
        specific document.

        Example:
            source="1706.03762v7.pdf"

        If None, all indexed documents are searched.
    """

    results = search_documents(
        query=question,
        top_k=top_k,
        source=source
    )

    return results


if __name__ == "__main__":

    question = input(
        "\nEnter your research question: "
    )

    print(
        "\nSearch scope:"
    )

    print(
        "1. All Documents"
    )

    print(
        "2. Specific PDF"
    )

    choice = input(
        "\nEnter 1 or 2: "
    ).strip()


    source = None


    if choice == "2":

        source = input(
            "\nEnter PDF filename exactly "
            "(example: 1706.03762v7.pdf): "
        ).strip()


    results = run_research_agent(
        question=question,
        top_k=DEFAULT_TOP_K,
        source=source
    )


    print("\n" + "=" * 70)
    print("RESEARCH AGENT")
    print("=" * 70)


    if source:

        print(
            f"Search scope: {source}"
        )

    else:

        print(
            "Search scope: All Documents"
        )


    print(
        f"\nRetrieved {len(results)} "
        "relevant document chunks."
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
            "-" * 70
        )

        print(
            f"Source: {result.get('source', 'Unknown')}"
        )

        print(
            f"Page: {result.get('page', 'Unknown')}"
        )

        print(
            result.get(
                "text",
                ""
            )[:1200]
        )