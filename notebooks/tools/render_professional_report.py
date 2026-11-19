"""Dựng PDF từ bản Markdown biên tập, giữ hình và ngắt trang có chủ đích."""
import argparse
import html
import re
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Image,
    Preformatted, KeepTogether,
)

ROOT = Path(__file__).resolve().parents[2]
INK, NAVY, TEAL = "#243B53", "#173F5F", "#147D80"
PAGE_W, PAGE_H = A4
MARGIN = 43
WIDTH = PAGE_W - MARGIN * 2


class PageNumbers(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pages = []

    def showPage(self):
        self.pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self.pages)
        for page in self.pages:
            self.__dict__.update(page)
            self.setFont("Report", 8)
            self.setFillColor(colors.HexColor(INK))
            self.drawString(MARGIN, 27, "Airbnb Toronto · Mẫu phân công · 20/11/2026")
            self.drawRightString(PAGE_W-MARGIN, 27, f"{self._pageNumber} / {total}")
            super().showPage()
        super().save()


def markup(text):
    text = html.escape(text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^\s)]+)\)",
                  r'<link href="\2" color="#147D80"><u>\1</u></link>', text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"`([^`]+)`", r'<font name="Mono">\1</font>', text)
    return text


def render(source, output, fonts):
    for name, file in (("Report", "DejaVuSans.ttf"), ("ReportBold", "DejaVuSans-Bold.ttf"),
                       ("ReportItalic", "DejaVuSans-Oblique.ttf"), ("Mono", "DejaVuSansMono.ttf")):
        pdfmetrics.registerFont(TTFont(name, str(fonts/file)))
    pdfmetrics.registerFontFamily("Report", normal="Report", bold="ReportBold", italic="ReportItalic", boldItalic="ReportBold")
    normal = ParagraphStyle("Body", fontName="Report", fontSize=9.5, leading=13.8,
                            textColor=colors.HexColor(INK), alignment=TA_JUSTIFY,
                            spaceAfter=8, splitLongWords=True)
    styles = {
        "body": normal,
        "h1": ParagraphStyle("Title", parent=normal, fontName="ReportBold", fontSize=26,
                             leading=32, textColor=colors.HexColor(NAVY), alignment=TA_LEFT,
                             spaceBefore=12, spaceAfter=14, keepWithNext=True),
        "h2": ParagraphStyle("Section", parent=normal, fontName="ReportBold", fontSize=16,
                             leading=21, textColor=colors.HexColor(NAVY), alignment=TA_LEFT,
                             spaceBefore=8, spaceAfter=10, keepWithNext=True),
        "h3": ParagraphStyle("Subsection", parent=normal, fontName="ReportBold", fontSize=11,
                             leading=15, textColor=colors.HexColor(TEAL), alignment=TA_LEFT,
                             spaceBefore=7, spaceAfter=6, keepWithNext=True),
        "caption": ParagraphStyle("Caption", parent=normal, fontSize=8, leading=11.2,
                                  alignment=TA_LEFT, textColor=colors.HexColor("#536A7D"), spaceAfter=9),
        "cell": ParagraphStyle("Cell", parent=normal, fontSize=8.1, leading=11.1,
                               alignment=TA_LEFT, spaceAfter=0),
        "header": ParagraphStyle("Header", parent=normal, fontName="ReportBold", fontSize=8.1,
                                 leading=11.1, textColor=colors.white, alignment=TA_LEFT, spaceAfter=0),
    }
    lines = source.read_text(encoding="utf-8").splitlines()
    story, i = [], 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line == "<!-- page -->":
            story.append(PageBreak()); i += 1; continue
        if line.startswith("```"):
            code = []; i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i]); i += 1
            code_style = ParagraphStyle("Code", fontName="Mono", fontSize=7.2, leading=11,
                                        textColor=colors.HexColor(INK), backColor=colors.HexColor("#EFF4F8"),
                                        borderPadding=7, spaceBefore=4, spaceAfter=10)
            story.append(Preformatted("\n".join(code), code_style)); i += 1; continue
        image = re.match(r"!\[(.*?)\]\((.*?)\)", line)
        if image:
            target = source.parent/image.group(2)
            with PILImage.open(target) as image_file:
                w, h = image_file.size
            limits = {"02_room_distribution.png": 140, "03_spatial_sample.png": 155,
                      "04_snapshot_trends.png": 178, "05_calendar_months.png": 148,
                      "06_model_vs_baseline.png": 170, "07_aspects.png": 163}
            scale = min(WIDTH/w, limits.get(target.name, 238)/h)
            picture = Image(str(target), width=w*scale, height=h*scale)
            caption_index = i+1
            while caption_index < len(lines) and not lines[caption_index].strip():
                caption_index += 1
            if caption_index < len(lines) and lines[caption_index].startswith("*Hình"):
                caption = Paragraph(markup(lines[caption_index].strip().strip("*")), styles["caption"])
                story.append(KeepTogether([picture, Spacer(1,5), caption])); i = caption_index+1
            else:
                story.extend([picture, Spacer(1,8)]); i += 1
            continue
        if line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [x.strip() for x in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", x) for x in cells):
                    rows.append(cells)
                i += 1
            count = len(rows[0])
            fractions = {2:[.35,.65], 3:[.18,.39,.43], 4:[.40,.17,.17,.26], 5:[.32,.13,.13,.20,.22]}[count]
            if "Phương pháp" in rows[0][0]:
                fractions = [.21,.13,.14,.26,.26]
            elif "Trạng thái giá" in rows[0][0]:
                fractions = [.36,.16,.48]
            elif "KPI" == rows[0][0]:
                fractions = [.08,.43,.49]
            cells = [[Paragraph(markup(v), styles["header"] if r==0 else styles["cell"])
                      for v in row] for r,row in enumerate(rows)]
            table = Table(cells, colWidths=[WIDTH*x for x in fractions], repeatRows=1, hAlign="LEFT")
            table.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,0),colors.HexColor(NAVY)),
                ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.HexColor("#F0F5F8"),colors.white]),
                ("VALIGN",(0,0),(-1,-1),"TOP"),
                ("LEFTPADDING",(0,0),(-1,-1),7), ("RIGHTPADDING",(0,0),(-1,-1),7),
                ("TOPPADDING",(0,0),(-1,-1),6), ("BOTTOMPADDING",(0,0),(-1,-1),6),
                ("LINEBELOW",(0,0),(-1,0),.6,colors.HexColor(NAVY)),
                ("LINEBELOW",(0,-1),(-1,-1),.5,colors.HexColor("#D5E1E8")),
            ]))
            story.extend([table,Spacer(1,10)])
            continue
        heading = re.match(r"(#{1,3})\s+(.*)", line)
        if heading:
            story.append(Paragraph(markup(heading.group(2)), styles[f"h{len(heading.group(1))}"]))
            i += 1; continue
        paragraph=[line]; i += 1
        while i<len(lines) and lines[i].strip() and not lines[i].startswith(("#","|","![","<!--","```")):
            paragraph.append(lines[i].strip()); i += 1
        story.append(Paragraph(markup(" ".join(paragraph)), styles["body"]))

    def header(c, doc):
        c.saveState()
        c.setFont("ReportBold",7.5)
        c.setFillColor(colors.HexColor(TEAL))
        c.drawString(MARGIN,PAGE_H-29,"LẬP TRÌNH XỬ LÝ DỮ LIỆU  /  NHÓM 07")
        c.setFont("Report",7.5)
        c.drawRightString(PAGE_W-MARGIN,PAGE_H-29,"TORONTO AIRBNB")
        c.setStrokeColor(colors.HexColor("#D5E1E8"))
        c.line(MARGIN,PAGE_H-38,PAGE_W-MARGIN,PAGE_H-38)
        c.restoreState()

    output.parent.mkdir(parents=True,exist_ok=True)
    doc=SimpleDocTemplate(str(output),pagesize=A4,leftMargin=MARGIN,rightMargin=MARGIN,
                          topMargin=51,bottomMargin=44,title="Phân tích thị trường Airbnb Toronto - Nhóm 07",
                          author="Nhóm 07", subject="Báo cáo kỹ thuật từ mẫu phân công Inside Airbnb")
    doc.build(story,onFirstPage=header,onLaterPages=header,canvasmaker=PageNumbers)
    print(output)


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",type=Path,default=ROOT/"reports/report_professional.md")
    parser.add_argument("--output",type=Path,default=ROOT/"output/pdf/toronto_airbnb_report.pdf")
    parser.add_argument("--font-dir",type=Path)
    args=parser.parse_args()
    if args.font_dir is None:
        import matplotlib
        args.font_dir=Path(matplotlib.get_data_path())/"fonts/ttf"
    render(args.source,args.output,args.font_dir)
