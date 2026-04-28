#!/usr/bin/env python3
"""Render a markdown blog (with inline ![](path) images) to PDF using reportlab."""
import re
import sys
from pathlib import Path
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, grey
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, HRFlowable, PageBreak
)
from PIL import Image as PILImage

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
base_dir = src.parent

styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=24, leading=28, spaceAfter=12, textColor=HexColor("#111"))
H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=18, leading=22, spaceBefore=14, spaceAfter=8, textColor=HexColor("#222"))
H3 = ParagraphStyle("H3", parent=styles["Heading3"], fontSize=14, leading=18, spaceBefore=10, spaceAfter=6, textColor=HexColor("#333"))
BODY = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=11, leading=16, spaceAfter=8)
QUOTE = ParagraphStyle("Quote", parent=BODY, leftIndent=20, textColor=HexColor("#555"), fontName="Helvetica-Oblique")
LI = ParagraphStyle("LI", parent=BODY, leftIndent=18, bulletIndent=6, spaceAfter=4)

def md_inline(t: str) -> str:
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<!\*)\*(?!\*)(.+?)\*", r"<i>\1</i>", t)
    t = re.sub(r"`([^`]+)`", r'<font face="Courier">\1</font>', t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<link href="\2" color="blue">\1</link>', t)
    return t

def resolve_img(p: str) -> Path:
    pp = (base_dir / p).resolve() if not p.startswith("/") else Path(p)
    return pp

def img_flowable(path: Path, max_w=5.5*inch):
    try:
        with PILImage.open(path) as im:
            w, h = im.size
        ratio = h / w
        iw = min(max_w, w)
        return Image(str(path), width=iw, height=iw * ratio)
    except Exception as e:
        return Paragraph(f"<i>[image missing: {path.name}]</i>", BODY)

flow = []
text = src.read_text()
lines = text.split("\n")
i = 0
img_re = re.compile(r"^!\[[^\]]*\]\(([^)]+)\)\s*$")
while i < len(lines):
    line = lines[i].rstrip()
    if not line.strip():
        flow.append(Spacer(1, 6)); i += 1; continue
    m = img_re.match(line)
    if m:
        flow.append(Spacer(1, 4))
        flow.append(img_flowable(resolve_img(m.group(1))))
        flow.append(Spacer(1, 6))
        i += 1; continue
    if line.startswith("# "):
        flow.append(Paragraph(md_inline(line[2:]), H1))
    elif line.startswith("## "):
        flow.append(Paragraph(md_inline(line[3:]), H2))
    elif line.startswith("### "):
        flow.append(Paragraph(md_inline(line[4:]), H3))
    elif line.startswith("> "):
        flow.append(Paragraph(md_inline(line[2:]), QUOTE))
    elif line.startswith("---"):
        flow.append(HRFlowable(width="100%", color=grey, spaceBefore=6, spaceAfter=6))
    elif re.match(r"^\s*[-*]\s", line):
        flow.append(Paragraph("• " + md_inline(re.sub(r"^\s*[-*]\s", "", line)), LI))
    elif re.match(r"^\s*\d+\.\s", line):
        flow.append(Paragraph(md_inline(re.sub(r"^\s*\d+\.\s", "", line)) , LI))
    else:
        # accumulate paragraph
        buf = [line]
        j = i + 1
        while j < len(lines) and lines[j].strip() and not lines[j].startswith(("#", ">", "-", "*", "!")) and not re.match(r"^\d+\.\s", lines[j]):
            buf.append(lines[j].rstrip()); j += 1
        flow.append(Paragraph(md_inline(" ".join(buf)), BODY))
        i = j; continue
    i += 1

doc = SimpleDocTemplate(str(dst), pagesize=LETTER,
                        leftMargin=0.7*inch, rightMargin=0.7*inch,
                        topMargin=0.7*inch, bottomMargin=0.7*inch,
                        title=src.stem)
doc.build(flow)
print(f"wrote {dst} ({dst.stat().st_size} bytes)")
