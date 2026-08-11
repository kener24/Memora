from io import BytesIO
from xml.sax.saxutils import escape

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .services import session_summary, user_name


NAVY = "#17243B"
BLUE = "#2563EB"
PALE = "#E8F0FE"
RED = "#B42318"
GREEN = "#067647"


def _money(value):
    return f"L {value:,.2f}"


def build_cash_closing_pdf(session):
    summary = session_summary(session) if session.status == "open" else {
        "opening_cash": session.opening_cash,
        "cash_in": session.cash_in_snapshot,
        "cash_out": session.cash_out_snapshot,
        "expected_cash": session.expected_cash_snapshot,
        "method_totals": session.method_totals_snapshot,
    }
    cash_count = session.cash_counts.prefetch_related("denominations").order_by("-counted_at", "-id").first()
    output = BytesIO()
    document = SimpleDocTemplate(
        output, pagesize=letter, leftMargin=14 * mm, rightMargin=14 * mm,
        topMargin=13 * mm, bottomMargin=14 * mm,
        title=f"Cierre de caja {session.session_number} - Memora", author="Memora",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CashSmall", parent=styles["BodyText"], fontSize=8, leading=10))
    styles.add(ParagraphStyle(name="CashTiny", parent=styles["BodyText"], fontSize=6.5, leading=8))
    styles.add(ParagraphStyle(
        name="CashTableHeader", parent=styles["CashTiny"], fontName="Helvetica-Bold",
        textColor=colors.white,
    ))
    styles.add(ParagraphStyle(name="CashMoney", parent=styles["CashSmall"], alignment=TA_RIGHT))
    opened_at = timezone.localtime(session.opened_at)
    closed_at = timezone.localtime(session.closed_at) if session.closed_at else None
    story = [
        Paragraph("MEMORA · CIERRE Y ARQUEO DE CAJA", styles["Title"]),
        Paragraph(
            f"{session.session_number} · {escape(session.cash_register.code)} · "
            f"Estado: {escape(session.get_status_display())}", styles["CashSmall"],
        ),
        Spacer(1, 4 * mm),
    ]
    identity = [
        ["Empresa", session.organization.name, "Sucursal", session.branch.name],
        ["Caja", f"{session.cash_register.code} · {session.cash_register.name}", "Cajero", user_name(session.cashier)],
        ["Apertura", opened_at.strftime("%d/%m/%Y %H:%M"), "Cierre", closed_at.strftime("%d/%m/%Y %H:%M") if closed_at else "-"],
        ["Abierta por", user_name(session.opened_by), "Cerrada por", user_name(session.closed_by) if session.closed_by_id else "-"],
    ]
    info = Table(identity, colWidths=[27 * mm, 62 * mm, 27 * mm, 62 * mm])
    info.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor(PALE)),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor(PALE)),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B8C4D6")),
        ("FONTSIZE", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.extend([info, Spacer(1, 4 * mm)])
    counted = session.counted_cash_snapshot if session.status == "closed" else (cash_count.counted_cash if cash_count else 0)
    difference = session.difference_snapshot if session.status == "closed" else (cash_count.difference if cash_count else 0)
    method_totals = summary.get("method_totals") or {}
    method_value = lambda key: float(method_totals.get(key, 0))
    totals_data = [
        ["Fondo inicial", _money(summary["opening_cash"]), "Entradas efectivo", _money(summary["cash_in"])],
        ["Salidas efectivo", _money(summary["cash_out"]), "Efectivo esperado", _money(summary["expected_cash"])],
        ["Efectivo contado", _money(counted), "Diferencia", _money(difference)],
        ["Transferencias", _money(method_value("transfer")), "Tarjetas", _money(method_value("card"))],
        ["Cheques", _money(method_value("check")), "Otros medios", _money(method_value("other"))],
    ]
    totals = Table(totals_data, colWidths=[42 * mm, 47 * mm, 42 * mm, 47 * mm])
    totals.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B8C4D6")),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"), ("ALIGN", (3, 0), (3, -1), "RIGHT"),
        ("TEXTCOLOR", (3, 2), (3, 2), colors.HexColor(RED) if difference else colors.HexColor(GREEN)),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
    ]))
    story.extend([totals, Spacer(1, 4 * mm)])
    if cash_count:
        story.append(Paragraph("Detalle del arqueo", styles["Heading2"]))
        denominations = [["Denominación", "Cantidad", "Subtotal"]]
        for item in cash_count.denominations.all():
            denominations.append([_money(item.denomination), str(item.quantity), _money(item.subtotal)])
        if len(denominations) == 1:
            denominations.append(["Total introducido", "-", _money(cash_count.counted_cash)])
        denom_table = Table(denominations, repeatRows=1, colWidths=[52 * mm, 42 * mm, 52 * mm])
        denom_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(BLUE)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D0D5DD")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"), ("FONTSIZE", (0, 0), (-1, -1), 8),
        ]))
        story.extend([denom_table, Spacer(1, 3 * mm)])
        if cash_count.difference_reason:
            story.append(Paragraph(f"Motivo de diferencia: {escape(cash_count.difference_reason)}", styles["CashSmall"]))
    story.extend([Spacer(1, 3 * mm), Paragraph("Movimientos de la sesión", styles["Heading2"])])
    rows = [[Paragraph(escape(value), styles["CashTableHeader"]) for value in (
        "Hora", "Movimiento", "Tipo", "Descripción", "Entrada", "Salida", "Método", "Estado"
    )]]
    for item in session.movements.select_related("created_by").order_by("created_at", "id"):
        local_time = timezone.localtime(item.created_at).strftime("%H:%M")
        rows.append([
            local_time, item.movement_number,
            Paragraph(escape(item.get_movement_type_display()), styles["CashTiny"]),
            Paragraph(escape(item.description), styles["CashSmall"]),
            _money(item.amount) if item.direction == "in" else "",
            _money(item.amount) if item.direction == "out" else "",
            Paragraph(escape(item.get_payment_method_display()), styles["CashTiny"]),
            Paragraph(escape(item.get_status_display()), styles["CashTiny"]),
        ])
    if len(rows) == 1:
        rows.append(["-", "-", "-", "Sin movimientos", "", "", "", ""])
    movement_table = Table(
        rows, repeatRows=1,
        colWidths=[12 * mm, 21 * mm, 25 * mm, 49 * mm, 22 * mm, 22 * mm, 22 * mm, 19 * mm],
    )
    movement_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D0D5DD")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("ALIGN", (4, 1), (5, -1), "RIGHT"), ("FONTSIZE", (0, 0), (-1, -1), 6.7),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.extend([movement_table, Spacer(1, 5 * mm)])
    if session.notes:
        story.extend([Paragraph(f"Observaciones: {escape(session.notes)}", styles["CashSmall"]), Spacer(1, 6 * mm)])
    story.append(Table([
        ["_______________________________", "_______________________________"],
        ["Firma del cajero", "Firma de revisión"],
    ], colWidths=[89 * mm, 89 * mm], style=TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("FONTSIZE", (0, 0), (-1, -1), 8),
    ])))

    def footer(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#667085"))
        canvas.drawString(14 * mm, 7 * mm, "Memora · Reporte operativo de caja")
        canvas.drawRightString(letter[0] - 14 * mm, 7 * mm, f"Página {canvas.getPageNumber()}")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
