from __future__ import annotations

import csv
import os
from datetime import datetime
from collections import defaultdict
from typing import Dict, List

from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image,
    PageBreak,
    HRFlowable,
    Table,
    TableStyle,
)
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.graphics.barcode import qr as rl_qr
# Force PyInstaller to include dynamically imported barcode modules.
from reportlab.graphics.barcode import common as _rl_barcode_common  # noqa: F401
from reportlab.graphics.barcode import code128 as _rl_barcode_code128  # noqa: F401
from reportlab.graphics.barcode import code39 as _rl_barcode_code39  # noqa: F401
from reportlab.graphics.barcode import code93 as _rl_barcode_code93  # noqa: F401
from reportlab.graphics.barcode import usps as _rl_barcode_usps  # noqa: F401
from reportlab.graphics.barcode import usps4s as _rl_barcode_usps4s  # noqa: F401
from reportlab.graphics.barcode import ecc200datamatrix as _rl_barcode_ecc200  # noqa: F401
from reportlab.graphics.barcode import dmtx as _rl_barcode_dmtx  # noqa: F401
from reportlab.graphics.shapes import Drawing
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

from .io_utils import resolve_path, ensure_dir, pause
from .settings import Settings


def _register_unicode_font() -> str:
    local_dejavu = resolve_path("assets/dejavu-fonts-ttf/ttf/DejaVuSans.ttf")
    candidates = [
        local_dejavu,
        os.path.join(os.environ.get("WINDIR", r"C:\\Windows"), "Fonts", "arial.ttf"),
        os.path.join(os.environ.get("WINDIR", r"C:\\Windows"), "Fonts", "Calibri.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ]
    font_name = "AppUnicode"
    for path in candidates:
        try:
            if path and os.path.isfile(path):
                pdfmetrics.registerFont(TTFont(font_name, path))
                return font_name
        except Exception:
            continue
    return "Helvetica"


def _make_styles(font_name: str):
    styles = getSampleStyleSheet()
    for key in ("Normal", "BodyText", "Title", "Heading1", "Heading2", "Heading3"):
        if key in styles.byName:
            styles.byName[key].fontName = font_name
    if "Justify" not in styles.byName:
        styles.add(ParagraphStyle(name="Justify", alignment=TA_JUSTIFY, fontName=font_name))
    return styles


class PDFGenerator:
    def __init__(self, settings: Settings) -> None:
        self.s = settings
        self.output_dir = resolve_path(self.s.pdf_outputpath or "pdf-files")
        ensure_dir(self.output_dir)

        self._font_name = _register_unicode_font()
        self.styles = _make_styles(self._font_name)

    def generate(self) -> None:
        """Generate ANTON PDFs from a CSV."""
        csv_path = resolve_path(self.s.csv_file)
        if not os.path.isfile(csv_path):
            print("FEHLER!")
            print(f"Die CSV-Datei ({csv_path}) wurde nicht gefunden.")
            pause()
            raise FileNotFoundError(csv_path)

        rows = self._read_anton_csv(csv_path, delimiter=(self.s.csv_delimiter or ","))
        if not rows:
            print("Keine Datenzeilen in der CSV gefunden.")
            pause()
            return
        total = len(rows)
        next_progress = 10

        onedoc_setting = str(getattr(self.s, "pdf_onedoc", "")).strip().lower()
        if onedoc_setting:
            one_doc = (onedoc_setting == "ja")
        else:
            one_doc = (str(self.s.pdf_einzeln).strip().lower() != "ja")
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        anton_logo = resolve_path("assets/ANTON.png")
        group_setting = str(getattr(self.s, "pdf_schoolgroup", "1")).strip() or "1"

        if one_doc:
            classes: Dict[str, List[Dict[str, str]]] = defaultdict(list)
            for r in rows:
                cls_raw = (r.get("Klasse") or "").strip()
                # Lehrkräfte haben oft keine Klassenangabe -> packe sie in "Lehrkräfte"
                if not cls_raw and (group_setting == "2" or (r.get("Anrede") or "").strip()):
                    cls = "Lehrkräfte"
                else:
                    cls = cls_raw or "ohne_klasse"
                classes[cls].append(r)

            processed = 0
            for cls, people in classes.items():
                if cls == "Lehrkräfte":
                    output_filename = f"Lehrkräfte_Zugangsdaten_{timestamp}.pdf"
                else:
                    output_filename = f"{cls}_ANTON-Zugangsdaten_{timestamp}.pdf"
                output_filepath = os.path.join(self.output_dir, output_filename)
                doc = SimpleDocTemplate(output_filepath, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=18, bottomMargin=18)
                story: List = []

                for idx, r in enumerate(people, start=1):
                    processed += 1
                    pct = int(processed * 100 / total) if total else 100
                    if pct >= next_progress:
                        print(f"Fortschritt: {pct}% ({processed}/{total})")
                        next_progress += 10
                    story.extend(self._build_anton_story(r, anton_logo))
                    # Nur zwischen Einträgen einen PageBreak einfügen
                    if idx < len(people):
                        story.append(PageBreak())

                doc.build(story)
        else:
            for idx, r in enumerate(rows, start=1):
                pct = int(idx * 100 / total) if total else 100
                if pct >= next_progress:
                    print(f"Fortschritt: {pct}% ({idx}/{total})")
                    next_progress += 10
                chunk = self._build_anton_story(r, anton_logo)
                first_given = (r.get("Vorname") or "").split()[0] if r.get("Vorname") else ""
                person_name = f"{r.get('Klasse','')}_{r.get('Nachname','')},{first_given}".strip("_")
                output_filename = f"{person_name}_{timestamp}.pdf"
                output_filepath = os.path.join(self.output_dir, output_filename)
                doc = SimpleDocTemplate(output_filepath, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=18, bottomMargin=18)
                doc.build(chunk)

        print(f"PDFs erstellt. Ausgabeordner: {self.output_dir}")
        pause()

    # Helpers
    def _read_anton_csv(self, path: str, *, delimiter: str = ",") -> List[Dict[str, str]]:
        rows: List[Dict[str, str]] = []
        with open(path, "r", encoding="utf-8", newline="") as f:
            first_line = f.readline()
            if ";" in first_line and delimiter == ",":
                delimiter = ";"
            f.seek(0)
            reader = csv.reader(f, delimiter=delimiter)
            try:
                header = next(reader)
            except StopIteration:
                return []
            hdr_norm = [(h or "").strip().lower() for h in header]

            def idx(name: str) -> int:
                try:
                    return hdr_norm.index(name.lower())
                except ValueError:
                    return -1

            i_anrede = idx("anrede")
            i_v = idx("vorname")
            i_n = idx("nachname")
            i_k = idx("klasse")
            i_r = idx("referenz")
            i_c = -1
            for cand in ("anmelde-code", "login-code", "logincode", "login_code"):
                j = idx(cand)
                if j != -1:
                    i_c = j
                    break

            assume = (min([x for x in (i_v, i_n, i_k, i_r) if x != -1] or [-1]) == -1)

            for row in reader:
                if not row:
                    continue
                if assume:
                    v = (row[0] if len(row) > 0 else "").strip()
                    n = (row[1] if len(row) > 1 else "").strip()
                    k = (row[2] if len(row) > 2 else "").strip()
                    r = (row[3] if len(row) > 3 else "").strip()
                    c = (row[4] if len(row) > 4 else "").strip()
                    anr = ""
                else:
                    anr = (row[i_anrede] if i_anrede != -1 and len(row) > i_anrede else "").strip()
                    v = (row[i_v] if i_v != -1 and len(row) > i_v else "").strip()
                    n = (row[i_n] if i_n != -1 and len(row) > i_n else "").strip()
                    k = (row[i_k] if i_k != -1 and len(row) > i_k else "").strip()
                    r = (row[i_r] if i_r != -1 and len(row) > i_r else "").strip()
                    c = (row[i_c] if i_c != -1 and len(row) > i_c else "").strip()
                    # Fallback auf erste Spalten, falls Inhalte leer waren
                    if not v and len(row) > 0:
                        v = (row[0] or "").strip()
                    if not n and len(row) > 1:
                        n = (row[1] or "").strip()
                if not (v or n):
                    continue
                rows.append({
                    "Anrede": anr,
                    "Vorname": v,
                    "Nachname": n,
                    "Klasse": k,
                    "Referenz": r,
                    "Code": c,
                })
        return rows

    def _qr_drawing(self, data: str, size: int = 200) -> Drawing:
        qr_code = rl_qr.QrCodeWidget(data)
        bounds = qr_code.getBounds()
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]
        drawing = Drawing(size, size, transform=[size / width, 0, 0, size / height, 0, 0])
        drawing.add(qr_code)
        return drawing

    def _divider(self) -> Table:
        """Scissor icon with horizontal line to visually separate sections."""
        scissor = Paragraph("<font size=14>✂</font>", self.styles["Normal"])
        hr = HRFlowable(width="100%", thickness=1, color=colors.black, spaceBefore=2, spaceAfter=2)
        tbl = Table([[scissor, hr]], colWidths=[10 * mm, None])
        tbl.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        return tbl

    def _sticker(self, firstname: str, lastname: str, code: str, anton_logo_path: str) -> Table:
        """Create a small table-based sticker with logo, stacked name, and QR."""
        # Logo with original aspect ratio (~25mm height)
        logo_w = 25 * mm
        logo_h = 25 * mm
        try:
            img_reader = ImageReader(anton_logo_path)
            iw, ih = img_reader.getSize()
            if iw and ih:
                logo_w = logo_h * (iw / ih)
            logo = Image(anton_logo_path, width=logo_w, height=logo_h)
        except Exception:
            logo = Paragraph("", self.styles["Normal"])

        # Name stacked; adjust font size dynamically; fixed sticker width ~100mm (10cm)
        first_given = (firstname or "").split()[0] if firstname else ""
        lines = [
            (first_given or " ").strip() or " ",
            (lastname or " ").strip() or " ",
        ]
        font_name = self._font_name
        base_size = 14
        target_width = 100 * mm  # fixed sticker width
        pad = 6

        # Name (small) at top center, big code centered vertically/horizontally
        name_font = 8
        available_name_col = target_width - logo_w - (30 * mm)

        # Find the largest code font that fits the available width (centered block)
        def code_font_that_fits() -> int:
            for fs in (28, 26, 24, 22, 20, 18, 16, 14, 12, 10, 9, 8):
                w = max(
                    pdfmetrics.stringWidth(code or "", font_name, fs),
                    pdfmetrics.stringWidth(lines[0], font_name, name_font),
                    pdfmetrics.stringWidth(lines[1], font_name, name_font),
                ) + 2 * pad
                if w <= available_name_col:
                    return fs
            return 8

        code_font = code_font_that_fits()
        name_col = max(0, available_name_col)

        text = Paragraph(
            (
                f"<para align='center'>"
                f"<font size={name_font}>{lines[0]}<br/>{lines[1]}</font>"
                f"<br/><br/>"
                f"<font size={code_font}>{code}</font>"
                f"</para>"
            ),
            self.styles["Normal"],
        )

        # QR code shrunk for sticker
        qr_size = 90  # points, larger to nearly fill the sticker height
        qr_flow = self._qr_drawing(code or f"{first_given} {lastname}", size=qr_size)
        try:
            qr_flow.hAlign = "CENTER"
        except Exception:
            pass
        qr_w = 30 * mm

        tbl = Table([[logo, text, qr_flow]], colWidths=[logo_w, name_col, qr_w])
        tbl.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 1, colors.black),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), pad),
            ("RIGHTPADDING", (0, 0), (-1, -1), pad),
            ("TOPPADDING", (0, 0), (-1, -1), pad),
            ("BOTTOMPADDING", (0, 0), (-1, -1), pad),
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ]))
        return tbl

    def _build_anton_story(self, r: Dict[str, str], anton_logo_path: str) -> List:
        styles = self.styles
        if "Justify" not in styles.byName:
            styles.add(ParagraphStyle(name="Justify", alignment=TA_JUSTIFY, fontName=styles["Normal"].fontName))

        story: List = []
        # Logo (keep aspect ratio)
        try:
            img_reader = ImageReader(anton_logo_path)
            iw, ih = img_reader.getSize()
            target_w = 150
            target_h = (target_w / iw) * ih if iw else 150
            im = Image(anton_logo_path, width=target_w, height=target_h)
            im.hAlign = "CENTER"
            story.append(im)
        except Exception:
            pass
        story.append(Spacer(1, 12))

        anrede = (r.get("Anrede") or "").strip()
        firstname = (r.get("Vorname") or "").strip()
        lastname = (r.get("Nachname") or "").strip()
        code = (r.get("Code") or "").strip()
        anton_link = (self.s.pdf_antonlink or "https://www.anton.app").strip() or "https://www.anton.app"

        group = str(getattr(self.s, "pdf_schoolgroup", "1")).strip()
        force_teacher = (group == "2")
        is_teacher = force_teacher or bool(anrede)

        # Greeting (use first given name if multiple)
        first_given = (firstname or "").split()[0] if firstname else ""
        if is_teacher:
            full_name = (f"{first_given} {lastname}".strip()).strip()
            greet = f"Hallo {full_name},"
            story.append(Paragraph(f"<font size=14>{greet}</font>", styles["Justify"]))
        else:
            full_name = (f"{first_given} {lastname}".strip()).strip()
            if anrede:
                greet = f"{anrede} {full_name},"
            else:
                greet = f"Hallo {full_name},"
            story.append(Paragraph(f"<font size=14>{greet}</font>", styles["Justify"]))
        story.append(Spacer(1, 12))

        # Intro text
        story.append(Paragraph("<font size=14>Willkommen bei ANTON - der Lern-App für die Schule.</font>", styles["Normal"]))
        story.append(Spacer(1, 12))
        if is_teacher:
            story.append(Paragraph("<font size=14>Für Sie wurde ein Account angelegt.</font>", styles["Normal"]))
        else:
            story.append(Paragraph("<font size=14>Für dich wurde ein Account angelegt.</font>", styles["Normal"]))
        story.append(Spacer(1, 24))

        if is_teacher:
            story.append(Paragraph("<font size=14>Gehen Sie im Browser auf </font>", styles["Normal"]))
        else:
            story.append(Paragraph("<font size=14>Gehe im Browser auf </font>", styles["Normal"]))
        story.append(Spacer(1, 12))
        story.append(Paragraph(f"<font size=18>{anton_link}</font>", styles["Normal"]))
        story.append(Spacer(1, 12))

        if is_teacher:
            story.append(Paragraph("<font size=14>oder laden Sie die kostenlose ANTON-App herunter.</font>", styles["Normal"]))
        else:
            story.append(Paragraph("<font size=14>oder lade dir die kostenlose ANTON-App herunter.</font>", styles["Normal"]))
        story.append(Spacer(1, 24))

        if code:
            if is_teacher:
                story.append(Paragraph("<font size=14>Sie können sich mit folgendem Code bei ANTON einloggen:</font>", styles["Normal"]))
            else:
                story.append(Paragraph("<font size=14>Du kannst dich mit folgendem Code bei ANTON einloggen:</font>", styles["Normal"]))
            story.append(Spacer(1, 24))
            story.append(Paragraph(f"<font size=24>{code}</font>", styles["Heading1"]))
            story.append(Spacer(1, 24))
            if is_teacher:
                story.append(Paragraph("<font size=14>Oder Sie scannen in der ANTON-App diesen QR-Code:</font>", styles["Normal"]))
            else:
                story.append(Paragraph("<font size=14>Oder du scannst in der ANTON-App diesen QR-Code:</font>", styles["Normal"]))
            story.append(Spacer(1, 12))
            qr_flow = self._qr_drawing(code, size=200)
            try:
                qr_flow.hAlign = "CENTER"
            except Exception:
                pass
            story.append(qr_flow)
        # Divider and table sticker
        story.append(Spacer(1, 18))
        story.append(self._divider())
        story.append(Spacer(1, 12))
        story.append(self._sticker(firstname, lastname, code or "", anton_logo_path))

        return story
