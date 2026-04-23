#!/usr/bin/env python3
"""Shared PDF → text extractor for judgment-skills.

Prefers pdfplumber (layout-preserving) and falls back to pypdf.
Usage:
    python scripts/pdf_to_text.py samples/judgment_sample_001.pdf
    # or as a module:
    from scripts.pdf_to_text import pdf_to_text
"""
from __future__ import annotations

import sys
from pathlib import Path


def pdf_to_text(path: str | Path) -> str:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    try:
        import pdfplumber  # type: ignore
        with pdfplumber.open(str(path)) as pdf:
            return "\n".join((page.extract_text() or "") for page in pdf.pages)
    except ImportError:
        pass

    from pypdf import PdfReader  # type: ignore
    reader = PdfReader(str(path))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: pdf_to_text.py <pdf>", file=sys.stderr)
        sys.exit(2)
    print(pdf_to_text(sys.argv[1]))
