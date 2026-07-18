"""Text-layer tokenization via pdfplumber.

The synthetic fixtures carry a large diagonal watermark whose glyphs (size
26-40 pt) overlap body text (size 7-18 pt) and corrupt naive word extraction.
We filter characters by size before assembling words.
"""
from __future__ import annotations

from pathlib import Path

import pdfplumber

WATERMARK_MIN_SIZE = 20.0


def _keep(obj) -> bool:
    if obj.get("object_type") != "char":
        return True
    return bool(obj.get("upright")) and obj.get("size", 0) < WATERMARK_MIN_SIZE


def extract_tokens(pdf_path: str | Path) -> tuple[list[dict], str, float, float]:
    """Returns (tokens, full_text, page_width, page_height).
    Tokens use PDF points with bottom-left origin. full_text includes every
    body-text word (used for adversarial-content detection, never as evidence).
    """
    with pdfplumber.open(str(pdf_path)) as pdf:
        page = pdf.pages[0]
        height = float(page.height)
        width = float(page.width)
        filtered = page.filter(_keep)
        tokens = []
        for w in filtered.extract_words():
            tokens.append(
                {
                    "text": w["text"],
                    "x0": float(w["x0"]),
                    "x1": float(w["x1"]),
                    "y0": height - float(w["bottom"]),
                    "y1": height - float(w["top"]),
                }
            )
        full_text = " ".join(t["text"] for t in tokens)
    return tokens, full_text, width, height


def has_text_layer(pdf_path: str | Path, min_tokens: int = 10) -> bool:
    try:
        tokens, _, _, _ = extract_tokens(pdf_path)
        return len(tokens) >= min_tokens
    except Exception:
        return False
