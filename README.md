# 🤖 Agentic RAG Research Assistant

An intelligent research assistant that combines **Retrieval-Augmented Generation (RAG)** with a **multi-agent architecture** to help users search, analyze, verify, compare, and synthesize information from research papers.

The system provides a Streamlit web interface where users can upload research papers, manage indexed documents, ask research questions, receive evidence-grounded answers, inspect the agent workflow, view source references, and download research reports.

The primary interface is now a FastAPI service with a browser client. The
original Streamlit interface remains available as a companion implementation.

## FastAPI application

From the repository root:

```bash
python -m pip install -r requirements.txt
python -m uvicorn fastapi_app.main:app --env-file .env --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/` for the browser client or
`http://127.0.0.1:8000/docs` for the interactive API documentation.

FastAPI endpoints:

- `GET /health` — service health
- `GET /api/documents` — indexed PDFs and statistics
- `POST /api/documents` — upload and index a PDF
- `DELETE /api/documents/{source}` — remove a PDF and its ChromaDB chunks
- `POST /api/research` — run the complete research workflow
- `GET /api/research/stream` — stream workflow events over Server-Sent Events
- `POST /api/auth/register` and `/api/auth/login` — local user accounts
- `GET/POST /api/workspaces` — research workspace management
- `GET /api/history` — persisted chat history
- `GET /api/reports/{chat_id}?format=txt|md|json|pdf` — rich report exports
- `GET /api/workspaces/{workspace_id}/diagrams` — workspace diagrams and versions
- `POST /api/workspaces/{workspace_id}/diagrams` — generate a Mermaid diagram
- `POST /api/diagrams/{diagram_id}/refine` — conversationally refine a diagram
- `GET /api/diagrams/{diagram_id}/download?format=mmd|svg|png|pdf` — safe diagram exports
- `POST /api/evaluate` — automated answer/retrieval evaluation metrics

Example research request:

```json
{
  "question": "What is the main contribution of the Transformer architecture?",
  "source": null
}
```

The research endpoint runs the existing supervisor, retrieval, analysis,
critic, revision, and synthesis stages in a worker thread so synchronous model
calls do not block the FastAPI event loop.

## Current RAG capabilities

- SHA-256 document hashing and normalized text hashing
- Semantic duplicate detection against the vector collection
- PyMuPDF table extraction with table text preserved in page chunks
- Hybrid retrieval: Chroma semantic retrieval plus lexical keyword scoring
- Reciprocal-rank fusion reranking
- Adaptive planning: comparison/gap questions retrieve more evidence and allow
  an additional revision round
- SQLite-backed users, sessions, workspaces, and chat history
- SSE progress events for long research jobs
- Plain-text, Markdown-compatible, JSON, and PDF report downloads
- Evaluation metrics for citation coverage, retrieval count, source diversity,
  critic pass status, and answer length

## AI Diagram Generator

Each workspace has a Diagram Generator for flowcharts, system architecture,
sequence diagrams, and entity-relationship diagrams. Describe a methodology or
system, optionally provide a selected paper passage, and the Diagram Agent
returns a structured title, Mermaid source, assumptions, and source references.
The browser client supports regeneration, Mermaid editing, conversational
refinement, renaming, version restore, and Mermaid/SVG/PNG/PDF downloads.

Mermaid is validated before it is displayed or exported. Directives, links,
click actions, raw HTML, scripts, and model-supplied configuration are rejected.
Uploaded-paper passages are treated as untrusted evidence and cannot become
application instructions. Diagram records and version history are stored in the
workspace SQLite database and use the same workspace ownership checks as other
workspace data.

Configure the diagram model with `DIAGRAM_MODEL_PROVIDER`, `DIAGRAM_MODEL`, and
the local/Hugging Face-compatible `HF_BASE_URL`/`HF_TOKEN` variables.
The default image provider is local Diffusers with
`Qwen/Qwen3-Coder-30B-A3B-Instruct` through a Hugging Face-compatible endpoint.
Qwen generates Mermaid source; the application renders that source into
sanitized SVG/PNG/PDF diagram assets without downloading a local image model.
Hosted Hugging Face inference may incur provider charges. Copy `.env.example` to
`.env` before generating diagrams.

