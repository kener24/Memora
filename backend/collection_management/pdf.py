from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def build_portfolio_pdf(rows, totals, filters_text, generated_at):
    output = BytesIO()
    document = SimpleDocTemplate(
        output, pagesize=landscape(letter), leftMargin=9 * mm, rightMargin=9 * mm,
        topMargin=11 * mm, bottomMargin=12 * mm,
        title="Cartera y morosidad - Memora", author="Memora",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=6.8, leading=8.2))
    styles.add(ParagraphStyle(name="Money", parent=styles["Small"], alignment=TA_RIGHT))
    story = [
        Paragraph("MEMORA · CARTERA Y MOROSIDAD", styles["Title"]),
        Paragraph(f"Generado: {generated_at:%d/%m/%Y %H:%M} · Filtros: {filters_text or 'Sin filtros adicionales'}", styles["Small"]),
        Spacer(1, 4 * mm),
    ]
    summary = [
        ["Contratos", totals["contracts"], "Clientes", totals["customers"], "Cuotas vencidas", totals["overdue_installments"]],
        ["Cartera pendiente", f'L {totals["pending"]:,.2f}', "Cartera vencida", f'L {totals["overdue"]:,.2f}', "Por vencer", f'L {totals["upcoming"]:,.2f}'],
    ]
    table = Table(summary, colWidths=[31 * mm, 28 * mm] * 3)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#E8F0FE")),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B8C4D6")),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"), ("ALIGN", (3, 0), (3, -1), "RIGHT"),
        ("ALIGN", (5, 0), (5, -1), "RIGHT"), ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.extend([table, Spacer(1, 4 * mm)])
    headers = ["Contrato", "Cliente / teléfono", "Sucursal / plan", "Saldo", "Vencido", "Días", "Próxima", "Estado", "Prioridad"]
    data = [[Paragraph(value, styles["Small"]) for value in headers]]
    for row in rows:
        data.append([
            Paragraph(row["contract_number"], styles["Small"]),
            Paragraph(f'{row["customer_name"]}<br/>{row["phone"] or "Sin teléfono"}', styles["Small"]),
            Paragraph(f'{row["branch"]["name"]}<br/>{row["plan"]["name"]}', styles["Small"]),
            Paragraph(f'L {row["balance"]:,.2f}', styles["Money"]),
            Paragraph(f'L {row["overdue_amount"]:,.2f}', styles["Money"]),
            Paragraph(str(row["days_overdue"]), styles["Money"]),
            Paragraph(row["next_due_date"].strftime("%d/%m/%Y") if row["next_due_date"] else "—", styles["Small"]),
            Paragraph(row["collection_status_label"], styles["Small"]),
            Paragraph(row["priority_label"], styles["Small"]),
        ])
    report = LongTable(data, repeatRows=1, colWidths=[24*mm, 46*mm, 43*mm, 25*mm, 25*mm, 12*mm, 23*mm, 28*mm, 20*mm])
    report.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563EB")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D0D5DD")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(report)

    def footer(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#667085"))
        canvas.drawString(9 * mm, 6 * mm, "Memora · Información financiera derivada de pagos confirmados y cuotas activas")
        canvas.drawRightString(landscape(letter)[0] - 9 * mm, 6 * mm, f"Página {canvas.getPageNumber()}")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()

