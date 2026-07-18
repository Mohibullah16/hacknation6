"""OCR path for rasterized (image-only) fixtures.

Pipeline: pypdfium2 renders the page at a fixed scale -> RapidOCR (ONNX,
pip-only) detects text boxes -> pixel coordinates are mapped back to PDF
points (same page coordinate system as the text-layer path, per the pack's
evidence contract). OCR line boxes are split into word-level tokens by
proportional character width so the shared labeler can consume them.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pypdfium2 as pdfium

RENDER_SCALE = 3.0

_ocr_engine = None


def _engine():
    global _ocr_engine
    if _ocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR

        _ocr_engine = RapidOCR()
    return _ocr_engine


def render_page(pdf_path: str | Path, scale: float = RENDER_SCALE):
    doc = pdfium.PdfDocument(str(pdf_path))
    try:
        page = doc[0]
        width_pt, height_pt = page.get_size()
        bitmap = page.render(scale=scale)
        img = bitmap.to_pil()
    finally:
        doc.close()
    return img, float(width_pt), float(height_pt)


def _split_line_to_words(text: str, x0: float, x1: float, y0: float, y1: float) -> list[dict]:
    """Distribute a line box across its space-separated words proportionally
    to character counts (monospace-ish approximation, adequate for IoU>=0.5)."""
    words = text.split()
    if not words:
        return []
    if len(words) == 1:
        return [{"text": words[0], "x0": x0, "x1": x1, "y0": y0, "y1": y1}]
    total_chars = sum(len(w) for w in words) + len(words) - 1
    span = x1 - x0
    out = []
    cursor = x0
    for w in words:
        w_width = span * (len(w) / total_chars)
        gap = span * (1 / total_chars)
        out.append({"text": w, "x0": cursor, "x1": cursor + w_width, "y0": y0, "y1": y1})
        cursor += w_width + gap
    return out


def extract_tokens_ocr(pdf_path: str | Path) -> tuple[list[dict], str, float, float, float]:
    """Returns (tokens, full_text, page_width_pt, page_height_pt, mean_ocr_score)."""
    img, width_pt, height_pt = render_page(pdf_path)
    result, _ = _engine()(np.array(img))
    tokens: list[dict] = []
    scores: list[float] = []
    if result:
        px_per_pt = img.width / width_pt
        for box, text, score in result:
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            x0 = min(xs) / px_per_pt
            x1 = max(xs) / px_per_pt
            # image y (top-left origin) -> PDF points (bottom-left origin)
            y1 = height_pt - min(ys) / px_per_pt
            y0 = height_pt - max(ys) / px_per_pt
            # Skip the giant diagonal watermark: its boxes are far taller than
            # any body-text line.
            if (y1 - y0) > 24:
                continue
            tokens.extend(_split_line_to_words(str(text), x0, x1, y0, y1))
            scores.append(float(score))
    full_text = " ".join(t["text"] for t in tokens)
    mean_score = float(np.mean(scores)) if scores else 0.0
    return tokens, full_text, width_pt, height_pt, mean_score
