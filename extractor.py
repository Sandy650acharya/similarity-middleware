import io
import os
from typing import Tuple

import chardet
import docx2txt
import pdfplumber

SUPPORTED = {".txt", ".pdf", ".docx"}

def _ext(name: str) -> str:
    return os.path.splitext(name or "")[1].lower()

def _read_txt(stream: io.BufferedReader) -> str:
    raw = stream.read()
    # Try to detect encoding; default utf-8
    enc = chardet.detect(raw).get("encoding") or "utf-8"
    try:
        return raw.decode(enc, errors="replace")
    except Exception:
        return raw.decode("utf-8", errors="replace")

def _read_pdf(stream: io.BufferedReader) -> str:
    text_parts = []
    with pdfplumber.open(stream) as pdf:
        for page in pdf.pages:
            text_parts.append(page.extract_text() or "")
    return "\n".join(text_parts).strip()

def _read_docx(stream: io.BufferedReader) -> str:
    # docx2txt expects a path; but it can also take file-like via NamedTemporaryFile.
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".docx") as tmp:
        tmp.write(stream.read())
        tmp.flush()
        return docx2txt.process(tmp.name) or ""

def extract_text_from_stream(stream, filename: str) -> Tuple[str, str]:
    """
    Returns (text, detected_type).
    Raises ValueError for unsupported types.
    """
    ext = _ext(filename)
    if ext not in SUPPORTED:
        raise ValueError(f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(SUPPORTED))}")
    buf = io.BytesIO(stream.read())
    buf.seek(0)

    if ext == ".txt":
        txt = _read_txt(buf)
        return txt, "text"
    if ext == ".pdf":
        txt = _read_pdf(buf)
        return txt, "pdf"
    if ext == ".docx":
        txt = _read_docx(buf)
        return txt, "docx"
    # (Legacy .doc not supported reliably on Render. Convert to .docx before upload.)
    raise ValueError("Unsupported file type.")
