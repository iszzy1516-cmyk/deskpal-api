"""Document parsing, chunking, and prompt-injection sanitization.

Upload security pipeline:
1. parse  — pypdf / python-docx / plain text, control chars stripped
2. chunk  — ~500 characters with 100-char overlap, paragraph-aware
3. screen — every chunk is checked against known prompt-injection patterns.
            Suspicious chunks are QUARANTINED: kept in the DB (auditability)
            but excluded from retrieval, and the document reports the count.

This is defense-in-depth layer 1. Layer 2 is the system prompt in rag.py that
tells the model document text is data, never instructions.
"""
import re

CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Known prompt-injection signals. Deliberately conservative patterns.
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+|any\s+|the\s+)?(previous|prior|above)\s+(instructions|prompts?|directions)",
    r"ignore\s+(all\s+)?(previous|the\s+above)\s+(rules|guidelines)",
    r"system\s+prompt",
    r"you\s+are\s+now\b",
    r"forget\s+(everything|all|your)\b.{0,30}(instructions|training|rules)",
    r"new\s+(instructions|persona|role)\s*:",
    r"disregard\s+(all|any|the)\s+(previous|prior|safety)",
    r"jailbreak",
    r"DAN\s+mode",
    r"developer\s+mode\s+enabled",
    r"reveal\s+(your\s+)?(system\s+)?prompt",
]
INJECTION_RE = re.compile("|".join(f"(?:{p})" for p in INJECTION_PATTERNS), re.IGNORECASE)

CHUNK_SIZE = 500
CHUNK_OVERLAP = 100

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def extract_text(filename: str, data: bytes) -> str:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}")
    if not data or len(data.strip()) == 0:
        raise ValueError("File is empty")

    if ext == ".txt":
        text = data.decode("utf-8", errors="replace")
    elif ext == ".pdf":
        from io import BytesIO

        from pypdf import PdfReader

        reader = PdfReader(BytesIO(data))
        text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
    else:  # .docx
        from io import BytesIO

        import docx

        document = docx.Document(BytesIO(data))
        text = "\n\n".join(p.text for p in document.paragraphs)

    text = CONTROL_CHARS.sub("", text).strip()
    if len(text) < 10:
        raise ValueError("No readable text found in the file")
    return text


def split_chunks(text: str) -> list[str]:
    """Paragraph-aware fixed-size chunks with overlap."""
    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + CHUNK_SIZE, n)
        # extend to the next paragraph break if one is nearby
        if end < n:
            para = text.find("\n\n", end, end + 120)
            if para != -1:
                end = para
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start = end - CHUNK_OVERLAP
    return chunks


def screen_chunk(chunk: str) -> bool:
    """True if the chunk looks like a prompt-injection attempt."""
    return bool(INJECTION_RE.search(chunk))


def process_document_text(text: str) -> tuple[list[tuple[str, bool]], int]:
    """Returns (chunks with quarantine flags, quarantine count)."""
    chunks = split_chunks(text)
    flagged = [(c, screen_chunk(c)) for c in chunks]
    quarantined = sum(1 for _, q in flagged if q)
    return flagged, quarantined
