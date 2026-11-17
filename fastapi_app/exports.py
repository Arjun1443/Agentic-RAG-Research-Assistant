"""Paginated, wrapped reports without truncating research text."""
import html
import re
import fitz


def tex_escape(text):
    mapping = {'\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#', '_': r'\_', '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'}
    return ''.join(mapping.get(char, char) for char in text)


def pdf_report(text, diagrams=None):
    # Story performs actual wrapping and pagination and supports Unicode text.
    paragraphs = ''.join('<p>' + html.escape(line or ' ') + '</p>' for line in text.splitlines())
    story = fitz.Story(html='<article>' + paragraphs + '</article>', user_css='body {font-family: sans-serif; font-size: 10pt;} p {margin: 0 0 5pt; overflow-wrap: anywhere;}')
    import io
    output = io.BytesIO()
    writer = fitz.DocumentWriter(output)
    more = True
    while more:
        device = writer.begin_page(fitz.paper_rect('a4'))
        more, _ = story.place(fitz.Rect(45, 45, 550, 797))
        story.draw(device)
        writer.end_page()
    writer.close()
    data = output.getvalue()
    if diagrams:
        from .diagram_render import svg_for
        with fitz.open(stream=data, filetype="pdf") as document:
            for diagram in diagrams:
                svg = svg_for(diagram["mermaid_source"], diagram["title"]).encode()
                with fitz.open(stream=svg, filetype="svg") as image:
                    with fitz.open(stream=image.convert_to_pdf(), filetype="pdf") as graphic:
                        page = document.new_page()
                        page.insert_text((45, 35), diagram["title"][:90], fontsize=12)
                        page.show_pdf_page(fitz.Rect(45, 60, 550, 790), graphic, 0)
            data = document.tobytes()
    return data


def latex_document(text):
    lines = [r'\documentclass{article}', r'\usepackage[T1]{fontenc}', r'\usepackage[utf8]{inputenc}', r'\usepackage[margin=1in]{geometry}', r'\begin{document}']
    for line in text.splitlines():
        match = re.match(r'^(#{1,3})\s+(.*)', line)
        if match:
            command = ['section','subsection','subsubsection'][len(match[1])-1]
            lines.append('\\' + command + '*{' + tex_escape(match[2]) + '}')
        elif not line.strip():
            lines.append(r'\par')
        else:
            lines.append(tex_escape(line) + r'\par')
    return '\n'.join(lines + [r'\end{document}'])


def export_text(text, format, diagrams=None):
    if format == 'pdf':
        return pdf_report(text, diagrams), 'application/pdf', 'pdf'
    if format == 'tex':
        return latex_document(text).encode(), 'application/x-tex', 'tex'
    if format in {'txt','md'}:
        return text.encode(), 'text/markdown' if format == 'md' else 'text/plain', format
    if format == 'docx':
        from docx import Document
        from io import BytesIO
        document = Document()
        for line in text.splitlines():
            match = re.match(r'^(#{1,3})\s+(.*)', line)
            if match:
                document.add_heading(match[2], len(match[1]))
            else:
                document.add_paragraph(line)
        if diagrams:
            from .diagram_render import png_for
            from docx.shared import Inches
            for diagram in diagrams:
                document.add_heading(diagram["title"], level=2)
                document.add_picture(BytesIO(png_for(diagram["mermaid_source"], diagram["title"])), width=Inches(6))
        output = BytesIO()
        document.save(output)
        return output.getvalue(), 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'docx'
    raise ValueError('Format must be pdf, docx, tex, md, or txt.')
