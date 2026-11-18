from openai import RateLimitError

from src.inference import complete_research


MAX_OUTPUT_TOKENS = 500
MAX_CHUNK_CHARS = 3500


def build_context(research_results):

    context_parts = []

    for result in research_results:

        text = result.get(
            "text",
            ""
        )

        # Limit each chunk so downstream agents
        # don't receive unnecessary tokens.
        text = text[:MAX_CHUNK_CHARS]

        context_parts.append(
            f"Source: {result.get('source', 'Unknown')}\n"
            f"Page: {result.get('page', 'Unknown')}\n"
            f"{text}"
        )

    return "\n\n".join(context_parts)


def run_analysis_agent(
    question,
    research_results
):

    if not research_results:

        return (
            "No research evidence was retrieved."
        )


    context = build_context(
        research_results
    )


    prompt = f"""
You are the Analysis Agent in a research assistant.

Question:
{question}

Evidence:
{context}

Analyze ONLY the supplied evidence.

Provide:

1. Key findings relevant to the question.
2. Important technical evidence.
3. Results or comparisons supported by the paper.
4. A short conclusion.

Rules:
- Do not invent facts.
- Do not use outside knowledge.
- Mention page numbers.
- Keep the analysis concise.
- If evidence is insufficient, say so.
"""


    try:

        content = complete_research(
            "analysis",

            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a concise, "
                        "evidence-grounded research analyst."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],

            max_tokens=MAX_OUTPUT_TOKENS
        )

        return content


    except RateLimitError:

        return (
            "Analysis could not be completed because "
            "the research model rate limit was reached. "
            "The retrieved evidence is still available."
        )


if __name__ == "__main__":

    from src.agents.research_agent import (
        run_research_agent
    )

    question = input(
        "\nEnter your research question: "
    )

    research_results = run_research_agent(
        question,
        top_k=3
    )

    analysis = run_analysis_agent(
        question,
        research_results
    )

    print("\n" + "=" * 70)
    print("ANALYSIS AGENT")
    print("=" * 70)

    print(analysis)