Attach saved diagrams to report exports with
`/api/reports/{chat_id}?format=pdf&diagram_ids=1&diagram_ids=2`. Use `format=docx`
for Word, `format=tex` for LaTeX, or `format=zip` for a LaTeX project archive
containing Mermaid and SVG assets. The controlled renderer creates sanitized
SVG/PNG/PDF assets without executing model-generated code.

### ChromaDB recovery

The persistent ChromaDB directory is local runtime state and is ignored by git.
If ChromaDB reports a Rust SQLite panic while opening an existing database,
stop the server, move `data\chroma_db` to a backup directory, and restart or
re-index the PDFs from `data\documents`. The application uses an absolute
repository path for ChromaDB, so the server can be launched from the repository
root without changing the storage location.

---

## 📌 Project Overview

Traditional RAG systems generally follow a simple pipeline:

```text
User Question
     ↓
Retrieve Documents
     ↓
Generate Answer
```

This project extends the traditional RAG approach into a multi-agent workflow:

```text
User Question
      ↓
Supervisor Agent
      ↓
Research Agent
      ↓
Analysis Agent
      ↓
Critic Agent
      ↓
Revision Loop
      ↓
Synthesis Agent
      ↓
Final Answer + Sources
```

The goal is to improve research question answering by separating retrieval, analysis, verification, revision, and synthesis into specialized stages.

---

## 🎯 Problem Statement

Students and researchers often need to search technical papers, identify relevant evidence, compare concepts, verify claims, and summarize research findings.

A basic search or RAG system may retrieve useful passages but can still produce incomplete answers, unsupported claims, weak comparisons, and poorly grounded summaries.

This project addresses these challenges using a multi-agent RAG pipeline where retrieved evidence is analyzed, critically verified, revised when necessary, and finally synthesized into a research answer.

---

## 🎯 Objectives

The main objectives of the project are:

1. Build a research assistant using Retrieval-Augmented Generation.
2. Allow users to upload research papers in PDF format.
3. Extract and split research documents into searchable chunks.
4. Store document chunks in ChromaDB.
5. Retrieve relevant evidence using semantic search.
6. Use specialized agents for research, analysis, criticism, revision, and synthesis.
7. Support single-document and multi-document research.
8. Provide source and page references.
9. Detect duplicate document uploads.
10. Allow users to remove indexed documents.
11. Generate downloadable research reports.
12. Provide an easy-to-use Streamlit interface.

---

# 🧠 System Architecture

The system consists of a document ingestion pipeline, ChromaDB retrieval layer, and multi-agent reasoning workflow.

## High-Level Architecture

```text
                    ┌────────────────────┐
                    │       User         │
                    │  Research Question │
                    └─────────┬──────────┘
                              │
                              ▼
                    ┌────────────────────┐
                    │   Streamlit UI     │
                    └─────────┬──────────┘
                              │
                              ▼
                    ┌────────────────────┐
                    │  Supervisor Agent  │
                    └─────────┬──────────┘
                              │
                              ▼
                    ┌────────────────────┐
                    │   Research Agent   │
                    └─────────┬──────────┘
                              │
                              ▼
                    ┌────────────────────┐
                    │   Analysis Agent   │
                    └─────────┬──────────┘
                              │
                              ▼
                    ┌────────────────────┐
                    │    Critic Agent    │
                    └─────────┬──────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
                   PASS          NEEDS_REVISION
                    │                   │
                    │                   ▼
                    │            ┌──────────────┐
                    │            │   Revision   │
                    │            └──────┬───────┘
                    │                   │
                    │                   ▼
                    │            ┌──────────────┐
                    │            │ Critic Again │
                    │            └──────┬───────┘
                    │                   │
                    └──────────┬────────┘
                               ▼
                    ┌────────────────────┐
                    │  Synthesis Agent   │
                    └─────────┬──────────┘
                              │
                              ▼
               ┌─────────────────────────────┐
               │ Final Answer + Sources      │
               │ + Downloadable Report       │
               └─────────────────────────────┘
```

---

# 📚 RAG Pipeline

## 1. PDF Upload

Users can upload research papers through the Streamlit interface.

```text
PDF
 ↓
PDF Loader
 ↓
Text Extraction
 ↓
Text Chunking
 ↓
ChromaDB
```

Uploaded papers are stored locally and their chunks are added to the persistent ChromaDB collection.

---

## 2. PDF Text Extraction

