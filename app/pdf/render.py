"""Render plain-text letters to simple A4 PDF (Windows + Linux fonts)."""

from __future__ import annotations

import os
from io import BytesIO


_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\calibri.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
]


def text_to_pdf_bytes(text: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    font_name = "Helvetica"
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("UIFont", path))
                font_name = "UIFont"
                break
            except Exception:
                pass

    t = (text or "").replace("**", "").replace("\r\n", "\n").replace("\r", "\n")
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    left, right, top, bottom = 50, 50, 60, 60
    font_size, leading = 11, 14
    c.setFont(font_name, font_size)
    y = height - top
    max_width = width - left - right

    def wrap_line(line: str):
        words = line.split(" ")
        out, cur = [], ""
        for w in words:
            cand = (cur + " " + w).strip()
            if pdfmetrics.stringWidth(cand, font_name, font_size) <= max_width:
                cur = cand
            else:
                if cur:
                    out.append(cur)
                cur = w
        if cur:
            out.append(cur)
        return out

    for raw in t.split("\n"):
        line = raw.rstrip()
        if not line.strip():
            y -= leading
            if y < bottom:
                c.showPage()
                c.setFont(font_name, font_size)
                y = height - top
            continue
        for wline in wrap_line(line):
            c.drawString(left, y, wline)
            y -= leading
            if y < bottom:
                c.showPage()
                c.setFont(font_name, font_size)
                y = height - top

    c.save()
    buf.seek(0)
    return buf.getvalue()
