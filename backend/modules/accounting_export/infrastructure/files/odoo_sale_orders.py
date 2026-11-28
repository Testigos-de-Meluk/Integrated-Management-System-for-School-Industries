"""Odoo Community 20 sale order import file (.xlsx) — ``OrderFileFormatter`` Strategy.

Odoo replaces Siigo Pyme at Industrias Escolares (team decision, November 2026). Each work order
becomes one **sale order** (``sale.order``) imported by hand in Odoo: Ventas → Pedidos → ⚙ →
Importar registros. The layout is Odoo's own "import-compatible" one:

* Row 1 holds the **technical field names**, so Odoo maps every column by itself whatever the
  language of the user interface.
* One row per item. The first row of each order carries the order fields; the following rows of
  the same order leave them empty and Odoo adds them as more lines of that order.

Columns:

=============================  ===========================================================
``partner_id``                 Customer **name**: the contact must already exist in Odoo with
                               exactly this name (customers are created there by hand).
``client_order_ref``           O.T. number (Odoo's "Referencia del cliente").
``origin``                     Source quotation number (Odoo's "Documento origen").
``commitment_date``            Agreed delivery date (Odoo's "Fecha de entrega"), at noon so no
                               time zone moves it to another day.
``order_line/product_id``      Product **code**: Odoo finds the product by its internal
                               reference, which must equal the IMSI code.
``order_line/name``            Item description (IMSI snapshot).
``order_line/product_uom_qty`` Quantity.
=============================  ===========================================================

O.T.s carry no prices: Odoo fills each line with the product's sale price. The NIT is not a
column because Odoo would not use it to find the contact; the O.T. number links both systems.
"""

from datetime import datetime, time
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font

from modules.accounting_export.ports.outbound.ports import OrderFileFormatter, QueuedWorkOrder

HEADERS = (
    "partner_id",
    "client_order_ref",
    "origin",
    "commitment_date",
    "order_line/product_id",
    "order_line/name",
    "order_line/product_uom_qty",
)
DELIVERY_TIME = time(12, 0)


class OdooSaleOrderXlsxFormatter(OrderFileFormatter):
    extension = "xlsx"
    content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    def format(self, orders: list[QueuedWorkOrder]) -> bytes:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Pedidos de venta"
        sheet.append(HEADERS)
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for order in orders:
            for position, item in enumerate(order.items):
                header = (
                    (
                        order.customer_name,
                        order.number,
                        order.quotation_number,
                        datetime.combine(order.agreed_delivery_date, DELIVERY_TIME),
                    )
                    if position == 0
                    else (None, None, None, None)
                )
                sheet.append((*header, item.product_code, item.description, item.quantity))
                if position == 0:
                    sheet.cell(sheet.max_row, 4).number_format = "yyyy-mm-dd hh:mm:ss"
        for column, width in zip("ABCDEFG", (40, 20, 20, 20, 22, 50, 14), strict=True):
            sheet.column_dimensions[column].width = width
        sheet.freeze_panes = "A2"
        buffer = BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()
