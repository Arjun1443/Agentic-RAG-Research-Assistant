import json

from src.agents.research_agent import run_research_agent
from src.agents.analysis_agent import run_analysis_agent
from src.agents.critic_agent import run_critic_agent
from src.agents.synthesis_agent import run_synthesis_agent


DEFAULT_TOP_K = 3
MAX_REVISION_ROUNDS = 1


# ============================================================
# SUPERVISOR PLANNER
# ============================================================

def create_supervisor_plan(question):

    question_lower = question.lower()

    if any(
        word in question_lower
        for word in [
            "compare",
            "comparison",
            "difference",
            "differences",
            "advantages",
            "versus",
            "vs"
        ]
    ):
        intent = "comparison"

    elif any(
        word in question_lower
        for word in [
            "summarize",
            "summary",
            "overview",
            "main contribution"
        ]
    ):
        intent = "summarization"

    elif any(
        word in question_lower
        for word in [
            "gap",
            "gaps",
            "future research",
            "research direction",
            "limitations"
        ]
    ):
        intent = "research_gaps"

    elif any(
        word in question_lower
        for word in [
            "idea",
            "ideas",
            "project",
            "future project"
        ]
    ):
        intent = "idea_generation"

    else:
        intent = "research_question"

    settings = {
        "top_k": 5 if intent in {"comparison", "research_gaps"} else 3,
        "max_revision_rounds": 2 if intent in {"comparison", "research_gaps"} else 1,
        "evidence_mode": "multi_document" if intent == "comparison" else "focused",
    }
    return {
        "question": question,
        "intent": intent,
        "agents": [
            "research",
            "analysis",
            "critic",
            "synthesis"
        ],
        "reason": (
            "The question requires research evidence, "
            "analysis, critical verification, and final "
            "synthesis."
        ),
        "settings": settings,
    }


# ============================================================
# SUPERVISOR
# ============================================================