PDF content is extracted using **PyMuPDF**.

The extracted information is organized by page so that source and page metadata can be preserved throughout the retrieval pipeline.

---

## 3. Text Chunking

Research paper text is divided into smaller overlapping chunks.

Each chunk is stored with metadata such as:

```text
source
page
```

This allows the final answer to reference the relevant source document and page.

---

# 🗄️ ChromaDB

The project uses **ChromaDB** as the persistent vector/document database.

Each indexed chunk contains:

```text
Document Text
Source Filename
Page Number
```

Example:

```text
Source: transformer_paper.pdf
Page: 2
Text: ...
```

The database allows semantic retrieval of relevant research evidence.

---

# 🔎 Retrieval

The retrieval layer supports two search modes.

## Single-Document Search

The user can select a particular research paper:

```text
Search Scope
→ transformer_paper.pdf
```

The retriever then searches only that selected document.

---

## All-Document Search

The user can choose:

```text
Search Scope
→ All Documents
```

The system searches across the indexed research papers.

For multi-document questions, the retrieval layer distributes retrieval across documents so that one document does not completely dominate the retrieved evidence.

This improves cross-paper comparison tasks.

---

# 🤖 Multi-Agent System

The project uses several specialized agents.

## 1. Supervisor Agent

The Supervisor coordinates the research workflow.

It identifies the likely intent of the user's question, such as:

```text
comparison
summarization
research_gaps
idea_generation
research_question
```

It then coordinates:

```text
Research
→ Analysis
→ Critic
→ Revision when required
→ Synthesis
```

---

## 2. Research Agent

The Research Agent retrieves relevant evidence from ChromaDB.

Responsibilities include:

* semantic retrieval
* document-specific retrieval
* multi-document retrieval
* preservation of source and page metadata

---

## 3. Analysis Agent

The Analysis Agent interprets the retrieved research evidence.

Responsibilities include:

* identifying important findings
* explaining relevant evidence
* comparing concepts when required
* maintaining source grounding
* avoiding unsupported claims

The analysis is restricted to the supplied research evidence.

---

## 4. Critic Agent

The Critic Agent evaluates the generated analysis.

It checks:

* factual support
* relevance
* source grounding
* unsupported claims
* hallucination risks
* missing important information

The critic can return:

```text
PASS
```

or:

```text
NEEDS_REVISION
```

---

## 5. Revision Loop

When the critic returns:

```text
NEEDS_REVISION
```

the system sends the analysis back through a revision stage using the critic's feedback.

The workflow becomes:

```text
Analysis
   ↓
Critic
   ↓
NEEDS_REVISION
   ↓
Revision
   ↓
Critic Again
```

The current implementation limits the number of revision rounds to control token consumption.

---

## 6. Synthesis Agent

The Synthesis Agent generates the final answer using:

```text
Research Evidence
+
Analysis
+
Critic Feedback
```

The final answer is designed to be:

* clear
* concise
* evidence-grounded
* student-friendly
* source-aware

---

# 📄 Document Management

The application supports research-paper management.

## Uploading Papers

Users can upload PDF files through:

```text
📤 Upload Research Paper
```

---

## Duplicate Detection

Before indexing a document, the system checks whether a document with the same filename is already stored.

If it already exists, the system displays a warning and does not index it again.

---

## Indexed Documents

The sidebar displays indexed documents with basic statistics.

Example:

```text
📄 transformer_paper.pdf
Pages: 15
Chunks: 52
```

---

## Removing Documents

Users can remove an indexed document using the document management interface.

The system removes:

* indexed chunks from ChromaDB
* the corresponding uploaded PDF when available locally

A confirmation step is provided before deletion.

---

# 🎯 Search Scope

The application provides a search-scope selector.

Example:

```text
Search within:
→ All Documents
```

or:

```text
Search within:
→ transformer_paper.pdf
```

This allows users to control whether the question is answered from one research paper or across the full indexed collection.

---

# 📚 Source Grounding

The final interface displays source names and page numbers associated with the retrieved research evidence.

Example:

```text
📄 transformer_paper.pdf — Page 2
📄 N19-1423.pdf — Page 3
```

This improves traceability and allows users to identify where the evidence came from.

---

# 📥 Research Report Download

After research is completed, users can download a text-based research report.

The report can contain:

