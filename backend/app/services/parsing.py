"""
Resume file → plain text.

PDF via pdfplumber (layout-aware word extraction handles most two-column
resumes), DOCX via python-docx (paragraphs *and* tables), plain text as-is.
Legacy binary .doc is rejected with a clear message rather than mis-parsed.
"""

import io
import re
import unicodedata
from pathlib import Path

import pdfplumber
from docx import Document

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}

_PDF_MAGIC = b"%PDF"
_ZIP_MAGIC = b"PK\x03\x04"  # DOCX is a zip container


class ParseError(ValueError):
    pass


def _clean(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\x00", "")
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return "\n".join(line.strip() for line in text.splitlines()).strip()


def parse_pdf(data: bytes) -> str:
    pages: list[str] = []
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            if len(pdf.pages) > 30:
                raise ParseError("PDF has more than 30 pages — that doesn't look like a resume.")
            for page in pdf.pages:
                text = page.extract_text(x_tolerance=2, y_tolerance=3, layout=False) or ""
                if text.strip():
                    pages.append(text)
    except ParseError:
        raise
    except Exception as e:  # pdfminer raises a zoo of exception types on corrupt files
        raise ParseError("The PDF could not be read. It may be corrupt or password protected.") from e
    return _clean("\n\n".join(pages))


def parse_docx(data: bytes) -> str:
    try:
        doc = Document(io.BytesIO(data))
    except Exception as e:
        raise ParseError("The DOCX file could not be read. It may be corrupt.") from e
    parts: list[str] = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(dict.fromkeys(cells)))  # merged cells repeat text
    return _clean("\n".join(parts))


def parse_txt(data: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return _clean(data.decode(encoding))
        except UnicodeDecodeError:
            continue
    raise ParseError("The text file encoding is not supported.")


def parse_resume(data: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".doc":
        raise ParseError("Legacy .doc files aren't supported. Please save the resume as PDF or DOCX.")
    if ext not in SUPPORTED_EXTENSIONS:
        raise ParseError(f"Unsupported file type '{ext or 'unknown'}'. Upload PDF, DOCX or TXT.")
    # Don't trust the extension alone
    if ext == ".pdf" and not data.startswith(_PDF_MAGIC):
        raise ParseError("This file has a .pdf extension but isn't a valid PDF.")
    if ext == ".docx" and not data.startswith(_ZIP_MAGIC):
        raise ParseError("This file has a .docx extension but isn't a valid Word document.")

    text = {".pdf": parse_pdf, ".docx": parse_docx, ".txt": parse_txt}[ext](data)
    if len(text) < 80:
        raise ParseError(
            "Almost no text could be extracted. If this is a scanned/image PDF, please upload a text-based version."
        )
    return text[:60_000]
