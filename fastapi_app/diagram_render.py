import html
import io
import re

import fitz
from PIL import Image, ImageDraw


def _labels(source):
    labels = []
    for line in source.splitlines()[1:]:
        for value in re.findall(r"\[([^\]]+)\]|\(([^)]+)\)|:\s*([^;]+)", line):
            label = next((item for item in value if item), "").strip()
            if label and label not in labels:
                labels.append(label[:80])
    return labels[:24] or ["Diagram"]


def svg_for(source, title):
    labels = _labels(source)
    width, height, box_w, box_h, gap = 1100, max(180, 110 + len(labels) * 90), 260, 56, 34
    items = []
    for index, label in enumerate(labels):
        x = 40 + (index % 3) * (box_w + gap)
        y = 55 + (index // 3) * 90
        items.append(
            f'<rect x="{x}" y="{y}" width="{box_w}" height="{box_h}" rx="8" fill="#eef2ff" stroke="#3730a3"/>'
            f'<text x="{x + box_w / 2}" y="{y + 34}" text-anchor="middle" font-family="Arial" font-size="16" fill="#172033">{html.escape(label)}</text>'
        )
        if index:
            px = 40 + ((index - 1) % 3) * (box_w + gap) + box_w
            py = 55 + ((index - 1) // 3) * 90 + box_h / 2
            items.append(f'<path d="M {px} {py} L {x} {y + box_h / 2}" stroke="#4f46e5" marker-end="url(#arrow)"/>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">'
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#4f46e5"/></marker></defs>'
        f'<rect width="100%" height="100%" fill="white"/><text x="40" y="30" font-family="Arial" font-size="20" font-weight="bold" fill="#172033">{html.escape(title)}</text>'
        + "".join(items) + "</svg>"
    )


def png_for(source, title):
    image = Image.new("RGB", (1100, max(180, 110 + len(_labels(source)) * 90)), "white")
    draw = ImageDraw.Draw(image)
    draw.text((40, 15), title[:100], fill="#172033")
    labels = _labels(source)
    for index, label in enumerate(labels):
        x = 40 + (index % 3) * 294
        y = 55 + (index // 3) * 90
        draw.rounded_rectangle((x, y, x + 260, y + 56), radius=8, fill="#eef2ff", outline="#3730a3", width=2)
        draw.text((x + 12, y + 20), label, fill="#172033")
        if index:
            px = 40 + ((index - 1) % 3) * 294 + 260
            py = 55 + ((index - 1) // 3) * 90 + 28
            draw.line((px, py, x, y + 28), fill="#4f46e5", width=2)
    stream = io.BytesIO()
    image.save(stream, format="PNG", optimize=True)
    return stream.getvalue()


def pdf_for(source, title):
    pdf = fitz.open()
    page = pdf.new_page(width=792, height=612)
    page.insert_text((40, 30), title[:100], fontsize=18)
    page.insert_image(fitz.Rect(40, 50, 752, 500), stream=png_for(source, title), keep_proportion=True)
    page.insert_textbox((40, 520, 752, 590), "Mermaid source is available as the .mmd download.", fontsize=9)
    data = pdf.tobytes()
    pdf.close()
    return data
