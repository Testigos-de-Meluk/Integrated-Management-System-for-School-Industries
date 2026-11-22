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
HEADERS = ["Código", "Producto", "Cantidad", "Precio unitario (COP)", "Subtotal (COP)"]


def cop(value: Decimal) -> str:
    """Colombian format: $9.800.000"""
    return "$" + f"{int(value):,}".replace(",", ".")


def cop_range(price_range: PriceRange | None) -> str:
    if price_range is None:
        return PENDING_PRICE
    if price_range.min == price_range.max:
        return cop(price_range.min)
    return f"{cop(price_range.min)} – {cop(price_range.max)}"


def _paragraphs(text: str, style: ParagraphStyle) -> list[Paragraph]:
    """User text, escaped (ReportLab paragraphs interpret markup), one paragraph per line."""
    return [Paragraph(escape(line) or "&nbsp;", style) for line in text.splitlines()]


class _Styles:
    def __init__(self) -> None:
        base = getSampleStyleSheet()
        self.heading = base["Heading2"]
        self.small = ParagraphStyle("small", parent=base["Normal"], fontSize=8.5, leading=11)
        self.right = ParagraphStyle("right", parent=self.small, alignment=TA_RIGHT)
        self.title = ParagraphStyle("title", parent=base["Title"], textColor=BRAND, fontSize=18)
        self.total = ParagraphStyle("total", parent=base["Normal"], alignment=TA_RIGHT, fontSize=11)


class ReportLabQuotationGenerator(QuotationDocumentGenerator):
    """Text typed by the requester or the Administrador is escaped."""

    def preliminary_pdf(self, quotation: Quotation) -> bytes:
        st = _Styles()
        story = self._header(quotation, st, f"Cotización preliminar {quotation.number}")
        story.append(
            self._table(
                [
                    [cop_range(item.unit_price_range), cop_range(item.subtotal_range)]
                    for item in quotation.items
                ],
                quotation,
                st,
            )
        )
        story += [
            Spacer(1, 4 * mm),
            Paragraph(f"<b>Total estimado:</b> {cop_range(quotation.estimated_total)}", st.total),
        ]
        if quotation.unpriced_items:
            story.append(
                Paragraph(
                    f"{quotation.unpriced_items} producto(s) con precio por confirmar: la "
                    "administradora lo definirá al revisar su solicitud.",
                    st.right,
                )
            )
        dispatch = (
            f"{quotation.estimated_dispatch_date:%d/%m/%Y} (sujeta a confirmación)"
            if quotation.estimated_dispatch_date
            else "por confirmar"
        )
        story += [
            Spacer(1, 6 * mm),
            Paragraph(f"<b>Fecha estimada de despacho:</b> {dispatch}", st.small),
            Spacer(1, 4 * mm),
            Paragraph(
                "<b>Cotización preliminar sujeta a aprobación.</b> Los valores son un rango "
                "estimado a partir de precios usados en cotizaciones recientes. Los precios, las "
                "condiciones comerciales y la fecha de despacho se confirman en la cotización "
                "formal que enviará Industrias Escolares.",
                st.small,
            ),
        ]
        return self._build(story, f"Cotización preliminar {quotation.number}")

    def formal_pdf(self, quotation: Quotation) -> bytes:
        st = _Styles()
        story = self._header(quotation, st, f"Cotización {quotation.number}")
        story.append(
            self._table(
                [
                    [
                        cop(item.final_unit_price) if item.final_unit_price is not None else "—",
                        cop(item.final_subtotal) if item.final_subtotal is not None else "—",
                    ]
                    for item in quotation.items
                ],
                quotation,
                st,
            )
        )
        total = quotation.final_total
        story += [
            Spacer(1, 4 * mm),
            Paragraph(f"<b>Total:</b> {cop(total) if total is not None else '—'}", st.total),
            Spacer(1, 6 * mm),
        ]
        if quotation.estimated_dispatch_date:
            story.append(
                Paragraph(
                    f"<b>Fecha de despacho:</b> {quotation.estimated_dispatch_date:%d/%m/%Y}",
                    st.small,
                )
            )
        if quotation.commercial_terms:
            story += [
                Spacer(1, 3 * mm),
                Paragraph("<b>Condiciones comerciales</b>", st.small),
                *_paragraphs(quotation.commercial_terms, st.small),
            ]
        approved = f"{quotation.approved_at:%d/%m/%Y}" if quotation.approved_at else ""
        story += [
            Spacer(1, 6 * mm),
            Paragraph(
                f"Cotización aprobada el {approved} por "
                f"{escape(quotation.approved_by_name) or 'Industrias Escolares'}.",
                st.small,
            ),
        ]
        return self._build(story, f"Cotización {quotation.number}")

    # --- Pieces -------------------------------------------------------------------------------

    @staticmethod
    def _header(quotation: Quotation, st: _Styles, heading: str) -> list:
        requester = quotation.requester
        story = [
            Paragraph("Industrias Escolares", st.title),
            Paragraph("Fabricación de mobiliario escolar · Bogotá, Colombia", st.small),
            Spacer(1, 6 * mm),
            Paragraph(f"<b>{heading}</b>", st.heading),
            Paragraph(
                f"Emitida el {quotation.issued_at:%d/%m/%Y} · Válida hasta el "
                f"{quotation.valid_until:%d/%m/%Y}",
                st.small,
            ),
            Spacer(1, 4 * mm),
            Paragraph(f"<b>Solicitante:</b> {escape(requester.full_name)}", st.small),
            Paragraph(
                f"<b>Correo:</b> {escape(requester.email)} · "
                f"<b>Teléfono:</b> {escape(requester.phone)}",
                st.small,
            ),
        ]
        if requester.institution or requester.tax_id:
            story.append(
                Paragraph(
                    f"<b>Institución:</b> {escape(requester.institution) or '—'} · "
                    f"<b>NIT:</b> {escape(requester.tax_id) or '—'}",
                    st.small,
                )
            )
        story.append(Spacer(1, 5 * mm))
        return story

    @staticmethod
    def _table(prices: list[list[str]], quotation: Quotation, st: _Styles) -> Table:
        rows: list[list] = [HEADERS]
        for item, (unit, subtotal) in zip(quotation.items, prices, strict=True):
            rows.append(
                [
                    item.product_code,
                    Paragraph(
                        f"{escape(item.description)}<br/>"
                        f"<font size=7>{escape(item.unit_of_measure)}</font>",
                        st.small,
                    ),
                    str(item.quantity),
                    Paragraph(unit, st.right),
                    Paragraph(subtotal, st.right),
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
        return table

    @staticmethod
    def _build(story: list, title: str) -> bytes:
        buffer = io.BytesIO()
        SimpleDocTemplate(
            buffer,
            pagesize=LETTER,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=16 * mm,
            bottomMargin=16 * mm,
            title=title,
            author="Industrias Escolares",
        ).build(story)
        return buffer.getvalue()
