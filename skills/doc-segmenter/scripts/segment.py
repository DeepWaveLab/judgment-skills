#!/usr/bin/env python3
"""doc-segmenter - split Taiwan criminal judgments into canonical sections.

CLI:
    python3 skills/doc-segmenter/scripts/segment.py <text-or-pdf>

Library:
    from segment import segment
    result = segment(raw_text)                     # -> {"sections": [...]}
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, List


# ---------------------------------------------------------------------------
# Section anchor table. Ordered list preserves document-order tie-breaking for
# single-line anchors that share a prefix (e.g. `事實` vs `事實及理由`).
# ---------------------------------------------------------------------------
SECTION_PATTERNS: List[tuple[str, re.Pattern[str]]] = [
    ("主文", re.compile(r"^\s*主\s*文\s*$")),
    ("事實及理由", re.compile(r"^\s*事\s*實(?:\s*及\s*理\s*由)?\s*$")),
    ("犯罪事實", re.compile(r"^\s*犯\s*罪\s*事\s*實\s*$")),
    ("證據及所犯法條", re.compile(r"^\s*證\s*據(?:\s*及\s*所\s*犯\s*法\s*條)?\s*$")),
    ("論罪科刑", re.compile(r"^\s*論\s*罪\s*科\s*刑\s*$")),
    ("據上論斷", re.compile(r"^\s*據\s*上\s*論\s*斷.*$")),
    ("附錄法條", re.compile(r"^\s*附\s*錄.*法\s*條.*$")),
    ("理由", re.compile(r"^\s*理\s*由\s*$")),
]

# Page markers that pdfplumber leaves in the text. Stripped before anchor match.
LEADING_PAGE_NUM = re.compile(r"^\s*\d{1,3}\s+")
PAGE_FOOTER = re.compile(r"^\s*第[一二三四五六七八九十百零]+頁\s*$")

# Ordinal bullets that start a new paragraph inside a section body.
ORDINAL_BULLET = re.compile(r"^\s*[一二三四五六七八九十]+\s*[、．.]\s*")


def _normalize_lines(text: str) -> List[str]:
    """Strip page footers and leading page-number artifacts line by line."""
    out: List[str] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if PAGE_FOOTER.match(line):
            continue
        # Drop a leading "01 " / "02 " style marker that pdfplumber/pypdf may leave.
        line = LEADING_PAGE_NUM.sub("", line, count=1)
        out.append(line)
    return out


def _match_section(line: str) -> str | None:
    stripped = line.strip()
    if not stripped:
        return None
    for label, pattern in SECTION_PATTERNS:
        if pattern.match(stripped):
            return label
    return None


def _split_paragraphs(block: List[str]) -> List[str]:
    """Split a section body into paragraphs.

    Rules: blank lines end a paragraph; a Chinese ordinal bullet (一、二、...)
    at the start of a line also begins a new paragraph.
    """
    paragraphs: List[str] = []
    buf: List[str] = []

    def flush() -> None:
        if buf:
            joined = "\n".join(buf).strip()
            if joined:
                paragraphs.append(joined)
            buf.clear()

    for line in block:
        if not line.strip():
            flush()
            continue
        if ORDINAL_BULLET.match(line) and buf:
            flush()
        buf.append(line)
    flush()
    return paragraphs


def segment(text: str) -> Dict:
    """Segment a judgment text into canonical sections.

    Returns a dict shaped like ``{"sections": [{"id", "label", "paragraphs": [...]}]}``.
    """
    lines = _normalize_lines(text)

    # First pass: locate anchor line indices.
    anchors: List[tuple[int, str]] = []
    for idx, line in enumerate(lines):
        label = _match_section(line)
        if label is not None:
            anchors.append((idx, label))

    if not anchors:
        paragraphs = _split_paragraphs(lines)
        return {
            "sections": [
                {
                    "id": "sec-01",
                    "label": "未分段",
                    "paragraphs": [
                        {"id": f"p-{i + 1:03d}", "text": p}
                        for i, p in enumerate(paragraphs)
                    ],
                }
            ]
        }

    sections: List[Dict] = []
    pid = 1  # global paragraph counter - ensures uniqueness across sections

    # Optional preamble (header / caption before the first anchor) is attached as
    # an implicit section so nothing is dropped.
    preamble_lines = lines[: anchors[0][0]]
    preamble_paragraphs = _split_paragraphs(preamble_lines)
    if preamble_paragraphs:
        sections.append(
            {
                "id": f"sec-{len(sections) + 1:02d}",
                "label": "前言",
                "paragraphs": [
                    {"id": f"p-{pid + i:03d}", "text": p}
                    for i, p in enumerate(preamble_paragraphs)
                ],
            }
        )
        pid += len(preamble_paragraphs)

    for i, (start_idx, label) in enumerate(anchors):
        end_idx = anchors[i + 1][0] if i + 1 < len(anchors) else len(lines)
        body = lines[start_idx + 1 : end_idx]
        paragraphs = _split_paragraphs(body)
        section_entry = {
            "id": f"sec-{len(sections) + 1:02d}",
            "label": label,
            "paragraphs": [
                {"id": f"p-{pid + j:03d}", "text": p}
                for j, p in enumerate(paragraphs)
            ],
        }
        pid += len(paragraphs)
        sections.append(section_entry)

    return {"sections": sections}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _load_input(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        # Delegate to the shared helper so PDFs work without pre-extraction.
        scripts_dir = Path(__file__).resolve().parents[3] / "scripts"
        sys.path.insert(0, str(scripts_dir))
        from pdf_to_text import pdf_to_text  # type: ignore

        return pdf_to_text(path)
    return path.read_text(encoding="utf-8")


def main(argv: List[str]) -> int:
    if len(argv) != 2:
        print("usage: segment.py <text-or-pdf>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    if not path.exists():
        print(f"not found: {path}", file=sys.stderr)
        return 1
    text = _load_input(path)
    result = segment(text)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
