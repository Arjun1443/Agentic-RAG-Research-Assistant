import os

import streamlit as st

from src.agents.supervisor import run_supervisor

from src.retriever import (
    list_indexed_documents,
    document_exists,
    get_document_statistics,
    delete_document
)

from src.ingestion.vector_store import (
    add_pdf_to_vector_database
)


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Agentic RAG Research Assistant",
    page_icon="🤖",
    layout="wide"
)


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>

    .main-title {
        font-size: 42px;
        font-weight: 700;
        margin-bottom: 5px;
    }

    .subtitle {
        font-size: 18px;
        color: #666;
        margin-bottom: 30px;
    }

    .answer-box {
        padding: 25px;
        border-radius: 12px;
        border: 1px solid #ddd;
        margin-top: 20px;
        margin-bottom: 20px;
    }

    .source-box {
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #ddd;
        margin-top: 10px;
        margin-bottom: 10px;
    }

    .document-box {
        padding: 12px;
        border-radius: 10px;
        border: 1px solid #ddd;
        margin-bottom: 10px;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">🤖 Agentic RAG Research Assistant</div>',
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="subtitle">
    Upload research papers, manage indexed documents, and ask
    questions using the multi-agent Agentic RAG system.
    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("📚 Research Assistant")

    st.write(
        """
        This system can:

        • Upload research papers
        • Detect duplicate documents
        • Store papers in ChromaDB
        • Search all documents
        • Search a specific document
        • Analyze research content
        • Critically verify answers
        • Revise weak analysis
        • Synthesize final answers
        • Remove indexed documents
        • Download research reports
        """
    )

    st.divider()


    # ========================================================
    # PDF UPLOAD
    # ========================================================

    st.subheader(
        "📤 Upload Research Paper"
    )

    uploaded_file = st.file_uploader(
        "Choose a PDF file",
        type=["pdf"],
        help="Upload a research paper in PDF format."
    )


    if uploaded_file is not None:

        st.info(
            f"Selected: {uploaded_file.name}"
        )


        if st.button(
            "📥 Add Paper to Knowledge Base",
            use_container_width=True
        ):

            os.makedirs(
                "data/documents",
                exist_ok=True
            )

            source_name = uploaded_file.name

            # ------------------------------------------------
            # DUPLICATE CHECK
            # ------------------------------------------------

            try:

                already_exists = document_exists(
                    source_name
                )

            except Exception:

                already_exists = False


            if already_exists:

                st.warning(
                    f"""
                    ⚠️ **{source_name}** is already indexed.

                    The document was not added again.
                    """
                )

            else:

                pdf_path = os.path.join(
                    "data",
                    "documents",
                    source_name
                )


                try:

                    with open(
                        pdf_path,
                        "wb"
                    ) as file:

                        file.write(
                            uploaded_file.getbuffer()
                        )


                    progress = st.empty()

                    progress.info(
                        "📄 Processing uploaded paper..."
                    )


                    result = add_pdf_to_vector_database(
                        pdf_path=pdf_path,
                        source_name=source_name
                    )


                    progress.success(
                        "✅ Research paper added successfully!"
                    )


                    st.success(
                        f"""
                        **{source_name}**

                        Pages: {result['pages']}

                        Chunks added: {result['chunks']}

                        Total chunks in knowledge base:
                        {result['total_documents']}
                        """
                    )


                except Exception as e:

                    st.error(
                        "Could not add the PDF "
                        "to the knowledge base."
                    )

                    st.error(
                        str(e)
                    )


    st.divider()


    # ========================================================
    # INDEXED DOCUMENTS
    # ========================================================

    st.subheader(
        "📚 Indexed Documents"
    )


    try:

        indexed_documents = (
            list_indexed_documents()
        )

    except Exception:

        indexed_documents = []


    if indexed_documents:

        for document_name in indexed_documents:

            try:

                stats = get_document_statistics(
                    document_name
                )

                pages = stats.get(
                    "pages",
                    0
                )

                chunks = stats.get(
                    "chunks",
                    0
                )

            except Exception:

                pages = "?"
                chunks = "?"


            # ------------------------------------------------
            # DOCUMENT INFO
            # ------------------------------------------------

            st.markdown(
                f"""
                <div class="document-box">
                📄 <b>{document_name}</b><br>
                Pages: {pages}<br>
                Chunks: {chunks}
                </div>
                """,
                unsafe_allow_html=True
            )


            # ------------------------------------------------
            # REMOVE DOCUMENT
            # ------------------------------------------------

            remove_key = (
                "remove_document_"
                + document_name
            )


            confirm_key = (
                "confirm_remove_"
                + document_name
            )


            if st.button(
                f"🗑 Remove {document_name}",
                key=remove_key,
                use_container_width=True
            ):

                st.session_state[
                    confirm_key
                ] = True


            # ------------------------------------------------
            # CONFIRMATION
            # ------------------------------------------------

            if st.session_state.get(
                confirm_key,
                False
            ):

                st.warning(
                    f"""
                    Are you sure you want to remove:

                    **{document_name}**

                    This will remove its indexed chunks
                    from ChromaDB.
                    """
                )


                confirm_col1, confirm_col2 = st.columns(2)


                with confirm_col1:

                    if st.button(
                        "✅ Yes, Remove",
                        key=(
                            "yes_remove_"
                            + document_name
                        ),
                        use_container_width=True
                    ):

                        try:

                            result = delete_document(
                                document_name
                            )


                            if result.get(
                                "deleted",
                                False
                            ):

                                st.success(
                                    f"""
                                    ✅ {document_name}
                                    was removed successfully.
                                    """
                                )

                            else:

                                st.warning(
                                    result.get(
                                        "message",
                                        "Document not found."
                                    )
                                )


                        except Exception as e:

                            st.error(
                                "Could not remove "
                                "the document."
                            )

                            st.error(
                                str(e)
                            )


                        # Clear confirmation state
                        st.session_state.pop(
                            confirm_key,
                            None
                        )


                        # Clear any selected scope
                        if (
                            st.session_state.get(
                                "research_scope"
                            )
                            == document_name
                        ):

                            st.session_state[
                                "research_scope"
                            ] = "All Documents"


                        # Refresh application
                        st.rerun()


                with confirm_col2:

                    if st.button(
                        "❌ Cancel",
                        key=(
                            "cancel_remove_"
                            + document_name
                        ),
                        use_container_width=True
                    ):

                        st.session_state.pop(
                            confirm_key,
                            None
                        )

                        st.rerun()

    else:

        st.info(
            "No documents indexed yet."
        )


    st.divider()


    # ========================================================
    # SEARCH SCOPE
    # ========================================================

    st.subheader(
        "🎯 Search Scope"
    )


    # Refresh list after any deletion/upload
    try:

        indexed_documents = (
            list_indexed_documents()
        )

    except Exception:

        indexed_documents = []


    search_options = [
        "All Documents"
    ] + indexed_documents


    current_scope = st.session_state.get(
        "research_scope",
        "All Documents"
    )


    if current_scope not in search_options:

        current_scope = "All Documents"


    selected_source = st.selectbox(

        "Search within:",

        search_options,

        index=search_options.index(
            current_scope
        )
    )


    if selected_source == "All Documents":

        st.caption(
            "Searching across all indexed PDFs."
        )

        retrieval_source = None

    else:

        st.caption(
            f"Searching only: {selected_source}"
        )

        retrieval_source = selected_source


    # Store current UI selection
    st.session_state[
        "research_scope"
    ] = selected_source


    st.divider()


    # ========================================================
    # AGENT WORKFLOW
    # ========================================================

    st.subheader(
        "🤖 Agent Workflow"
    )

    st.write(
        """
        🧭 Supervisor
        ↓
        🔎 Research Agent
        ↓
        🧠 Analysis Agent
        ↓
        🔍 Critic Agent
        ↓
        🔄 Revision
        ↓
        ✍️ Synthesis Agent
        """
    )


    st.divider()


    st.caption(
        "Agentic RAG-Based Intelligent Research "
        "and Project Assistance System"
    )


# ============================================================
# QUESTION INPUT
# ============================================================

st.subheader(
    "🔍 Ask a Research Question"
)


question = st.text_area(
    "Enter your research question:",
    placeholder=(
        "Example: What is the main contribution "
        "of the Transformer architecture?"
    ),
    height=120
)


# ============================================================
# EXAMPLE QUESTIONS
# ============================================================

st.markdown(
    "### 💡 Example Questions"
)


col1, col2, col3 = st.columns(3)


with col1:

    if st.button(
        "Main contribution",
        use_container_width=True
    ):

        question = (
            "What is the main contribution "
            "of the research paper?"
        )


with col2:

    if st.button(
        "Methodology",
        use_container_width=True
    ):

        question = (
            "What datasets, baseline models, "
            "evaluation metrics, and experimental "
            "settings were used to evaluate the model?"
        )


with col3:

    if st.button(
        "Research gaps",
        use_container_width=True
    ):

        question = (
            "What research gaps or future research "
            "directions are suggested by the paper?"
        )


# ============================================================
# RESEARCH BUTTON
# ============================================================

research_button = st.button(
    "🚀 Start Multi-Agent Research",
    type="primary",
    use_container_width=True
)


# ============================================================
# RUN SUPERVISOR
# ============================================================

if research_button:

    if not question.strip():

        st.warning(
            "Please enter a research question first."
        )

    else:

        progress_placeholder = st.empty()


        if retrieval_source:

            progress_placeholder.info(
                f"🤖 Searching {retrieval_source} "
                "and running the multi-agent workflow..."
            )

        else:

            progress_placeholder.info(
                "🤖 Searching all documents and "
                "running the multi-agent workflow..."
            )


        try:

            result = run_supervisor(
                question=question.strip(),
                source=retrieval_source
            )


            progress_placeholder.success(
                "✅ Multi-agent research completed!"
            )


            st.session_state[
                "research_result"
            ] = result


            st.session_state[
                "research_question"
            ] = question.strip()


            st.session_state[
                "research_scope"
            ] = (
                retrieval_source
                if retrieval_source
                else "All Documents"
            )


        except Exception as e:

            progress_placeholder.empty()


            error_text = str(e).lower()


            if (
                "rate limit" in error_text
                or "429" in error_text
                or "tokens per day" in error_text
            ):

                st.warning(
                    """
                    ⚠️ The Groq model rate limit has been reached.

                    Your document retrieval system is still working.
                    Please wait for the model quota to become available
                    and try again.
                    """
                )

            else:

                st.error(
                    "An error occurred while running "
                    "the multi-agent system."
                )

                st.error(
                    str(e)
                )


# ============================================================
# LOAD SAVED RESULT
# ============================================================

result = st.session_state.get(
    "research_result"
)


saved_question = st.session_state.get(
    "research_question",
    question
)


saved_scope = st.session_state.get(
    "research_scope",
    "All Documents"
)


# ============================================================
# DISPLAY RESULTS
# ============================================================

if result:

    st.divider()


    # ========================================================
    # SEARCH SCOPE USED
    # ========================================================

    if saved_scope == "All Documents":

        st.info(
            "🎯 Search scope used: All Documents"
        )

    else:

        st.info(
            f"🎯 Search scope used: {saved_scope}"
        )


    # ========================================================
    # SUPERVISOR PLAN
    # ========================================================

    plan = result.get(
        "plan",
        {}
    )


    with st.expander(
        "🧭 View Supervisor Research Plan",
        expanded=True
    ):

        st.markdown(
            f"**Intent:** "
            f"{plan.get('intent', 'Unknown')}"
        )


        st.markdown(
            f"**Reason:** "
            f"{plan.get('reason', 'Not available')}"
        )


        st.markdown(
            "**Agent sequence:**"
        )


        agent_names = {

            "research":
                "🔎 Research Agent",

            "analysis":
                "🧠 Analysis Agent",

            "critic":
                "🔍 Critic Agent",

            "synthesis":
                "✍️ Synthesis Agent"
        }


        for index, agent in enumerate(

            plan.get(
                "agents",
                []
            ),

            start=1
        ):

            display_name = agent_names.get(

                str(agent).lower(),

                str(agent).title()
                + " Agent"
            )


            st.markdown(
                f"**{index}. {display_name}**"
            )


    # ========================================================
    # MULTI-AGENT WORKFLOW
    # ========================================================

    st.subheader(
        "🤖 Multi-Agent Research Workflow"
    )


    col1, col2, col3, col4 = st.columns(4)


    with col1:

        st.success(
            "🔎 Research\n\nCompleted"
        )


    with col2:

        st.success(
            "🧠 Analysis\n\nCompleted"
        )


    critique = result.get(
        "critique",
        {}
    )


    critic_status = critique.get(
        "status",
        "UNKNOWN"
    )


    with col3:

        if critic_status == "PASS":

            st.success(
                "🔍 Critic\n\nPASS"
            )

        elif critic_status == "RATE_LIMITED":

            st.warning(
                "🔍 Critic\n\nRate Limited"
            )

        else:

            st.warning(
                f"🔍 Critic\n\n{critic_status}"
            )


    with col4:

        st.success(
            "✍️ Synthesis\n\nCompleted"
        )


    # ========================================================
    # REVISION
    # ========================================================

    revision_rounds = result.get(
        "revision_rounds",
        0
    )


    if revision_rounds > 0:

        st.info(
            f"🔄 Revision rounds completed: "
            f"{revision_rounds}"
        )

    else:

        st.info(
            "🔄 No revision round was required."
        )


    # ========================================================
    # FINAL ANSWER
    # ========================================================

    st.divider()


    st.subheader(
        "💡 Final Research Answer"
    )


    answer = result.get(
        "answer",
        "No answer was generated."
    )


    st.markdown(
        f"""
        <div class="answer-box">
        {answer}
        </div>
        """,
        unsafe_allow_html=True
    )


    # ========================================================
    # CRITIC DETAILS
    # ========================================================

    with st.expander(
        "🔍 View Critic Verification"
    ):

        st.markdown(
            f"**Status:** "
            f"`{critic_status}`"
        )


        st.markdown(
            critique.get(
                "critique",
                "No critic details available."
            )
        )


    # ========================================================
    # ANALYSIS
    # ========================================================

    analysis = result.get(
        "analysis",
        ""
    )


    if analysis:

        with st.expander(
            "🧠 View Research Analysis"
        ):

            st.markdown(
                analysis
            )


    # ========================================================
    # SOURCES
    # ========================================================

    sources = result.get(
        "sources",
        []
    )


    st.divider()


    st.subheader(
        "📚 Sources"
    )


    if sources:

        for source_item in sources:

            if isinstance(
                source_item,
                (tuple, list)
            ) and len(source_item) >= 2:

                source_name = source_item[0]

                page = source_item[1]

            elif isinstance(
                source_item,
                dict
            ):

                source_name = source_item.get(
                    "source",
                    "Unknown document"
                )

                page = source_item.get(
                    "page",
                    "Unknown"
                )

            else:

                source_name = str(
                    source_item
                )

                page = "Unknown"


            st.markdown(
                f"""
                <div class="source-box">
                📄 <b>{source_name}</b>
                — Page {page}
                </div>
                """,
                unsafe_allow_html=True
            )


    else:

        st.info(
            "No source information was returned."
        )


    # ========================================================
    # DOWNLOAD REPORT
    # ========================================================

    st.divider()


    st.subheader(
        "📥 Download Research Report"
    )


    report_lines = []


    report_lines.append(
        "AGENTIC RAG RESEARCH REPORT"
    )


    report_lines.append(
        "=" * 70
    )


    report_lines.append("")


    report_lines.append(
        "RESEARCH QUESTION"
    )


    report_lines.append(
        "-" * 70
    )


    report_lines.append(
        saved_question
    )


    report_lines.append("")


    report_lines.append(
        "SEARCH SCOPE"
    )


    report_lines.append(
        "-" * 70
    )


    report_lines.append(
        saved_scope
    )


    report_lines.append("")


    report_lines.append(
        "SUPERVISOR PLAN"
    )


    report_lines.append(
        "-" * 70
    )


    report_lines.append(
        f"Intent: "
        f"{plan.get('intent', 'Unknown')}"
    )


    report_lines.append(
        f"Reason: "
        f"{plan.get('reason', 'Not available')}"
    )


    report_lines.append("")


    report_lines.append(
        "FINAL ANSWER"
    )


    report_lines.append(
        "-" * 70
    )


    report_lines.append(
        answer
    )


    report_lines.append("")


    report_lines.append(
        "CRITIC STATUS"
    )


    report_lines.append(
        "-" * 70
    )


    report_lines.append(
        critic_status
    )


    report_lines.append("")


    report_lines.append(
        "REVISION ROUNDS"
    )


    report_lines.append(
        "-" * 70
    )


    report_lines.append(
        str(revision_rounds)
    )


    report_lines.append("")


    report_lines.append(
        "SOURCES"
    )


    report_lines.append(
        "-" * 70
    )


    for source_item in sources:

        if isinstance(
            source_item,
            (tuple, list)
        ) and len(source_item) >= 2:

            report_lines.append(
                f"{source_item[0]} — Page "
                f"{source_item[1]}"
            )

        elif isinstance(
            source_item,
            dict
        ):

            report_lines.append(
                f"{source_item.get('source', 'Unknown')} "
                f"— Page "
                f"{source_item.get('page', 'Unknown')}"
            )

        else:

            report_lines.append(
                str(source_item)
            )


    report_content = "\n".join(
        report_lines
    )


    st.download_button(

        label="📥 Download Research Report",

        data=report_content,

        file_name="agentic_rag_research_report.txt",

        mime="text/plain",

        use_container_width=True
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()


st.caption(
    "Built using Python • Streamlit • ChromaDB • "
    "Groq • Multi-Agent Agentic RAG"
)