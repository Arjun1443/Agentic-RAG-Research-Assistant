import os

from dotenv import load_dotenv
from openai import OpenAI, RateLimitError


load_dotenv()


MODEL_NAME = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-20b"
)

MAX_OUTPUT_TOKENS = 400
MAX_CHUNK_CHARS = 3000


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

        text = text[:MAX_CHUNK_CHARS]

        context_parts.append(
            f"Source: {result.get('source', 'Unknown')}\n"
            f"Page: {result.get('page', 'Unknown')}\n"
            f"{text}"
        )

    return "\n\n".join(context_parts)


def run_critic_agent(
    question,
    research_results,
    analysis
):

    if not research_results:

        return {
            "status": "FAIL",
            "critique": (
                "No research evidence was provided."
            )
        }


    context = build_context(
        research_results
    )


    prompt = f"""
You are the Critic Agent.

Question:
{question}

Research evidence:
{context}

Analysis:
{analysis}

Check the analysis for:

1. Unsupported claims
2. Incorrect conclusions
3. Missing important evidence
4. Incorrect page references

Return exactly:

CRITIC VERDICT:
PASS or NEEDS_REVISION

SUPPORTED_POINTS:
- ...

UNSUPPORTED_OR_WEAK_POINTS:
- ...

RECOMMENDED_CORRECTIONS:
- ...

FINAL_CRITIC_COMMENT:
...

Rules:
- Use only the supplied evidence.
- Do not introduce outside knowledge.
- Be concise.
"""


    client = get_groq_client()


    try:

        response = client.chat.completions.create(

            model=MODEL_NAME,

            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a strict but concise "
                        "research evidence critic."
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

        critique = (
            response.choices[0]
            .message
            .content
        )


        if "NEEDS_REVISION" in critique.upper():

            status = "NEEDS_REVISION"

        else:

            status = "PASS"


        return {
            "status": status,
            "critique": critique
        }


    except RateLimitError:

        return {
            "status": "RATE_LIMITED",
            "critique": (
                "Critic verification could not be completed "
                "because the Groq model rate limit was reached."
            )
        }


if __name__ == "__main__":

    from src.agents.research_agent import (
        run_research_agent
    )

    from src.agents.analysis_agent import (
        run_analysis_agent
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


    result = run_critic_agent(
        question,
        research_results,
        analysis
    )


    print("\n" + "=" * 70)
    print("CRITIC AGENT")
    print("=" * 70)

    print(
        f"Status: {result['status']}"
    )

    print(
        "\n" + result["critique"]
    )