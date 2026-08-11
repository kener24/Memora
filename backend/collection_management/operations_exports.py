from io import BytesIO

import xlsxwriter
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


NAVY = "#17243B"
BLUE = "#2563EB"
PALE = "#E8F0FE"
RED = "#B42318"


def _workbook(title):
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    workbook.set_properties({"title": title, "company": "Memora"})
    formats = {
        "title": workbook.add_format({"bold": True, "font_size": 18, "font_color": "#FFFFFF", "bg_color": NAVY}),
        "subtitle": workbook.add_format({"font_color": "#475467", "italic": True}),
        "header": workbook.add_format({"bold": True, "font_color": "#FFFFFF", "bg_color": BLUE, "text_wrap": True, "valign": "vcenter"}),
        "text": workbook.add_format({"bottom": 1, "bottom_color": "#D0D5DD"}),
        "integer": workbook.add_format({"num_format": "#,##0", "bottom": 1, "bottom_color": "#D0D5DD"}),
        "money": workbook.add_format({"num_format": 'L #,##0.00;[Red]-L #,##0.00', "bottom": 1, "bottom_color": "#D0D5DD"}),
        "date": workbook.add_format({"num_format": "dd/mm/yyyy hh:mm", "bottom": 1, "bottom_color": "#D0D5DD"}),
        "difference": workbook.add_format({"num_format": 'L #,##0.00;[Red]-L #,##0.00', "font_color": RED, "bottom": 1, "bottom_color": "#D0D5DD"}),
    }
    return output, workbook, formats


def build_productivity_excel(rows, generated_at):
    output, workbook, fmt = _workbook("Productividad de cobradores - Memora")
    sheet = workbook.add_worksheet("Productividad")
    columns = [
        ("Código", "employee_code", 16, "text"), ("Cobrador", "name", 27, "text"),
        ("Sucursal", "branch_name", 20, "text"), ("Contratos", "assigned_contracts", 12, "integer"),
        ("Clientes", "assigned_customers", 12, "integer"), ("Cartera pendiente", "pending_portfolio", 18, "money"),
        ("Cartera vencida", "overdue_portfolio", 18, "money"), ("Cobrado hoy", "collected_today", 16, "money"),
        ("Cobrado mes", "collected_month", 16, "money"), ("Pagos hoy", "payments_today", 12, "integer"),
        ("Gestiones hoy", "actions_today", 13, "integer"), ("Clientes atendidos", "customers_attended_today", 16, "integer"),
        ("Promesas pendientes", "pending_promises", 17, "integer"), ("Última liquidación", "last_settlement", 18, "text"),
    ]
    sheet.merge_range(0, 0, 0, len(columns) - 1, "MEMORA · PRODUCTIVIDAD DE COBRADORES", fmt["title"])
    sheet.write(1, 0, f"Generado: {generated_at:%d/%m/%Y %H:%M}", fmt["subtitle"])
    for col, (label, _, width, _) in enumerate(columns):
        sheet.write(3, col, label, fmt["header"])
        sheet.set_column(col, col, width)
    for row_index, row in enumerate(rows, start=4):
        for col, (_, key, _, kind) in enumerate(columns):
            value = row.get(key)
            if kind in {"money", "integer"}:
                sheet.write_number(row_index, col, float(value or 0), fmt[kind])
            else:
                sheet.write(row_index, col, value or "", fmt["text"])
    last_row = max(4, 3 + len(rows))
    sheet.autofilter(3, 0, last_row, len(columns) - 1)
    sheet.freeze_panes(4, 3)
    sheet.set_landscape()
    sheet.fit_to_pages(1, 0)
    sheet.set_footer("Memora · Página &P de &N")
    workbook.close()
    return output.getvalue()


def build_settlements_excel(rows, generated_at):
    output, workbook, fmt = _workbook("Liquidaciones de cobradores - Memora")
    sheet = workbook.add_worksheet("Liquidaciones")
    columns = [
        ("Liquidación", "settlement_number", 18, "text"), ("Fecha", "submitted_at", 19, "date"),
        ("Cobrador", "collector_name", 27, "text"), ("Sucursal", "branch_name", 20, "text"),
        ("Total cobrado", "total_collected", 17, "money"), ("Efectivo esperado", "expected_cash", 18, "money"),
        ("Efectivo reportado", "reported_cash", 19, "money"), ("Transferencia", "transfer_total", 16, "money"),
        ("Tarjeta", "card_total", 14, "money"), ("Cheque", "check_total", 14, "money"),
        ("Otros", "other_total", 14, "money"), ("Diferencia", "difference", 15, "difference"),
        ("Estado", "status_label", 16, "text"), ("Revisado por", "reviewed_by_name", 24, "text"),
    ]
    sheet.merge_range(0, 0, 0, len(columns) - 1, "MEMORA · LIQUIDACIONES DE COBRADORES", fmt["title"])
    sheet.write(1, 0, f"Generado: {generated_at:%d/%m/%Y %H:%M}", fmt["subtitle"])
    for col, (label, _, width, _) in enumerate(columns):
        sheet.write(3, col, label, fmt["header"])
        sheet.set_column(col, col, width)
    for row_index, row in enumerate(rows, start=4):
        for col, (_, key, _, kind) in enumerate(columns):
            value = row.get(key)
            if kind in {"money", "difference"}:
                sheet.write_number(row_index, col, float(value or 0), fmt[kind])
            elif kind == "date" and value:
                sheet.write_datetime(row_index, col, value.replace(tzinfo=None), fmt["date"])
            else:
                sheet.write(row_index, col, value or "", fmt["text"])
    last_row = max(4, 3 + len(rows))
    sheet.autofilter(3, 0, last_row, len(columns) - 1)
    sheet.freeze_panes(4, 2)
    sheet.set_landscape()
    sheet.fit_to_pages(1, 0)
    sheet.set_footer("Memora · Página &P de &N")
    workbook.close()
    return output.getvalue()


