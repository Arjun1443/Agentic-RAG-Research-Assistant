import os

from dotenv import load_dotenv
from openai import OpenAI, RateLimitError


load_dotenv()


MODEL_NAME = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-20b"
)

MAX_OUTPUT_TOKENS = 500
MAX_CHUNK_CHARS = 3500


def get_groq_client():

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:

        raise ValueError(
            "GROQ_API_KEY was not found in the .env file."
        )

    return OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1"
    )


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


    client = get_groq_client()


    try:

        response = client.chat.completions.create(

            model=MODEL_NAME,

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

            temperature=0.1,

            max_tokens=MAX_OUTPUT_TOKENS
        )

        return response.choices[0].message.content


    except RateLimitError:

        return (
            "Analysis could not be completed because "
            "the Groq model rate limit was reached. "
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