def run_supervisor(question, source=None, on_event=None, mode="simple"):
    """
    Run the complete multi-agent research workflow.

    Parameters
    ----------
    question : str
        User's research question.

    source : str or None
        Selected PDF name.

        None means search across all indexed documents.

        Example:
            source="1706.03762v7.pdf"
    """

    # ========================================================
    # 1. CREATE PLAN
    # ========================================================

    plan = create_supervisor_plan(
        question
    )
    emit = on_event or (lambda event, data=None: None)
    emit("plan", plan)

    print("\n" + "=" * 70)
    print("SUPERVISOR AGENT PLAN")
    print("=" * 70)

    print(
        json.dumps(
            plan,
            indent=4
        )
    )

    # ========================================================
    # SEARCH SCOPE
    # ========================================================

    if source:

        print(
            f"\nSearch scope: {source}"
        )

    else:

        print(
            "\nSearch scope: All Documents"
        )

    # ========================================================
    # 2. RESEARCH AGENT
    # ========================================================

    print("\n" + "=" * 70)
    print("1. RESEARCH AGENT")
    print("=" * 70)

    emit("research_started")
    research_results = run_research_agent(
        question=question,
        top_k=plan["settings"]["top_k"],
        source=source
    )
    emit("research_completed", {"count": len(research_results)})

    print(
        f"Retrieved {len(research_results)} "
        "relevant document chunks."
    )

    # ========================================================
    # 3. ANALYSIS AGENT
    # ========================================================

    print("\n" + "=" * 70)
    print("2. ANALYSIS AGENT")
    print("=" * 70)

    analysis = run_analysis_agent(
        question,
        research_results
    )
    emit("analysis_completed")

    print(
        "Research analysis completed."
    )

    # ========================================================
    # 4. CRITIC + REVISION LOOP
    # ========================================================

    revision_round = 0

    critic_result = {
        "status": "UNKNOWN",
        "critique": ""
    }

    while True:

        print("\n" + "=" * 70)

        print(
            f"3. CRITIC AGENT "
            f"(Round {revision_round + 1})"
        )

        print("=" * 70)

        emit("critic_started", {"round": revision_round + 1})
        critic_result = run_critic_agent(
            question,
            research_results,
            analysis
        )

        critic_status = critic_result.get(
            "status",
            "UNKNOWN"
        )
        emit("critic_completed", {"status": critic_status})

        print(
            f"Critic status: {critic_status}"
        )

        # ----------------------------------------------------
        # PASS
        # ----------------------------------------------------

        if critic_status == "PASS":

            print(
                "✓ Analysis passed critic verification."
            )

            break

        # ----------------------------------------------------
        # RATE LIMITED
        # ----------------------------------------------------

        if critic_status == "RATE_LIMITED":

            print(
                "⚠ Critic was rate limited. "
                "Skipping further revision."
            )

            break

        # ----------------------------------------------------
        # REVISION LIMIT
        # ----------------------------------------------------

        if revision_round >= plan["settings"]["max_revision_rounds"]:

            print(
                "⚠ Maximum revision rounds reached. "
                "Proceeding to synthesis."
            )

            break

        # ----------------------------------------------------
        # REVISION
        # ----------------------------------------------------

        revision_round += 1

        print("\n" + "=" * 70)

        print(
            f"REVISION AGENT "
            f"(Round {revision_round})"
        )

        print("=" * 70)

        critique_text = critic_result.get(
            "critique",
            ""
        )

        revised_question = f"""
Original user question:
{question}

The research document being analyzed is:
{source if source else "all indexed documents"}

Your previous analysis was:

{analysis}

The critic identified these issues:

{critique_text}

Revise the analysis.

IMPORTANT:
- Correct unsupported claims.
- Remove weak or speculative statements.
- Keep only information supported by the research evidence.
- Preserve page references.
- Keep the revised analysis concise.
"""

        analysis = run_analysis_agent(
            revised_question,
            research_results
        )
        emit("revision_completed", {"round": revision_round})

        print(
            "✓ Analysis revised using critic feedback."
        )

        # Loop back to Critic.

    # ========================================================
    # 5. SYNTHESIS
    # ========================================================

    print("\n" + "=" * 70)
    print("4. SYNTHESIS AGENT")
    print("=" * 70)

    style = "Explain in plain language and briefly define technical terms." if mode == "simple" else "Preserve technical detail, equations, and methodological qualifications."
    final_answer = run_synthesis_agent(
        question + "\nResponse style: " + style,
        research_results,
        analysis,
        critic_result.get(
            "critique",
            ""
        ),
    )
    emit("synthesis_completed")

    print(
        "Final synthesis completed."
    )

    # ========================================================
    # 6. SOURCES
    # ========================================================

    sources = []

    for result in research_results:

        source_item = (
            result.get(
                "source",
                "Unknown"
            ),
            result.get(
                "page",
                "Unknown"
            )
        )

        if source_item not in sources:

            sources.append(
                source_item
            )

    # ========================================================
    # 7. TERMINAL OUTPUT
    # ========================================================

    print("\n" + "=" * 70)
    print("FINAL MULTI-AGENT RAG ANSWER")
    print("=" * 70)

    print(
        "\n" + final_answer
    )

    print("\n" + "=" * 70)
    print("SOURCES")
    print("=" * 70)

    for source_name, page in sources:

        print(
            f"📄 {source_name} — Page {page}"
        )

    # ========================================================
    # 8. RETURN RESULT FOR STREAMLIT
    # ========================================================

    return {
        "plan": plan,

        "research": research_results,

        "analysis": analysis,

        "critique": critic_result,

        "answer": final_answer,

        "sources": sources,

        "revision_rounds": revision_round,

        "search_scope": (
            source
            if source
            else "All Documents"
        ),
        "evaluation": {
            "retrieved_chunks": len(research_results),
            "unique_sources": len(sources),
            "citation_coverage": round(
                sum(1 for source_name, _ in sources if source_name in final_answer)
                / max(1, len(sources)),
                3,
            ),
            "critic_passed": critic_result.get("status") == "PASS",
        },
    }


# ============================================================
# COMMAND-LINE TEST
# ============================================================

if __name__ == "__main__":

    question = input(
        "\nEnter your research question: "
    )

    source_choice = input(
        "\nEnter PDF filename "
        "or press Enter for all documents: "
    ).strip()

    if source_choice == "":
        source_choice = None

    run_supervisor(
        question=question,
        source=source_choice
    )