def build_settlement_pdf(settlement):
    output = BytesIO()
    document = SimpleDocTemplate(
        output, pagesize=letter, leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=13 * mm, bottomMargin=14 * mm,
        title=f"Liquidación {settlement.settlement_number} - Memora", author="Memora",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=8, leading=10))
    styles.add(ParagraphStyle(name="Money", parent=styles["Small"], alignment=TA_RIGHT))
    collector_name = settlement.collector.get_full_name().strip() or settlement.collector.username
    started_at = timezone.localtime(settlement.work_session.started_at)
    ended_at = timezone.localtime(settlement.work_session.ended_at) if settlement.work_session.ended_at else None
    submitted_at = timezone.localtime(settlement.submitted_at)
    story = [
        Paragraph("MEMORA · LIQUIDACIÓN DIARIA DE COBRADOR", styles["Title"]),
        Paragraph(
            f"{settlement.settlement_number} · Jornada {settlement.work_session.work_date:%d/%m/%Y} · "
            f"Estado: {settlement.get_status_display()}", styles["Small"],
        ),
        Spacer(1, 4 * mm),
    ]
    identity = [
        ["Cobrador", collector_name, "Sucursal", settlement.branch.name],
        ["Inicio", started_at.strftime("%d/%m/%Y %H:%M"),
         "Cierre", ended_at.strftime("%d/%m/%Y %H:%M") if ended_at else "-"],
        ["Presentada por", settlement.submitted_by.get_full_name().strip() or settlement.submitted_by.username,
         "Fecha", submitted_at.strftime("%d/%m/%Y %H:%M")],
    ]
    info = Table(identity, colWidths=[28 * mm, 60 * mm, 28 * mm, 60 * mm])
    info.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor(PALE)),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor(PALE)),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"), ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B8C4D6")),
        ("FONTSIZE", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.extend([info, Spacer(1, 4 * mm)])
    summary = [
        ["Total cobrado", f"L {settlement.total_collected:,.2f}", "Efectivo esperado", f"L {settlement.expected_cash:,.2f}"],
        ["Efectivo reportado", f"L {settlement.reported_cash:,.2f}", "Diferencia", f"L {settlement.difference:,.2f}"],
        ["Transferencia", f"L {settlement.transfer_total:,.2f}", "Tarjeta", f"L {settlement.card_total:,.2f}"],
        ["Cheque", f"L {settlement.check_total:,.2f}", "Otros", f"L {settlement.other_total:,.2f}"],
    ]
    totals = Table(summary, colWidths=[42 * mm, 46 * mm, 42 * mm, 46 * mm])
    totals.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B8C4D6")),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"), ("ALIGN", (3, 0), (3, -1), "RIGHT"),
        ("TEXTCOLOR", (3, 1), (3, 1), colors.HexColor(RED) if settlement.difference else colors.HexColor("#067647")),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
    ]))
    story.extend([totals, Spacer(1, 5 * mm), Paragraph("Detalle de pagos incluidos", styles["Heading2"])])
    data = [["Pago", "Recibo", "Cliente / contrato", "Método", "Monto"]]
    for item in settlement.payment_items.all():
        data.append([
            item.payment_number_snapshot, item.receipt_number_snapshot,
            Paragraph(f"{item.customer_name_snapshot}<br/>{item.contract_number_snapshot}", styles["Small"]),
            item.payment.get_payment_method_display(), f"L {item.amount_snapshot:,.2f}",
        ])
    payments = Table(data, repeatRows=1, colWidths=[27 * mm, 27 * mm, 65 * mm, 27 * mm, 30 * mm])
    payments.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(BLUE)), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D0D5DD")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("ALIGN", (-1, 1), (-1, -1), "RIGHT"), ("FONTSIZE", (0, 0), (-1, -1), 7.8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.extend([payments, Spacer(1, 5 * mm)])
    if settlement.notes:
        story.extend([Paragraph(f"Notas del cobrador: {settlement.notes}", styles["Small"]), Spacer(1, 2 * mm)])
    if settlement.review_notes:
        story.extend([Paragraph(f"Revisión: {settlement.review_notes}", styles["Small"]), Spacer(1, 7 * mm)])
    story.extend([
        Spacer(1, 7 * mm),
        Table([
            ["_______________________________", "_______________________________"],
            ["Firma del cobrador", "Firma de quien recibe / revisa"],
        ], colWidths=[88 * mm, 88 * mm], style=TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("FONTSIZE", (0, 0), (-1, -1), 8),
        ])),
    ])

    def footer(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#667085"))
        canvas.drawString(15 * mm, 7 * mm, "Memora · Documento operativo; no registra movimiento de caja por sí mismo")
        canvas.drawRightString(letter[0] - 15 * mm, 7 * mm, f"Página {canvas.getPageNumber()}")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