```text
Research Question
Search Scope
Supervisor Plan
Final Answer
Critic Status
Revision Rounds
Sources
```

The downloaded file is:

```text
agentic_rag_research_report.txt
```

---

# 🖥️ Streamlit Interface

The user interface is built using **Streamlit**.

The interface provides:

* PDF upload
* indexed document management
* search scope selection
* research question input
* example questions
* multi-agent workflow visualization
* final answer display
* critic verification
* research analysis
* source references
* report download

---

# 🧭 Supervisor Workflow Display

The UI shows the current agent sequence:

```text
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
```

This makes the multi-agent process visible to the user.

---

# 🛠️ Technologies Used

## Programming Language

* Python

## Frontend

* Streamlit

## PDF Processing

* PyMuPDF

## Vector Database

* ChromaDB

## LLM API

* Groq using an OpenAI-compatible client
* Default model: `openai/gpt-oss-20b`

Set `GROQ_MODEL` in `.env` to another model returned by the Groq model-list
endpoint. Model availability can change as providers deprecate models; the
previous `llama-3.1-8b-instant` default is no longer available for this
project.

## Environment Configuration

* python-dotenv

## Additional Python Packages

* LangChain
* LangChain Community
* LangChain OpenAI
* LangGraph
* OpenAI
* tiktoken

The current production workflow is centered around the custom multi-agent implementation under `src/agents/`.

---

# 📁 Project Structure

The cleaned project structure is:

```text
Agentic-RAG-Research-Assistant/
│
├── .env
├── README.md
├── app.py
├── requirements.txt
│
├── data/
│   └── documents/
│       ├── research_paper_1.pdf
│       ├── research_paper_2.pdf
│       └── ...
│
└── src/
    │
    ├── retriever.py
    │
    ├── agents/
    │   ├── __init__.py
    │   ├── supervisor.py
    │   ├── research_agent.py
    │   ├── analysis_agent.py
    │   ├── critic_agent.py
    │   └── synthesis_agent.py
    │
    └── ingestion/
        ├── pdf_loader.py
        ├── text_splitter.py
        └── vector_store.py
```

---

# ⚙️ Installation

## 1. Create or activate the virtual environment

### Windows

```powershell
python -m venv venv
venv\Scripts\activate
```

---

## 2. Install dependencies

```powershell
pip install -r requirements.txt
```

---

# 🔑 Environment Variables

Create a `.env` file in the project root.

Example:

```env
GROQ_API_KEY=your_groq_api_key
```

The application uses `python-dotenv` to load the API key.

Do not upload your `.env` file to GitHub.

Add these entries to `.gitignore`:

```text
.env
venv/
__pycache__/
data/chroma_db/
```

---

# ▶️ Running the Application

From the project root, run:

```powershell
streamlit run app.py
```

Then open the Streamlit URL shown in the terminal.

Usually:

```text
http://localhost:8501
```

---

# 🧪 Command-Line Testing

You can also test the Supervisor directly:

```powershell
python -m src.agents.supervisor
```

Test the Research Agent:

```powershell
python -m src.agents.research_agent
```

Test the Retriever:

```powershell
python -m src.retriever
```

---

# 💡 Example Research Questions

The system supports different types of research questions.

## Comparison

```text
What are the advantages of the Transformer compared
with recurrent neural networks?
```

## Methodology

```text
What datasets, baseline models, evaluation metrics,
and experimental settings were used to evaluate the model?
```

## Main Contribution

```text
What is the main contribution of the research paper?
```

## Research Gaps

```text
What limitations of the architecture suggest directions
for future research?
```

## Cross-Paper Comparison

```text
What are the main differences between BERT and the
Transformer architecture, particularly in their training
objectives, architecture, and evaluation tasks?
```

---

# ✅ Key Features

The current implementation supports:

* PDF upload
* PDF text extraction
* Text chunking
* Persistent ChromaDB storage
* Semantic retrieval
* Single-document search
* Multi-document search
* Document-specific retrieval
* Duplicate detection
* Document removal
* Supervisor planning
* Multi-agent research
* Evidence analysis
* Critic verification
* Revision loop
* Final synthesis
* Source and page references
* Downloadable research reports
* Streamlit user interface
* Groq rate-limit-aware behavior
* Reduced intermediate token usage

---

# 🔍 Example Workflow

A typical user workflow is:

