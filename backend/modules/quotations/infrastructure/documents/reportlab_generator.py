"""``QuotationDocumentGenerator`` with ReportLab (pure Python: no system libraries needed)."""

import io
from decimal import Decimal
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from modules.quotations.domain.quotation import Quotation
from modules.quotations.ports.outbound.ports import QuotationDocumentGenerator
from modules.shared_kernel.domain.money import PriceRange

BRAND = colors.HexColor("#b91c1c")
PENDING_PRICE = "Por confirmar"


def cop(value: Decimal) -> str:
    """Colombian format: $9.800.000"""
    return "$" + f"{int(value):,}".replace(",", ".")


def cop_range(price_range: PriceRange | None) -> str:
    if price_range is None:
        return PENDING_PRICE
    if price_range.min == price_range.max:
        return cop(price_range.min)
    return f"{cop(price_range.min)} – {cop(price_range.max)}"


class ReportLabQuotationGenerator(QuotationDocumentGenerator):
    """Text typed by the requester is escaped: ReportLab paragraphs interpret markup."""

    def preliminary_pdf(self, quotation: Quotation) -> bytes:
        buffer = io.BytesIO()
        document = SimpleDocTemplate(
            buffer,
            pagesize=LETTER,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=16 * mm,
            bottomMargin=16 * mm,
            title=f"Cotización preliminar {quotation.number}",
            author="Industrias Escolares",
        )
        styles = getSampleStyleSheet()
        small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8.5, leading=11)
        right = ParagraphStyle("right", parent=small, alignment=TA_RIGHT)
        title = ParagraphStyle("title", parent=styles["Title"], textColor=BRAND, fontSize=18)

        requester = quotation.requester
        story = [
            Paragraph("Industrias Escolares", title),
            Paragraph("Fabricación de mobiliario escolar · Bogotá, Colombia", small),
            Spacer(1, 6 * mm),
            Paragraph(f"<b>Cotización preliminar {quotation.number}</b>", styles["Heading2"]),
            Paragraph(
                f"Emitida el {quotation.issued_at:%d/%m/%Y} · Válida hasta el "
                f"{quotation.valid_until:%d/%m/%Y}",
                small,
            ),
            Spacer(1, 4 * mm),
            Paragraph(f"<b>Solicitante:</b> {escape(requester.full_name)}", small),
            Paragraph(
                f"<b>Correo:</b> {escape(requester.email)} · "
                f"<b>Teléfono:</b> {escape(requester.phone)}",
                small,
            ),
        ]
        if requester.institution or requester.tax_id:
            story.append(
                Paragraph(
                    f"<b>Institución:</b> {escape(requester.institution) or '—'} · "
                    f"<b>NIT:</b> {escape(requester.tax_id) or '—'}",
                    small,
                )
            )
        story.append(Spacer(1, 5 * mm))

        rows = [["Código", "Producto", "Cantidad", "Precio unitario (COP)", "Subtotal (COP)"]]
        for item in quotation.items:
            rows.append(
                [
                    item.product_code,
                    Paragraph(
                        f"{escape(item.description)}<br/>"
                        f"<font size=7>{escape(item.unit_of_measure)}</font>",
                        small,
                    ),
                    str(item.quantity),
                    Paragraph(cop_range(item.unit_price_range), right),
                    Paragraph(cop_range(item.subtotal_range), right),
                ]
            )
        table = Table(rows, colWidths=[22 * mm, 62 * mm, 18 * mm, 38 * mm, 38 * mm], repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (2, 1), (2, -1), "CENTER"),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story += [table, Spacer(1, 4 * mm)]

        total = quotation.estimated_total
        story.append(
            Paragraph(
                f"<b>Total estimado:</b> {cop_range(total)}",
                ParagraphStyle("total", parent=styles["Normal"], alignment=TA_RIGHT, fontSize=11),
            )
        )
        if quotation.unpriced_items:
            story.append(
                Paragraph(
                    f"{quotation.unpriced_items} producto(s) con precio por confirmar: la "
                    "administradora lo definirá al revisar su solicitud.",
                    right,
                )
            )

        dispatch = (
            f"{quotation.estimated_dispatch_date:%d/%m/%Y} (sujeta a confirmación)"
            if quotation.estimated_dispatch_date
            else "por confirmar"
        )
        story += [
            Spacer(1, 6 * mm),
            Paragraph(f"<b>Fecha estimada de despacho:</b> {dispatch}", small),
            Spacer(1, 4 * mm),
            Paragraph(
                "<b>Cotización preliminar sujeta a aprobación.</b> Los valores son un rango "
                "estimado a partir de precios usados en cotizaciones recientes. Los precios, las "
                "condiciones comerciales y la fecha de despacho se confirman en la cotización "
                "formal que enviará Industrias Escolares.",
                small,
            ),
        ]
        document.build(story)
        return buffer.getvalue()
