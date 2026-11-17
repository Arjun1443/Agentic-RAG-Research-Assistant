import fitz
from pathlib import Path


def load_pdf(pdf_path: str):
    """
    Load a PDF and extract text page by page.
    """

    pdf_file = Path(pdf_path)

    if not pdf_file.exists():
        raise FileNotFoundError(
            f"PDF file not found: {pdf_file}"
        )

    document = fitz.open(pdf_file)

    pages = []

    for page_number, page in enumerate(document, start=1):
        text = page.get_text("text")
        tables = []
        try:
            finder = page.find_tables()
            for table in finder.tables:
                rows = table.extract()
                if rows:
                    tables.append(
                        "\n".join(
                            " | ".join("" if cell is None else str(cell) for cell in row)
                            for row in rows
                        )
                    )
        except (AttributeError, RuntimeError, ValueError):
            tables = []
        if tables:
            text = f"{text}\n\n[TABLE]\n" + "\n\n".join(tables)

        if text.strip():
            pages.append(
                {
                    "page_number": page_number,
                    "text": text,
                    "tables": tables,
                }
            )

    document.close()

    return pages


if __name__ == "__main__":

    pdf_path = "data/documents/transformer_paper.pdf"

    pages = load_pdf(pdf_path)

    print("PDF loaded successfully!")
    print(f"Total pages with text: {len(pages)}")

    if pages:
        print("\nFirst page preview:")
        print("-" * 60)
        print(pages[0]["text"][:1000])
        print("-" * 60)