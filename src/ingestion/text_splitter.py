# ============================================================
# TEXT SPLITTER
# ============================================================

def create_chunks(
    pages,
    chunk_size=1000,
    chunk_overlap=200
):
    """
    Split PDF page text into overlapping chunks.

    Expected input:
        [
            {
                "page_number": 1,
                "text": "..."
            },
            ...
        ]

    Returns:
        [
            {
                "text": "...",
                "page_number": 1
            },
            ...
        ]
    """

    chunks = []

    if not pages:
        return chunks

    for page in pages:

        page_number = page.get(
            "page_number",
            0
        )

        text = page.get(
            "text",
            ""
        )

        if not text:
            continue

        # Normalize whitespace
        text = " ".join(
            text.split()
        )

        start = 0

        while start < len(text):

            end = start + chunk_size

            chunk_text = text[start:end].strip()

            if chunk_text:

                chunks.append(
                    {
                        "text": chunk_text,
                        "page_number": page_number
                    }
                )

            # Move forward while keeping overlap
            next_start = end - chunk_overlap

            if next_start <= start:
                break

            start = next_start

    return chunks


if __name__ == "__main__":

    print(
        "Text splitter module loaded successfully."
    )