```text
1. Upload Research Paper
          ↓
2. Add Paper to Knowledge Base
          ↓
3. Select Search Scope
          ↓
4. Enter Research Question
          ↓
5. Supervisor Plans Workflow
          ↓
6. Research Agent Retrieves Evidence
          ↓
7. Analysis Agent Interprets Evidence
          ↓
8. Critic Agent Verifies Analysis
          ↓
9. Revision if Required
          ↓
10. Synthesis Agent Generates Final Answer
          ↓
11. Sources Are Displayed
          ↓
12. Research Report Can Be Downloaded
```

---

# 🧠 Why Agentic RAG?

A traditional RAG system usually follows:

```text
Question
   ↓
Retriever
   ↓
LLM
   ↓
Answer
```

This project adds specialized reasoning stages:

```text
Question
   ↓
Supervisor
   ↓
Research
   ↓
Analysis
   ↓
Critic
   ↓
Revision
   ↓
Synthesis
   ↓
Answer
```

The multi-agent design separates retrieval, reasoning, verification, correction, and final response generation.

---

# ⚠️ Current Limitations

The current implementation has several limitations.

## Model and API Limits

The system depends on a hosted language model, so token and rate limits can affect execution.

The application includes basic handling for rate-limit errors, but service quotas still apply.

## Retrieval Quality

Answer quality depends on:

* chunk size
* chunk overlap
* query wording
* document quality
* the number of retrieved chunks

Cross-document questions may still require retrieval tuning.

## Duplicate Content

The current duplicate detection primarily checks whether the same document filename is already indexed.

Two differently named files containing the same paper may still be stored separately.

## PDF Extraction

Complex PDFs may contain:

* tables
* equations
* multi-column layouts
* images
* footnotes

Text extraction quality may vary depending on document structure.

## Revision Rounds

The revision loop is intentionally limited to control token usage.

A future version could support adaptive revision depth.

---

# 🚀 Future Enhancements

Possible future improvements include:

* semantic duplicate detection
* document hashing
* improved table extraction
* hybrid keyword and semantic retrieval
* retrieval reranking
* richer report formats
* PDF report generation
* chat history
* user accounts
* research workspaces
* streaming responses
* adaptive agent planning
* automated evaluation metrics

---

# 🎓 Academic Value

This project demonstrates practical integration of:

* Retrieval-Augmented Generation
* Vector databases
* Semantic search
* Large language models
* Multi-agent systems
* Evidence grounding
* Critic-based verification
* Iterative revision
* Document management
* Research question answering

It provides a practical example of how agentic systems can assist students and researchers in exploring technical literature.

---

# 🧪 Recommended Demonstration

## Demo 1 — Single Paper

Upload:

```text
transformer_paper.pdf
```

Ask:

```text
What are the advantages of the Transformer compared
with recurrent neural networks?
```

---

## Demo 2 — Methodology

Ask:

```text
What datasets, baseline models, evaluation metrics,
and experimental settings were used to evaluate the Transformer?
```

---

## Demo 3 — Critic and Revision

Use a comparison question and demonstrate:

```text
Analysis
   ↓
Critic
   ↓
NEEDS_REVISION
   ↓
Revision
   ↓
Critic
   ↓
Synthesis
```

---

## Demo 4 — Multi-Document Search

Upload a second research paper.

Select:

```text
All Documents
```

Ask a cross-paper comparison question and verify that the final sources reference multiple papers.

---

# 🏁 Project Status

The current implementation provides a working end-to-end Agentic RAG research assistant with:

```text
PDF Ingestion              ✅
ChromaDB                   ✅
Semantic Retrieval         ✅
Multi-Document Retrieval   ✅
Document Management        ✅
Supervisor Agent           ✅
Research Agent             ✅
Analysis Agent             ✅
Critic Agent               ✅
Revision Loop              ✅
Synthesis Agent            ✅
Streamlit UI               ✅
Source References          ✅
Downloadable Reports       ✅
```

---

# 👨‍💻 Project

## Agentic RAG Research Assistant

Built using:

```text
Python
Streamlit
ChromaDB
PyMuPDF
Groq
OpenAI-Compatible API
Multi-Agent Architecture
```

---

# 📄 License

Add the license appropriate for your project before publishing.

For example:

```text
MIT License
```

if you choose to distribute the project under the MIT License.
