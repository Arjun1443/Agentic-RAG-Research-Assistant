"""Render actual Mermaid syntax using the locally installed Mermaid CLI."""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def _render(source, output_format):
    local = Path(__file__).resolve().parents[1] / 'node_modules' / '.bin' / ('mmdc.cmd' if os.name == 'nt' else 'mmdc')
    executable = os.environ.get('MERMAID_CLI') or shutil.which('mmdc') or (str(local) if local.exists() else None)
    if not executable:
        raise RuntimeError('Diagram image export requires Mermaid CLI (mmdc). You can still preview diagrams and download Mermaid source.')
    with tempfile.TemporaryDirectory() as directory:
        input_path = Path(directory) / 'diagram.mmd'
        output_path = Path(directory) / ('diagram.' + output_format)
        input_path.write_text(source, encoding='utf-8')
        command = [executable, '-i', str(input_path), '-o', str(output_path), '-b', 'white']
        if os.environ.get('MERMAID_PUPPETEER_CONFIG'):
            command.extend(['-p', os.environ['MERMAID_PUPPETEER_CONFIG']])
        result = subprocess.run(command, capture_output=True, timeout=45, shell=(os.name == 'nt'))
        if result.returncode or not output_path.exists():
            raise RuntimeError('Diagram could not be rendered. Check the Mermaid source and retry.')
        return output_path.read_bytes()


def svg_for(source, title):
    return _render(source, 'svg').decode('utf-8')


def png_for(source, title):
    return _render(source, 'png')


def pdf_for(source, title):
    return _render(source, 'pdf')
